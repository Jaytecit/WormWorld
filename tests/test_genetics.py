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


def test_version_1_identity_is_retained_and_version_2_round_trips() -> None:
    version1 = Genome()
    assert version1.genome_id == "ee3ef0b954712e867ac1209dc1949f742900f96a701f435e9c141af9e50ea95d"
    assert "brain_priors" not in version1.to_json()

    version2 = Genome.version2(version1, hidden_size=4)
    restored = Genome.from_json(version2.to_json())
    assert restored == version2
    assert restored.genome_id == version2.genome_id != version1.genome_id
    assert restored.brain_hidden_size == 4
    assert len(restored.brain_priors or ()) == 90


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


def test_version_2_inheritance_and_mutation_stay_in_declared_bounds() -> None:
    first = Genome.version2(Genome(mutation_scale=0.5), hidden_size=3)
    second = Genome.version2(
        Genome(max_speed=2.0, mutation_scale=0.5),
        hidden_size=3,
        plasticity_rate=0.08,
        eligibility_trace_decay=0.2,
    )
    unmutated = inherit_genome(first, second, random.Random(4), mutation_enabled=False)
    assert unmutated.schema_version == 2
    assert unmutated.brain_priors is not None
    assert all(
        value in {left, right}
        for value, left, right in zip(
            unmutated.brain_priors,
            first.brain_priors or (),
            second.brain_priors or (),
            strict=True,
        )
    )
    for seed in range(20):
        child = inherit_genome(first, second, random.Random(seed), mutation_enabled=True)
        assert child.brain_priors is not None
        assert all(-1.0 <= value <= 1.0 for value in child.brain_priors)
        assert child.plasticity_rate is not None and 0.0 <= child.plasticity_rate <= 0.1
        assert child.eligibility_trace_decay is not None
        assert 0.0 <= child.eligibility_trace_decay <= 1.0


def test_lineage_storage_is_ordered_idempotent_and_transitive() -> None:
    store = LineageStore()
    store.add(1, "a" * 64, (), 0)
    store.add(2, "b" * 64, (1,), 2)
    store.add(3, "c" * 64, (2,), 4)
    assert store.descendants(1) == (2, 3)
    assert store.mark_death(2, 8)
    assert not store.mark_death(2, 9)
    assert store.record(2).death_step == 8
