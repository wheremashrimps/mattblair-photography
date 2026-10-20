import os
import smtplib
from email.message import EmailMessage

from flask import Flask, jsonify, request, send_from_directory

SITE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "site")
app = Flask(__name__, static_folder=None)

KINDS = {"print": "Print", "license": "Licensing", "commission": "Commission", "other": "Other"}


@app.get("/")
def index():
    return send_from_directory(SITE, "index.html", max_age=300)


@app.get("/healthz")
def healthz():
    return "ok"


@app.get("/<path:path>")
def static_files(path):
    # Photos never change in place (new photos get new names), so let browsers cache them for a year.
    max_age = 31536000 if path.startswith("p/") else 3600
    return send_from_directory(SITE, path, max_age=max_age)


@app.post("/api/contact")
def contact():
    """Email an enquiry to CONTACT_TO. Returns 503 until the SMTP variables are set in Railway."""
    cfg = {k: os.environ.get(k) for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASS", "CONTACT_TO")}
    if not all(cfg.values()):
        return jsonify(error="Contact form is not configured"), 503

    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()[:200]
    email = str(data.get("email", "")).strip()[:200]
    message = str(data.get("message", "")).strip()[:5000]
    if not name or "@" not in email or not message:
        return jsonify(error="Name, email and message are required"), 400

    kind = KINDS.get(data.get("kind"), "Other")
    frame = str(data.get("frame", "")).strip()[:200]
    msg = EmailMessage()
    msg["Subject"] = f"Website enquiry ({kind}) from {name}"
    msg["From"] = cfg["SMTP_USER"]
    msg["To"] = cfg["CONTACT_TO"]
    msg["Reply-To"] = email
    msg.set_content(f"{message}\n\n---\nName: {name}\nEmail: {email}\nType: {kind}\nImage: {frame or 'not specified'}\n")

    port = int(os.environ.get("SMTP_PORT", "587"))
    try:
        with smtplib.SMTP(cfg["SMTP_HOST"], port, timeout=15) as s:
            s.starttls()
            s.login(cfg["SMTP_USER"], cfg["SMTP_PASS"])
            s.send_message(msg)
    except (smtplib.SMTPException, OSError):
        app.logger.exception("Sending contact email failed")
        return jsonify(error="Could not send"), 502
    return jsonify(ok=True)


if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5000)))
