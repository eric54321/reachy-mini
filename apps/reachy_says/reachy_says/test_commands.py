"""Sanity checks on the static command library — no robot needed."""

from reachy_says.commands import COMMANDS

# Snapshot of Pollen Robotics' reachy-mini-emotions-library move names, taken
# via `python -m reachy_says.gestures --list` (identical library to
# voice_gesture's). Re-run that if the library changes and a command's
# move_name needs to move.
KNOWN_MOVE_NAMES = {
    "amazed1", "anxiety1", "attentive1", "attentive2", "boredom1", "boredom2",
    "calming1", "cheerful1", "come1", "confused1", "contempt1", "curious1",
    "dance1", "dance2", "dance3", "disgusted1", "displeased1", "displeased2",
    "downcast1", "dying1", "electric1", "enthusiastic1", "enthusiastic2",
    "exhausted1", "fear1", "frustrated1", "furious1", "go_away1", "grateful1",
    "helpful1", "helpful2", "impatient1", "impatient2", "incomprehensible2",
    "indifferent1", "inquiring1", "inquiring2", "inquiring3", "irritated1",
    "irritated2", "laughing1", "laughing2", "lonely1", "lost1", "loving1",
    "mini-deep-sleep", "no1", "no_excited1", "no_sad1", "oops1", "oops2",
    "proud1", "proud2", "proud3", "rage1", "relief1", "relief2", "reprimand1",
    "reprimand2", "reprimand3", "resigned1", "sad1", "sad2", "scared1",
    "serenity1", "shy1", "sleep1", "success1", "success2", "surprised1",
    "surprised2", "thoughtful1", "thoughtful2", "tired1", "toc-toc-toc",
    "uncertain1", "uncomfortable1", "understanding1", "understanding2",
    "waiting", "wake-mini-up", "welcoming1", "welcoming2", "yes1", "yes_sad1",
}


def test_command_names_are_unique():
    names = [c.name for c in COMMANDS]
    assert len(names) == len(set(names))


def test_at_least_fifteen_commands():
    assert len(COMMANDS) >= 15


def test_every_move_name_exists_in_the_emotions_library():
    for command in COMMANDS:
        assert command.move_name in KNOWN_MOVE_NAMES, (
            f"{command.name!r} references unknown move {command.move_name!r}"
        )


def test_phrases_are_non_empty_lowercase_actions():
    for command in COMMANDS:
        assert command.phrase
        assert command.phrase == command.phrase.lower()


def test_result_and_game_over_moves_exist_in_the_library():
    from reachy_says.main import RESULT_MOVE

    for move_name in RESULT_MOVE.values():
        assert move_name in KNOWN_MOVE_NAMES
    for move_name in ("welcoming1", "cheerful1"):  # game-over reactions
        assert move_name in KNOWN_MOVE_NAMES


def test_intro_move_exists_in_the_library():
    from reachy_says.main import INTRO_MOVE

    assert INTRO_MOVE in KNOWN_MOVE_NAMES
