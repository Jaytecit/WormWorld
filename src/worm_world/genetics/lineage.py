"""Deterministic ancestry records, separate from lifetime organism state."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from worm_world.schemas import JsonValue


@dataclass(slots=True)
class LineageRecord:
    entity_id: int
    lineage_id: str
    genome_id: str
    parent_ids: tuple[int, ...]
    birth_step: int
    death_step: int | None = None

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "birth_step": self.birth_step,
            "death_step": self.death_step,
            "entity_id": self.entity_id,
            "genome_id": self.genome_id,
            "lineage_id": self.lineage_id,
            "parent_ids": list(self.parent_ids),
        }


class LineageStore:
    """Append-only ancestry facts keyed by stable population entity ID."""

    def __init__(self) -> None:
        self._records: dict[int, LineageRecord] = {}

    @staticmethod
    def derive_id(entity_id: int, genome_id: str, parent_ids: tuple[int, ...]) -> str:
        payload = f"{entity_id}:{genome_id}:{','.join(map(str, parent_ids))}".encode()
        return hashlib.sha256(payload).hexdigest()[:24]

    def add(
        self, entity_id: int, genome_id: str, parent_ids: tuple[int, ...], birth_step: int
    ) -> LineageRecord:
        if entity_id in self._records:
            raise ValueError(f"entity ID {entity_id} already has lineage")
        if tuple(sorted(parent_ids)) != parent_ids or len(set(parent_ids)) != len(parent_ids):
            raise ValueError("parent IDs must be unique and sorted")
        record = LineageRecord(
            entity_id,
            self.derive_id(entity_id, genome_id, parent_ids),
            genome_id,
            parent_ids,
            birth_step,
        )
        self._records[entity_id] = record
        return record

    def mark_death(self, entity_id: int, step: int) -> bool:
        record = self._records[entity_id]
        if record.death_step is not None:
            return False
        record.death_step = step
        return True

    def record(self, entity_id: int) -> LineageRecord:
        return self._records[entity_id]

    def records(self) -> tuple[LineageRecord, ...]:
        return tuple(self._records[key] for key in sorted(self._records))

    def descendants(self, ancestor_id: int) -> tuple[int, ...]:
        descendants: set[int] = set()
        changed = True
        while changed:
            changed = False
            for record in self.records():
                if record.entity_id not in descendants and (
                    ancestor_id in record.parent_ids
                    or any(p in descendants for p in record.parent_ids)
                ):
                    descendants.add(record.entity_id)
                    changed = True
        return tuple(sorted(descendants))
