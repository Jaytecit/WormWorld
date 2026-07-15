"""Genetics-owned immutable inheritance and ancestry interfaces."""

from worm_world.genetics.genome import (
    FounderPhenotype,
    Genome,
    compatible,
    founder_phenotype,
    genetic_distance,
    inherit_genome,
)
from worm_world.genetics.lineage import LineageRecord, LineageStore

__all__ = [
    "FounderPhenotype",
    "Genome",
    "LineageRecord",
    "LineageStore",
    "compatible",
    "founder_phenotype",
    "genetic_distance",
    "inherit_genome",
]
