"""Tests for deterministic named random-number streams."""

from worm_world.rng import NamedRandomStreams


def test_named_stream_is_reproducible() -> None:
    """The same master seed and name reproduce an identical sequence."""
    first = NamedRandomStreams(8675309).stream("terrain")
    second = NamedRandomStreams(8675309).stream("terrain")

    assert [first.random() for _ in range(8)] == [second.random() for _ in range(8)]


def test_named_streams_are_independent_of_access_and_consumption_order() -> None:
    """Activity in one subsystem cannot perturb another subsystem's stream."""
    interleaved = NamedRandomStreams(11)
    interleaved.stream("weather").random()
    terrain_after_weather = [interleaved.stream("terrain").random() for _ in range(5)]

    isolated = NamedRandomStreams(11)
    terrain_alone = [isolated.stream("terrain").random() for _ in range(5)]

    assert terrain_after_weather == terrain_alone
    assert isolated.seed_for("terrain") != isolated.seed_for("weather")


def test_stream_calls_resume_the_named_stream() -> None:
    """Repeated lookup returns the existing state instead of restarting it."""
    streams = NamedRandomStreams(5)
    first_draw = streams.stream("births").random()
    second_draw = streams.stream("births").random()

    reference = NamedRandomStreams(5).stream("births")
    assert (first_draw, second_draw) == (reference.random(), reference.random())
