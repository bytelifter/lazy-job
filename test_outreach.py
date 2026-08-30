import os
import sys
from main import load_config
from remote_job_hunter.maps_lead_gen import MapsLeadGen
from remote_job_hunter.email_scraper import EmailScraper
from remote_job_hunter.ai_council import AICouncil
from remote_job_hunter.whatsapp_sender import WhatsAppSender
from remote_job_hunter.gmail_sender import GmailSender
from remote_job_hunter.crm_manager import CRMManager

def is_mobile(phone: str) -> bool:
    """Controlla se un numero di telefono italiano è un cellulare."""
    p = phone.strip().replace(" ", "").replace("+", "")
    if p.startswith("39"):
        p = p[2:] # Rimuovi prefisso
    # I cellulari italiani iniziano con 3
    return p.startswith("3")

def test_campaign():
    print("="*60)
    print("🎯 STARTING END-TO-END OUTREACH CAMPAIGN TEST")
    print("="*60)
    
    # 1. Inizializziamo i moduli
    config = load_config()
    crm = CRMManager()
    gmail = GmailSender(config)
    maps = MapsLeadGen(gmail)
    email_scraper = EmailScraper()
    ai = AICouncil()
    wa_sender = WhatsAppSender()
    
    # Parametri campagna
    query = "agenzie immobiliari Roma est"
    service = "soluzioni digitali, software e servizi fotografici"
    my_location = "Roma Est"
    
    # 2. Ricerca su Google Maps
    # Chiediamo fino a 30 risultati, ma ci fermeremo appena ne abbiamo contattati 10 utili
    leads = maps.run_campaign(query, max_results=30)
    
    if not leads:
        print("❌ Nessun lead trovato.")
        return
        
    print(f"\n📊 Trovati {len(leads)} lead da analizzare. Cerco 10 candidati idonei...")
    
    contacted_count = 0
    
    # 3. Processamento
    for lead in leads:
        if contacted_count >= 10:
            print("\n🎯 Raggiunto il target di 10 agenzie contattate! Interrompo la ricerca.")
            break
            
        name = lead.get("name")
        website = lead.get("website")
        phone = lead.get("phone")
        
        print(f"\n🔍 Analisi Lead: {name}")
        
        email = None
        if website:
            email = email_scraper.extract_email(website)
            
        if email:
            print(f"  👉 Email trovata ({email}). Generazione pitch...")
            pitch = ai.generate_outreach_pitch(name, service, my_location)
            print(f"  📝 Pitch Generato:\n{'-'*40}\n{pitch}\n{'-'*40}")
            
            target_email = email
            print(f"  ✉️ Invio email VERA a: {target_email}...")
            
            success = gmail.send_email(
                to_email=target_email, 
                subject=f"Proposta collaborazione - {name}",
                body=pitch
            )
            if success:
                print("  ✅ Email inviata con successo!")
                crm.log_outreach(target_email, name, target_email, phone, "email", pitch)
                contacted_count += 1
                
        elif phone:
            if is_mobile(phone):
                print(f"  👉 Niente email, ma ha un cellulare ({phone}). Generazione pitch per WhatsApp...")
                pitch = ai.generate_outreach_pitch(name, service, my_location)
                print(f"  📝 Pitch Generato:\n{'-'*40}\n{pitch}\n{'-'*40}")
                
                # Pulisci il numero per WhatsApp e aggiungi prefisso +39 se manca
                target_phone = phone.strip().replace(" ", "").replace("+", "")
                if target_phone.startswith("3"):
                    target_phone = "39" + target_phone
                    
                print(f"  💬 Invio WhatsApp VERO a: {target_phone}...")
                
                success = wa_sender.send_message(target_phone, pitch)
                if success:
                    print("  ✅ WhatsApp inviato con successo!")
                    crm.log_outreach(target_phone, name, email, target_phone, "whatsapp", pitch)
                    contacted_count += 1
            else:
                print(f"  🗑️ Niente email e il numero ({phone}) è un FISSO. SCARTATO.")
        else:
            print("  🗑️ Nessun contatto utile trovato. SCARTATO.")
            
    print("\n" + "="*60)
    print(f"🏁 CAMPAGNA TERMINATA. Contattate {contacted_count} su {len(leads)} agenzie trovate.")
    print("="*60)

if __name__ == "__main__":
    test_campaign()
