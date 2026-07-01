"""Transparency label generation.

Maps a (label_class, confidence) pair to the exact plain-language text shown to a
reader. Three variants — one per label class (planning.md §3). The text is
confidence-aware: it embeds both the numeric percentage and a qualitative tier word
(high / moderate / low) so the label genuinely changes with the confidence score and
never over-claims certainty it doesn't have.
"""


def confidence_tier(confidence: float) -> str:
    if confidence >= 0.60:
        return "high"
    if confidence >= 0.30:
        return "moderate"
    return "low"


def build_label(label_class: str, confidence: float) -> str:
    """Return the reader-facing transparency label for this decision."""
    pct = round((confidence or 0.0) * 100)
    tier = confidence_tier(confidence or 0.0)

    if label_class == "ai":
        return (
            f"⚠️ Likely AI-generated ({tier} confidence: {pct}%). "
            "Our automated analysis indicates this text was most likely produced by "
            "an AI system. If you created this yourself and believe the result is "
            "wrong, you can appeal it for human review."
        )
    if label_class == "human":
        return (
            f"✅ Likely human-written ({tier} confidence: {pct}%). "
            "Our automated analysis found no strong signs of AI generation in this "
            "text."
        )
    # uncertain (default / safe fallback)
    return (
        f"❓ Attribution uncertain (confidence in a firm call: {pct}%). "
        "Our two checks disagreed or were inconclusive, so we can't reliably say "
        "whether a person or an AI wrote this. We've labeled it uncertain rather than "
        "guess. If you're the creator, you can appeal for human review."
    )
