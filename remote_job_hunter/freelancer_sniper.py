import json
import os
import time
import random
from typing import Any, Dict

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    pass

class FreelancerSniper:
    """
    Ingests projects from Freelancer.com via public feeds and uses Playwright
    to automatically bid on projects marked as 'STEAL' by the AI Council.
    Includes anti-bot stochastic delays and human-like typing simulation.
    """
    
    def __init__(self, ai_writer, ai_council, telegram=None, config_path="config.local.json"):
        self.ai = ai_writer
        self.council = ai_council
        self.telegram = telegram
        self.config_path = config_path
        self._load_config()
        
    def _load_config(self):
        try:
            from dotenv import load_dotenv
            load_dotenv()
            self.email = os.environ.get("FREELANCER_EMAIL", "")
            self.password = os.environ.get("FREELANCER_PASSWORD", "")
        except Exception:
            self.email = ""
            self.password = ""
            
    def simulate_human_delay(self, min_s=1.0, max_s=3.0):
        """Gaussian-like random delay to bypass basic anti-bot heuristics."""
        delay = random.uniform(min_s, max_s)
        time.sleep(delay)
        
    def auto_apply(self, gig_url: str, proposal_text: str, bid_amount: str, delivery_time: str) -> bool:
        """
        Uses Playwright to navigate to Freelancer.com, log in if needed, 
        and submit the proposal automatically (STEAL mode).
        """
        if not self.email or not self.password:
            print("⚠️ Freelancer Auto-Apply skipped: No credentials in config.local.json")
            return False
            
        print(f"🤖 [STEAL MODE] Initiating Playwright auto-apply for {gig_url}...")
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True) # Run headless to save RAM
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
                page = context.new_page()
                
                # Load state if exists (to avoid constant logins)
                state_file = "secrets/freelancer_state.json"
                import os
                if os.path.exists(state_file):
                    context.add_cookies(json.load(open(state_file)))
                
                page.goto(gig_url)
                self.simulate_human_delay(2, 5)
                
                # Check if we need to login
                if page.locator("text=Log In").is_visible():
                    print("  └ Logging in...")
                    # Clicchiamo e aspettiamo che carichi la nuova pagina di login
                    page.click("text=Log In")
                    page.wait_for_url("**/login**", timeout=45000)
                    self.simulate_human_delay(3, 6)
                    
                    # Compiliamo i campi (con i nuovi selettori)
                    page.wait_for_selector('#emailOrUsernameInput', timeout=30000)
                    page.fill('#emailOrUsernameInput', self.email)
                    self.simulate_human_delay(2, 4)
                    page.fill('#passwordInput', self.password)
                    
                    # Spuntiamo "Remember me"
                    try:
                        page.locator("text=Remember me").click(timeout=5000)
                        self.simulate_human_delay(1, 2)
                    except Exception:
                        pass
                        
                    # Tentiamo di cliccare "I'm not a robot" (reCAPTCHA)
                    try:
                        print("  └ Tentativo di click su reCAPTCHA...")
                        page.frame_locator('iframe[src*="recaptcha"]').locator('.recaptcha-checkbox-border').click(timeout=10000)
                        self.simulate_human_delay(4, 7)
                    except Exception as e:
                        print(f"  └ ⚠️ Impossibile cliccare reCAPTCHA: {e}")
                    
                    # Clicchiamo il tasto di Log in e aspettiamo di tornare alla pagina del progetto
                    page.click('button:has-text("Log in")')
                    print("  └ Waiting for redirect back to project page...")
                    try:
                        page.wait_for_url("**/projects/**", timeout=60000)
                    except Exception as e:
                        print("  └ ⚠️ Timeout durante il redirect. Salvataggio screenshot (debug_login.png)...")
                        page.screenshot(path="debug_login.png")
                        raise e
                    self.simulate_human_delay(4, 7)
                    
                    # Save cookies to avoid future logins
                    cookies = context.cookies()
                    with open(state_file, "w") as f:
                        json.dump(cookies, f)
                
                # Scroll to bottom to trigger lazy loading
                for _ in range(3):
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    page.wait_for_timeout(1000)
                    
                # Find the bid box
                bid_box = page.locator('textarea')
                
                try:
                    bid_box.wait_for(state="visible", timeout=10000)
                except Exception:
                    print("⚠️ Bid box not found or project closed. Salvo HTML e screenshot di debug...")
                    try:
                        page.screenshot(path="debug_bidbox.png")
                        with open("debug_bidbox.html", "w", encoding="utf-8") as f:
                            f.write(page.content())
                    except Exception:
                        pass
                    browser.close()
                    return False

                if bid_box.is_visible():
                    print("  └ Typing proposal (simulating human typing...)")
                    # Type slowly
                    import random
                    bid_box.type(proposal_text, delay=random.randint(10, 50))
                    
                    # Fill bid amount
                    amount_input = page.locator('input[name="bidAmount"]')
                    if amount_input.is_visible():
                        amount_input.fill(str(bid_amount))
                        
                    # Submit
                    page.click('button:has-text("Place Bid")') 
                    self.simulate_human_delay(2, 4)
                    print(f"✅ [SUCCESS] Proposal placed for {bid_amount}!")
                    browser.close()
                    return True
                else:
                    print("⚠️ Bid box non visibile.")
                    browser.close()
                    return False
                    
        except Exception as e:
            print(f"❌ Playwright Error during Auto-Apply: {e}")
            return False

    def run_campaign(self, verbose_test=False):
        """
        Scarica gli ultimi progetti dal feed RSS di Freelancer.com,
        li fa valutare al CFO/CTO, e per quelli con punteggio alto,
        effettua il bidding in automatico.
        """
        print("🎯 [FREELANCER SNIPER] Avvio campagna di ricerca Gigs...")
        import feedparser
        
        # Puoi personalizzare le keyword dell'RSS url se serve
        rss_url = "https://www.freelancer.com/rss.xml"
        feed = feedparser.parse(rss_url)
        
        if not feed.entries:
            print("  └ Nessun progetto trovato nel feed RSS.")
            return

        print(f"  └ Trovati {len(feed.entries)} progetti recenti. Analisi in corso...")
        
        for entry in feed.entries[:300]:
            title = entry.get("title", "")
            link = entry.get("link", "")
            summary = entry.get("summary", "")
            
            # Stampa cosa vede il cecchino a terminale solo se in modalità test verbosa
            if verbose_test:
                print(f"\n👀 [VISIONE CECCHINO] Analisi Progetto:")
                print(f"  Titolo: {title}")
                print(f"  Descrizione (estratto): {summary[:300]}...")
            
            # Estrazione e filtro Budget ($300 minimo)
            import re
            budget_str = ""
            max_budget = 0
            match = re.search(r'Budget:([^,]+)', summary)
            if match:
                budget_str = match.group(1).strip()
                nums = [float(x.replace(',', '')) for x in re.findall(r'\d+(?:,\d+)*', budget_str)]
                max_budget = max(nums) if nums else 0
                if 'INR' in budget_str or '₹' in budget_str: max_budget /= 80
                elif 'GBP' in budget_str or '£' in budget_str: max_budget *= 1.2
                elif 'EUR' in budget_str or '€' in budget_str: max_budget *= 1.1
                elif 'AUD' in budget_str or 'CAD' in budget_str: max_budget *= 0.7
                
                if max_budget > 0 and max_budget < 300:
                    if verbose_test: print(f"  └ ⏭️ Scartato: Budget troppo basso (~${max_budget:.0f} USD)")
                    continue

            # Valutazione ultra-veloce con modello pesante (7b)
            # Chiediamo al CEO se vale la pena fare una bid (STEAL)
            prompt = f"Analizza questo progetto e decidi se fare una bid. Titolo: {title}. Rispondi con 'STEAL' o 'IGNORE'."
            decision = self.council.company.call_c_suite_manager("CEO", "qwen2.5:7b", prompt, "Sei un CEO spietato. Rispondi solo STEAL o IGNORE.")
            
            if "STEAL" in decision.upper():
                print(f"  └ 🎯 MATCH TROVATO (Decisione: STEAL)")
                
                # Generiamo la proposal con l'AI Writer in modo super-dettagliato
                candidate = {}
                try:
                    import json
                    if os.path.exists(self.config_path):
                        candidate = json.load(open(self.config_path)).get("candidate_profile", {})
                except Exception:
                    pass
                
                council_data = {
                    "specialist": "I have thoroughly analyzed the requirements and I am fully equipped to deliver a scalable, robust solution.",
                    "pricing": f"My bid is perfectly aligned with your posted budget ({budget_str})",
                    "timeline": "I can deliver a complete production-ready version within a few days"
                }
                
                proposal = ""
                if hasattr(self.ai, 'generate_unique_proposal'):
                    proposal = self.ai.generate_unique_proposal(candidate, title, summary, council_data)
                elif hasattr(self.ai, 'generate_cover_letter'):
                    proposal = self.ai.generate_cover_letter(candidate, title, "Client", summary, ["Python", "Automation"], budget_str)
                else:
                    proposal = f"Hi! I can deliver '{title}' with high quality and quickly. Let's discuss the details. Best regards."
                
                if verbose_test:
                    print(f"  📝 [PROPOSTA GENERATA]:\n{proposal}\n")
                    
                # Eseguiamo il bidding vero e proprio
                success = self.auto_apply(link, proposal, bid_amount="150", delivery_time="3")
                if success and self.telegram:
                    msg = f"🎯 <b>FREELANCER BID INVIATA</b>\n\n<b>Progetto:</b> {title}\n<b>Bid:</b> €150 (3 Giorni)\n<a href='{link}'>Vai al Progetto</a>"
                    self.telegram.send_message(msg)
                    
                self.simulate_human_delay(5, 10)
                
                # Una volta inviata una bid con successo, fermiamo il loop per questo ciclo
                if success:
                    print("  └ 🛑 [STOP] Bid inviata con successo. Interrompo la scansione di questo ciclo per non fare spam.")
                    break
            else:
                print(f"  └ ⏭️ Scartato: {title}")
                if verbose_test:
                    print(f"  ❌ [PROPOSTA NON GENERATA]: Progetto ignorato dal CEO.")
