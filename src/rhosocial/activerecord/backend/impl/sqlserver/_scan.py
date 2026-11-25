# src/rhosocial/activerecord/backend/impl/sqlserver/_scan.py
"""Plain character-scanning primitives shared by the SQL Server parsers.

The backend reads server text -- driver error messages, declared type
spellings, prepared statements -- by scanning characters instead of using the
standard-library ``re`` module. The parsing rules stay explicit, and the shipped
source carries no regular-expression dependency. Tests may still use regexes to
assert generated SQL.

Each helper mirrors the corresponding regular-expression construct, so the
parsers built on them keep the behaviour they had when they were regex based.
"""

from typing import Optional, Tuple


def is_word_char(ch: str) -> bool:
    """Whether *ch* counts as a regex ``\\w`` character."""
    return ch.isalnum() or ch == "_"


def is_ascii_identifier_start(ch: str) -> bool:
    """Whether *ch* may open a ``[A-Za-z_]`` identifier."""
    return ch.isascii() and (ch.isalpha() or ch == "_")


def is_ascii_identifier_char(ch: str) -> bool:
    """Whether *ch* may continue a ``[A-Za-z0-9_]`` identifier."""
    return ch.isascii() and (ch.isalnum() or ch == "_")


def word_boundary_at(text: str, index: int) -> bool:
    """Whether a regex ``\\b`` would hold at *index*."""
    if index <= 0 or index >= len(text):
        return True
    return is_word_char(text[index - 1]) != is_word_char(text[index])


def skip_space(text: str, index: int) -> int:
    """Return the index just past any whitespace starting at *index*."""
    while index < len(text) and text[index].isspace():
        index += 1
    return index


def skip_space_at_least_one(text: str, index: int) -> Optional[int]:
    """Consume ``\\s+``; return ``None`` when no whitespace is present."""
    end = skip_space(text, index)
    if end == index:
        return None
    return end


def digit_run_length(text: str, index: int) -> int:
    """Length of the decimal-digit run beginning at *index*."""
    end = index
    while end < len(text) and text[end].isdecimal():
        end += 1
    return end - index


def leading_word(text: str) -> str:
    """Return the run of word characters at the start of *text*.

    Equals the longest prefix a ``^(?:WORD...)\\b`` alternation could take, so
    comparing the result with a spelling reproduces ``^WORD\\b`` exactly.
    """
    end = 0
    while end < len(text) and is_word_char(text[end]):
        end += 1
    return text[:end]


def keyword_at(text: str, index: int, word: str) -> bool:
    """Whether *word* appears at *index*, case-insensitively and unbounded."""
    return text[index:index + len(word)].lower() == word.lower()


def consume_keyword(text: str, index: int, word: str) -> Optional[int]:
    """Return the index after *word*, or ``None`` when it is absent."""
    if keyword_at(text, index, word):
        return index + len(word)
    return None


def find_ci(text: str, needle: str, start: int = 0) -> int:
    """Index of *needle* in *text*, case-insensitively, or ``-1``."""
    width = len(needle)
    target = needle.lower()
    index = start
    while index + width <= len(text):
        if text[index:index + width].lower() == target:
            return index
        index += 1
    return -1


def parse_identifier(text: str, index: int) -> Optional[Tuple[str, int]]:
    """Read a bracketed ``[name]`` or bare ``name`` identifier at *index*.

    Returns the name and the index just past it, or ``None`` when the text at
    *index* does not spell an identifier.
    """
    if index >= len(text):
        return None
    if text[index] == "[":
        close = text.find("]", index + 1)
        if close <= index + 1:  # missing bracket, or the empty "[]"
            return None
        return text[index + 1:close], close + 1
    if not is_ascii_identifier_start(text[index]):
        return None
    end = index + 1
    while end < len(text) and (is_word_char(text[end]) or text[end] == "$"):
        end += 1
    return text[index:end], end


def bare_identifier_end(text: str, index: int) -> Optional[int]:
    """Read a bare ``[A-Za-z_][\\w$]*`` word; return its end index."""
    if index >= len(text) or not is_ascii_identifier_start(text[index]):
        return None
    end = index + 1
    while end < len(text) and (is_word_char(text[end]) or text[end] == "$"):
        end += 1
    return end


def find_argument_list(text: str) -> Optional[Tuple[int, Optional[int]]]:
    """Find the first ``(n)`` or ``(p,s)`` argument list in *text*.

    Mirrors ``\\(\\s*(\\d+)\\s*(?:,\\s*(\\d+)\\s*)?\\)``: the opening parenthesis
    must be followed by a number (an argument list such as ``(MAX)`` is not one),
    the numbers keep their original digit runs, and a third component means the
    text is not an argument list. Returns ``(first, second)`` with ``second``
    ``None`` when no scale was declared.
    """
    index = text.find("(")
    while index != -1:
        cursor = skip_space(text, index + 1)
        first_length = digit_run_length(text, cursor)
        if first_length:
            after_first = skip_space(text, cursor + first_length)
            if after_first < len(text) and text[after_first] == ")":
                return int(text[cursor:cursor + first_length]), None
            if after_first < len(text) and text[after_first] == ",":
                scale_start = skip_space(text, after_first + 1)
                scale_length = digit_run_length(text, scale_start)
                if scale_length:
                    after_scale = skip_space(text, scale_start + scale_length)
                    if after_scale < len(text) and text[after_scale] == ")":
                        return (
                            int(text[cursor:cursor + first_length]),
                            int(text[scale_start:scale_start + scale_length]),
                        )
        index = text.find("(", index + 1)
    return None
