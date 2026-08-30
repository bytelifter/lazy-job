import os
import time
import random
import urllib.parse
from playwright.sync_api import sync_playwright

class WhatsAppSender:
    """
    Gestisce l'invio di messaggi su WhatsApp tramite Playwright (Headless).
    Richiede che wa_auth.py sia stato eseguito almeno una volta per salvare i cookie.
    """
    
    def __init__(self):
        self.session_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "secrets", "wa_session")
        
    def send_message(self, phone_number: str, message: str) -> bool:
        """
        Invia un messaggio WhatsApp in background usando i cookie salvati.
        """
        print(f"📱 Preparazione invio WhatsApp a {phone_number} (Modalità Fantasma)...")
        
        if not os.path.exists(self.session_dir):
            print("❌ ERRORE: Sessione non trovata. Devi prima lanciare wa_auth.py per scansionare il QR code!")
            return False
            
        phone = str(phone_number).strip().replace(" ", "")
        if phone.startswith("3") and len(phone) == 10:
            phone = "39" + phone
        phone = phone.replace("+", "")
        
        try:
            with sync_playwright() as p:
                print("  └ 🌐 Apertura browser invisibile (Headless)...")
                # Lanciamo il browser con i cookie salvati in modalità invisibile
                browser = p.chromium.launch_persistent_context(
                    user_data_dir=self.session_dir,
                    headless=False,
                    args=["--headless=new"], # Usa la nuova architettura headless di Chrome (previene i crash di sessione)
                    viewport={'width': 1280, 'height': 800},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
                )
                
                page = browser.pages[0]
                encoded_msg = urllib.parse.quote(message)
                url = f"https://web.whatsapp.com/send?phone={phone}&text={encoded_msg}"
                
                print("  └ 🔄 Navigazione verso la chat e attesa caricamento...")
                page.goto(url, timeout=60000)
                
                # Aspettiamo che il container principale (la lista chat o la chat stessa) sia visibile
                try:
                    # Riduciamo il timeout a 15s. Se un numero non è valido, WA mostrerà un popup e non caricherà la chat.
                    print("  └ Attendo il caricamento della chat (max 15s)...")
                    page.wait_for_selector('#main', timeout=15000)
                    time.sleep(2) # Pausa extra per sicurezza
                    
                    # Premiamo 'Enter' (invio) dato che l'URL pre-compila già il testo nel box attivo
                    page.keyboard.press("Enter")
                    print(f"✅ Messaggio WhatsApp inviato con successo a {phone}!")
                    
                    # Aspettiamo un paio di secondi per permettere l'invio fisico del pacchetto
                    time.sleep(3)
                    
                except Exception as ex:
                    # Timeout raggiunto (spesso perché il numero non è registrato su WhatsApp)
                    print(f"  └ ⚠️ Numero non valido su WhatsApp. Fallimento silenzioso.")
                    browser.close()
                    return False
                
                browser.close()
                return True
                
        except Exception as e:
            print(f"❌ Errore critico durante l'automazione Playwright: {e}")
            return False

    def check_replies(self, crm) -> list:
        """
        Scansiona WhatsApp Web alla ricerca di risposte. 
        Meccanismo sicuro: Cerca solo i numeri presenti nel CRM tramite la barra di ricerca,
        evitando di cliccare su chat personali casuali.
        """
        replies = []
        print("📱 [WA SCANNER] Controllo risposte su WhatsApp (Modalità Sicura)...")
        if not os.path.exists(self.session_dir):
            print("❌ ERRORE: Sessione non trovata.")
            return replies
            
        wa_leads = {k: v for k, v in crm.db.get("outreach_leads", {}).items() if v.get("channel") == "whatsapp"}
        if not wa_leads:
            print("  └ Nessun lead WhatsApp nel CRM.")
            return replies

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch_persistent_context(
                    user_data_dir=self.session_dir,
                    headless=False,
                    args=["--headless=new"],
                    viewport={'width': 1280, 'height': 800},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
                )
                page = browser.pages[0]
                page.goto("https://web.whatsapp.com/", timeout=60000)
                
                # Attendiamo che la barra laterale (lista chat) sia completamente caricata
                page.wait_for_selector('#pane-side', timeout=60000)
                time.sleep(5)
                
                for identifier, data in wa_leads.items():
                    phone = data.get("phone", "")
                    if not phone: continue
                    phone_norm = phone.strip().replace("+", "").replace(" ", "")
                    
                    search_box = page.locator('div[contenteditable="true"]').first
                    search_box.fill(phone_norm)
                    time.sleep(2)
                    page.keyboard.press("Enter")
                    time.sleep(3)
                    
                    try:
                        # In WhatsApp Web, incoming messages usually have 'message-in' class.
                        # Since classes can be minified, we try to grab the last message row.
                        # Wait a bit for chat to load
                        time.sleep(2)
                        # Troviamo l'ultimo messaggio ricevuto
                        msg_in = page.locator('div.message-in').last
                        if msg_in.is_visible():
                            last_msg_text = msg_in.inner_text().strip()
                            # Spesso il testo contiene l'orario in fondo, prendiamo solo la prima riga
                            last_msg_text = last_msg_text.split('\n')[0]
                            
                            history = data.get("history", [])
                            last_crm_client_msg = next((m["content"] for m in reversed(history) if m["role"] == "client"), None)
                            
                            if last_msg_text and last_msg_text != last_crm_client_msg:
                                print(f"  └ 💬 Nuova risposta da {phone}!")
                                replies.append({
                                    "identifier": identifier,
                                    "lead_data": data,
                                    "content": last_msg_text,
                                    "channel": "whatsapp"
                                })
                    except Exception as e:
                        pass
                        
                    try:
                        # Pulisci la ricerca in modo robusto
                        search_box.fill("")
                        for _ in range(5):
                            page.keyboard.press("Backspace")
                        page.locator('button[aria-label="Annulla ricerca"], button[aria-label="Chiudi chat"]').click(timeout=1000)
                    except Exception:
                        pass
                    
                    time.sleep(1)
                
                browser.close()
        except Exception as e:
            print(f"❌ Errore WA Scanner: {e}")
            
        return replies
