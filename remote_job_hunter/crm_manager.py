import json
import os
from datetime import datetime

class CRMManager:
    """
    Gestisce il database locale (JSON) per memorizzare lo storico delle agenzie
    contattate e delle gig per cui si è fatto un'offerta.
    """
    def __init__(self, db_path="crm_db.json"):
        # Put DB in the root directory
        self.db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), db_path)
        self._load_db()

    def _load_db(self):
        if os.path.exists(self.db_path):
            with open(self.db_path, "r", encoding="utf-8") as f:
                self.db = json.load(f)
        else:
            self.db = {
                "freelancer_gigs": {},
                "outreach_leads": {}
            }

    def _save_db(self):
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(self.db, f, indent=4, ensure_ascii=False)

    def log_outreach(self, identifier: str, name: str, email: str, phone: str, channel: str, initial_pitch: str, address: str = ""):
        """
        Salva un nuovo contatto Outreach nel CRM.
        L'identifier è la chiave primaria (il numero di telefono se WA, l'email se Gmail).
        """
        if "outreach_leads" not in self.db:
            self.db["outreach_leads"] = {}
            
        self.db["outreach_leads"][identifier] = {
            "name": name,
            "email": email,
            "phone": phone,
            "address": address,
            "channel": channel,
            "status": "contacted",
            "timestamp": datetime.now().isoformat(),
            "history": [
                {"role": "bot", "content": initial_pitch, "timestamp": datetime.now().isoformat()}
            ]
        }
        self._save_db()

    def add_reply(self, identifier: str, content: str, role: str = "client"):
        """
        Aggiunge un messaggio alla cronologia di un lead esistente.
        """
        if identifier in self.db.get("outreach_leads", {}):
            self.db["outreach_leads"][identifier]["history"].append({
                "role": role,
                "content": content,
                "timestamp": datetime.now().isoformat()
            })
            if role == "client":
                self.db["outreach_leads"][identifier]["status"] = "replied"
            self._save_db()

    def log_freelancer_bid(self, gig_id: str, title: str, url: str, proposal: str, bid_amount: str):
        if "freelancer_gigs" not in self.db:
            self.db["freelancer_gigs"] = {}
            
        self.db["freelancer_gigs"][gig_id] = {
            "title": title,
            "url": url,
            "proposal": proposal,
            "bid_amount": bid_amount,
            "status": "bid_sent",
            "timestamp": datetime.now().isoformat()
        }
        self._save_db()

    def get_lead_by_phone(self, phone: str):
        """Cerca un lead tramite numero di telefono, normalizzandolo."""
        if not phone: return None, None
        phone_norm = phone.strip().replace("+", "").replace(" ", "")
        
        for identifier, data in self.db.get("outreach_leads", {}).items():
            db_phone = data.get("phone", "")
            if db_phone:
                db_phone_norm = db_phone.strip().replace("+", "").replace(" ", "")
                # Se i numeri combaciano (o uno contiene l'altro per evitare problemi col prefisso 39)
                if phone_norm in db_phone_norm or db_phone_norm in phone_norm:
                    return identifier, data
        return None, None
        
    def get_lead_by_email(self, email: str):
        """Cerca un lead tramite email."""
        if not email: return None, None
        for identifier, data in self.db.get("outreach_leads", {}).items():
            db_email = data.get("email", "")
            if db_email and db_email.lower().strip() == email.lower().strip():
                return identifier, data
        return None, None
        
    def check_agency_exists(self, agency_name: str = "", email: str = "", phone: str = "", address: str = "", threshold=0.75) -> bool:
        """
        Deduplicazione Multi-Fattore.
        Ritorna True se l'agenzia esiste già basandosi su:
        1. Match esatto Email
        2. Match esatto Telefono
        3. Fuzzy Match del Nome
        4. Fuzzy Match dell'Indirizzo
        """
        import difflib
        
        agency_name = agency_name.lower().strip() if agency_name else ""
        email = email.lower().strip() if email else ""
        phone = phone.replace("+", "").replace(" ", "").strip() if phone else ""
        address = address.lower().strip() if address else ""
        
        # Se non abbiamo nessun dato da controllare, non possiamo dedurre nulla
        if not any([agency_name, email, phone, address]):
            return False
            
        for identifier, data in self.db.get("outreach_leads", {}).items():
            db_name = data.get("name", "").lower().strip()
            db_email = data.get("email", "").lower().strip()
            db_phone = data.get("phone", "").replace("+", "").replace(" ", "").strip()
            db_address = data.get("address", "").lower().strip()
            
            # 1. Controllo Email (Hard Match)
            if email and db_email and email == db_email:
                return True
                
            # 2. Controllo Telefono (Hard Match - Inclusione)
            if phone and db_phone and (phone in db_phone or db_phone in phone):
                return True
                
            # 3. Controllo Nome (Fuzzy Match)
            if agency_name and db_name:
                if agency_name in db_name or db_name in agency_name:
                    return True
                if difflib.SequenceMatcher(None, agency_name, db_name).ratio() > threshold:
                    return True
                    
            # 4. Controllo Indirizzo (Fuzzy Match - molto stringente per evitare falsi positivi)
            if address and db_address:
                if address in db_address or db_address in address:
                    return True
                if difflib.SequenceMatcher(None, address, db_address).ratio() > 0.85:
                    return True
                    
        return False
