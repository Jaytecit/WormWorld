"""Structure-of-arrays storage for deterministic organism lifecycles."""

from __future__ import annotations

from worm_world.organisms.core import PhysiologyState, WormState
from worm_world.schemas import JsonValue


class PopulationStore:
    """Authoritative organism state with stable IDs and tombstoned slots."""

    def __init__(self) -> None:
        self._entity_ids: list[int] = []
        self._x: list[float] = []
        self._y: list[float] = []
        self._heading_radians: list[float] = []
        self._energy: list[float] = []
        self._hydration: list[float] = []
        self._injury: list[float] = []
        self._age_seconds: list[float] = []
        self._alive: list[bool] = []
        self._active: list[bool] = []
        self._slot_by_id: dict[int, int] = {}
        self._next_entity_id = 1

    def __len__(self) -> int:
        return sum(self._active)

    @property
    def next_entity_id(self) -> int:
        return self._next_entity_id

    def active_entity_ids(self) -> tuple[int, ...]:
        """Return live slots in monotonically allocated, stable order."""
        return tuple(
            entity_id
            for entity_id, active in zip(self._entity_ids, self._active, strict=True)
            if active
        )

    def entity_ids(self) -> tuple[int, ...]:
        """Return every allocated ID, including tombstones, in stable order."""
        return tuple(self._entity_ids)

    def insert(self, state: WormState) -> int:
        """Copy one live state into a newly allocated slot."""
        if not state.physiology.alive:
            raise ValueError("new population members must be alive")
        entity_id = self._next_entity_id
        self._next_entity_id += 1
        slot = len(self._entity_ids)
        self._slot_by_id[entity_id] = slot
        self._entity_ids.append(entity_id)
        self._x.append(state.x)
        self._y.append(state.y)
        self._heading_radians.append(state.heading_radians)
        self._energy.append(state.physiology.energy)
        self._hydration.append(state.physiology.hydration)
        self._injury.append(state.physiology.injury)
        self._age_seconds.append(state.physiology.age_seconds)
        self._alive.append(True)
        self._active.append(True)
        return entity_id

    def _slot(self, entity_id: int) -> int:
        try:
            return self._slot_by_id[entity_id]
        except KeyError as error:
            raise KeyError(f"unknown entity ID {entity_id}") from error

    def is_active(self, entity_id: int) -> bool:
        return self._active[self._slot(entity_id)]

    def state(self, entity_id: int) -> WormState:
        """Return a detached state value for an active member or tombstone."""
        slot = self._slot(entity_id)
        return WormState(
            x=self._x[slot],
            y=self._y[slot],
            heading_radians=self._heading_radians[slot],
            physiology=PhysiologyState(
                energy=self._energy[slot],
                hydration=self._hydration[slot],
                injury=self._injury[slot],
                age_seconds=self._age_seconds[slot],
                alive=self._alive[slot],
            ),
        )

    def update(self, entity_id: int, state: WormState) -> None:
        """Replace the columns for an active member before lifecycle resolution."""
        slot = self._slot(entity_id)
        if not self._active[slot]:
            raise ValueError(f"entity ID {entity_id} is tombstoned")
        self._x[slot] = state.x
        self._y[slot] = state.y
        self._heading_radians[slot] = state.heading_radians
        self._energy[slot] = state.physiology.energy
        self._hydration[slot] = state.physiology.hydration
        self._injury[slot] = state.physiology.injury
        self._age_seconds[slot] = state.physiology.age_seconds
        self._alive[slot] = state.physiology.alive

    def tombstone(self, entity_id: int) -> bool:
        """Remove an entity from active iteration exactly once while retaining state."""
        slot = self._slot(entity_id)
        if not self._active[slot]:
            return False
        self._active[slot] = False
        self._alive[slot] = False
        return True

    def records(self) -> list[JsonValue]:
        """Return canonically ordered population records, including tombstones."""
        records: list[JsonValue] = []
        for entity_id in self._entity_ids:
            slot = self._slot_by_id[entity_id]
            records.append(
                {
                    "active": self._active[slot],
                    "age_seconds": self._age_seconds[slot],
                    "alive": self._alive[slot],
                    "energy": self._energy[slot],
                    "entity_id": entity_id,
                    "heading_radians": self._heading_radians[slot],
                    "hydration": self._hydration[slot],
                    "injury": self._injury[slot],
                    "x": self._x[slot],
                    "y": self._y[slot],
                }
            )
        return records
