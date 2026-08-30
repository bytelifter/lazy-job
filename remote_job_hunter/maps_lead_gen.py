import time
import json
import os
import random
import re
import requests
from playwright.sync_api import sync_playwright
from remote_job_hunter.email_scraper import EmailScraper
from remote_job_hunter.whatsapp_sender import WhatsAppSender
from remote_job_hunter.gmail_sender import GmailSender
from remote_job_hunter.website_analyzer import WebsiteAnalyzer
from remote_job_hunter.demo_generator import DemoGenerator

class MapsLeadGen:
    """
    Motore di lead generation su Google Maps.
    Strategia DUALE:
      PRIMARIO  — Google Places API (veloce, pulita, affidabile)
      FALLBACK  — Playwright scraper (se API key assente o quota esaurita)
    
    Alterna tra LOCAL_NICHES (Roma, fotografia) e GLOBAL_NICHES (mondo, software).
    Per ogni lead: CRM dedup → analisi sito → competitor → pitch CMO → invio.
    """
    
    MAX_LEADS_PER_CYCLE = 5  # Quante attività analizzare per ciclo

    def __init__(self, crm, ai, config=None):
        self.crm = crm
        self.ai = ai
        self.email_scraper = EmailScraper()
        self.wa_sender = WhatsAppSender()
        self.gmail_sender = GmailSender(config or {})
        self.analyzer = WebsiteAnalyzer()
        self.demo_gen = DemoGenerator()
        self.state_file = "maps_state.json"
        
        self.LOCAL_NICHES = [
            "Agenzie Immobiliari", 
            "Bed and Breakfast", 
            "Hotel", 
            "Case Vacanze",
            "Architetti", 
            "Interior Designer", 
            "Costruttori Edili"
        ]
        
        self.GLOBAL_NICHES = [
            "Forni e Pasticcerie", "Palestre", "Ristoranti", "Centri Estetici", 
            "Studi Medici", "Avvocati", "Commercialisti", "Autosalone",
            "Dentisti", "Parrucchieri", "Idraulici", "Elettricisti",
            "Agenzie di Viaggio", "Negozi di Abbigliamento", "Fiorai",
            "Cliniche Veterinarie", "Scuole di Lingue", "Autoscuole"
        ]
        
        self.ITALIAN_LOCATIONS = [
            "Roma, Italia", "Milano, Italia", "Torino, Italia", 
            "Napoli, Italia", "Bologna, Italia", "Firenze, Italia",
            "Venezia, Italia", "Verona, Italia", "Bari, Italia"
        ]
        
        self.GLOBAL_LOCATIONS = [
            "London, UK", "New York, USA", "Los Angeles, USA", "Miami, USA",
            "Berlin, Germany", "Munich, Germany", "Zurich, Switzerland",
            "Dubai, UAE", "Sydney, Australia", "Toronto, Canada"
        ]
        
        self._load_state()

    def _load_state(self):
        if os.path.exists(self.state_file):
            with open(self.state_file, "r", encoding="utf-8") as f:
                self.state = json.load(f)
        else:
            self.state = {
                "last_local_niche_idx": 0,
                "last_local_location_idx": 0,
                "last_global_niche_idx": 0,
                "last_global_location_idx": 0
            }

    def _save_state(self):
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=4)

    def run_campaign(self):
        print("🗺️ [MAPS SNIPER] Avvio rotazione nicchie su Google Maps...")
        
        is_local = (int(time.time()) % 2) == 0
        
        if is_local:
            niche = self.LOCAL_NICHES[self.state["last_local_niche_idx"]]
            location = self.ITALIAN_LOCATIONS[self.state.get("last_local_location_idx", 0)]
            print(f"🇮🇹 Modalità: ITALIA (Software & Web) — {niche} in {location}")
            
            self.state["last_local_location_idx"] = self.state.get("last_local_location_idx", 0) + 1
            if self.state["last_local_location_idx"] >= len(self.ITALIAN_LOCATIONS):
                self.state["last_local_location_idx"] = 0
                self.state["last_local_niche_idx"] = (self.state["last_local_niche_idx"] + 1) % len(self.LOCAL_NICHES)
        else:
            niche = self.GLOBAL_NICHES[self.state["last_global_niche_idx"]]
            location = self.GLOBAL_LOCATIONS[self.state["last_global_location_idx"]]
            print(f"🌍 Modalità: GLOBALE (Software & Web) — {niche} in {location}")
            self.state["last_global_location_idx"] += 1
            if self.state["last_global_location_idx"] >= len(self.GLOBAL_LOCATIONS):
                self.state["last_global_location_idx"] = 0
                self.state["last_global_niche_idx"] = (self.state["last_global_niche_idx"] + 1) % len(self.GLOBAL_NICHES)
        
        self._save_state()
        
        # ── Tenta prima via API, poi via Playwright ──────────────────────────
        api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "")
        if api_key:
            print("⚡ [PRIMARIO] Uso Google Places API (veloce e pulita)...")
            businesses = self._fetch_via_places_api(niche, location, api_key)
            if businesses:
                self._process_leads(businesses, niche, location, is_local)
                return
            print("⚠️ Places API senza risultati o quota esaurita. Attivo Playwright fallback...")
        else:
            print("ℹ️ GOOGLE_MAPS_API_KEY non trovata. Uso Playwright scraper...")
        
        self._scrape_maps(niche, location, is_local)

    def _fetch_via_places_api(self, niche: str, location: str, api_key: str) -> list:
        """
        Usa la Google Places API (New) per recuperare
        nome, telefono e sito web di ogni business in una SINGOLA chiamata.
        Molto più veloce e meno costosa della vecchia API (Text Search + Details).
        Ritorna una lista di dict con i dati grezzi.
        """
        query = f"{niche} in {location}"
        url = "https://places.googleapis.com/v1/places:searchText"
        
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": "places.displayName.text,places.formattedAddress,places.nationalPhoneNumber,places.websiteUri"
        }
        
        payload = {
            "textQuery": query,
            "languageCode": "it"
        }
        
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=15)
            data = resp.json()
            
            # Se la chiave non è valida o c'è un errore API
            if "error" in data:
                print(f"  └ ⚠️ Places API (New) error: {data['error'].get('message')}")
                return []
                
            places = data.get("places", [])
            print(f"  └ 📋 Places API (New): trovati {len(places)} business per '{query}'")
            
            businesses = []
            for place in places[:self.MAX_LEADS_PER_CYCLE]:
                name = place.get("displayName", {}).get("text", "")
                if not name:
                    continue
                    
                phone = place.get("nationalPhoneNumber", "")
                website = place.get("websiteUri", "")
                address = place.get("formattedAddress", "")
                
                businesses.append({
                    "name": name,
                    "phone": phone,
                    "website": website,
                    "address": address,
                })
                print(f"  └ 🎯 [{len(businesses)}] {name} | Tel: {phone or 'N/A'} | Sito: {website or 'N/A'}")
            
            return businesses
            
        except Exception as e:
            print(f"  └ ❌ Errore Places API (New): {e}")
            return []

    def _process_leads(self, businesses: list, niche: str, location: str, is_local: bool):
        """Processa una lista di business (da API o Playwright) attraverso la pipeline completa."""
        leads_processed = 0
        for biz in businesses:
            business_name = biz.get("name", "")
            phone = biz.get("phone", "")
            website = biz.get("website", "")
            
            if not business_name:
                continue
            
            if self.crm.check_agency_exists(agency_name=business_name, phone=phone):
                print(f"  ⏭️  Già nel CRM: {business_name}. Skip.")
                continue
            
            # Analisi sito (se presente)
            website_critique = ""
            seo_critique = ""
            if website:
                website_critique = self.analyzer.capture_and_analyze(website)
                seo_critique = self.analyzer.analyze_performance(website)
            
            # Competitor (usa Playwright in una finestra separata se necessario)
            competitor_name = ""
            # Nota: competitor search via Playwright richiede browser aperto.
            # Viene eseguita solo durante _scrape_maps. Con API, omettiamo per velocità.
            
            # Demo (link vuoto finché non c'è hosting)
            demo_link = self.demo_gen.generate_mini_site(business_name, niche)
            
            # Pitch CMO
            pitch = self.ai.generate_maps_software_pitch(
                business_name=business_name,
                niche=niche,
                location=location,
                has_website=bool(website),
                website_critique=website_critique,
                seo_critique=seo_critique,
                competitor_name=competitor_name,
                demo_link="" # Il link viene inviato SOLO quando il cliente risponde
            )
            
            if not pitch:
                continue
            
            # Canale di contatto
            email_addr = ""
            if not phone and website:
                email_addr = self.email_scraper.extract_email(website) or ""
            
            if phone:
                channel, identifier = "whatsapp", phone
            elif email_addr:
                channel, identifier = "email", email_addr
            else:
                print(f"  ⚠️ Nessun contatto per {business_name}. Skip.")
                continue
            
            sent = False
            if channel == "whatsapp":
                sent = self.wa_sender.send_message(phone, pitch)
                if not sent and email_addr:
                    print(f"  ⚠️ WhatsApp fallito per {business_name}. Tento il piano B (Email)...")
                    channel = "email"
                    identifier = email_addr
                    
            if channel == "email" and not sent:
                sent = self.gmail_sender.send_email(
                    to_email=email_addr,
                    subject=f"Una proposta per {business_name}",
                    body=pitch,
                    lead_source="Maps_LeadGen"
                )
                
            if sent:
                self.crm.log_outreach(
                    identifier=identifier,
                    name=business_name,
                    email=email_addr,
                    phone=phone or "",
                    channel=channel,
                    initial_pitch=pitch,
                    address=location
                )
            
            leads_processed += 1
            print(f"  {'✅' if sent else '📋'} Lead #{leads_processed}: {business_name} ({channel})")
            time.sleep(random.uniform(3, 7))
        
        print(f"\n🏁 Pipeline API completata. Lead processati: {leads_processed}")

    def _find_top_competitor(self, page, niche: str, location: str, exclude_name: str) -> str:
        """Cerca il miglior competitor per usarlo come leva psicologica nel pitch."""
        try:
            print(f"  🕵️ [SABOTATORE] Cerco competitor per '{exclude_name}'...")
            comp_query = f"best {niche} in {location}"
            page.locator("input#searchboxinput").fill(comp_query)
            page.locator("button#searchbox-searchbutton").click()
            time.sleep(4)
            
            results = page.locator(".fontHeadlineSmall").all()
            for res in results:
                name = res.inner_text().strip()
                if name and name.lower() != exclude_name.lower() and len(name) > 3:
                    print(f"  └ 🎯 Competitor: {name}")
                    return name
            return ""
        except Exception as e:
            print(f"  └ ⚠️ Errore ricerca competitor: {e}")
            return ""

    def _scrape_maps(self, niche: str, location: str, is_local: bool):
        search_query = f"{niche} {location}"
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            
            try:
                print(f"🔍 Cerco '{search_query}' su Google Maps...")
                page.goto("https://www.google.com/maps", timeout=30000)
                time.sleep(2)
                
                # Accetta cookie
                for btn in ["Accetta tutto", "Accept all"]:
                    try:
                        page.locator(f"button:has-text('{btn}')").click(timeout=2000)
                        time.sleep(1)
                        break
                    except:
                        pass
                
                # Esegui ricerca
                page.locator("input#searchboxinput").fill(search_query)
                page.locator("button#searchbox-searchbutton").click()
                time.sleep(5)
                
                # Scroll nella sidebar per caricare risultati
                results_panel = page.locator("div[role='feed']")
                leads_processed = 0
                
                for scroll_attempt in range(4):  # Scorri 4 volte per caricare abbastanza risultati
                    results_panel.evaluate("el => el.scrollBy(0, 800)")
                    time.sleep(2)
                
                # Raccogli tutte le card dei business
                business_cards = page.locator(".fontHeadlineSmall").all()
                print(f"📋 Trovati {len(business_cards)} business. Analizzo i primi {self.MAX_LEADS_PER_CYCLE}...")
                
                for card in business_cards[:self.MAX_LEADS_PER_CYCLE]:
                    if leads_processed >= self.MAX_LEADS_PER_CYCLE:
                        break
                    try:
                        business_name = card.inner_text().strip()
                        if not business_name:
                            continue
                        
                        # Clicca sulla card per aprire il pannello del business
                        card.click()
                        time.sleep(3)
                        
                        # Estrai dati dal pannello laterale
                        phone = self._extract_phone(page)
                        website = self._extract_website(page)
                        
                        print(f"\n  📌 {business_name} | Tel: {phone or 'N/A'} | Sito: {website or 'Nessuno'}")
                        
                        # Deduplicazione CRM
                        if self.crm.check_agency_exists(agency_name=business_name, phone=phone):
                            print(f"  ⏭️  Già nel CRM: {business_name}. Skip.")
                            time.sleep(1)
                            continue
                        
                        # --- Analisi Sito Web (se presente) ---
                        website_critique = ""
                        seo_critique = ""
                        if website:
                            website_critique = self.analyzer.capture_and_analyze(website)
                            seo_critique = self.analyzer.analyze_performance(website)
                        
                        # --- Cerca Competitor (leva psicologica) ---
                        competitor_name = self._find_top_competitor(page, niche, location, business_name)
                        
                        # Torna ai risultati di ricerca originali
                        page.go_back()
                        time.sleep(3)
                        
                        # --- Genera Mini-Sito Demo ---
                        demo_link = self.demo_gen.generate_mini_site(business_name, niche)
                        
                        # --- Genera Pitch CMO ---
                        pitch = self.ai.generate_maps_software_pitch(
                            business_name=business_name,
                            niche=niche,
                            location=location,
                            has_website=bool(website),
                            website_critique=website_critique,
                            seo_critique=seo_critique,
                            competitor_name=competitor_name,
                            demo_link="" # Il link viene inviato SOLO quando il cliente risponde
                        )
                        
                        if not pitch:
                            continue
                        
                        # --- Estrai email dal sito (sempre, come piano B) ---
                        email_addr = ""
                        if website:
                            email_addr = self.email_scraper.extract_email(website) or ""
                        
                        # Determina canale principale
                        if phone:
                            channel = "whatsapp"
                            identifier = phone
                        elif email_addr:
                            channel = "email"
                            identifier = email_addr
                        else:
                            print(f"  ⚠️ Nessun contatto trovato per {business_name}. Skip.")
                            continue
                        
                        # --- INVIA il messaggio! ---
                        sent = False
                        if channel == "whatsapp":
                            sent = self.wa_sender.send_message(phone, pitch)
                            if not sent and email_addr:
                                print(f"  ⚠️ WhatsApp fallito per {business_name}. Tento il piano B (Email)...")
                                channel = "email"
                                identifier = email_addr
                                
                        if channel == "email" and not sent:
                            sent = self.gmail_sender.send_email(
                                to_email=email_addr,
                                subject=f"Una proposta per {business_name}",
                                body=pitch,
                                lead_source="Maps_LeadGen"
                            )
                            
                        # --- Salva nel CRM solo se inviato con successo ---
                        if sent:
                            self.crm.log_outreach(
                                identifier=identifier,
                                name=business_name,
                                email=email_addr,
                                phone=phone or "",
                                channel=channel,
                                initial_pitch=pitch,
                                address=location
                            )
                        
                        leads_processed += 1
                        status_icon = "✅" if sent else "📋"
                        print(f"  {status_icon} Lead #{leads_processed} {'inviato' if sent else 'salvato (invio fallito)'}: {business_name} ({channel})")
                        
                        # Delay anti-ban
                        time.sleep(random.uniform(5, 10))
                        
                    except Exception as e:
                        print(f"  ⚠️ Errore su business card: {e}")
                        try:
                            page.go_back()
                            time.sleep(2)
                        except:
                            pass
                        continue
                        
                print(f"\n🏁 Ciclo Maps completato. Lead trovati: {leads_processed}")
                
            except Exception as e:
                print(f"❌ Errore Maps Sniper: {e}")
            finally:
                browser.close()

    def _extract_phone(self, page) -> str:
        """Estrae il numero di telefono dal pannello laterale di Maps."""
        try:
            # Maps mostra il telefono in un elemento con attributo data-tooltip o aria-label contenente il numero
            phone_selectors = [
                "button[data-tooltip*='+']",
                "button[aria-label*='+']",
                "a[href^='tel:']",
                "[data-item-id*='phone'] span",
            ]
            for sel in phone_selectors:
                try:
                    el = page.locator(sel).first
                    text = el.get_attribute("aria-label") or el.get_attribute("data-tooltip") or el.inner_text()
                    if text:
                        # Pulisci il numero (rimuovi tutto tranne + e cifre)
                        import re
                        match = re.search(r'[\+\d][\d\s\-\(\)]{7,}', text)
                        if match:
                            return re.sub(r'[^\d+]', '', match.group(0))
                except:
                    pass
        except:
            pass
        return ""

    def _extract_website(self, page) -> str:
        """Estrae il link al sito web dal pannello laterale di Maps."""
        try:
            web_selectors = [
                "a[data-item-id='authority']",
                "a[href]:not([href*='google']):not([href*='maps'])[aria-label*='ito']",
                "a[data-tooltip*='http']",
            ]
            for sel in web_selectors:
                try:
                    el = page.locator(sel).first
                    href = el.get_attribute("href")
                    if href and href.startswith("http") and "google" not in href and "maps" not in href:
                        return href
                except:
                    pass
        except:
            pass
        return ""
