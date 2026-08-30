import json
import os
import time
from datetime import datetime, timedelta

class GDPRCompliance:
    """
    GDPR & ePrivacy compliance engine for B2B cold outreach.
    Manages data retention limits (90 days) and a permanent opt-out blacklist.
    """
    RETENTION_DAYS = 90
    SECRETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "secrets")
    BLACKLIST_FILE = os.path.join(SECRETS_DIR, "gdpr_blacklist.json")
    DATA_LOG_FILE = os.path.join(SECRETS_DIR, "data_processing_log.json")

    def __init__(self):
        os.makedirs(self.SECRETS_DIR, exist_ok=True)
        self._ensure_files()

    def _ensure_files(self):
        if not os.path.exists(self.BLACKLIST_FILE):
            with open(self.BLACKLIST_FILE, "w") as f:
                json.dump([], f)
        if not os.path.exists(self.DATA_LOG_FILE):
            with open(self.DATA_LOG_FILE, "w") as f:
                json.dump([], f)

    def is_blacklisted(self, email: str) -> bool:
        """Checks if an email is in the permanent opt-out blacklist."""
        try:
            with open(self.BLACKLIST_FILE, "r") as f:
                blacklist = json.load(f)
            return email.lower().strip() in [e.lower() for e in blacklist]
        except Exception:
            return False

    def add_to_blacklist(self, email: str, reason: str = "Opt-out requested"):
        """Adds an email to the permanent blacklist."""
        email = email.lower().strip()
        if self.is_blacklisted(email):
            return
        
        with open(self.BLACKLIST_FILE, "r") as f:
            blacklist = json.load(f)
        
        blacklist.append(email)
        with open(self.BLACKLIST_FILE, "w") as f:
            json.dump(blacklist, f, indent=4)
            
        print(f"🔒 GDPR: Added {email} to permanent blacklist. Reason: {reason}")

    def log_data_processing(self, email: str, purpose: str, source: str):
        """Logs data collection for GDPR Article 30 (Record of processing)."""
        email = email.lower().strip()
        entry = {
            "email": email,
            "timestamp": time.time(),
            "date": datetime.now().isoformat(),
            "purpose": purpose, # e.g. "B2B Cold Outreach for Web Design"
            "source": source,   # e.g. "Google Maps Public Data"
            "expires_at": (datetime.now() + timedelta(days=self.RETENTION_DAYS)).isoformat()
        }
        
        with open(self.DATA_LOG_FILE, "r") as f:
            logs = json.load(f)
            
        # Avoid duplicate active logs for the same email
        logs = [l for l in logs if l.get("email") != email]
        logs.append(entry)
        
        with open(self.DATA_LOG_FILE, "w") as f:
            json.dump(logs, f, indent=4)

    def auto_purge_expired(self):
        """Deletes lead data older than RETENTION_DAYS if not converted."""
        with open(self.DATA_LOG_FILE, "r") as f:
            logs = json.load(f)
            
        now = datetime.now()
        active_logs = []
        purged_count = 0
        
        for log in logs:
            try:
                expires = datetime.fromisoformat(log.get("expires_at", ""))
                if expires > now:
                    active_logs.append(log)
                else:
                    purged_count += 1
            except Exception:
                pass
                
        if purged_count > 0:
            with open(self.DATA_LOG_FILE, "w") as f:
                json.dump(active_logs, f, indent=4)
            print(f"🧹 GDPR: Purged {purged_count} expired lead records (>{self.RETENTION_DAYS} days).")
            
if __name__ == "__main__":
    gdpr = GDPRCompliance()
    gdpr.auto_purge_expired()
