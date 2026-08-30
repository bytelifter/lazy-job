import os
import json
import smtplib
from email.message import EmailMessage
from typing import Optional

try:
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
except ImportError:
    pass

from privacy.gdpr_compliance import GDPRCompliance

class GmailSender:
    """
    Handles B2B cold outreach via Gmail API (SMTP with App Password).
    Includes built-in GDPR checks and Budget limits (max emails per day).
    """
    MAX_EMAILS_PER_DAY = 50
    
    def __init__(self, config_path: str = "config.local.json"):
        self.config_path = config_path
        self.gdpr = GDPRCompliance()
        self._load_config()

    def _load_config(self):
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass
        self.sender_email = os.environ.get("GMAIL_ADDRESS", "")
        self.app_password = os.environ.get("GMAIL_APP_PASSWORD", "")

    def authenticate(self) -> bool:
        """Checks if credentials exist. Real auth happens during send."""
        if not self.sender_email or not self.app_password:
            print("⚠️ Gmail auth skipped: Missing GMAIL_ADDRESS or GMAIL_APP_PASSWORD in .env.")
            return False
        return True

    def check_daily_limit(self) -> bool:
        """
        Conta le email inviate oggi leggendo il CRM.
        Blocca l'invio se abbiamo raggiunto il limite giornaliero (default: 40).
        """
        import json
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        
        crm_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "crm_db.json")
        
        try:
            if not os.path.exists(crm_path):
                return True
            with open(crm_path, "r", encoding="utf-8") as f:
                db = json.load(f)
            
            count = 0
            for lead in db.get("outreach_leads", {}).values():
                for msg in lead.get("history", []):
                    if msg.get("role") == "bot" and msg.get("timestamp", "").startswith(today):
                        count += 1
            
            if count >= self.MAX_EMAILS_PER_DAY:
                print(f"🛑 Limite giornaliero raggiunto: {count}/{self.MAX_EMAILS_PER_DAY} messaggi già inviati oggi.")
                return False
            return True
        except Exception:
            return True  # In caso di errore di lettura, lasciamo passare

    def send_email(self, to_email: str, subject: str, body: str, lead_source: str = "Direct") -> bool:
        """
        Sends an email via Gmail SMTP, after passing GDPR and Budget Guard checks.
        """
        if self.gdpr.is_blacklisted(to_email):
            print(f"🚫 BLOCKED: {to_email} is in the GDPR blacklist. Aborting send.")
            return False
            
        if not self.check_daily_limit():
            print(f"🛑 BLOCKED: Reached daily limit of {self.MAX_EMAILS_PER_DAY} emails.")
            return False

        if not self.authenticate():
            print(f"📧 DRY RUN (No Auth): Would have sent email to {to_email} | Subject: {subject}")
            return False

        try:
            message = EmailMessage()
            
            # GDPR requirement: Opt-out instructions in footer
            footer = (
                "\n\n---\n"
                "Samuele Columbu\n"
                "Ricevi questa email perché ho notato la tua attività online. "
                "Se non desideri ricevere ulteriori comunicazioni, rispondi con 'STOP'."
            )
            
            message.set_content(body + footer)
            message['To'] = to_email
            message['From'] = self.sender_email
            message['Subject'] = subject

            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(self.sender_email, self.app_password)
                server.send_message(message)
                
            print(f"✅ Email sent to {to_email}!")
            
            # Log for GDPR compliance
            self.gdpr.log_data_processing(to_email, f"B2B Cold Outreach - {subject}", lead_source)
            return True
            
        except Exception as e:
            print(f"❌ Failed to send email to {to_email}: {e}")
            return False

