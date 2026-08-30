import os
import time
from playwright.sync_api import sync_playwright

def authenticate_whatsapp():
    """
    Lancia un'istanza visibile di Chromium per permettere all'utente 
    di scansionare il QR code di WhatsApp Web. Salva la sessione in locale.
    """
    print("🚀 Avvio procedura di Autenticazione WhatsApp...")
    
    # Crea la directory segreta per salvare la sessione
    session_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "secrets", "wa_session")
    os.makedirs(session_dir, exist_ok=True)
    
    with sync_playwright() as p:
        print("  └ 🌐 Apertura browser...")
        # Usa launch_persistent_context per salvare i cookie/localStorage
        browser = p.chromium.launch_persistent_context(
            user_data_dir=session_dir,
            headless=False, # DEVE essere visibile per farti scansionare il QR code
            viewport={'width': 1280, 'height': 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        )
        
        page = browser.pages[0]
        page.goto("https://web.whatsapp.com/")
        
        print("\n" + "="*50)
        print("📱 AZIONE RICHIESTA: SCANSIONA IL QR CODE")
        print("1. Apri WhatsApp sul tuo telefono.")
        print("2. Vai su Impostazioni -> Dispositivi collegati.")
        print("3. Inquadra il QR code sullo schermo.")
        print("="*50 + "\n")
        
        print("In attesa del login...")
        
        try:
            # Chiediamo all'utente di premere invio quando ha finito, è il modo più infallibile.
            input("\n👉 PREMI INVIO QUI NEL TERMINALE *SOLO DOPO* CHE HAI SCANSIONATO IL QR CODE E VEDI LE TUE CHAT... ")
            print("✅ Login confermato dall'utente!")
            time.sleep(3) # Pausa extra per assicurarsi che i cookie vengano scritti
        except Exception as e:
            print(f"❌ Errore durante l'attesa: {e}")
        
        print("🔒 Chiusura browser e salvataggio sessione...")
        try:
            browser.close()
        except Exception:
            pass
        
if __name__ == "__main__":
    authenticate_whatsapp()
