"""
reporter.py — Modulo per la generazione dei report.

Produce:
1. File CSV ordinato per match score decrescente
2. Report formattato per il terminale con colori ANSI
"""

from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .matcher import ScoredOffer


class Reporter:
    """
    Generatore di report per le offerte filtrate e scored.

    Supporta output CSV e report terminale con colori ANSI.
    """

    # Colori ANSI per il terminale
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"
    WHITE = "\033[97m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_RED = "\033[41m"

    CSV_COLUMNS: list[str] = [
        "Date",
        "Title",
        "Company",
        "Job Type",
        "Sector",
        "Match Score",
        "Automatable Score",
        "Automation Strategy",
        "Salary",
        "Matched Skills",
        "Source",
        "Direct Link",
    ]

    def __init__(self) -> None:
        """Inizializza il reporter."""
        pass

    def get_seen_urls(self, directory: str) -> set[str]:
        """
        Scansiona tutti i file CSV nella cartella specificata ed estrae
        i link delle offerte già salvate per evitare duplicati nelle ricerche future.

        Args:
            directory: Cartella contenente i CSV storici.

        Returns:
            Set di URL (stringhe) già visti.
        """
        seen: set[str] = set()
        dir_path = Path(directory)
        
        if not dir_path.exists():
            return seen

        for file_path in dir_path.glob("*.csv"):
            try:
                with file_path.open("r", encoding="utf-8-sig") as csvfile:
                    reader = csv.reader(csvfile)
                    header = next(reader, None)
                    if not header:
                        continue
                    
                    try:
                        if "Direct Link" in header:
                            url_idx = header.index("Direct Link")
                        elif "Link Diretto" in header:
                            url_idx = header.index("Link Diretto")
                        else:
                            url_idx = -1
                    except ValueError:
                        url_idx = -1  # Fallback to last column
                    
                    for row in reader:
                        if row and len(row) > url_idx:
                            url = row[url_idx].strip()
                            if url:
                                seen.add(url)
            except Exception:
                # Salta silenziosamente file non leggibili o aperti da altri processi
                continue
        return seen

    def save_csv(
        self,
        results: list[ScoredOffer],
        output_path: str,
    ) -> str:
        """
        Salva i risultati in un file CSV ordinato per score.

        Args:
            results: Lista di ScoredOffer (già ordinata per score).
            output_path: Percorso del file CSV di output.

        Returns:
            Percorso assoluto del file CSV creato.

        Raises:
            RuntimeError: Se la scrittura fallisce.
        """
        path = Path(output_path)

        try:
            path.parent.mkdir(parents=True, exist_ok=True)

            with path.open("w", newline="", encoding="utf-8-sig") as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(self.CSV_COLUMNS)

                for offer in results:
                    writer.writerow([
                        offer.pub_date or "N/A",
                        offer.title,
                        offer.company,
                        offer.job_type or "Contractor",
                        offer.sector,
                        offer.match_score,
                        f"{offer.automatability_score}%",
                        offer.automation_strategy,
                        offer.salary or "N/A",
                        ", ".join(offer.matched_skills),
                        offer.source,
                        offer.url,
                    ])

            return str(path.resolve())

        except Exception as e:
            raise RuntimeError(f"Error writing CSV: {e}") from e

    def print_terminal_report(
        self,
        results: list[ScoredOffer],
        total_fetched: int = 0,
        total_before_filter: int = 0,
    ) -> None:
        """
        Stampa un report formattato sul terminale con colori ANSI.

        Args:
            results: Lista di ScoredOffer ordinate per score.
            total_fetched: Numero totale di offerte recuperate.
            total_before_filter: Numero di offerte prima del filtraggio.
        """
        self._print_header(len(results), total_fetched)

        if not results:
            print(f"\n  {self.YELLOW}⚠  No jobs found matching the criteria.{self.RESET}")
            print(f"  {self.DIM}Try lowering min_match_score or selecting more areas in config.json{self.RESET}")
            return

        # Mostra le top offerte
        max_display = min(len(results), 25)

        for i, offer in enumerate(results[:max_display], 1):
            self._print_offer_card(i, offer)

        if len(results) > max_display:
            remaining = len(results) - max_display
            print(f"\n  {self.DIM}... and {remaining} more jobs saved to CSV.{self.RESET}")

        self._print_footer(results)

    def _print_header(self, result_count: int, total_fetched: int) -> None:
        """Stampa l'intestazione del report."""
        separator = "═" * 70
        print(f"\n{self.CYAN}{self.BOLD}{separator}{self.RESET}")
        print(f"{self.CYAN}{self.BOLD}  🎯  LAZYJOBHUNTER — REMOTE CONTRACTOR JOB REPORT{self.RESET}")
        print(f"{self.CYAN}{self.BOLD}{separator}{self.RESET}")
        print(f"  {self.DIM}Total jobs analyzed: {total_fetched}{self.RESET}")
        print(f"  {self.DIM}Matching jobs:       {result_count}{self.RESET}")
        print(f"{self.CYAN}{'─' * 70}{self.RESET}")

    def _print_offer_card(self, index: int, offer: ScoredOffer) -> None:
        """
        Stampa una singola offerta come card formattata.

        Args:
            index: Numero progressivo dell'offerta.
            offer: L'offerta scored da visualizzare.
        """
        # Score color
        score_color = self._score_color(offer.match_score)
        score_badge = f"{score_color}{self.BOLD}[{offer.match_score:3d}/100]{self.RESET}"

        # High value badge & Automatable badge
        value_badge = f" {self.GREEN}💰 HIGH VALUE{self.RESET}" if offer.is_high_value else ""
        auto_badge = f" {self.CYAN}{self.BOLD}⚡🤖 AUTOMATABLE ({offer.automatability_score}%){self.RESET}" if offer.is_highly_automatable else ""

        # Separator
        print(f"\n  {self.DIM}{'─' * 66}{self.RESET}")

        # Title line
        print(f"  {self.BOLD}{self.WHITE}#{index:02d}{self.RESET}  {score_badge}  {self.BOLD}{offer.title}{self.RESET}{value_badge}{auto_badge}")

        # Company & Source
        print(f"       {self.CYAN}🏢 {offer.company}{self.RESET}  •  {self.DIM}{offer.source}{self.RESET}")

        # Job type & Location
        job_type_display = offer.job_type if offer.job_type else "Contractor"
        print(f"       {self.MAGENTA}📋 {job_type_display}{self.RESET}  •  {self.DIM}📍 {offer.location or 'Remote'}{self.RESET}")

        # Salary
        if offer.salary:
            print(f"       {self.GREEN}💵 {offer.salary}{self.RESET}")

        # Sector
        if offer.sector != "General":
            print(f"       {self.YELLOW}🏷️  {offer.sector}{self.RESET}")

        # Automation Strategy
        if offer.is_highly_automatable:
            print(f"       {self.CYAN}⚡ Lazy Strategy: {offer.automation_strategy}{self.RESET}")

        # Matched skills
        if offer.matched_skills:
            skills_str = ", ".join(offer.matched_skills[:10])
            print(f"       {self.GREEN}✅ Skills: {skills_str}{self.RESET}")

        # Date
        if offer.pub_date:
            print(f"       {self.DIM}📅 {offer.pub_date}{self.RESET}")

        # Link
        print(f"       {self.DIM}🔗 {offer.url}{self.RESET}")

    def _print_footer(self, results: list[ScoredOffer]) -> None:
        """Stampa il footer con statistiche riassuntive."""
        separator = "═" * 70

        # Stats
        avg_score = sum(o.match_score for o in results) / len(results) if results else 0
        high_value_count = sum(1 for o in results if o.is_high_value)
        highly_auto_count = sum(1 for o in results if o.is_highly_automatable)
        top_sectors: dict[str, int] = {}
        for o in results:
            if o.sector != "General":
                top_sectors[o.sector] = top_sectors.get(o.sector, 0) + 1

        print(f"\n{self.CYAN}{'─' * 70}{self.RESET}")
        print(f"  {self.BOLD}📈 SUMMARY STATISTICS{self.RESET}")
        print(f"  {self.DIM}{'─' * 40}{self.RESET}")
        print(f"  Total matched jobs:             {self.BOLD}{len(results)}{self.RESET}")
        print(f"  Average match score:            {self.BOLD}{avg_score:.1f}/100{self.RESET}")
        print(f"  High Value jobs:                {self.GREEN}{self.BOLD}{high_value_count}{self.RESET}")
        print(f"  ⚡ Highly Automatable (Lazy-Mode): {self.CYAN}{self.BOLD}{highly_auto_count}{self.RESET}")

        if top_sectors:
            print(f"  Top sectors:")
            for sector, count in sorted(top_sectors.items(), key=lambda x: x[1], reverse=True):
                print(f"    • {sector}: {count}")

        # Sources breakdown
        sources: dict[str, int] = {}
        for o in results:
            sources[o.source] = sources.get(o.source, 0) + 1
        if sources:
            print(f"  Sources:")
            for source, count in sorted(sources.items(), key=lambda x: x[1], reverse=True):
                print(f"    • {source}: {count}")

        print(f"\n{self.CYAN}{self.BOLD}{separator}{self.RESET}")
        print(f"  {self.GREEN}{self.BOLD}✅ Report completed. Happy hunting! 🎯{self.RESET}")
        print(f"{self.CYAN}{self.BOLD}{separator}{self.RESET}\n")

    def _score_color(self, score: int) -> str:
        """
        Restituisce il codice colore ANSI in base al punteggio.

        Args:
            score: Punteggio dell'offerta (0-100).

        Returns:
            Stringa con codice colore ANSI.
        """
        if score >= 70:
            return self.GREEN
        elif score >= 50:
            return self.YELLOW
        else:
            return self.RED
