"""Keep list: posts never removed, whatever the rules say.

A plain text file, one post ID or post link per line. Blank lines and `#` comments are ignored.
"""

import re
from collections.abc import Iterable
from pathlib import Path

_ID = re.compile(r"\d+")
_LINK = re.compile(
    r"(?:https?://)?(?:www\.|mobile\.)?(?:x|twitter)\.com/[^/\s]+(?:/web)?/status/(\d+)(?:[/?#]\S*)?"
)


class KeepError(ValueError):
    """The keep file is invalid. The message is shown as is."""


def parse_keep(lines: Iterable[str]) -> frozenset[str]:
    ids: set[str] = set()
    for number, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if _ID.fullmatch(line):
            ids.add(line)
        elif match := _LINK.fullmatch(line):
            ids.add(match.group(1))
        else:
            raise KeepError(f"line {number}: '{line}' is not a post ID or post link")
    return frozenset(ids)


def read_keep(path: Path) -> frozenset[str]:
    try:
        text = path.read_text()
    except FileNotFoundError:
        raise KeepError(f"keep file not found: {path}") from None
    try:
        return parse_keep(text.splitlines())
    except KeepError as e:
        raise KeepError(f"{path}, {e}") from None
