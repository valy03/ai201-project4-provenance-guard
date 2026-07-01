"""Detection signals.

Signal 1 (this milestone): stylometric analyzer — a local, deterministic measure of
structural fingerprints of the text. Returns an AI-likelihood score in [0,1] plus the
raw features it measured, per planning.md §1.

Signal 2 (LLM-as-judge, Groq) and score fusion are added in Milestone 4.
"""

import re
import statistics

# Connectors/phrases LLM prose tends to over-use. Density of these is one AI tell.
TRANSITION_PHRASES = [
    "moreover", "furthermore", "in conclusion", "it is important to note",
    "it's important to note", "additionally", "in addition", "however",
    "therefore", "consequently", "as a result", "on the other hand",
    "in today's world", "in summary", "overall", "notably", "ultimately",
    "delve", "tapestry", "realm", "navigate the", "when it comes to",
]

_SENTENCE_SPLIT = re.compile(r"[.!?]+(?:\s+|$)")
_WORD = re.compile(r"[A-Za-z']+")


def _sentences(text: str):
    return [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()]


def _words(text: str):
    return _WORD.findall(text.lower())


def _clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def stylometric_signal(text: str) -> dict:
    """Score how AI-like the *structure* of `text` is.

    Returns {"p_ai": float in [0,1], "features": {...}}. Higher p_ai == more
    machine-like structure. Sub-scores are each in [0,1] as "AI-ness" and combined
    with fixed weights so the result stays explainable and auditable.
    """
    sentences = _sentences(text)
    words = _words(text)
    n_words = len(words)
    n_sentences = len(sentences)

    # --- Feature 1: burstiness (variance in sentence length) --------------------
    # Humans mix short and long sentences (high coefficient of variation); LLM prose
    # is evenly paced (low CV). Low CV -> more AI-like.
    sent_lengths = [len(_words(s)) for s in sentences]
    if n_sentences >= 2 and statistics.mean(sent_lengths) > 0:
        mean_len = statistics.mean(sent_lengths)
        cv = statistics.pstdev(sent_lengths) / mean_len
    else:
        cv = 0.0
    ai_burstiness = _clamp((0.6 - cv) / 0.6)  # cv~0 -> 1.0 ; cv>=0.6 -> 0.0

    # --- Feature 2: lexical diversity (type-token ratio) ------------------------
    # Very low diversity (lots of repeated words) reads as templated. Weak signal,
    # small weight, and length-sensitive so we only trust it on longer text.
    ttr = len(set(words)) / n_words if n_words else 0.0
    ai_diversity = _clamp((0.6 - ttr) / 0.4) if n_words >= 40 else 0.0

    # --- Feature 3: transition-phrase density -----------------------------------
    low = text.lower()
    transition_hits = sum(low.count(p) for p in TRANSITION_PHRASES)
    trans_density = transition_hits / n_sentences if n_sentences else 0.0
    ai_transitions = _clamp(trans_density / 0.5)  # ~half of sentences flagged -> 1.0

    # --- Feature 4: repeated sentence openers -----------------------------------
    openers = [tuple(_words(s)[:2]) for s in sentences if _words(s)]
    if openers:
        most_common = max(openers.count(o) for o in set(openers))
        repeat_ratio = (most_common - 1) / len(openers)
    else:
        repeat_ratio = 0.0
    ai_repetition = _clamp(repeat_ratio / 0.3)

    # --- Combine (explainable fixed weights) ------------------------------------
    p_ai = _clamp(
        0.40 * ai_burstiness
        + 0.10 * ai_diversity
        + 0.30 * ai_transitions
        + 0.20 * ai_repetition
    )

    return {
        "p_ai": round(p_ai, 4),
        "features": {
            "n_words": n_words,
            "n_sentences": n_sentences,
            "sentence_length_cv": round(cv, 4),
            "type_token_ratio": round(ttr, 4),
            "transition_density": round(trans_density, 4),
            "repeated_opener_ratio": round(repeat_ratio, 4),
            "sub_scores": {
                "ai_burstiness": round(ai_burstiness, 4),
                "ai_diversity": round(ai_diversity, 4),
                "ai_transitions": round(ai_transitions, 4),
                "ai_repetition": round(ai_repetition, 4),
            },
        },
    }
