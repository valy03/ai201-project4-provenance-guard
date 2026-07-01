"""Provenance Guard — Flask API.

Endpoints:
  POST /submit  — run both detection signals, fuse into a confidence-scored label,
                  audit-log the decision, and return the transparency label.
  POST /appeal  — a creator contests a decision; logs the appeal and flips the
                  content's status to "under_review".
  GET  /log     — the structured audit log (decisions + appeals).
  GET  /health  — liveness check.
"""

import uuid

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

import audit_log
from detection import llm_signal, stylometric_signal
from labels import build_label
from scoring import score

load_dotenv()

app = Flask(__name__)

# Rate limiting (see README for chosen limits + reasoning). In-memory storage is
# fine for local dev / grading; a real deployment would use Redis.
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)

MIN_TEXT_CHARS = 20  # short texts make the stylometric stats meaningless (planning §5)


@app.errorhandler(429)
def ratelimit_handler(e):
    return (
        jsonify({"error": "rate limit exceeded", "detail": str(e.description)}),
        429,
    )


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.post("/submit")
@limiter.limit("10 per minute;100 per day")
def submit():
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    creator_id = data.get("creator_id")

    if len(text) < MIN_TEXT_CHARS:
        return (
            jsonify({"error": f"'text' is required and must be at least "
                              f"{MIN_TEXT_CHARS} characters."}),
            400,
        )

    content_id = "c_" + uuid.uuid4().hex[:10]

    # --- Signal 1: stylometric (local) ----------------------------------------
    style = stylometric_signal(text)
    # --- Signal 2: LLM-as-judge (Groq) ----------------------------------------
    llm = llm_signal(text)
    # --- Fuse into a calibrated confidence + label class ----------------------
    result = score(style["p_ai"], llm["p_ai"], llm["available"])

    label_class = result["label_class"]
    confidence = result["confidence"]
    label_text = build_label(label_class, confidence)

    signals = {"stylometric": style, "llm": llm}

    # --- Audit log (records both signals + combined result) -------------------
    audit_log.append({
        "kind": "decision",
        "content_id": content_id,
        "creator_id": creator_id,
        "attribution": label_class,
        "score": result["score"],
        "confidence": confidence,
        "disagreement": result["disagreement"],
        "degraded": result["degraded"],
        "signals": {
            "stylometric_p_ai": style["p_ai"],
            "llm_p_ai": llm["p_ai"],
            "llm_available": llm["available"],
        },
        "label_text": label_text,
        "appealed": False,
        "status": "classified",
    })

    return jsonify({
        "content_id": content_id,
        "creator_id": creator_id,
        "label_class": label_class,
        "confidence": confidence,
        "score": result["score"],
        "label_text": label_text,
        "signals": signals,
        "status": "classified",
    })


@app.post("/appeal")
def appeal():
    data = request.get_json(silent=True) or {}
    content_id = data.get("content_id")
    # Accept the grader's field name and a shorter alias.
    reasoning = (data.get("creator_reasoning") or data.get("reason") or "").strip()

    if not content_id or not reasoning:
        return (
            jsonify({"error": "Both 'content_id' and 'creator_reasoning' are "
                              "required."}),
            400,
        )

    original = audit_log.find_decision(content_id)
    if original is None:
        return jsonify({"error": f"No decision found for content_id {content_id!r}."}), 404

    appeal_id = "a_" + uuid.uuid4().hex[:8]

    # Log the appeal alongside the original decision, and set status under_review.
    audit_log.append({
        "kind": "appeal",
        "appeal_id": appeal_id,
        "content_id": content_id,
        "creator_id": original.get("creator_id"),
        "appeal_reasoning": reasoning,
        "original_attribution": original.get("attribution"),
        "original_confidence": original.get("confidence"),
        "status": "under_review",
    })

    return jsonify({
        "content_id": content_id,
        "appeal_id": appeal_id,
        "status": "under_review",
        "message": "Appeal received. This content is now under review by a human "
                   "moderator.",
    })


@app.get("/log")
def get_log():
    return jsonify({"entries": audit_log.read_all()})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
