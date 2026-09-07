"""Feedback regeneration context and provider-returned thought tags."""
import re

from pydantic import BaseModel, Field


class FeedbackUndoInput(BaseModel):
    feedback: str = Field(min_length=1, max_length=100_000, pattern=r"\S")


class RegenerationContext(BaseModel):
    turn_to_replace: str = Field(min_length=1, max_length=2_000_000, pattern=r"\S")
    model_thoughts: str = Field(default="", max_length=2_000_000)
    feedback: str = Field(min_length=1, max_length=100_000, pattern=r"\S")


THOUGHT_TAGS = re.compile(
    r"<(?P<tag>thought|think|thoughts|thaughts)\b[^>]*>.*?</(?P=tag)\s*>",
    re.IGNORECASE | re.DOTALL,
)


def extract_model_thoughts(text: str) -> str:
    """Preserve the actual complete tags and their contents; invent no reasoning."""
    return "\n".join(match.group(0) for match in THOUGHT_TAGS.finditer(text or ""))


def without_model_thoughts(text: str) -> str:
    return THOUGHT_TAGS.sub("", text or "")


def with_regeneration_feedback(user_message: str, context: RegenerationContext | None) -> str:
    if context is None:
        return user_message
    return f"""{user_message}

Regeneration instructions:
Write a replacement for the removed turn below, using the original user input,
the normal story context, and the feedback. The removed turn and its model
thoughts are reference material for revision and may contain mistakes.
Return the replacement story prose. Keep the feedback and these reference
labels out of the story itself.

Turn to replace:
<turn_to_replace>
{context.turn_to_replace}
</turn_to_replace>

Model thoughts:
<model_thoughts>
{context.model_thoughts or '(No model thoughts were saved for this turn.)'}
</model_thoughts>

Feedback:
<feedback>
{context.feedback}
</feedback>"""
