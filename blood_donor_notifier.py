"""
Blood Donor Notification System
================================
Sends personalized email (Gmail SMTP) and WhatsApp alerts to donors
when their blood type is urgently needed.

Dependencies:
    pip install twilio python-dotenv

Setup:
    1. Create a .env file (see .env.example below) with your credentials.
    2. For Gmail  → enable 2FA and generate an App Password.
    3. For WhatsApp → sign up at https://www.twilio.com/whatsapp (free sandbox).
"""

import smtplib
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum
from typing import Optional

from dotenv import load_dotenv
from twilio.rest import Client as TwilioClient

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

load_dotenv()  # reads from .env in the project root

# Gmail SMTP
GMAIL_SENDER   = os.getenv("GMAIL_SENDER")        # e.g. yourapp@gmail.com
GMAIL_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")  # 16-char App Password

# Twilio / WhatsApp
TWILIO_SID         = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN  = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WA_NUMBER   = os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")  # Twilio sandbox

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class UrgencyLevel(str, Enum):
    LOW      = "low"       # routine awareness
    MEDIUM   = "medium"    # needed within a week
    HIGH     = "high"      # needed within 48 hours
    CRITICAL = "critical"  # needed TODAY / emergency


URGENCY_META: dict[UrgencyLevel, dict] = {
    UrgencyLevel.LOW: {
        "label":   "Awareness Notice",
        "emoji":   "🩸",
        "colour":  "#4CAF50",
        "cta":     "Please consider scheduling a donation at your earliest convenience.",
        "wa_only": False,   # email only is fine
    },
    UrgencyLevel.MEDIUM: {
        "label":   "Donation Needed Soon",
        "emoji":   "🟡",
        "colour":  "#FF9800",
        "cta":     "Please book an appointment within the next 7 days.",
        "wa_only": False,
    },
    UrgencyLevel.HIGH: {
        "label":   "URGENT — Donate Within 48 Hours",
        "emoji":   "🔴",
        "colour":  "#F44336",
        "cta":     "Lives are at stake. Please visit the nearest donation centre TODAY or TOMORROW.",
        "wa_only": False,
    },
    UrgencyLevel.CRITICAL: {
        "label":   "⚠️ CRITICAL EMERGENCY ⚠️",
        "emoji":   "🚨",
        "colour":  "#B71C1C",
        "cta":     (
            "THIS IS A CRITICAL EMERGENCY. Your blood type is needed RIGHT NOW. "
            "Please call us immediately or go directly to the nearest donation centre."
        ),
        "wa_only": True,   # also send WhatsApp for critical alerts
    },
}

# Compatible blood types (who can donate TO each type)
COMPATIBLE_DONORS: dict[str, list[str]] = {
    "A+":  ["A+", "A-", "O+", "O-"],
    "A-":  ["A-", "O-"],
    "B+":  ["B+", "B-", "O+", "O-"],
    "B-":  ["B-", "O-"],
    "AB+": ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"],
    "AB-": ["A-", "B-", "AB-", "O-"],
    "O+":  ["O+", "O-"],
    "O-":  ["O-"],
}


@dataclass
class Donor:
    name:         str
    blood_type:   str          # e.g. "O-"
    email:        Optional[str] = None
    phone:        Optional[str] = None   # E.164 format: +919876543210
    last_donated: Optional[datetime] = None
    tags:         list[str] = field(default_factory=list)

    # Convenience helpers
    @property
    def whatsapp_number(self) -> Optional[str]:
        return f"whatsapp:{self.phone}" if self.phone else None


# ---------------------------------------------------------------------------
# Message personalisation
# ---------------------------------------------------------------------------

