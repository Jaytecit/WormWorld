"""Deterministic lifetime-only recurrent controller contracts."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping
from dataclasses import dataclass

from worm_world.organisms import SensorReadings, WormAction

SENSOR_WIDTH = 10
ACTION_WIDTH = 6


def _finite(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")


@dataclass(frozen=True, slots=True)
class ControllerConfig:
    """Runtime switch and dimensions; no learned state is serialized here."""

    hidden_size: int = 8
    recurrent_enabled: bool = True
    binary_threshold: float = 0.5

    def __post_init__(self) -> None:
        if isinstance(self.hidden_size, bool) or not 1 <= self.hidden_size <= 64:
            raise ValueError("hidden_size must be an integer in [1, 64]")
        _finite("binary_threshold", self.binary_threshold)
        if not 0.0 <= self.binary_threshold <= 1.0:
            raise ValueError("binary_threshold must be in [0, 1]")


@dataclass(frozen=True, slots=True)
class ControllerPriors:
    """Immutable initial weights deterministically encoded by a genome identity."""

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
    def from_genome_id(cls, genome_id: str, hidden_size: int) -> ControllerPriors:
        """Expand a canonical genome ID into stable, platform-independent priors."""
        if len(genome_id) != 64 or any(
            character not in "0123456789abcdef" for character in genome_id
        ):
            raise ValueError("genome_id must be a lowercase SHA-256 digest")
        if isinstance(hidden_size, bool) or not 1 <= hidden_size <= 64:
            raise ValueError("hidden_size must be an integer in [1, 64]")
        count = hidden_size * SENSOR_WIDTH + hidden_size**2 + hidden_size
        count += ACTION_WIDTH * hidden_size + ACTION_WIDTH
        values: list[float] = []
        block = 0
        while len(values) < count:
            digest = hashlib.sha256(f"{genome_id}:controller-v1:{block}".encode()).digest()
            values.extend(((byte / 255.0) - 0.5) * 0.5 for byte in digest)
            block += 1
        iterator = iter(values)

        def matrix(rows: int, columns: int) -> tuple[tuple[float, ...], ...]:
            return tuple(tuple(next(iterator) for _ in range(columns)) for _ in range(rows))

        return cls(
            input_weights=matrix(hidden_size, SENSOR_WIDTH),
            recurrent_weights=matrix(hidden_size, hidden_size),
            hidden_bias=tuple(next(iterator) for _ in range(hidden_size)),
            output_weights=matrix(ACTION_WIDTH, hidden_size),
            output_bias=tuple(next(iterator) for _ in range(ACTION_WIDTH)),
        )


@dataclass(frozen=True, slots=True)
class ControllerState:
    """Lifetime-only recurrent state, created cleanly for each entity."""

    hidden: tuple[float, ...]
    step_count: int = 0

    def __post_init__(self) -> None:
        if not self.hidden:
            raise ValueError("hidden state must not be empty")
        if isinstance(self.step_count, bool) or self.step_count < 0:
            raise ValueError("step_count must be non-negative")
        for value in self.hidden:
            _finite("hidden state", value)

    @classmethod
    def clean(cls, hidden_size: int) -> ControllerState:
        if isinstance(hidden_size, bool) or hidden_size < 1:
            raise ValueError("hidden_size must be positive")
        return cls((0.0,) * hidden_size)


@dataclass(frozen=True, slots=True)
class ControllerAction:
    motion: WormAction
    reproduce: bool


@dataclass(frozen=True, slots=True)
class ControllerStep:
    action: ControllerAction
    state: ControllerState
    outputs: tuple[float, ...]


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
    """Small pure-Python recurrent policy with no simulator authority."""

    def __init__(self, config: ControllerConfig, priors: ControllerPriors) -> None:
        if len(priors.hidden_bias) != config.hidden_size:
            raise ValueError("controller config and prior hidden sizes disagree")
        self.config = config
        self.priors = priors

    def step(self, sensors: SensorReadings, state: ControllerState) -> ControllerStep:
        if len(state.hidden) != self.config.hidden_size:
            raise ValueError("controller state has invalid shape")
        inputs = sensor_vector(sensors)
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
                weight * value
                for weight, value in zip(self.priors.output_weights[row], hidden, strict=True)
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
        next_hidden = hidden if self.config.recurrent_enabled else (0.0,) * len(hidden)
        return ControllerStep(action, ControllerState(next_hidden, state.step_count + 1), raw)


class PopulationController:
    """Own isolated controller state for a changing set of entity IDs."""

    def __init__(self, config: ControllerConfig) -> None:
        self.config = config
        self._states: dict[int, ControllerState] = {}

    def state(self, entity_id: int) -> ControllerState:
        return self._states[entity_id]

    def decide(
        self,
        sensors: Mapping[int, SensorReadings],
        genome_ids: Mapping[int, str],
    ) -> dict[int, ControllerAction]:
        if set(sensors) != set(genome_ids):
            raise ValueError("sensors and genome IDs must cover the same entities")
        active = set(sensors)
        self._states = {
            entity_id: state for entity_id, state in self._states.items() if entity_id in active
        }
        actions: dict[int, ControllerAction] = {}
        for entity_id in sorted(active):
            state = self._states.get(entity_id, ControllerState.clean(self.config.hidden_size))
            priors = ControllerPriors.from_genome_id(genome_ids[entity_id], self.config.hidden_size)
            result = RecurrentController(self.config, priors).step(sensors[entity_id], state)
            self._states[entity_id] = result.state
            actions[entity_id] = result.action
        return actions
