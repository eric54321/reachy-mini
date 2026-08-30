"""Split a manually emotion-tagged message into per-sentence segments.

Input looks like:

    "[happy] Hi there! How are you? [sad] I have to go now."

Emotion tags are written inline as `[tag]` and apply to every sentence that
follows, until the next tag (or the end of the message). Text before the
first tag has no emotion (``None``).
"""

import re
from dataclasses import dataclass

# Matches an inline emotion tag like "[happy]" — letters, digits, underscore,
# hyphen inside the brackets.
_TAG_RE = re.compile(r"\[([\w\-]+)\]")

# Splits text into sentences on '.', '!', '?' (one or more), followed by
# whitespace or end of string. Keeps the terminating punctuation attached.
_SENTENCE_RE = re.compile(r"[^.!?]*[.!?]+(?=\s+|$)|[^.!?]+$")

# A '.' directly between two digits (e.g. "3.14") is a decimal point, not a
# sentence end. Swap it for a placeholder before splitting, then restore it.
_DECIMAL_POINT_RE = re.compile(r"(?<=\d)\.(?=\d)")
_DECIMAL_PLACEHOLDER = "\x00"


@dataclass
class Segment:
    """One sentence paired with the emotion tag active when it was said."""

    sentence: str
    emotion: str | None


def split_message(text: str) -> list[Segment]:
    """Split ``text`` into a list of ``Segment(sentence, emotion)``.

    - Emotion tags (``[tag]``) apply to all following sentences until the
      next tag.
    - Sentences are split on `.`, `!`, `?`.
    - Empty/whitespace-only sentences and stray text are dropped.
    - Text before any tag gets ``emotion=None``.
    """
    segments: list[Segment] = []

    # Split the message on tags, keeping the tags themselves in the result,
    # so we can walk (tag_or_none, following_text) pairs in order.
    parts = _TAG_RE.split(text)
    # re.split with a capturing group returns:
    #   [text_before_first_tag, tag1, text_after_tag1, tag2, text_after_tag2, ...]
    current_emotion: str | None = None
    chunks: list[tuple[str | None, str]] = [(None, parts[0])]
    for i in range(1, len(parts), 2):
        tag = parts[i]
        following = parts[i + 1] if i + 1 < len(parts) else ""
        chunks.append((tag, following))

    for emotion, chunk in chunks:
        if emotion is not None:
            current_emotion = emotion
        protected = _DECIMAL_POINT_RE.sub(_DECIMAL_PLACEHOLDER, chunk)
        for match in _SENTENCE_RE.finditer(protected):
            sentence = match.group(0).replace(_DECIMAL_PLACEHOLDER, ".").strip()
            if sentence:
                segments.append(Segment(sentence=sentence, emotion=current_emotion))

    return segments
