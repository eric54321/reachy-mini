"""Tests for split_message. Run with: pytest test_split_message.py"""

from voice_gesture.split_message import Segment, split_message


def test_basic_tagged_sentences():
    msg = "[happy] Hi there! How are you? [sad] I have to go now. Bye."
    assert split_message(msg) == [
        Segment("Hi there!", "happy"),
        Segment("How are you?", "happy"),
        Segment("I have to go now.", "sad"),
        Segment("Bye.", "sad"),
    ]


def test_no_tag_at_all():
    assert split_message("Just plain text with no tags.") == [
        Segment("Just plain text with no tags.", None),
    ]


def test_text_before_first_tag_has_no_emotion():
    msg = "No tag, then [sad] a tag mid-sentence continues here."
    assert split_message(msg) == [
        Segment("No tag, then", None),
        Segment("a tag mid-sentence continues here.", "sad"),
    ]


def test_decimal_point_is_not_a_sentence_break():
    msg = "[curious] What is 3.14? Interesting!"
    assert split_message(msg) == [
        Segment("What is 3.14?", "curious"),
        Segment("Interesting!", "curious"),
    ]


def test_repeated_punctuation_stays_on_one_sentence():
    msg = "[excited] Wow!!! Really?!"
    assert split_message(msg) == [
        Segment("Wow!!!", "excited"),
        Segment("Really?!", "excited"),
    ]


def test_empty_and_whitespace_only_input():
    assert split_message("") == []
    assert split_message("   ") == []


def test_tag_with_no_following_text():
    assert split_message("[happy]") == []


def test_emotion_persists_across_multiple_sentences_until_next_tag():
    msg = "[proud] One. Two. Three. [shy] Four."
    result = split_message(msg)
    assert [s.emotion for s in result] == ["proud", "proud", "proud", "shy"]
    assert [s.sentence for s in result] == ["One.", "Two.", "Three.", "Four."]
