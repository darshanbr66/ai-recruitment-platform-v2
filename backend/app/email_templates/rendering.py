"""Placeholder resolution for email subjects and bodies.

Contract (relied on by the compose/preview/send flow):

* ``{{name}}`` for a known placeholder with a value is replaced by that
  value (single pass — a value is never itself re-expanded).
* A line containing a known placeholder that has NO value is dropped
  entirely, so an optional detail such as the meeting link never leaves a
  dangling ``Meeting link:`` label behind.
* A *required* placeholder with no value, or a placeholder that isn't in
  ``KNOWN_PLACEHOLDERS``, is reported in ``unresolved`` and left in place
  in the text. The composer shows it so the recruiter can fill it in;
  sending is refused while anything is unresolved, so a raw ``{{...}}`` can
  never reach a candidate.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass

from app.email_templates.templates import KNOWN_PLACEHOLDERS

PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")
_EXCESS_BLANK_LINES = re.compile(r"\n{3,}")


@dataclass(frozen=True)
class ResolvedText:
    text: str
    unresolved: tuple[str, ...]


def resolve_placeholders(
    text: str, values: Mapping[str, str], *, required: frozenset[str] = frozenset()
) -> ResolvedText:
    output_lines: list[str] = []

    for line in text.replace("\r\n", "\n").split("\n"):
        names = PLACEHOLDER_PATTERN.findall(line)
        if not names:
            output_lines.append(line)
            continue

        drop_line = any(
            name in KNOWN_PLACEHOLDERS
            and name not in required
            and not (values.get(name) or "").strip()
            for name in names
        )
        if drop_line:
            continue

        def substitute(match: re.Match[str]) -> str:
            name = match.group(1)
            value = (values.get(name) or "").strip()
            if name in KNOWN_PLACEHOLDERS and value:
                return value
            return match.group(0)  # unknown or required-but-empty: keep visible

        output_lines.append(PLACEHOLDER_PATTERN.sub(substitute, line))

    resolved = _EXCESS_BLANK_LINES.sub("\n\n", "\n".join(output_lines)).strip()

    # Scan the *result*: this also catches a placeholder that arrived through
    # a value (e.g. a recruiter typing "{{x}}" into a field).
    unresolved = tuple(dict.fromkeys(PLACEHOLDER_PATTERN.findall(resolved)))
    return ResolvedText(text=resolved, unresolved=unresolved)
