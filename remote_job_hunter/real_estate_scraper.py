import time
import random
from playwright.sync_api import sync_playwright
from remote_job_hunter.crm_manager import CRMManager
from remote_job_hunter.ai_council import AICouncil
from remote_job_hunter.email_scraper import EmailScraper
from remote_job_hunter.whatsapp_sender import WhatsAppSender
from remote_job_hunter.gmail_sender import GmailSender

class RealEstateScraper:
    """
    Scraper Playwright per portali immobiliari (Immobiliare.it, Idealista, Airbnb).
    Per ogni annuncio:
    1. Apre la pagina del singolo annuncio
    2. Estrae TUTTE le foto dalla galleria
    3. Le passa a Llava (Vision AI) per giudizio qualità
    4. Se le foto sono scadenti, estrae i contatti (email/telefono/nome agenzia)
    5. Genera il pitch personalizzato con il CMO
    6. Salva nel CRM ed invia via WhatsApp o Email
    """
    
    MAX_LISTINGS_PER_CYCLE = 8  # Non esageriamo per evitare blocchi

    def __init__(self, crm: CRMManager, ai: AICouncil, config=None):
        self.crm = crm
        self.ai = ai
        self.email_scraper = EmailScraper()
        self.wa_sender = WhatsAppSender()
        self.gmail_sender = GmailSender(config or {})

    def run_campaign(self, city: str = "roma-provincia", portal: str = "immobiliare"):
        print(f"🏠 [REAL ESTATE SNIPER] Avvio campagna su {portal} ({city})...")
        
        configs = {
            "immobiliare": {
                "url": f"https://www.immobiliare.it/vendita-case/{city}/?criterio=rilevanza",
                "listing_cards": "a[class*='in-card']",
                "image_selector": "img.nd-figure__image, img[class*='swiper-lazy']",
                "agency_selector": ".in-realEstateAgency__title, .in-realEstateAgency__name",
                "phone_selector": "a[href^='tel:']",
            },
            "idealista": {
                "url": f"https://www.idealista.it/vendita-case/{city}/",
                "listing_cards": "article.item a.item-link",
                "image_selector": ".picture-image, img[data-src]",
                "agency_selector": ".about-advertiser-name",
                "phone_selector": "a[href^='tel:']",
            },
            "airbnb": {
                "url": f"https://www.airbnb.it/s/{city}/homes",
                "listing_cards": "a[aria-label][href*='/rooms/']",
                "image_selector": "img[data-original-uri], picture img",
                "agency_selector": "h2, .t1jojoys",
                "phone_selector": "",
            },
        }
        
        if portal not in configs:
            print(f"❌ Portale '{portal}' non supportato.")
            return
            
        cfg = configs[portal]
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 900}
            )
            page = context.new_page()
            
            try:
                page.goto(cfg["url"], timeout=45000)
                time.sleep(4)
                
                # Accetta cookie se compaiono
                for btn_text in ["Accetta tutto", "Accetta", "Accept all", "OK"]:
                    try:
                        page.locator(f"button:has-text('{btn_text}')").first.click(timeout=2000)
                        time.sleep(1)
                        break
                    except:
                        pass

                # Raccogli tutti i link degli annunci dalla pagina di ricerca
                listing_links = []
                cards = page.locator(cfg["listing_cards"]).all()
                for card in cards[:self.MAX_LISTINGS_PER_CYCLE]:
                    href = card.get_attribute("href")
                    if href:
                        if not href.startswith("http"):
                            base = "https://www.immobiliare.it" if portal == "immobiliare" else \
                                   "https://www.idealista.it" if portal == "idealista" else \
                                   "https://www.airbnb.it"
                            href = base + href
                        listing_links.append(href)
                
                print(f"📋 Trovati {len(listing_links)} annunci. Analizzo uno per uno...")
                
                for link in listing_links:
                    self._process_listing(page, link, cfg, portal)
                    # Delay anti-ban randomizzato
                    time.sleep(random.uniform(8, 15))
                    
            except Exception as e:
                print(f"❌ Errore durante la campagna {portal}: {e}")
            finally:
                browser.close()

    def _process_listing(self, page, url: str, cfg: dict, portal: str):
        """Analizza un singolo annuncio."""
        try:
            print(f"\n  🔗 Apro annuncio: {url}")
            page.goto(url, timeout=30000)
            time.sleep(3)
            
            # --- 1. Estrai titolo annuncio ---
            listing_title = ""
            try:
                listing_title = page.locator("h1").first.inner_text(timeout=3000).strip()
            except:
                listing_title = url.split("/")[-1].replace("-", " ")
            
            # --- 2. Estrai nome agenzia/privato ---
            agency_name = ""
            is_private = True
            try:
                el = page.locator(cfg["agency_selector"]).first
                agency_name = el.inner_text(timeout=2000).strip()
                is_private = "privato" in agency_name.lower() or "proprietario" in agency_name.lower()
            except:
                agency_name = "Inserzionista"
                is_private = True

            # --- 3. Estrai telefono ---
            phone = ""
            if cfg["phone_selector"]:
                try:
                    phone_el = page.locator(cfg["phone_selector"]).first
                    phone = phone_el.get_attribute("href", timeout=2000)
                    if phone:
                        phone = phone.replace("tel:", "").strip()
                except:
                    pass
            
            # --- 4. Controlla deduplicazione CRM ---
            if self.crm.check_agency_exists(agency_name=agency_name, phone=phone):
                print(f"  ⏭️  Già contattato: {agency_name}. Skip.")
                return
            
            # --- 5. Raccogli TUTTE le foto ---
            image_urls = []
            try:
                imgs = page.locator(cfg["image_selector"]).all()
                for img in imgs:
                    src = img.get_attribute("src") or img.get_attribute("data-src") or img.get_attribute("data-original-uri")
                    if src and src.startswith("http") and src not in image_urls:
                        image_urls.append(src)
            except:
                pass
            
            print(f"  📸 Trovate {len(image_urls)} foto per: {agency_name} ({listing_title})")
            
            if not image_urls:
                print("  ⚠️ Nessuna foto trovata, skip.")
                return
            
            # --- 6. Giudizio Llava sulla qualità ---
            are_bad = self.ai.evaluate_image_quality(image_urls)
            
            if not are_bad:
                print(f"  🟢 Foto OK. Questo cliente non ha bisogno di noi.")
                return
            
            print(f"  🔴 Foto scadenti! Genero pitch per {agency_name}...")
            
            # --- 7. Genera pitch personalizzato ---
            agency_size = len(image_urls)  # proxy per dimensione portafoglio
            pitch = self.ai.generate_real_estate_pitch(
                agency_name=agency_name,
                is_private=is_private,
                listing_title=listing_title,
                agency_portfolio_size=agency_size
            )
            
            if not pitch:
                print("  ⚠️ Pitch vuoto, skip.")
                return
            
            identifier = phone if phone else ""
            channel = "whatsapp" if phone else ""
            
            # --- Cerca link mailto: nella pagina (Sempre, come piano B) ---
            email_addr = ""
            try:
                mailto = page.locator("a[href^='mailto:']").first
                if mailto.is_visible(timeout=1000):
                    email_addr = mailto.get_attribute("href", timeout=1500).replace("mailto:", "").split('?')[0].strip()
            except:
                pass
                
            if email_addr and not identifier:
                identifier = email_addr
                channel = "email"
            
            if not identifier:
                print(f"  ⚠️ Nessun contatto per {agency_name}. Skip.")
                return
            
            # --- 8. INVIA il messaggio! ---
            sent = False
            if channel == "whatsapp":
                sent = self.wa_sender.send_message(phone, pitch)
                if not sent and email_addr:
                    print(f"  ⚠️ WhatsApp fallito per {agency_name}. Tento il piano B (Email)...")
                    channel = "email"
                    identifier = email_addr
                    
            if channel == "email" and not sent:
                sent = self.gmail_sender.send_email(
                    to_email=email_addr,
                    subject=f"Le foto del vostro annuncio — {listing_title}",
                    body=pitch,
                    lead_source="RealEstate_Scraper"
                )
            
            # --- 9. Salva nel CRM solo se inviato con successo ---
            if sent:
                self.crm.log_outreach(
                    identifier=identifier,
                    name=agency_name,
                    email=email_addr,
                    phone=phone,
                    channel=channel,
                    initial_pitch=pitch,
                    address=url
                )
            
            status_icon = "✅" if sent else "📋"
            print(f"  {status_icon} Lead {'inviato' if sent else 'salvato (no invio)'}: {agency_name} ({channel})")
            
        except Exception as e:
            print(f"  ❌ Errore su annuncio {url}: {e}")


if __name__ == "__main__":
    crm = CRMManager()
    ai = AICouncil()
    scraper = RealEstateScraper(crm, ai)
    scraper.run_campaign("roma-provincia", "immobiliare")
