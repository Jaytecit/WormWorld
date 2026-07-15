"""Deterministic random streams derived from an experiment seed."""

from __future__ import annotations

import hashlib
import random


class NamedRandomStreams:
    """Own independent pseudo-random streams identified by stable names.

    Each stream seed is derived solely from the master seed and its UTF-8 name, so
    creating or consuming one stream cannot perturb any other stream.
    """

    def __init__(self, master_seed: int) -> None:
        """Create an empty stream registry for a validated unsigned 64-bit seed."""
        if isinstance(master_seed, bool) or not 0 <= master_seed <= (1 << 64) - 1:
            raise ValueError("master_seed must be an unsigned 64-bit integer")
        self._master_seed = master_seed
        self._streams: dict[str, random.Random] = {}

    def stream(self, name: str) -> random.Random:
        """Return the persistent stream for ``name``, creating it when first used."""
        if not name:
            raise ValueError("stream name must not be empty")
        if name not in self._streams:
            self._streams[name] = random.Random(self.seed_for(name))
        return self._streams[name]

    def seed_for(self, name: str) -> int:
        """Derive a stable 256-bit seed without consuming any stream state."""
        if not name:
            raise ValueError("stream name must not be empty")
        seed_bytes = self._master_seed.to_bytes(8, byteorder="big", signed=False)
        name_bytes = name.encode("utf-8")
        payload = seed_bytes + len(name_bytes).to_bytes(4, byteorder="big") + name_bytes
        return int.from_bytes(hashlib.sha256(payload).digest(), byteorder="big")
