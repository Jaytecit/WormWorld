"""Genetics-owned immutable inheritance and ancestry interfaces."""

from worm_world.genetics.genome import (
    FounderPhenotype,
    Genome,
    compatible,
    controller_prior_count,
    controller_prior_values_from_id,
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
    "controller_prior_count",
    "controller_prior_values_from_id",
    "founder_phenotype",
    "genetic_distance",
    "inherit_genome",
]
