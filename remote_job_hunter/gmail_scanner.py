import imaplib
import email
from email.header import decode_header
import os
import datetime

class GmailScanner:
    """
    Scanner per la casella Gmail. Legge solo le email non lette,
    e se il mittente NON è nel CRM (ovvero è un'email personale),
    la risegna come NON LETTA per non disturbare l'utente.
    """
    def __init__(self, crm):
        self.crm = crm
        self.username = os.environ.get("GMAIL_ADDRESS")
        self.password = os.environ.get("GMAIL_APP_PASSWORD")

    def connect(self):
        if not self.username or not self.password:
            raise ValueError("GMAIL_ADDRESS o GMAIL_APP_PASSWORD mancanti in .env")
        self.mail = imaplib.IMAP4_SSL("imap.gmail.com")
        self.mail.login(self.username, self.password)

    def scan_replies(self):
        replies = []
        try:
            self.connect()
            self.mail.select("inbox")
            
            # Limita la ricerca alle email degli ultimi 2 giorni per evitare
            # di scansionare migliaia di email vecchie ad ogni ciclo (che causava il blocco di 10 min)
            date_since = (datetime.datetime.now() - datetime.timedelta(days=2)).strftime("%d-%b-%Y")
            status, messages = self.mail.uid('search', None, "UNSEEN", "SINCE", date_since)
            
            if status != "OK" or not messages[0]:
                self.mail.logout()
                return replies
                
            uids = messages[0].split()
            
            # Se ci sono troppe email recenti non lette, limitiamo alle ultime 50 per sicurezza
            if len(uids) > 50:
                uids = uids[-50:]
                
            for uid in uids:
                # 1. Fetch SOLO dell'header in modalità PEEK (NON segna l'email come letta)
                status, msg_data = self.mail.uid('fetch', uid, '(BODY.PEEK[HEADER.FIELDS (FROM)])')
                if status != "OK":
                    continue
                    
                sender = ""
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        sender = msg.get("From", "")
                        
                # Estrai indirizzo email pulito
                sender_email = sender
                if "<" in sender and ">" in sender:
                    sender_email = sender.split("<")[1].split(">")[0]
                elif sender:
                    sender_email = sender.strip()
                    
                if not sender_email:
                    continue
                    
                # Controllo Whitelist CRM
                identifier, lead_data = self.crm.get_lead_by_email(sender_email)
                
                if identifier:
                    # 2. È un lead! Facciamo la fetch completa dell'email (rimuovendo PEEK così viene segnata letta)
                    print(f"📧 [GMAIL] Trovata risposta da un Lead: {sender_email}")
                    status, full_data = self.mail.uid('fetch', uid, '(RFC822)')
                    for response_part in full_data:
                        if isinstance(response_part, tuple):
                            full_msg = email.message_from_bytes(response_part[1])
                            body = self._extract_body(full_msg)
                            replies.append({
                                "identifier": identifier,
                                "lead_data": lead_data,
                                "content": body,
                                "channel": "email"
                            })
                else:
                    # E-mail personale. Abbiamo usato PEEK, quindi è rimasta UNSEEN nativamente.
                    # Questo azzera i tempi di caricamento (non fa download pesanti) e non scrive sul server.
                    pass
                            
            self.mail.logout()
        except Exception as e:
            print(f"❌ Errore Gmail Scanner: {e}")
            
        return replies

    def _extract_body(self, msg):
        try:
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        return part.get_payload(decode=True).decode(errors='ignore')
            else:
                return msg.get_payload(decode=True).decode(errors='ignore')
        except Exception:
            pass
        return ""
