"""Unit tests for the Reachy Says state machine — no robot, no real threads
or sleeps. `GameState` takes an injectable rng and clock (see game.py) for
exactly this reason."""

import random

import pytest

from reachy_says.game import DEFAULT_TIMER_SECONDS, GameState, Status


class FakeClock:
    """Callable clock main.py would normally get from time.monotonic()."""

    def __init__(self, t: float = 0.0):
        self.t = t

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


def make_state(seed: int = 0) -> tuple[GameState, FakeClock]:
    clock = FakeClock()
    state = GameState()
    state._rng = random.Random(seed)
    state._time_fn = clock
    return state, clock


def start_round_one(state: GameState) -> None:
    """start() + begin_first_round() — the two-step flow main.py drives in
    production (it speaks the intro greeting in between). Most tests below
    only care about round 1's resulting state, not the intro phase itself
    (see test_start_enters_intro_before_round_one for that)."""
    state.start()
    state.begin_first_round()


def test_start_enters_intro_before_round_one():
    state, _ = make_state()
    state.start()
    assert state.status == Status.INTRO
    assert state.round_number == 0
    assert state.current_command is None

    state.begin_first_round()
    assert state.status == Status.ANNOUNCING
    assert state.round_number == 1


def test_round_one_is_never_a_trick():
    state, _ = make_state()
    start_round_one(state)
    assert state.round_number == 1
    assert state.status == Status.ANNOUNCING
    assert state.is_trick is False
    assert state.current_command is not None


def test_begin_waiting_sets_a_full_timer_deadline():
    state, clock = make_state()
    start_round_one(state)
    state.begin_waiting()
    assert state.status == Status.WAITING
    assert state.time_remaining() == pytest.approx(DEFAULT_TIMER_SECONDS)
    clock.advance(DEFAULT_TIMER_SECONDS / 2)
    assert state.time_remaining() == pytest.approx(DEFAULT_TIMER_SECONDS / 2)


def test_confirm_only_takes_effect_while_waiting():
    state, _ = make_state()
    start_round_one(state)  # status == ANNOUNCING
    state.confirm()
    assert state.confirmed is False
    state.begin_waiting()
    state.confirm()
    assert state.confirmed is True


def test_non_trick_confirm_before_deadline_is_success():
    state, clock = make_state()
    start_round_one(state)
    state.is_trick = False
    state.begin_waiting()
    state.confirm()
    event = state.tick()
    assert event == "result"
    assert state.last_result == "success"
    assert state.score == 1
    assert state.status == Status.RESULT


def test_non_trick_timeout_still_counts_as_success():
    """No camera verification in V1 — the game must not stall forever
    waiting for a press that may never come."""
    state, clock = make_state()
    start_round_one(state)
    state.is_trick = False
    state.begin_waiting()
    clock.advance(DEFAULT_TIMER_SECONDS + 1)
    event = state.tick()
    assert event == "result"
    assert state.last_result == "success"
    assert state.score == 1


def test_trick_confirmed_is_gotcha_and_ends_the_game():
    state, clock = make_state()
    start_round_one(state)
    state.is_trick = True
    state.begin_waiting()
    state.confirm()
    assert state.tick() == "result"
    assert state.last_result == "gotcha"
    assert state.score == 0  # caught — no point for this round

    clock.advance(10)  # past the result pause
    assert state.tick() == "game_over"
    assert state.status == Status.GAME_OVER


def test_trick_timeout_is_survived_and_the_game_continues():
    state, clock = make_state()
    start_round_one(state)
    state.is_trick = True
    state.begin_waiting()
    clock.advance(DEFAULT_TIMER_SECONDS + 1)
    assert state.tick() == "result"
    assert state.last_result == "survived_trick"
    assert state.score == 1

    clock.advance(10)
    assert state.tick() == "announce"
    assert state.status == Status.ANNOUNCING
    assert state.round_number == 2


def test_game_ends_after_max_rounds_without_a_gotcha():
    state, clock = make_state()
    state.max_rounds = 1
    start_round_one(state)
    state.is_trick = False
    state.begin_waiting()
    state.confirm()
    state.tick()  # -> RESULT
    clock.advance(10)
    assert state.tick() == "game_over"
    assert state.status == Status.GAME_OVER
    assert state.last_result == "success"


def test_never_two_trick_rounds_in_a_row():
    state, _ = make_state()
    state.last_trick_round = True
    state.round_number = 1  # about to become 2, which is > 1
    state._begin_round()
    # The "not last_trick_round" guard short-circuits before touching rng,
    # so this is deterministic regardless of seed.
    assert state.is_trick is False


def test_configure_validates_the_timer_and_rounds_range():
    state, _ = make_state()
    state.configure(6.0, 8)
    assert state.timer_seconds == 6.0
    assert state.max_rounds == 8
    with pytest.raises(ValueError):
        state.configure(1.0, 8)
    with pytest.raises(ValueError):
        state.configure(100.0, 8)
    with pytest.raises(ValueError):
        state.configure(6.0, 0)
    with pytest.raises(ValueError):
        state.configure(6.0, 999)


def test_reset_clears_everything():
    state, clock = make_state()
    start_round_one(state)
    state.begin_waiting()
    state.confirm()
    state.tick()
    state.reset()
    assert state.status == Status.IDLE
    assert state.round_number == 0
    assert state.score == 0
    assert state.last_result is None


def test_public_dict_hides_trick_flag_while_waiting():
    state, _ = make_state()
    start_round_one(state)
    state.is_trick = True
    state.begin_waiting()
    data = state.to_public_dict()
    assert "is_trick" not in data
    assert data["last_result"] is None
    assert data["status"] == "waiting"
