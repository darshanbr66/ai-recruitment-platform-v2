"""Shared prompt-construction and output-validation helpers for any AI
capability that interpolates *retrieved data* (resume/job/application text)
into a Gemini prompt. Used by both the matching engine
(app/services/matching/match_engine.py) and the internal AI service
(app/services/internal_ai/internal_ai_service.py) — kept here, in
`integrations/ai/`, rather than in either of those packages, so neither
depends on the other just to share this.

Deliberately a sibling of `app/services/sigvi_prompts.py`, not a shared
import from it: Sigvi's prompt module is public-surface code, and the
brief's isolation requirement ("internal AI must never be reachable from
the public chatbot's code path") is easiest to keep true by construction
when the internal surface never imports from the public one at all, even
for logic this similar. The safety properties are the same:

- Retrieved text is always wrapped in an explicit tag and told to be data,
  never instructions (defends against a resume/job description containing
  an embedded instruction — CLAUDE.md § 9: "do not allow prompt injection
  from resume content to override system instructions").
- A planted canary catches the model echoing its own instructions.
- Output is scrubbed for anything key-shaped before a caller ever sees it.
"""

import re
from collections.abc import Iterable
from typing import Final

#: Distinct from Sigvi's PROMPT_CANARY (sigvi_prompts.py) on purpose — a
#: match between the two canaries in a log would itself indicate the two
#: surfaces' prompts had been merged, which must never happen.
INTERNAL_AI_PROMPT_CANARY: Final = "internal-ai-guard-4f2b8e"

CANNOT_SHARE_REPLY: Final = (
    "I can't share that. Ask me about a specific candidate, job or the recruitment "
    "pipeline instead."
)

MAX_REPLY_CHARS: Final = 4000

_KEY_LIKE = re.compile(r"AIza[0-9A-Za-z_\-]{20,}")
_BLANK_RUNS = re.compile(r"\n{3,}")


def clean_tagged_text(text: str) -> str:
    """Single line, no angle brackets — so retrieved text can't forge or
    close the delimiter tag it's about to be wrapped in."""
    return " ".join(text.replace("<", "(").replace(">", ")").split())


def wrap_as_data(tag: str, text: str) -> str:
    """Wraps `text` in `<tag>...</tag>` with the standard warning that its
    contents are data, not instructions — the one place every retrieved-data
    interpolation in the internal AI surface should go through, so the
    protection can't be forgotten at a new call site."""
    cleaned = clean_tagged_text(text) if text else "(none available)"
    return f"<{tag}>\n{cleaned}\n</{tag}>"


def validate_reply(text: str, *, secrets: Iterable[str] = ()) -> str | None:
    """The last gate before a generated reply is persisted or returned.
    Returns the cleaned reply, or `None` if there is nothing usable. A reply
    that echoes the prompt canary or anything credential-shaped is replaced
    wholesale by a safe refusal, mirroring sigvi_prompts.validate_reply."""
    reply = _BLANK_RUNS.sub("\n\n", text.strip())
    if not reply:
        return None

    if INTERNAL_AI_PROMPT_CANARY in reply.lower() or _KEY_LIKE.search(reply):
        return CANNOT_SHARE_REPLY
    if any(secret and len(secret) >= 8 and secret in reply for secret in secrets):
        return CANNOT_SHARE_REPLY

    if len(reply) > MAX_REPLY_CHARS:
        cut = reply[:MAX_REPLY_CHARS]
        reply = (cut[: cut.rfind(" ")] if " " in cut else cut).rstrip() + "…"
    return reply
