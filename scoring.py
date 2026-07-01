"""Confidence scoring — fuse the two signal scores into one calibrated result.

Implements planning.md §2 exactly:
    S          = 0.25*p_style + 0.75*p_llm        (fused AI-likelihood)
    d          = |p_style - p_llm|                (disagreement)
    distance   = |S - 0.5| * 2                    (how decisive S is)
    agreement  = 1 - d                            (how much signals agree)
    confidence = distance * agreement             (high only if decisive AND agreeing)

Label bands (disagreement override checked first):
    d >= 0.40           -> uncertain
    else S >= 0.70      -> ai
    else S <= 0.30      -> human
    else                -> uncertain
"""

W_STYLE = 0.25
W_LLM = 0.75
DISAGREEMENT_THRESHOLD = 0.40
AI_BAND = 0.70
HUMAN_BAND = 0.30
DEGRADED_CONFIDENCE_CAP = 0.60  # one signal only -> cap how confident we may claim


def _clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def score(p_style: float, p_llm: float, llm_available: bool = True) -> dict:
    """Combine the two signal AI-likelihoods into a calibrated decision.

    Returns {score, confidence, label_class, disagreement, degraded}.
    If the LLM signal is unavailable, falls back to the stylometric signal alone and
    caps confidence to reflect reduced reliability.
    """
    if not llm_available:
        s = p_style
        d = 0.0
        distance = abs(s - 0.5) * 2
        confidence = _clamp(min(distance, DEGRADED_CONFIDENCE_CAP))
        label_class = _band(s, d)
        return {
            "score": round(s, 4),
            "confidence": round(confidence, 4),
            "label_class": label_class,
            "disagreement": 0.0,
            "degraded": True,
        }

    s = W_STYLE * p_style + W_LLM * p_llm
    d = abs(p_style - p_llm)
    distance = abs(s - 0.5) * 2
    agreement = 1.0 - d
    confidence = _clamp(distance * agreement)
    return {
        "score": round(s, 4),
        "confidence": round(confidence, 4),
        "label_class": _band(s, d),
        "disagreement": round(d, 4),
        "degraded": False,
    }


def _band(s: float, d: float) -> str:
    if d >= DISAGREEMENT_THRESHOLD:
        return "uncertain"
    if s >= AI_BAND:
        return "ai"
    if s <= HUMAN_BAND:
        return "human"
    return "uncertain"
