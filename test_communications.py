import os
import sys

# Assicuriamoci di poter importare dai nostri moduli
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from remote_job_hunter.gmail_sender import GmailSender
from remote_job_hunter.telegram_notifier import TelegramNotifier

def test_telegram():
    print("Testing Telegram...")
    config = {
        "telegram_settings": {
            "enabled": True,
            "bot_token": os.environ.get("TELEGRAM_BOT_TOKEN"),
            "chat_id": os.environ.get("TELEGRAM_CHAT_ID")
        }
    }
    
    # Inizializziamo il notifier
    notifier = TelegramNotifier(config)
    
    if notifier.is_configured:
        # Usiamo il metodo _send_message per un test semplice
        import requests
        url = f"https://api.telegram.org/bot{notifier._bot_token}/sendMessage"
        payload = {
            "chat_id": notifier._chat_id,
            "text": "🚀 *Test LazyJobHunter*\n\nQuesto è un messaggio di test per verificare che le notifiche arrivino correttamente!",
            "parse_mode": "Markdown"
        }
        resp = requests.post(url, json=payload)
        if resp.status_code == 200:
            print("✅ Messaggio Telegram inviato con successo!")
        else:
            print(f"❌ Errore Telegram: {resp.text}")
    else:
        print("❌ TelegramNotifier non è configurato correttamente (mancano le credenziali).")

def test_email():
    print("\nTesting Email (SMTP via App Password)...")
    sender = GmailSender()
    
    my_email = os.environ.get("GMAIL_ADDRESS")
    if not my_email:
        print("❌ GMAIL_ADDRESS non trovato nel file .env")
        return

    subject = "🤖 LazyJobHunter - Test Invio Email"
    body = "Ciao!\n\nSe stai leggendo questa email, significa che il sistema SMTP con Password per le App funziona perfettamente.\n\nIl cacciatore di lavori è pronto a sparare le email in automatico per te.\n\nBuon lavoro!"
    
    # Invia a se stesso per il test
    success = sender.send_email(to_email=my_email, subject=subject, body=body)
    
    if success:
        print("✅ Email inviata con successo alla tua casella!")
    else:
        print("❌ Invio email fallito. Controlla i log per i dettagli.")

if __name__ == "__main__":
    print("--- INIZIO TEST COMUNICAZIONI ---")
    test_telegram()
    test_email()
    print("--- FINE TEST ---")
