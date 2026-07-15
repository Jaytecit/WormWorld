import random

import pytest

from worm_world.genetics import (
    Genome,
    LineageStore,
    compatible,
    founder_phenotype,
    inherit_genome,
)


def test_genome_is_canonical_and_maps_traits_to_founder() -> None:
    genome = Genome(segment_count=7, max_speed=2.0, basal_energy_rate=0.05)
    restored = Genome.from_json(genome.to_json())
    assert restored == genome
    assert restored.genome_id == genome.genome_id
    phenotype = founder_phenotype(genome)
    assert phenotype.body.segment_count == 7
    assert phenotype.body.max_speed == 2.0
    assert phenotype.physiology.basal_energy_rate == 0.05


def test_genome_validation_and_strict_fields() -> None:
    with pytest.raises(ValueError, match="segment_count"):
        Genome(segment_count=1)
    with pytest.raises(ValueError, match="offspring"):
        Genome(fertility_energy_fraction=0.25, offspring_energy_fraction=0.25)
    with pytest.raises(ValueError, match="missing or unknown"):
        Genome.from_json('{"segment_count":4}')


def test_inheritance_is_seeded_and_mutation_can_be_disabled() -> None:
    first = Genome(max_speed=1.0, basal_energy_rate=0.1)
    second = Genome(max_speed=2.0, basal_energy_rate=0.4)
    child_a = inherit_genome(first, second, random.Random(9), mutation_enabled=False)
    child_b = inherit_genome(first, second, random.Random(9), mutation_enabled=False)
    assert child_a == child_b
    assert child_a.max_speed in {1.0, 2.0}
    assert child_a.basal_energy_rate in {0.1, 0.4}
    assert compatible(first, first, 0.0)
    assert not compatible(first, Genome(segment_count=32, max_speed=5.0), 0.01)


def test_lineage_storage_is_ordered_idempotent_and_transitive() -> None:
    store = LineageStore()
    store.add(1, "a" * 64, (), 0)
    store.add(2, "b" * 64, (1,), 2)
    store.add(3, "c" * 64, (2,), 4)
    assert store.descendants(1) == (2, 3)
    assert store.mark_death(2, 8)
    assert not store.mark_death(2, 9)
    assert store.record(2).death_step == 8
