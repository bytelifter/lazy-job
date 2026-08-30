import time
import os
import signal
import sys
from datetime import datetime
import threading

from remote_job_hunter.crm_manager import CRMManager
from remote_job_hunter.gmail_scanner import GmailScanner
from remote_job_hunter.whatsapp_sender import WhatsAppSender
from remote_job_hunter.ai_council import AICouncil
from remote_job_hunter.gmail_sender import GmailSender
from remote_job_hunter.real_estate_scraper import RealEstateScraper
from remote_job_hunter.maps_lead_gen import MapsLeadGen
from remote_job_hunter.telegram_notifier import TelegramNotifier
from remote_job_hunter.fetcher import JobFetcher
from remote_job_hunter.matcher import JobMatcher
from remote_job_hunter.reporter import Reporter
from remote_job_hunter.applier import ApplicationOrchestrator
from remote_job_hunter.learning_loop import FinancialLoop
from remote_job_hunter.freelancer_sniper import FreelancerSniper
from main import load_config

class MasterDaemon:
    """
    Background orchestrator che esegue l'intero LazyJobHunter suite automaticamente.
    Può essere fermato con Ctrl+C in modo sicuro.
    Tutto viene loggato nella cartella daemon_logs/.
    
    Tasks:
    1. Gmail Scanner: risponde alle email in entrata dai lead
    2. WhatsApp Scanner: risponde ai messaggi WA in entrata dai lead
    3. Job Fetcher Pipeline: cerca gig su Remotive, Himalayas, Jobicy, LinkedIn, Indeed
    4. Maps Lead Gen: scansiona nicchie su Google Maps e invia pitch (ogni ~1 ora)
    5. Real Estate Sniper: scansiona Immobiliare.it / Airbnb (ogni ~1.5 ore)
    6. Freelancer Sniper: fa auto-bidding su freelancer.com (ogni 2 cicli)
    """
    
    def __init__(self):
        self.running = True
        self.log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "daemon_logs")
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Graceful shutdown
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        
        self.config = load_config()
        self.crm = CRMManager()
        self.gmail_scanner = GmailScanner(self.crm)
        self.wa_scanner = WhatsAppSender()
        self.gmail_sender = GmailSender(self.config)
        self.ai = AICouncil()
        self.telegram = TelegramNotifier(self.config)
        self.real_estate = RealEstateScraper(self.crm, self.ai, self.config)
        self.maps_sniper = MapsLeadGen(self.crm, self.ai, self.config)
        self.finance = FinancialLoop()
        
        self.real_estate_portals = ["immobiliare", "idealista", "airbnb"]
        self.real_estate_cities = ["roma-provincia"]
        self.last_re_portal_idx = 0
        self.last_re_city_idx = 0
        
        # Inizializza il Freelancer Sniper passandogli l'AI Council e il LocalAIWriter
        from remote_job_hunter.ai_writer import LocalAIWriter
        self.ai_writer = LocalAIWriter(self.config)
        self.freelancer_sniper = FreelancerSniper(ai_writer=self.ai_writer, ai_council=self.ai, telegram=self.telegram, config_path="config.json")
        
    def _handle_shutdown(self, signum, frame):
        print("\n🛑 Ricevuto segnale di stop. Spegnimento sicuro in corso...")
        self.running = False
        
    def _log(self, module: str, message: str):
        """Log su file giornaliero e stdout."""
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = os.path.join(self.log_dir, f"{today}_daemon.log")
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = f"[{timestamp}] [{module}] {message}\n"
        print(entry.strip())
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(entry)
            
    def _check_pending_teardowns(self):
        teardown_file = os.path.join(self.log_dir, "pending_teardowns.json")
        if not os.path.exists(teardown_file): return
        
        import json
        try:
            with open(teardown_file, "r") as f:
                teardowns = json.load(f)
                
            now = time.time()
            remaining = []
            
            for item in teardowns:
                execute_at = item.get("execute_at", 0)
                domain = item.get("domain", "")
                deploy_dir = item.get("deploy_dir", "")
                
                if not domain: continue
                
                if now >= execute_at:
                    self._log("SYSTEM", f"Eseguo teardown arretrato per {domain}")
                    import subprocess, shutil
                    subprocess.run(["surge", "teardown", domain], shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    try: shutil.rmtree(deploy_dir)
                    except: pass
                else:
                    def delayed_teardown(dom, d_dir, delay, item_ref):
                        time.sleep(delay)
                        import subprocess, shutil
                        subprocess.run(["surge", "teardown", dom], shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        try: shutil.rmtree(d_dir)
                        except: pass
                        self._remove_pending_teardown(item_ref)
                    
                    delay = execute_at - now
                    threading.Thread(target=delayed_teardown, args=(domain, deploy_dir, delay, item), daemon=True).start()
                    remaining.append(item)
                    
            with open(teardown_file, "w") as f:
                json.dump(remaining, f, indent=4)
                
        except Exception as e:
            self._log("ERROR", f"Errore lettura teardowns: {e}")

    def _add_pending_teardown(self, domain, deploy_dir, execute_at):
        import json
        teardown_file = os.path.join(self.log_dir, "pending_teardowns.json")
        item = {"domain": domain, "deploy_dir": deploy_dir, "execute_at": execute_at}
        try:
            teardowns = []
            if os.path.exists(teardown_file):
                with open(teardown_file, "r") as f:
                    teardowns = json.load(f)
            teardowns.append(item)
            with open(teardown_file, "w") as f:
                json.dump(teardowns, f, indent=4)
            return item
        except:
            return item

    def _remove_pending_teardown(self, item):
        import json
        teardown_file = os.path.join(self.log_dir, "pending_teardowns.json")
        try:
            if os.path.exists(teardown_file):
                with open(teardown_file, "r") as f:
                    teardowns = json.load(f)
                teardowns = [t for t in teardowns if t.get("domain") != item.get("domain")]
                with open(teardown_file, "w") as f:
                    json.dump(teardowns, f, indent=4)
        except:
            pass

    def start(self):
        self._log("SYSTEM", "🚀 Master Daemon Avviato. Premi [Ctrl+C] per fermarlo.")
        
        # Recupero spegnimenti pendenti (demo su Surge)
        self._check_pending_teardowns()
        
        # Mostra situazione finanziaria all'avvio
        try:
            status = self.finance.get_weekly_status()
            self._log("FINANCE", f"💰 Settimana: €{status['weekly_income']:.2f}/{status['goal']:.0f} ({status['progress_pct']:.0f}%) | Pipeline: €{status['pending_pipeline']:.2f}")
        except Exception:
            pass
        
        cycle_count = 0
        while self.running:
            try:
                cycle_count += 1
                self._log("SCHEDULER", f"━━━ Inizio Ciclo #{cycle_count} ━━━")
                
                # ── TASK 1: Scansione Gmail per risposte ──────────────────────
                self._log("GMAIL", "Controllo nuove risposte Email...")
                try:
                    email_replies = self.gmail_scanner.scan_replies()
                    for reply in email_replies:
                        self._log("GMAIL", f"Trovata risposta da {reply['identifier']}")
                        self.crm.add_reply(reply['identifier'], reply['content'], role="client")
                        response = self.ai.generate_auto_reply(reply['lead_data'], reply['content'])
                        
                        if response and "[DEMO_LINK]" in response:
                            from remote_job_hunter.demo_generator import DemoGenerator
                            demo_gen = DemoGenerator()
                            b_name = reply['lead_data'].get('name', 'Business')
                            # Rigeneriamo la demo per sicurezza
                            local_path = demo_gen.generate_mini_site(b_name, "software")
                            url = demo_gen.host_on_surge(b_name, local_path)
                            if url:
                                response = response.replace("[DEMO_LINK]", url)
                                # Schedula spegnimento persistente tra 12 ore
                                execute_at = time.time() + 12 * 3600
                                domain = url.replace("https://", "")
                                deploy_dir = os.path.dirname(local_path)
                                item = self._add_pending_teardown(domain, deploy_dir, execute_at)
                                
                                def teardown_demo(dom, d_dir, item_ref):
                                    time.sleep(12 * 3600)
                                    import subprocess, shutil
                                    subprocess.run(["surge", "teardown", dom], shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                                    try: shutil.rmtree(d_dir)
                                    except: pass
                                    self._remove_pending_teardown(item_ref)
                                
                                threading.Thread(target=teardown_demo, args=(domain, deploy_dir, item), daemon=True).start()
                                self._log("COO", f"Demo attivata per 12 ore su {url}")
                            else:
                                response = response.replace("[DEMO_LINK]", "(errore generazione link)")
                        
                        if response and response.strip() != "IGNORE":
                            self.gmail_sender.send_email(
                                to_email=reply['identifier'],
                                subject="Re: La nostra proposta",
                                body=response
                            )
                            self.crm.add_reply(reply['identifier'], response, role="bot")
                            self._log("COO", f"Risposta inviata a {reply['identifier']}")
                except Exception as e:
                    self._log("GMAIL", f"Errore scanner: {e}")
                
                # ── TASK 2: Scansione WhatsApp per risposte ───────────────────
                self._log("WHATSAPP", "Controllo nuove risposte WhatsApp...")
                try:
                    wa_replies = self.wa_scanner.check_replies(self.crm)
                    for reply in wa_replies:
                        self._log("WHATSAPP", f"Trovata risposta da {reply['identifier']}")
                        self.crm.add_reply(reply['identifier'], reply['content'], role="client")
                        response = self.ai.generate_auto_reply(reply['lead_data'], reply['content'])
                        
                        if response and "[DEMO_LINK]" in response:
                            from remote_job_hunter.demo_generator import DemoGenerator
                            demo_gen = DemoGenerator()
                            b_name = reply['lead_data'].get('name', 'Business')
                            local_path = demo_gen.generate_mini_site(b_name, "software")
                            url = demo_gen.host_on_surge(b_name, local_path)
                            if url:
                                response = response.replace("[DEMO_LINK]", url)
                                execute_at = time.time() + 12 * 3600
                                domain = url.replace("https://", "")
                                deploy_dir = os.path.dirname(local_path)
                                item = self._add_pending_teardown(domain, deploy_dir, execute_at)
                                
                                def teardown_demo(dom, d_dir, item_ref):
                                    time.sleep(12 * 3600)
                                    import subprocess, shutil
                                    subprocess.run(["surge", "teardown", dom], shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                                    try: shutil.rmtree(d_dir)
                                    except: pass
                                    self._remove_pending_teardown(item_ref)
                                    
                                threading.Thread(target=teardown_demo, args=(domain, deploy_dir, item), daemon=True).start()
                                self._log("COO", f"Demo attivata per 12 ore su {url}")
                            else:
                                response = response.replace("[DEMO_LINK]", "(errore generazione link)")
                        
                        if response and response.strip() != "IGNORE":
                            self.wa_scanner.send_message(reply['identifier'], response)
                            self.crm.add_reply(reply['identifier'], response, role="bot")
                            self._log("COO", f"Risposta WA inviata a {reply['identifier']}")
                except Exception as e:
                    self._log("WHATSAPP", f"Errore scanner: {e}")
                
                # ── TASK 3: Job Fetcher Pipeline (ogni 10 cicli, ~10 min) ─────────────────
                if cycle_count % 10 == 0:
                    self._log("GIG_HUNTER", "Scansione nuovi lavori remoti (Remotive, Himalayas, LinkedIn...)...")
                try:
                    fetcher = JobFetcher(self.config)
                    raw_offers = fetcher.fetch_all()
                    
                    if raw_offers:
                        matcher = JobMatcher(self.config)
                        scored = matcher.process(
                            raw_offers,
                            user_skills=self.config.get("candidate_profile", {}).get("skills", []),
                            user_location=self.config.get("candidate_profile", {}).get("location", "Italy")
                        )
                        # Il matcher ha già scartato le offerte sotto la soglia minima (40)
                        top_offers = scored
                        self._log("GIG_HUNTER", f"Trovati {len(raw_offers)} lavori → {len(top_offers)} match di qualità")
                        
                        if top_offers:
                            # Genera report e invia su Telegram
                            reporter = Reporter()
                            from datetime import datetime
                            csv_fname = f"results/gig_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                            csv_path = reporter.save_csv(top_offers, csv_fname)
                            self.telegram.send_match_summary(len(top_offers), top_offers[:5], csv_path)
                            
                            # Applica ai migliori automaticamente
                            orchestrator = ApplicationOrchestrator(self.config)
                            for offer in top_offers[:3]:
                                results = orchestrator.process_applications([offer], max_applications=1)
                                if results:
                                    res = results[0]
                                    self._log("APPLIER", f"{res.status}: {offer.title} @ {offer.company}")
                except Exception as e:
                    self._log("GIG_HUNTER", f"Errore pipeline gig: {e}")
                
                # ── TASK 4: Maps Lead Gen (ogni 40 cicli, ~40 min) ────────────
                if cycle_count % 40 == 0:
                    self._log("MAPS", "Avvio rotazione nicchie Google Maps...")
                    try:
                        self.maps_sniper.run_campaign()
                    except Exception as e:
                        self._log("MAPS", f"Errore Maps Sniper: {e}")
                        
                # ── TASK 5: Real Estate (ogni 60 cicli, ~1 ora) ───────────────
                if cycle_count % 60 == 0:
                    portal = self.real_estate_portals[self.last_re_portal_idx]
                    city = self.real_estate_cities[self.last_re_city_idx]
                    
                    self._log("REAL_ESTATE", f"Avvio scansione su {portal} ({city})...")
                    try:
                        self.real_estate.run_campaign(city, portal)
                        
                        # Rotazione
                        self.last_re_city_idx += 1
                        if self.last_re_city_idx >= len(self.real_estate_cities):
                            self.last_re_city_idx = 0
                            self.last_re_portal_idx = (self.last_re_portal_idx + 1) % len(self.real_estate_portals)
                    except Exception as e:
                        self._log("REAL_ESTATE", f"Errore Real Estate: {e}")
                        
                # ── TASK 6: Freelancer Sniper (ogni 2 cicli, ~2 min) ────────
                if cycle_count % 2 == 0:
                    self._log("FREELANCER", "Avvio cecchino su Freelancer.com...")
                    try:
                        self.freelancer_sniper.run_campaign()
                    except Exception as e:
                        self._log("FREELANCER", f"Errore Sniper: {e}")
                    
                self._log("SCHEDULER", "Ciclo completato. Pausa 1 minuto...")
                
                # Attesa interrompibile
                for _ in range(60):
                    if not self.running:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                self._log("ERROR", f"Errore critico nel ciclo: {e}")
                time.sleep(60)
                
        self._log("SYSTEM", "✅ Spegnimento completato. A presto!")

if __name__ == "__main__":
    daemon = MasterDaemon()
    daemon.start()
