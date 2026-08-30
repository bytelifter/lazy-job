import json
import base64
import requests
import time
from typing import Any
import sys
import os

# Add parent directory to path to allow absolute imports if needed
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from remote_job_hunter.micro_llm_army import VirtualCompany

class AICouncil:
    """
    Virtual Company Orchestrator for Gig Evaluation.
    Delegates tasks sequentially to specific department models to respect 6GB VRAM limits.
    """
    
    def __init__(self, ai_writer=None):
        # Instantiate the Virtual Company architecture
        self.company = VirtualCompany()

    def evaluate_opportunity(self, gig_data: dict[str, Any]) -> dict[str, Any]:
        """Runs the gig through the specialized Virtual Company Departments."""
        
        print("\n🏢 [VIRTUAL COMPANY] Convening C-Suite to evaluate new gig opportunity...")
        
        context = f"Title: {gig_data.get('title')}\nBudget: {gig_data.get('budget')}\nDescription: {gig_data.get('description', '')[:1000]}"
        council_results = {}
        
        # 1. LEGAL, COMPLIANCE & SCAM DETECTION (Qwen 2 1.5B)
        res_legal = self.company.call_c_suite_manager(
            "Legal & Compliance Officer",
            "qwen2:1.5b",
            f"Context:\n{context}\n\nTask: Detect scams, impossible budgets, or TOS violations. Reply exactly CLEAN or SCAM, followed by a 1 sentence reason.",
            "You are a strict Legal & Compliance officer. Be ruthless in your risk assessment."
        )
        council_results["legal"] = res_legal
        if "SCAM" in res_legal.upper():
            print(f"🚫 Legal flagged this as SCAM/RISK. Reason: {res_legal}. Skipping.")
            return {"verdict": "REJECT", "reason": res_legal}

        # 2. CTO ARCHITECT (Qwen2.5-Coder 1.5B)
        res_cto = self.company.call_c_suite_manager(
            "CTO",
            "qwen2.5-coder:1.5b",
            f"Context:\n{context}\n\nTask: Propose a purely automated Python architecture for this job. What libraries will we use?",
            "You are the CTO. Provide technical architectures only. Focus on Python and automation."
        )
        council_results["architect"] = res_cto
        
        # 3. CFO (FinBERT on CPU)
        print("  └ 🧠 Waking up CFO (FinBERT on CPU) for Financial Sentiment...")
        res_cfo = self.company.finbert_financial_analysis(context + f"\nProposed Solution: {res_cto}")
        council_results["roi_sentiment"] = res_cfo
        print(f"  └ 💰 CFO Sentiment: {res_cfo}")
        
        # 4. CEO & PROJECT MANAGER (Llama 3.1 8B)
        res_ceo = self.company.call_c_suite_manager(
            "CEO & Final Decision Maker",
            "llama3.1:8b",
            f"Gig Context:\n{context}\n\nCTO Proposal:\n{res_cto}\n\nCFO Sentiment:\n{res_cfo}\n\nTask: Make the final decision. Reply exactly STEAL, BID, or SKIP on the first line. Then provide a 1 sentence strategy on the second line.",
            "You are the CEO. You make ruthless financial decisions based on your team's input."
        )
        
        final_verdict = "SKIP"
        if "STEAL" in res_ceo.upper(): final_verdict = "STEAL"
        elif "BID" in res_ceo.upper(): final_verdict = "BID"
        
        council_results["verdict"] = final_verdict
        council_results["ceo_strategy"] = res_ceo
        print(f"⚖️ Final Verdict from CEO: {final_verdict}")
        
        # Unload all at the end to keep RAM/VRAM pristine while waiting for the next job
        self.company.unload_all()
        
        return council_results

    def generate_outreach_pitch(self, lead_name: str, service: str, my_location: str) -> str:
        """
        Uses Llama 3.1 8B (CEO role) to write a personalized outreach pitch in Italian.
        """
        print(f"\n✍️ [AI WRITER] Scrittura messaggio per {lead_name}...")
        
        prompt = f"""
Sei un professionista freelance esperto in {service}. Vivi a {my_location}.
Devi scrivere un breve messaggio di contatto (cold outreach) per l'azienda/attività "{lead_name}".

Obiettivo:
Cerca di intuire (dal nome o dal tipo di attività) di cosa si occupano e scrivi un messaggio altamente personalizzato proponendo i tuoi servizi di {service}. 
Mostra brevemente come il tuo servizio possa portare valore pratico al loro specifico settore.

Regole:
1. Sii breve, professionale e intelligente (max 3-4 frasi). Non usare mai un tono robotico, da venditore o "da template".
2. Usa un approccio empatico e naturale (es. puoi rivolgerti al team o a chi gestisce l'attività, mantieni un tono formale ma umano).
3. Inizia SEMPRE il messaggio con "Salve," (con la virgola) e poi vai a capo. Non usare altre forme di saluto.
4. Chiedi in modo leggero se sono aperti a fare due chiacchiere o a ricevere un link ai tuoi lavori/portfolio.
5. Non inserire segnaposti ([Nome], ecc.), scrivi il testo già pronto per essere inviato.
6. NON racchiudere MAI il messaggio tra virgolette o apici.
7. Crea messaggi strutturalmente diversi ogni volta.
8. Usa la lingua Italiana.
        """
        
        # We use llama3.1:8b for best Italian language capabilities
        pitch = self.company.call_c_suite_manager(
            "Chief Marketing Officer",
            "llama3.1:8b",
            prompt,
            "Sei un marketer esperto nel cold outreach. Scrivi un messaggio diretto, intelligente e altamente personalizzato in base al tipo di business. Ricordati di iniziare assolutamente con 'Salve,'. Scrivi solo il messaggio finale, senza commenti."
        )
        
        pitch = pitch.strip().strip('"').strip("'")
        
        self.company.unload_all()
        return pitch.strip()

    def generate_real_estate_pitch(self, agency_name: str, is_private: bool, listing_title: str, agency_portfolio_size: int = 0) -> str:
        """
        Genera un messaggio altamente personalizzato per un annuncio specifico in cui 
        la Vision AI ha rilevato foto scadenti.
        """
        target_type = "Privato" if is_private else "Agenzia"
        urgency_note = ""
        if not is_private:
            if agency_portfolio_size > 50:
                urgency_note = "Questa agenzia ha tantissimi immobili in gestione, sottolinea come potresti fargli risparmiare tempo e vendere più in fretta il loro enorme portafoglio."
            else:
                urgency_note = "Questa agenzia ha pochi immobili, sottolinea come potresti aiutarli a dare più valore a quel poco che hanno per massimizzare i profitti."
                
        prompt = f"""
Sei il Chief Marketing Officer (CMO) esperto di Copywriting a freddo per un fotografo di immobili.
Stai scrivendo a: {agency_name} (Tipo: {target_type}).
Hai appena visto il loro annuncio intitolato: "{listing_title}".
Le foto attuali di questo annuncio NON rendono giustizia all'immobile. 
{urgency_note}

Scrivi un messaggio diretto, formale ma non noioso.
Inizia SEMPRE con la parola "Salve," e vai a capo.
Menziona chiaramente di aver visto il loro annuncio "{listing_title}" e che le foto attuali potrebbero essere migliorate per attirare più visite.
Non essere offensivo verso le foto attuali, usa tatto (es. "non rendono piena giustizia al potenziale dell'immobile").
Proponiti per un servizio fotografico per valorizzarlo. Non inserire prezzi.
Includi sempre questo link al tuo portfolio lavori alla fine del messaggio per mostrare la tua qualità: https://drive.google.com/drive/folders/1Ni_YWu5Yh4L72oemM7bnl7gP3cPLuWKk?usp=drive_link
NON USARE MAI le virgolette " " nel messaggio.
"""
        print(f"\n✍️ [CMO - REAL ESTATE] Scrittura messaggio per annuncio: {listing_title} ({agency_name})...")
        pitch = self.company.call_c_suite_manager(
            "Chief Marketing Officer",
            "llama3.1:8b",
            prompt,
            "Sei il CMO. Restituisci SOLO il testo finale del messaggio da inviare."
        )
        pitch = pitch.strip().strip('"').strip("'")
        self.company.unload_all()
        return pitch.strip()

    def generate_maps_software_pitch(self, business_name: str, niche: str, location: str, has_website: bool, website_critique: str = "", seo_critique: str = "", competitor_name: str = "", demo_link: str = "") -> str:
        """
        Genera un messaggio per le attività fisiche scansionate da Maps.
        L'obiettivo è vendere un ecosistema digitale in abbonamento (siti web, gestionali, automazioni).
        """
        demo_note = f"\n\nHo già preparato una bozza gratuita di come potrebbe essere il vostro nuovo ecosistema, dategli un'occhiata qui: {demo_link}" if demo_link else ""
        comp_note = f"\nTra l'altro, ho notato che i vostri concorrenti in zona (come {competitor_name}) hanno già un sistema online ben ottimizzato e vi stanno togliendo potenziale clientela." if competitor_name else ""
        
        if has_website:
            critique_note = f"Ho appena visitato il vostro sito web. {website_critique} {seo_critique}" if website_critique else f"Ho visitato il vostro sito web ma ho notato che manca un sistema gestionale integrato per ordini/prenotazioni. {seo_critique}"
            pitch_goal = "Proponi un restyling estetico e l'aggiunta di un gestionale cloud con abbonamento mensile di manutenzione per sbloccare più fatturato online."
        else:
            critique_note = "Cercando su Google Maps ho notato che non avete un sito web o una piattaforma per ricevere ordini o prenotazioni online."
            pitch_goal = "Fagli capire che stanno perdendo un sacco di clienti. Proponi la creazione di un ecosistema digitale completo e un piccolo canone mensile per mantenerlo aggiornato."

        prompt = f"""
Sei il Chief Marketing Officer (CMO) di un'agenzia Software e Digitale di alto livello.
Stai scrivendo a: {business_name} (Nicchia: {niche}, in zona {location}).
{critique_note}
{comp_note}

Il tuo obiettivo: {pitch_goal}
Scrivi un messaggio diretto, formale ma non noioso.
Inizia SEMPRE con la parola "Salve," e vai a capo.
Spiega brevemente chi sei, evidenzia il problema tecnico o estetico, sfrutta la leva della concorrenza (se presente) 
e proponiti per mostrare loro una soluzione senza impegno.{demo_note}
NON inserire prezzi esatti, ma fai capire che è una soluzione in abbonamento gestita interamente da noi, togliendo a loro ogni stress tecnico.
NON USARE MAI le virgolette " " nel messaggio.
"""
        print(f"\n✍️ [CMO - SOFTWARE] Scrittura messaggio per: {business_name} ({niche})...")
        pitch = self.company.call_c_suite_manager(
            "Chief Marketing Officer",
            "llama3.1:8b",
            prompt,
            "Sei il CMO. Restituisci SOLO il testo finale del messaggio da inviare."
        )
        pitch = pitch.strip().strip('"').strip("'")
        self.company.unload_all()
        return pitch.strip()

    def generate_auto_reply(self, lead_data: dict, incoming_msg: str) -> str:
        """
        Il COO (Chief Operating Officer) analizza la risposta del cliente e genera la replica.
        """
        print(f"\n🧠 [COO] Analisi messaggio in entrata da {lead_data.get('name')}...")
        
        history_text = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in lead_data.get('history', [])])
        
        prompt = f"""
Sei l'AI Manager (COO) di un'agenzia ibrida (Software e Fotografia). Abbiamo contattato "{lead_data.get('name')}".
Ecco la cronologia della conversazione:
{history_text}

Il cliente ha appena risposto questo:
CLIENT: "{incoming_msg}"

Scrivi la TUA RISPOSTA in base a queste regole ferree:
1. Se il cliente NON è interessato (es. "No grazie", "Non ci serve"), rispondi ESATTAMENTE con la parola "IGNORE". Non scrivere nient'altro.
2. Se il cliente chiede il PREZZO per SERVIZI FOTOGRAFICI (o immobiliari), invia un listino dettagliato basato sulla tipologia dell'immobile, usando QUESTI PREZZI:
   - Monolocale: 120€
   - Bilocale: 150€
   - Trilocale: 180€
   - Quadrilocale o superiore: da 220€ (su preventivo)
   - Extra Spazi Esterni (Giardino, grande terrazza, piscina): +30€
   - Virtual Staging: +50€ a stanza
   - Video Tour Immobiliare: +250€
   (IMPORTANTE: Specifica che NON si effettuano riprese con il Drone). Chiedi poi che tipologia di immobili trattano maggiormente per capire come aiutarli.
3. Se il cliente chiede un PREZZO per SOFTWARE, SITI WEB o GESTIONALI, il prezzo è variabile. Proponi una breve chiamata di 5 minuti per capire i dettagli e fargli un preventivo su misura.
4. Se chiedono il PORTFOLIO FOTOGRAFICO, rispondi includendo questo link: https://drive.google.com/drive/folders/1Ni_YWu5Yh4L72oemM7bnl7gP3cPLuWKk?usp=drive_link
5. DEMO RICHIESTA: Se il cliente chiede di vedere la demo software (es. "Sì mostramela", "Vorrei vederla"), includi nel messaggio ESATTAMENTE il testo [DEMO_LINK]. Spiega che per motivi di gestione interna dei nostri server di test, il link rimarrà attivo solo per 12 ore e poi verrà disattivato per liberare spazio. Aggiungi che se non riescono a vederla in tempo, basta scriverti e la riattiverai.
6. DEMO VISTA/INTERESSATI: Se il cliente dice di aver visto la demo ed è interessato, spiegagli che hai disattivato il link per liberare spazio nei server di gestione interna. Digli che se vogliono rivederla puoi riattivarlo in 1 minuto, altrimenti proponi direttamente una chiamata per organizzarvi.
7. Sii professionale, empatico e vai dritto al sodo (max 3-4 frasi).
8. NON usare virgolette. NON inserire commenti. Scrivi direttamente il messaggio.
"""
        
        reply = self.company.call_c_suite_manager(
            "Chief Operating Officer",
            "llama3.1:8b",
            prompt,
            "Sei il COO. Scrivi solo il testo finale della risposta al cliente in italiano."
        )
        
        reply = reply.strip().strip('"').strip("'")
        self.company.unload_all()
        return reply

    def evaluate_image_quality(self, image_urls: list) -> bool:
        """
        Usa il modello llava:7b per analizzare un set di immagini (fino a 3) e capire se sono
        di scarsa qualità / amatoriali. 
        Ritorna True se le immagini sono "Meh" (scarse), False se sono buone.
        """
        if not image_urls:
            return False
            
        print(f"👁️ [VISION AI] Analisi qualità di {len(image_urls)} immagini...")
        try:
            images_b64 = []
            for url in image_urls: # Elabora TUTTE le foto, senza limite
                resp = requests.get(url, timeout=10)
                if resp.status_code == 200:
                    img_b64 = base64.b64encode(resp.content).decode("utf-8")
                    images_b64.append(img_b64)
            
            if not images_b64:
                return False
                
            payload = {
                "model": "llava:7b",
                "prompt": "You are a professional real estate photographer. Look at these real estate photos from a single listing. Do they look like amateur photos taken with a smartphone (bad lighting, crooked angles, messy rooms, low quality)? Answer ONLY with 'YES' if they are amateur/bad overall, or 'NO' if they are high quality and professional.",
                "images": images_b64,
                "stream": False
            }
            
            # Aumentato il timeout a 300 secondi (5 minuti) per supportare l'analisi di 50+ foto
            res = requests.post("http://localhost:11434/api/generate", json=payload, timeout=300)
            if res.status_code == 200:
                response_text = res.json().get("response", "").strip().upper()
                if "YES" in response_text:
                    print("  └ 🔴 Giudizio AI: FOTO SCADENTI (Meh)")
                    return True
                else:
                    print("  └ 🟢 Giudizio AI: Foto OK / Professionali")
                    return False
        except Exception as e:
            print(f"  └ ⚠️ Errore durante l'analisi visiva: {e}")
            
        return False

