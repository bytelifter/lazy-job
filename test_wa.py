import os
import sys

# Assicuriamoci di poter importare dai nostri moduli
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from remote_job_hunter.whatsapp_sender import WhatsAppSender

if __name__ == "__main__":
    print("--- INIZIO TEST WHATSAPP ---")
    sender = WhatsAppSender()
    # Il numero viene formattato in automatico con +39 dal nostro sender
    sender.send_message("3899243631", "Ciao! Questo è un messaggio di test automatico dal tuo fido LazyJobHunter. Se lo stai leggendo dal profilo giusto, l'automazione funziona!")
    print("--- FINE TEST WHATSAPP ---")
