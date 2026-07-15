"""Deterministic recurrent control and lifetime-only local plasticity."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

from worm_world.genetics import Genome, controller_prior_values_from_id
from worm_world.organisms import SensorReadings, WormAction

SENSOR_WIDTH = 10
ACTION_WIDTH = 6


def _finite(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")


def _zero_matrix(rows: int, columns: int) -> tuple[tuple[float, ...], ...]:
    return tuple((0.0,) * columns for _ in range(rows))


@dataclass(frozen=True, slots=True)
class ControllerConfig:
    """Runtime ablations and dimensions; learned state is never serialized here."""

    hidden_size: int = 8
    recurrent_enabled: bool = True
    plasticity_enabled: bool = True
    binary_threshold: float = 0.5

    def __post_init__(self) -> None:
        if isinstance(self.hidden_size, bool) or not 1 <= self.hidden_size <= 64:
            raise ValueError("hidden_size must be an integer in [1, 64]")
        _finite("binary_threshold", self.binary_threshold)
        if not 0.0 <= self.binary_threshold <= 1.0:
            raise ValueError("binary_threshold must be in [0, 1]")


@dataclass(frozen=True, slots=True)
class PlasticityParameters:
    """Genome-encoded three-factor update coefficients, not lifetime state."""

    learning_rate: float = 0.0
    trace_decay: float = 0.0
    energy_weight: float = 0.0
    hydration_weight: float = 0.0
    injury_weight: float = 0.0

    def __post_init__(self) -> None:
        for name, value in (
            ("learning_rate", self.learning_rate),
            ("trace_decay", self.trace_decay),
            ("energy_weight", self.energy_weight),
            ("hydration_weight", self.hydration_weight),
            ("injury_weight", self.injury_weight),
        ):
            _finite(name, value)
        if not 0.0 <= self.learning_rate <= 0.1:
            raise ValueError("learning_rate must be in [0, 0.1]")
        if not 0.0 <= self.trace_decay <= 1.0:
            raise ValueError("trace_decay must be in [0, 1]")
        if any(
            not -4.0 <= value <= 4.0
            for value in (self.energy_weight, self.hydration_weight, self.injury_weight)
        ):
            raise ValueError("homeostatic weights must be in [-4, 4]")

    @classmethod
    def from_genome(cls, genome: Genome) -> PlasticityParameters:
        if genome.schema_version == 1:
            return cls()
        assert genome.plasticity_rate is not None
        assert genome.eligibility_trace_decay is not None
        assert genome.homeostatic_energy_weight is not None
        assert genome.homeostatic_hydration_weight is not None
        assert genome.homeostatic_injury_weight is not None
        return cls(
            genome.plasticity_rate,
            genome.eligibility_trace_decay,
            genome.homeostatic_energy_weight,
            genome.homeostatic_hydration_weight,
            genome.homeostatic_injury_weight,
        )


@dataclass(frozen=True, slots=True)
class ControllerPriors:
    """Immutable initial controller weights inherited through the genome."""

    input_weights: tuple[tuple[float, ...], ...]
    recurrent_weights: tuple[tuple[float, ...], ...]
    hidden_bias: tuple[float, ...]
    output_weights: tuple[tuple[float, ...], ...]
    output_bias: tuple[float, ...]

    def __post_init__(self) -> None:
        hidden_size = len(self.hidden_bias)
        if hidden_size < 1:
            raise ValueError("controller priors require at least one hidden unit")
        if len(self.input_weights) != hidden_size or any(
            len(row) != SENSOR_WIDTH for row in self.input_weights
        ):
            raise ValueError("input weights have invalid shape")
        if len(self.recurrent_weights) != hidden_size or any(
            len(row) != hidden_size for row in self.recurrent_weights
        ):
            raise ValueError("recurrent weights have invalid shape")
        if len(self.output_weights) != ACTION_WIDTH or any(
            len(row) != hidden_size for row in self.output_weights
        ):
            raise ValueError("output weights have invalid shape")
        if len(self.output_bias) != ACTION_WIDTH:
            raise ValueError("output bias has invalid shape")
        for value in (
            *(value for row in self.input_weights for value in row),
            *(value for row in self.recurrent_weights for value in row),
            *self.hidden_bias,
            *(value for row in self.output_weights for value in row),
            *self.output_bias,
        ):
            _finite("controller prior", value)

    @classmethod
    def from_flattened(cls, values: tuple[float, ...], hidden_size: int) -> ControllerPriors:
        iterator = iter(values)

        def matrix(rows: int, columns: int) -> tuple[tuple[float, ...], ...]:
            return tuple(tuple(next(iterator) for _ in range(columns)) for _ in range(rows))

        try:
            priors = cls(
                input_weights=matrix(hidden_size, SENSOR_WIDTH),
                recurrent_weights=matrix(hidden_size, hidden_size),
                hidden_bias=tuple(next(iterator) for _ in range(hidden_size)),
                output_weights=matrix(ACTION_WIDTH, hidden_size),
                output_bias=tuple(next(iterator) for _ in range(ACTION_WIDTH)),
            )
        except StopIteration as error:
            raise ValueError("flattened controller priors are too short") from error
        try:
            next(iterator)
        except StopIteration:
            return priors
        raise ValueError("flattened controller priors are too long")

    @classmethod
    def from_genome_id(cls, genome_id: str, hidden_size: int) -> ControllerPriors:
        """Retain the v1 implicit-prior expansion exactly."""
        return cls.from_flattened(
            controller_prior_values_from_id(genome_id, hidden_size), hidden_size
        )

    @classmethod
    def from_genome(cls, genome: Genome) -> ControllerPriors:
        if genome.schema_version == 1:
            raise ValueError("version-1 genomes require an explicit runtime hidden size")
        assert genome.brain_hidden_size is not None and genome.brain_priors is not None
        return cls.from_flattened(genome.brain_priors, genome.brain_hidden_size)


@dataclass(frozen=True, slots=True)
class ControllerState:
    """All mutable controller values; initialized cleanly for each lifetime."""

    hidden: tuple[float, ...]
    step_count: int = 0
    output_weight_deltas: tuple[tuple[float, ...], ...] = ()
    eligibility_traces: tuple[tuple[float, ...], ...] = ()
    previous_homeostasis: tuple[float, float, float] | None = None

    def __post_init__(self) -> None:
        if not self.hidden:
            raise ValueError("hidden state must not be empty")
        if isinstance(self.step_count, bool) or self.step_count < 0:
            raise ValueError("step_count must be non-negative")
        for value in self.hidden:
            _finite("hidden state", value)
        for matrix_name, matrix in (
            ("output weight delta", self.output_weight_deltas),
            ("eligibility trace", self.eligibility_traces),
        ):
            if matrix and (
                len(matrix) != ACTION_WIDTH or any(len(row) != len(self.hidden) for row in matrix)
            ):
                raise ValueError(f"{matrix_name} has invalid shape")
            for row in matrix:
                for value in row:
                    _finite(matrix_name, value)
        if self.previous_homeostasis is not None:
            for value in self.previous_homeostasis:
                _finite("previous homeostasis", value)

    @classmethod
    def clean(cls, hidden_size: int) -> ControllerState:
        if isinstance(hidden_size, bool) or hidden_size < 1:
            raise ValueError("hidden_size must be positive")
        zeros = _zero_matrix(ACTION_WIDTH, hidden_size)
        return cls((0.0,) * hidden_size, output_weight_deltas=zeros, eligibility_traces=zeros)


@dataclass(frozen=True, slots=True)
class ControllerAction:
    motion: WormAction
    reproduce: bool


@dataclass(frozen=True, slots=True)
class PlasticityDiagnostic:
    """Raw homeostatic changes and aggregate local-update values for experiment logs."""

    energy_change: float
    hydration_change: float
    injury_change: float
    neuromodulator: float
    update_l1: float
    learned_weight_l1: float

    def to_dict(self) -> dict[str, float]:
        return {
            "energy_change": self.energy_change,
            "hydration_change": self.hydration_change,
            "injury_change": self.injury_change,
            "neuromodulator": self.neuromodulator,
            "update_l1": self.update_l1,
            "learned_weight_l1": self.learned_weight_l1,
        }


@dataclass(frozen=True, slots=True)
class ControllerStep:
    action: ControllerAction
    state: ControllerState
    outputs: tuple[float, ...]
    diagnostic: PlasticityDiagnostic


def sensor_vector(sensors: SensorReadings) -> tuple[float, ...]:
    values = (
        sensors.energy_fraction,
        sensors.hydration_fraction,
        sensors.injury_fraction,
        sensors.food_dx,
        sensors.food_dy,
        sensors.food_intensity,
        sensors.water_dx,
        sensors.water_dy,
        sensors.water_intensity,
        1.0 if sensors.boundary_contact else 0.0,
    )
    if len(values) != SENSOR_WIDTH or any(not math.isfinite(value) for value in values):
        raise ValueError("sensor vector must contain ten finite values")
    return values


class RecurrentController:
    """Small pure-Python policy with deterministic local output-synapse updates."""

    def __init__(
        self,
        config: ControllerConfig,
        priors: ControllerPriors,
        plasticity: PlasticityParameters | None = None,
    ) -> None:
        if len(priors.hidden_bias) != config.hidden_size:
            raise ValueError("controller config and prior hidden sizes disagree")
        self.config = config
        self.priors = priors
        self.plasticity = PlasticityParameters() if plasticity is None else plasticity

    def step(self, sensors: SensorReadings, state: ControllerState) -> ControllerStep:
        if len(state.hidden) != self.config.hidden_size:
            raise ValueError("controller state has invalid shape")
        inputs = sensor_vector(sensors)
        homeostasis = (inputs[0], inputs[1], inputs[2])
        changes = (
            (0.0, 0.0, 0.0)
            if state.previous_homeostasis is None
            else tuple(
                current - previous
                for current, previous in zip(homeostasis, state.previous_homeostasis, strict=True)
            )
        )
        neuromodulator = sum(
            change * weight
            for change, weight in zip(
                changes,
                (
                    self.plasticity.energy_weight,
                    self.plasticity.hydration_weight,
                    self.plasticity.injury_weight,
                ),
                strict=True,
            )
        )
        previous_deltas = state.output_weight_deltas or _zero_matrix(
            ACTION_WIDTH, self.config.hidden_size
        )
        previous_traces = state.eligibility_traces or _zero_matrix(
            ACTION_WIDTH, self.config.hidden_size
        )
        rate = self.plasticity.learning_rate if self.config.plasticity_enabled else 0.0
        updates = tuple(
            tuple(rate * neuromodulator * trace for trace in row) for row in previous_traces
        )
        deltas = tuple(
            tuple(
                min(2.0, max(-2.0, old + update))
                for old, update in zip(old_row, update_row, strict=True)
            )
            for old_row, update_row in zip(previous_deltas, updates, strict=True)
        )
        recurrent = state.hidden if self.config.recurrent_enabled else (0.0,) * len(state.hidden)
        hidden = tuple(
            math.tanh(
                self.priors.hidden_bias[row]
                + sum(
                    weight * value
                    for weight, value in zip(self.priors.input_weights[row], inputs, strict=True)
                )
                + sum(
                    weight * value
                    for weight, value in zip(
                        self.priors.recurrent_weights[row], recurrent, strict=True
                    )
                )
            )
            for row in range(self.config.hidden_size)
        )
        raw = tuple(
            self.priors.output_bias[row]
            + sum(
                (weight + delta) * value
                for weight, delta, value in zip(
                    self.priors.output_weights[row], deltas[row], hidden, strict=True
                )
            )
            for row in range(ACTION_WIDTH)
        )
        probabilities = tuple(1.0 / (1.0 + math.exp(-value)) for value in raw[2:])
        threshold = self.config.binary_threshold
        action = ControllerAction(
            WormAction(
                forward=math.tanh(raw[0]),
                turn=math.tanh(raw[1]),
                eat=probabilities[0] >= threshold,
                drink=probabilities[1] >= threshold,
                rest=probabilities[2] >= threshold,
            ),
            reproduce=probabilities[3] >= threshold,
        )
        traces = tuple(
            tuple(
                self.plasticity.trace_decay * previous + pre * math.tanh(raw[row])
                for previous, pre in zip(previous_traces[row], hidden, strict=True)
            )
            for row in range(ACTION_WIDTH)
        )
        next_hidden = hidden if self.config.recurrent_enabled else (0.0,) * len(hidden)
        diagnostic = PlasticityDiagnostic(
            changes[0],
            changes[1],
            changes[2],
            neuromodulator,
            sum(abs(value) for row in updates for value in row),
            sum(abs(value) for row in deltas for value in row),
        )
        return ControllerStep(
            action,
            ControllerState(
                next_hidden,
                state.step_count + 1,
                deltas,
                traces,
                homeostasis,
            ),
            raw,
            diagnostic,
        )


class PopulationController:
    """Own isolated controller state and diagnostics for changing entity IDs."""

    def __init__(self, config: ControllerConfig) -> None:
        self.config = config
        self._states: dict[int, ControllerState] = {}
        self._diagnostics: dict[int, PlasticityDiagnostic] = {}
        self._outputs: dict[int, tuple[float, ...]] = {}

    def state(self, entity_id: int) -> ControllerState:
        return self._states[entity_id]

    def diagnostic(self, entity_id: int) -> PlasticityDiagnostic:
        return self._diagnostics[entity_id]

    def outputs(self, entity_id: int) -> tuple[float, ...]:
        return self._outputs[entity_id]

    def synchronize(self, active_entity_ids: set[int]) -> None:
        """Remove all lifetime state for entities no longer active."""
        self._states = {
            entity_id: state
            for entity_id, state in self._states.items()
            if entity_id in active_entity_ids
        }
        self._diagnostics = {
            entity_id: diagnostic
            for entity_id, diagnostic in self._diagnostics.items()
            if entity_id in active_entity_ids
        }
        self._outputs = {
            entity_id: outputs
            for entity_id, outputs in self._outputs.items()
            if entity_id in active_entity_ids
        }

    def decide(
        self,
        sensors: Mapping[int, SensorReadings],
        genomes: Mapping[int, Genome | str],
    ) -> dict[int, ControllerAction]:
        if set(sensors) != set(genomes):
            raise ValueError("sensors and genomes must cover the same entities")
        active = set(sensors)
        self.synchronize(active)
        actions: dict[int, ControllerAction] = {}
        for entity_id in sorted(active):
            genome = genomes[entity_id]
            if isinstance(genome, str):
                priors = ControllerPriors.from_genome_id(genome, self.config.hidden_size)
                plasticity = PlasticityParameters()
            else:
                if genome.schema_version == 1:
                    priors = ControllerPriors.from_genome_id(
                        genome.genome_id, self.config.hidden_size
                    )
                else:
                    if genome.brain_hidden_size != self.config.hidden_size:
                        raise ValueError("controller config and genome hidden sizes disagree")
                    priors = ControllerPriors.from_genome(genome)
                plasticity = PlasticityParameters.from_genome(genome)
            state = self._states.get(entity_id, ControllerState.clean(self.config.hidden_size))
            result = RecurrentController(self.config, priors, plasticity).step(
                sensors[entity_id], state
            )
            self._states[entity_id] = result.state
            self._diagnostics[entity_id] = result.diagnostic
            self._outputs[entity_id] = result.outputs
            actions[entity_id] = result.action
        return actions
