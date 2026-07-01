"""Provenance Guard — Flask API.

Milestone 3: POST /submit runs Signal 1 (stylometric) and writes a structured audit
entry; GET /log surfaces the audit log; GET /health is a liveness check. Confidence
and the transparency label are placeholders here and become real in M4/M5.
"""

import uuid

from dotenv import load_dotenv
from flask import Flask, jsonify, request

import audit_log
from detection import stylometric_signal

load_dotenv()

app = Flask(__name__)

MIN_TEXT_CHARS = 20  # short texts make the stylometric stats meaningless (planning §5)


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.post("/submit")
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

    # --- Signal 1: stylometric ------------------------------------------------
    style = stylometric_signal(text)

    # --- Placeholders (real fusion + label arrive in M4/M5) -------------------
    confidence = None
    label_class = "pending"
    label_text = "Analysis in progress — second signal and confidence scoring " \
                 "are added in Milestone 4."

    # --- Audit log ------------------------------------------------------------
    audit_log.append({
        "kind": "decision",
        "content_id": content_id,
        "creator_id": creator_id,
        "attribution": label_class,
        "confidence": confidence,
        "signals": {"stylometric": style},
        "status": "classified",
    })

    return jsonify({
        "content_id": content_id,
        "creator_id": creator_id,
        "label_class": label_class,
        "confidence": confidence,
        "score": style["p_ai"],
        "label_text": label_text,
        "signals": {"stylometric": style},
        "status": "classified",
    })


@app.get("/log")
def get_log():
    return jsonify({"entries": audit_log.read_all()})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
