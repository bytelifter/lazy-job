"""
upwork_sniper.py — Real-Time Freelance & Gig Sniper (Freelancer.com, Upwork, Remote Gigs).

Monitors freelance project APIs in real-time for high-margin Python, Web Scraping,
Data Automation, ETL, and API Integration gigs, generates AI proposals with technical blueprints,
and dispatches instant 1-click application cards to Telegram.
"""

from __future__ import annotations

import html
import json
import re
import time
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

from .ai_writer import LocalAIWriter
from .telegram_notifier import TelegramNotifier


@dataclass
class FreelanceGig:
    """Represents a client gig project."""

    title: str = ""
    url: str = ""
    description: str = ""
    budget: str = ""
    currency: str = "USD"
    platform: str = "Freelancer.com"
    skills: list[str] = field(default_factory=list)
    pub_date: str = ""
    project_id: str = ""
    proposal: str = ""


class UpworkSniper:
    """
    Scans Freelancer & Upwork feeds for new gigs, generates AI proposals,
    saves results to results_gigs/ directory, and alerts the user via Telegram.
    """

    RESULTS_DIR = Path("results_gigs")
    CACHE_FILE = Path("results_gigs/seen_freelance_gigs.json")

    def __init__(self, config: dict[str, Any]) -> None:
        self._config = config
        self._upwork_cfg: dict[str, Any] = config.get("upwork_settings", {})
        self._enabled: bool = self._upwork_cfg.get("enabled", True)
        self._queries: list[str] = self._upwork_cfg.get(
            "search_queries",
            [
                "python automation",
                "web scraping python",
                "data processing pandas",
                "api integration python",
                "ai llm developer langchain",
            ],
        )
        self._poll_interval = int(self._upwork_cfg.get("poll_interval_minutes", 15)) * 60
        self._ai_writer = LocalAIWriter(config)
        self._notifier = TelegramNotifier(config)
        self._candidate = config.get("candidate_profile", {})
        self._seen_ids: set[str] = self._load_seen_cache()

    def _load_seen_cache(self) -> set[str]:
        """Loads previously alerted gig IDs to avoid duplicate alerts."""
        if self.CACHE_FILE.exists():
            try:
                with self.CACHE_FILE.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                    return set(data)
            except Exception:
                pass
        return set()

    def _save_seen_cache(self) -> None:
        """Saves alerted gig IDs to cache file."""
        self.CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self.CACHE_FILE.open("w", encoding="utf-8") as f:
                # Keep only last 500 IDs
                json.dump(list(self._seen_ids)[-500:], f, indent=2)
        except Exception:
            pass

    def fetch_new_gigs(self) -> list[FreelanceGig]:
        """
        Polls Freelancer & Upwork search endpoints for new matching projects.

        Returns:
            List of un-seen FreelanceGig objects.
        """
        new_gigs: list[FreelanceGig] = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        for query in self._queries:
            # 1. Fetch from Freelancer.com Official REST API
            encoded_q = urllib.parse.quote(query)
            api_url = f"https://www.freelancer.com/api/projects/0.1/projects/active/?query={encoded_q}&compact=true&limit=15"

            try:
                resp = requests.get(api_url, headers=headers, timeout=15)
                if resp.status_code == 200:
                    data = resp.json()
                    projects = data.get("result", {}).get("projects", [])

                    for p in projects:
                        pid = str(p.get("id", ""))
                        if not pid or pid in self._seen_ids:
                            continue

                        seo_url = p.get("seo_url", "")
                        direct_url = f"https://www.freelancer.com/projects/{seo_url}" if seo_url else f"https://www.freelancer.com/projects/{pid}"

                        # Currency and budget validation
                        b_info = p.get("budget", {})
                        min_b = float(b_info.get("minimum") or 0)
                        max_b = float(b_info.get("maximum") or 0)
                        curr = str(p.get("currency", {}).get("code", "USD")).upper()

                        budget_str = f"{min_b:,.0f} - {max_b:,.0f} {curr}" if max_b else f"{min_b:,.0f} {curr}"

                        raw_desc = p.get("preview_description", "")
                        clean_desc = re.sub(r"\s+", " ", raw_desc).strip()

                        # Skills
                        jobs_list = p.get("jobs", [])
                        skills = [str(j.get("name", "")) for j in jobs_list if j.get("name")]

                        gig = FreelanceGig(
                            title=p.get("title", "").strip(),
                            url=direct_url,
                            description=clean_desc,
                            budget=budget_str,
                            currency=curr,
                            platform="Freelancer.com",
                            skills=skills or ["Python", "Automation"],
                            pub_date=str(datetime.now().strftime("%Y-%m-%d")),
                            project_id=pid,
                        )

                        # Filter out spam, agency pitches, and micro-budget gigs
                        if not self._is_legitimate_high_roi_gig(gig, min_b, max_b, curr):
                            continue

                        if gig.title:
                            new_gigs.append(gig)
                            self._seen_ids.add(pid)

            except Exception as e:
                print(f"  [ERR] Gig query '{query}' failed: {e}")
                continue

        self._save_seen_cache()
        return new_gigs

    def _is_legitimate_high_roi_gig(self, gig: FreelanceGig, min_b: float, max_b: float, curr: str) -> bool:
        """
        Strictly filters out agency sales spam, fake co-founder ads, and micro-penny tasks.
        Requires genuine Python, Web Scraping, Data Processing, or API automation requirements.
        """
        full_text = f"{gig.title} {gig.description}".lower()

        # 1. Blocked spam / agency pitch phrases
        blocked_phrases = self._upwork_cfg.get("blocked_gig_phrases", [])
        if any(bp.lower() in full_text for bp in blocked_phrases):
            return False

        # 2. Must contain concrete technical / data / automation intent
        must_contain = self._upwork_cfg.get("must_contain_one_of", [])
        skills_text = " ".join(gig.skills).lower()
        if not any(kw.lower() in full_text or kw.lower() in skills_text for kw in must_contain):
            return False

        # 3. Currency conversion to USD to check minimum threshold
        val = max_b if max_b > 0 else min_b
        curr_upper = curr.upper()
        if curr_upper == "INR":
            usd_equiv = val / 86.0
        elif curr_upper in ("EUR", "GBP"):
            usd_equiv = val * 1.1
        elif curr_upper in ("AUD", "CAD"):
            usd_equiv = val * 0.7
        else:
            usd_equiv = val

        # Minimum USD value check (e.g. at least $80 USD)
        min_usd = float(self._upwork_cfg.get("min_budget_fixed_usd", 80))
        if usd_equiv < min_usd:
            return False

        return True

    def process_and_alert(self, gig: FreelanceGig) -> None:
        """Generates AI proposal and sends an instant Telegram alert."""
        price_str = gig.budget or "Open / Negotiable"
        print(f"\n🎯 [FREELANCE SNIPER] New Gig: {gig.title}")
        print(f"   💵 Budget: {price_str} | 🌐 Platform: {gig.platform}")
        print(f"   🔗 Link: {gig.url}")

        # Generate custom Upwork/Freelancer proposal
        proposal = self._ai_writer.generate_upwork_proposal(
            candidate=self._candidate,
            gig_title=gig.title,
            gig_description=gig.description,
            budget=price_str,
            skills=gig.skills,
        )
        gig.proposal = proposal

        tool_hint = self._detect_toolstack(gig)

        # Dispatch alert to Telegram
        if self._notifier.is_configured:
            clean_proposal = proposal.replace("<", "&lt;").replace(">", "&gt;")
            clean_title = gig.title.replace("<", "&lt;").replace(">", "&gt;")
            msg = (
                f"⚡ <b>FREELANCE GIG SNIPER ALERT</b> ⚡\n\n"
                f"💼 <b>Project:</b> {clean_title}\n"
                f"💵 <b>Budget:</b> <code>{price_str}</code>\n"
                f"🌐 <b>Platform:</b> {gig.platform}\n"
                f"🏷️ <b>Skills:</b> {', '.join(gig.skills[:5]) if gig.skills else 'Python, Automation'}\n"
                f"🛠️ <b>Tool/AI da Usare:</b> <code>{tool_hint}</code>\n\n"
                f"📝 <b>READY-TO-PASTE PROPOSAL:</b>\n"
                f"<blockquote>{clean_proposal}</blockquote>\n\n"
                f"🚀 <a href='{gig.url}'><b>Open Direct Gig Page & Submit Bid</b></a>"
            )
            self._notifier.send_message(msg)
            print("   ✅ Instant Telegram proposal dispatched!")

    def _detect_toolstack(self, gig: FreelanceGig) -> str:
        """Detects the best AI / Python toolstack to solve this specific gig in 15 mins."""
        txt = f"{gig.title} {gig.description} {' '.join(gig.skills)}".lower()

        if any(k in txt for k in ("scrap", "crawl", "extract", "selenium", "playwright")):
            return "Playwright Python + BeautifulSoup4 + Pandas (Export CSV)"
        elif any(k in txt for k in ("translat", "localiz", "subtitl", "italian", "english")):
            return "DeepL API / Whisper (Audio) + Ollama Qwen-2.5"
        elif any(k in txt for k in ("copywrit", "content", "article", "blog", "seo")):
            return "Ollama Qwen-2.5-Coder + Python Markdown/Docx loop"
        elif any(k in txt for k in ("csv", "excel", "clean", "pandas", "data processing", "etl")):
            return "Pandas + Openpyxl + DuckDB (Clean & Reformat script)"
        elif any(k in txt for k in ("shopify", "catalog", "woocommerce", "e-commerce")):
            return "Shopify REST API + Openpyxl (Bulk CSV template)"
        elif any(k in txt for k in ("api", "webhook", "zapier", "n8n", "automation")):
            return "FastAPI (Python) / n8n Workflow + Requests"
        else:
            return "Python Script + Local Ollama LLM"

    def _save_gigs_csv(self, gigs: list[FreelanceGig]) -> str:
        """Saves processed gigs to a dedicated CSV file in results_gigs/."""
        self.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = self.RESULTS_DIR / f"freelance_gigs_{timestamp}.csv"

        import csv

        with open(filename, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Timestamp", "Platform", "Title", "Budget", "Currency",
                "Skills", "Direct_URL", "AI_Proposal", "Description"
            ])
            for g in gigs:
                writer.writerow([
                    g.pub_date or datetime.now().strftime("%Y-%m-%d %H:%M"),
                    g.platform,
                    g.title,
                    g.budget,
                    g.currency,
                    ", ".join(g.skills),
                    g.url,
                    g.proposal,
                    g.description,
                ])

        print(f"📁 Gigs saved to dedicated folder: {filename.resolve()}")
        return str(filename)

    def run_once(self, max_alerts: int = 5) -> int:
        """Runs a single scan of freelance feeds."""
        print("\n🔍 Scanning freelance feeds for fresh Python/Automation gigs...")
        gigs = self.fetch_new_gigs()
        print(f"📊 Found {len(gigs)} new matching freelance projects!")

        for gig in gigs[:max_alerts]:
            self.process_and_alert(gig)
            time.sleep(1)

        if gigs:
            self._save_gigs_csv(gigs)

        return len(gigs)

    def run_loop(self) -> None:
        """Runs continuous monitoring loop with configured sleep interval."""
        print(f"\n🚀 Freelance Gig Sniper active! Monitoring feeds every {self._poll_interval // 60} minutes...")
        print("   Press Ctrl+C to stop.")

        try:
            while True:
                self.run_once()
                print(f"\n💤 Sleeping {self._poll_interval // 60}m until next scan...")
                time.sleep(self._poll_interval)
        except KeyboardInterrupt:
            print("\n🛑 Freelance Gig Sniper stopped.")
