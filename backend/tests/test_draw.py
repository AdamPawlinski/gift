from uuid import uuid4

import pytest

from app.draw import draw


@pytest.mark.parametrize("n", range(2, 11))
def test_draw_is_derangement_bijection(n):
    ids = [uuid4() for _ in range(n)]
    for _ in range(500):
        result = draw(ids)
        assert set(result) == set(ids)
        assert set(result.values()) == set(ids)
        assert all(giver != receiver for giver, receiver in result.items())


def test_two_participants_swap():
    a, b = uuid4(), uuid4()
    assert draw([a, b]) == {a: b, b: a}


@pytest.mark.parametrize("n", [0, 1])
def test_too_few_participants(n):
    with pytest.raises(ValueError):
        draw([uuid4() for _ in range(n)])


def test_duplicate_ids_rejected():
    a = uuid4()
    with pytest.raises(ValueError):
        draw([a, a])
    with pytest.raises(ValueError):
        draw([a, uuid4(), a])


def test_input_is_not_mutated():
    ids = [uuid4() for _ in range(5)]
    before = list(ids)
    draw(ids)
    assert ids == before


def test_result_keeps_input_order_of_givers():
    ids = [uuid4() for _ in range(6)]
    assert list(draw(ids)) == ids


def test_works_with_any_hashable_ids():
    names = ["Ala", "Bartek", "Czesia"]
    result = draw(names)
    assert set(result) == set(names) == set(result.values())


def test_input_can_be_any_iterable_order():
    ids = [uuid4() for _ in range(4)]
    assert set(draw(list(reversed(ids)))) == set(ids)


@pytest.mark.parametrize(("n", "derangements"), [(3, 2), (4, 9), (5, 44)])
def test_every_valid_pairing_is_reachable(n, derangements):
    ids = list(range(n))
    seen = {tuple(draw(ids).values()) for _ in range(derangements * 300)}
    assert len(seen) == derangements


def test_pairings_are_roughly_uniform():
    ids = [0, 1, 2]
    runs = 6000
    first = sum(draw(ids)[0] == 1 for _ in range(runs))
    # With 3 people there are two derangements: 0 -> 1 in one of them (50%).
    assert abs(first / runs - 0.5) < 0.05


def test_large_group():
    ids = [uuid4() for _ in range(500)]
    result = draw(ids)
    assert len(result) == 500
    assert all(giver != receiver for giver, receiver in result.items())
    assert set(result.values()) == set(ids)
