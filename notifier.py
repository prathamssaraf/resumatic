"""
Email notifier — sends resume PDF, cover letter PDF, and job link.
Uses Gmail SMTP with App Password.
"""
from __future__ import annotations
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from pathlib import Path
import config


def send_job_email(job: dict, resume_pdf: Path | None, cover_pdf: Path | None) -> bool:
    """
    Send an email with the tailored resume, cover letter, and job link.
    Returns True on success.
    """
    if not config.GMAIL_APP_PASSWORD:
        print("⚠ GMAIL_APP_PASSWORD not set in config.py — skipping email")
        return False
    if not config.GMAIL_SENDER:
        print("⚠ GMAIL_SENDER not set in config.py — skipping email")
        return False

    title   = job.get("title", "Unknown Role")
    company = job.get("company", "Unknown Company")
    url     = job.get("url", "")
    score   = job.get("score", 0)
    reason  = job.get("score_reason", "")
    loc     = job.get("location", "")

    msg = MIMEMultipart()
    msg["From"]    = config.GMAIL_SENDER
    msg["To"]      = config.GMAIL_RECIPIENT
    msg["Subject"] = f"[Job Match] {title} @ {company} — score {score}"

    body = f"""New job match found:

Role:     {title}
Company:  {company}
Location: {loc}
Score:    {score}/100  ({reason})
Link:     {url}

"""
    if resume_pdf and resume_pdf.exists():
        body += f"Resume:      {resume_pdf.name}\n"
    if cover_pdf and cover_pdf.exists():
        body += f"Cover letter: {cover_pdf.name}\n"

    body += "\n— jobs-auto-scanner"
    msg.attach(MIMEText(body, "plain"))

    # Attach PDFs
    for pdf in [resume_pdf, cover_pdf]:
        if pdf and pdf.exists():
            with open(pdf, "rb") as f:
                part = MIMEApplication(f.read(), _subtype="pdf")
                part.add_header("Content-Disposition", "attachment", filename=pdf.name)
                msg.attach(part)

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as server:
            server.login(config.GMAIL_SENDER, config.GMAIL_APP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"  ✗ Email failed: {e}")
        return False