def build_email_html(donor: Donor, needed_type: str, urgency: UrgencyLevel,
                     hospital: str = "City Blood Bank") -> str:
    """Return a styled HTML email body personalised for the donor."""
    meta = URGENCY_META[urgency]
    last_donated_str = (
        donor.last_donated.strftime("%d %b %Y") if donor.last_donated else "N/A"
    )
    compatible_note = (
        f"As a <strong>{donor.blood_type}</strong> donor you can donate to "
        f"<strong>{needed_type}</strong> patients."
        if donor.blood_type in COMPATIBLE_DONORS.get(needed_type, [])
        else f"Your blood type <strong>{donor.blood_type}</strong> is compatible and urgently needed."
    )

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head><meta charset="UTF-8">
    <style>
      body      {{ font-family: Arial, sans-serif; background: #f5f5f5; margin: 0; padding: 20px; }}
      .card     {{ background: #fff; border-radius: 10px; max-width: 580px;
                   margin: auto; padding: 30px; box-shadow: 0 2px 8px rgba(0,0,0,.12); }}
      .banner   {{ background: {meta["colour"]}; color: #fff; border-radius: 6px;
                   padding: 16px 20px; text-align: center; }}
      .banner h2{{ margin: 0; font-size: 22px; }}
      .section  {{ margin-top: 24px; }}
      .info-row {{ display: flex; justify-content: space-between; padding: 6px 0;
                   border-bottom: 1px solid #eee; font-size: 14px; }}
      .cta      {{ margin-top: 24px; background: {meta["colour"]}; color: #fff;
                   border-radius: 6px; padding: 14px 20px; text-align: center;
                   font-weight: bold; font-size: 15px; }}
      .footer   {{ margin-top: 28px; font-size: 12px; color: #999; text-align: center; }}
    </style>
    </head>
    <body>
    <div class="card">
      <div class="banner">
        <h2>{meta["emoji"]} {meta["label"]}</h2>
        <p style="margin:6px 0 0">Blood Type Needed: <strong>{needed_type}</strong></p>
      </div>

      <div class="section">
        <p>Dear <strong>{donor.name}</strong>,</p>
        <p>
          We hope this message finds you well. <strong>{hospital}</strong> urgently requires
          <strong>{needed_type}</strong> blood. {compatible_note}
        </p>
      </div>

      <div class="section">
        <div class="info-row"><span>Your Blood Type</span><strong>{donor.blood_type}</strong></div>
        <div class="info-row"><span>Blood Type Needed</span><strong>{needed_type}</strong></div>
        <div class="info-row"><span>Urgency Level</span><strong>{urgency.value.upper()}</strong></div>
        <div class="info-row"><span>Your Last Donation</span><strong>{last_donated_str}</strong></div>
        <div class="info-row"><span>Contact Hospital</span><strong>{hospital}</strong></div>
      </div>

      <div class="cta">{meta["cta"]}</div>

      <div class="footer">
        You are receiving this because you registered as a blood donor.<br>
        To unsubscribe or update preferences, reply to this email.<br>
        &copy; {datetime.now().year} Blood Donor Network
      </div>
    </div>
    </body>
    </html>
    """


def build_whatsapp_text(donor: Donor, needed_type: str, urgency: UrgencyLevel,
                        hospital: str = "City Blood Bank") -> str:
    """Return a plain-text WhatsApp message personalised for the donor."""
    meta = URGENCY_META[urgency]
    return (
        f"{meta['emoji']} *{meta['label']}* {meta['emoji']}\n\n"
        f"Hello *{donor.name}*,\n\n"
        f"*{hospital}* urgently needs *{needed_type}* blood.\n"
        f"Your type *{donor.blood_type}* is a match!\n\n"
        f"📋 *Urgency:* {urgency.value.upper()}\n\n"
        f"{meta['cta']}\n\n"
        f"_Reply STOP to opt out._"
    )


# ---------------------------------------------------------------------------
# Email delivery (Gmail SMTP)
# ---------------------------------------------------------------------------

def send_email(donor: Donor, needed_type: str, urgency: UrgencyLevel,
               hospital: str = "City Blood Bank") -> bool:
    """Send a personalised HTML email via Gmail SMTP. Returns True on success."""
    if not donor.email:
        log.warning("[Email] %s has no email address — skipping.", donor.name)
        return False
    if not GMAIL_SENDER or not GMAIL_PASSWORD:
        log.error("[Email] Gmail credentials not configured in .env.")
        return False

    meta    = URGENCY_META[urgency]
    subject = f"{meta['emoji']} [{urgency.value.upper()}] {needed_type} Blood Needed — {hospital}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = GMAIL_SENDER
    msg["To"]      = donor.email

    # Plain-text fallback
    plain = (
        f"Dear {donor.name},\n\n"
        f"{hospital} urgently needs {needed_type} blood (your type: {donor.blood_type}).\n"
        f"Urgency: {urgency.value.upper()}\n\n"
        f"{meta['cta']}\n"
    )
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(build_email_html(donor, needed_type, urgency, hospital), "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_SENDER, GMAIL_PASSWORD)
            server.sendmail(GMAIL_SENDER, donor.email, msg.as_string())
        log.info("[Email] ✅  Sent to %s <%s>", donor.name, donor.email)
        return True
    except smtplib.SMTPAuthenticationError:
        log.error("[Email] ❌  Authentication failed — check GMAIL_APP_PASSWORD in .env.")
    except smtplib.SMTPException as exc:
        log.error("[Email] ❌  SMTP error for %s: %s", donor.name, exc)
    return False


# ---------------------------------------------------------------------------
# WhatsApp delivery (Twilio sandbox — free tier)
# ---------------------------------------------------------------------------

def send_whatsapp(donor: Donor, needed_type: str, urgency: UrgencyLevel,
                  hospital: str = "City Blood Bank") -> bool:
    """Send a WhatsApp message via Twilio. Returns True on success."""
    if not donor.phone:
        log.warning("[WhatsApp] %s has no phone number — skipping.", donor.name)
        return False
    if not all([TWILIO_SID, TWILIO_AUTH_TOKEN]):
        log.error("[WhatsApp] Twilio credentials not configured in .env.")
        return False

    body = build_whatsapp_text(donor, needed_type, urgency, hospital)
    try:
        client  = TwilioClient(TWILIO_SID, TWILIO_AUTH_TOKEN)
        message = client.messages.create(
            from_=TWILIO_WA_NUMBER,
            to=donor.whatsapp_number,
            body=body,
        )
        log.info("[WhatsApp] ✅  Sent to %s (%s) — SID: %s",
                 donor.name, donor.phone, message.sid)
        return True
    except Exception as exc:       # Twilio raises TwilioRestException
        log.error("[WhatsApp] ❌  Failed for %s: %s", donor.name, exc)
    return False


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def notify_donor(donor: Donor, needed_type: str, urgency: UrgencyLevel,
                 hospital: str = "City Blood Bank") -> dict[str, bool]:
    """
    Send all appropriate notifications to a single donor.

    Returns a result dict e.g. {"email": True, "whatsapp": False}.
    WhatsApp is always attempted for CRITICAL urgency; optional otherwise.
    """
    meta   = URGENCY_META[urgency]
    result = {}

    # Always send email (if address available)
    result["email"] = send_email(donor, needed_type, urgency, hospital)

    # Send WhatsApp for CRITICAL urgency or if donor has phone and urgency >= HIGH
    send_wa = meta["wa_only"] or urgency in (UrgencyLevel.HIGH, UrgencyLevel.CRITICAL)
    if send_wa:
        result["whatsapp"] = send_whatsapp(donor, needed_type, urgency, hospital)

    return result


def notify_all_compatible_donors(
    donors: list[Donor],
    needed_type: str,
    urgency: UrgencyLevel,
    hospital: str = "City Blood Bank",
) -> list[dict]:
    """
    Filter donors whose blood type is compatible with `needed_type`,
    then notify each one. Returns a summary list.
    """
    compatible_types = COMPATIBLE_DONORS.get(needed_type, [])
    targets = [d for d in donors if d.blood_type in compatible_types]

    log.info(
        "📢  Notifying %d/%d donors for blood type %s [%s urgency] at %s",
        len(targets), len(donors), needed_type, urgency.value.upper(), hospital,
    )

    summary = []
    for donor in targets:
        channels = notify_donor(donor, needed_type, urgency, hospital)
        summary.append({"donor": donor.name, "blood_type": donor.blood_type, **channels})

    return summary


# ---------------------------------------------------------------------------
# Example usage
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Sample donor registry (replace with DB/CSV lookup in production)
    donors = [
        Donor(
            name="Priya Sharma",
            blood_type="O-",
            email="priya@example.com",
            phone="+919876543210",
            last_donated=datetime(2024, 10, 15),
        ),
        Donor(
            name="Arjun Mehta",
            blood_type="O+",
            email="arjun@example.com",
            phone="+919812345678",
            last_donated=datetime(2025, 1, 3),
        ),
        Donor(
            name="Sneha Patel",
            blood_type="AB+",
            email="sneha@example.com",
            # No phone — email only
        ),
        Donor(
            name="Rahul Verma",
            blood_type="B-",
            email="rahul@example.com",
            phone="+919898001122",
        ),
    ]

    # Scenario: AB+ blood critically needed at Apollo Hospital
    results = notify_all_compatible_donors(
        donors=donors,
        needed_type="AB+",
        urgency=UrgencyLevel.CRITICAL,
        hospital="Apollo Hospital, Ahmedabad",
    )

    print("\n─── Notification Summary ───")
    for r in results:
        channels = ", ".join(
            f"{ch}={'✅' if ok else '❌'}"
            for ch, ok in r.items()
            if ch not in ("donor", "blood_type")
        )
        print(f"  {r['donor']} ({r['blood_type']}): {channels}")
