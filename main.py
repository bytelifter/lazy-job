#!/usr/bin/env python3
"""
main.py — CLI Orchestrator for LazyJobHunter.

Executes the sequential automated pipeline:
1. Banner and introduction
2. Interactive CV file upload
3. Parsing and skill confirmation
4. Target job area selection
5. Candidate location / country selection for geo-filtering
6. Multi-source parallel API fetching
7. Historical duplicate detection & exclusion
8. Hard filtering, location compatibility, and scoring
9. Report generation (timestamped CSV + ANSI colored terminal report)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Force UTF-8 on stdout/stderr for Windows (emoji & box drawing characters support)
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    os.system("")  # Enable VT100 in Windows Console
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass

from remote_job_hunter.applier import ApplicationOrchestrator
from remote_job_hunter.cv_parser import CVParser, UserProfile
from remote_job_hunter.fetcher import JobFetcher
from remote_job_hunter.matcher import JobMatcher
from remote_job_hunter.reporter import Reporter


# ─── ANSI Constants ──────────────────────────────────────────
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"


def print_banner() -> None:
    """Prints the application startup banner."""
    banner = f"""
{CYAN}{BOLD}╔══════════════════════════════════════════════════════════════════════╗
║                                                                      ║
║   ██╗      █████╗ ███████╗██╗   ██╗     ██╗ ██████╗ ██████╗         ║
║   ██║     ██╔══██╗╚══███╔╝╚██╗ ██╔╝     ██║██╔═══██╗██╔══██╗       ║
║   ██║     ███████║  ███╔╝  ╚████╔╝      ██║██║   ██║██████╔╝       ║
║   ██║     ██╔══██║ ███╔╝    ╚██╔╝  ██   ██║██║   ██║██╔══██╗       ║
║   ███████╗██║  ██║███████╗   ██║   ╚█████╔╝╚██████╔╝██████╔╝       ║
║   ╚══════╝╚═╝  ╚═╝╚══════╝  ╚═╝    ╚════╝  ╚═════╝ ╚═════╝        ║
║                                                                      ║
║   🎯  HUNTER  —  Contractor & Freelance Remote Job Pipeline         ║
║   ─────────────────────────────────────────────────────────────      ║
║   Automated batch pipeline for high-value remote contractor jobs    ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝{RESET}
"""
    print(banner)


def load_config() -> dict[str, Any]:
    """
    Loads configuration from config.json.

    Returns:
        Configuration dictionary.

    Raises:
        FileNotFoundError: If config.json is not found.
        json.JSONDecodeError: If config.json contains invalid JSON.
    """
    config_path = Path(__file__).parent / "remote_job_hunter" / "config.json"

    if not config_path.exists():
        config_path = Path(__file__).parent / "config.json"

    if not config_path.exists():
        raise FileNotFoundError(
            f"Configuration file not found.\n"
            f"Searched in: {config_path}\n"
            f"Please make sure config.json exists in the project root."
        )

    with config_path.open("r", encoding="utf-8") as f:
        config: dict[str, Any] = json.load(f)

    return config


def interactive_cv_prompt() -> str:
    """
    Interactively asks user for CV file path.

    Returns:
        Validated CV file path.
    """
    print(f"\n{BOLD}📄 CV FILE UPLOAD{RESET}")
    print(f"{DIM}{'─' * 50}{RESET}")
    print(f"  Supported formats: {GREEN}.pdf{RESET}, {GREEN}.txt{RESET}, {GREEN}.json{RESET}")
    print(f"  {DIM}(For JSON format, use structure: {{'skills': [...], 'experience_years': N}}){RESET}")
    print()

    while True:
        try:
            raw_input = input(f"  {CYAN}➜{RESET} Enter CV file path: ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n\n  {RED}Operation cancelled.{RESET}")
            sys.exit(0)

        if not raw_input:
            print(f"  {RED}✗ Path cannot be empty. Please try again.{RESET}")
            continue

        raw_input = raw_input.strip("\"'")
        file_path = Path(raw_input).expanduser().resolve()

        if not file_path.exists():
            print(f"  {RED}✗ File not found: {file_path}{RESET}")
            continue

        extension = file_path.suffix.lower()
        if extension not in {".pdf", ".txt", ".json"}:
            print(f"  {RED}✗ Unsupported format '{extension}'. Use .pdf, .txt, or .json{RESET}")
            continue

        print(f"  {GREEN}✓ File found: {file_path.name} ({file_path.stat().st_size:,} bytes){RESET}")
        return str(file_path)


def display_profile_summary(profile: UserProfile) -> None:
    """
    Displays summary of skills extracted from CV.

    Args:
        profile: Extracted user profile.
    """
    print(f"\n{BOLD}📋 EXTRACTED SKILLS SUMMARY{RESET}")
    print(f"{DIM}{'─' * 50}{RESET}")

    if profile.skills:
        for i in range(0, len(profile.skills), 5):
            chunk = profile.skills[i:i + 5]
            skills_line = "  •  ".join(f"{GREEN}{s}{RESET}" for s in chunk)
            print(f"  {skills_line}")
    else:
        print(f"  {YELLOW}⚠  No technical skills detected.{RESET}")

    if profile.experience_years is not None:
        print(f"\n  {CYAN}📅 Experience: ~{profile.experience_years} years{RESET}")

    print(f"\n  {DIM}Total skills detected: {len(profile.skills)}{RESET}")


def confirm_profile(profile: UserProfile) -> UserProfile:
    """
    Asks user to confirm or edit profile skills.

    Args:
        profile: Profile extracted from CV.

    Returns:
        Confirmed or modified profile.
    """
    print(f"\n{DIM}{'─' * 50}{RESET}")

    while True:
        try:
            choice = input(
                f"  {CYAN}➜{RESET} Confirm these skills? "
                f"[{GREEN}Y{RESET}=confirm / {YELLOW}E{RESET}=edit / {RED}Q{RESET}=quit]: "
            ).strip().upper()
        except (EOFError, KeyboardInterrupt):
            print(f"\n\n  {RED}Operation cancelled.{RESET}")
            sys.exit(0)

        if choice in ("Y", "YES", "", "S", "SI"):
            print(f"  {GREEN}✓ Profile confirmed.{RESET}")
            return profile

        elif choice in ("E", "EDIT", "M", "MODIFICA"):
            print(f"\n  {YELLOW}Enter skills separated by comma:{RESET}")
            print(f"  {DIM}Example: python, sql, pandas, excel, git, api{RESET}")

            try:
                raw = input(f"  {CYAN}➜{RESET} Skills: ").strip()
            except (EOFError, KeyboardInterrupt):
                print(f"\n\n  {RED}Operation cancelled.{RESET}")
                sys.exit(0)

            if raw:
                new_skills = [s.strip().lower() for s in raw.split(",") if s.strip()]
                profile.skills = sorted(set(new_skills))
                print(f"  {GREEN}✓ Skills updated: {len(profile.skills)} skills.{RESET}")
                display_profile_summary(profile)
            else:
                print(f"  {YELLOW}⚠  No changes applied.{RESET}")

        elif choice in ("Q", "QUIT", "EXIT", "N", "NO"):
            print(f"\n  {RED}Operation cancelled.{RESET}")
            sys.exit(0)

        else:
            print(f"  {RED}✗ Invalid choice. Use Y, E, or Q.{RESET}")


def select_job_areas(config: dict[str, Any]) -> dict[str, Any]:
    """
    Displays an interactive menu to select one or more job areas.

    Args:
        config: Configuration dictionary.

    Returns:
        Dictionary containing aggregated filters for the selected areas.
    """
    job_areas: dict[str, dict[str, Any]] = config.get("job_areas", {})
    rss_all: dict[str, str] = config.get("rss_feeds_all", {})

    if not job_areas:
        return {}

    area_names = [name for name in job_areas.keys() if name not in ("All Areas", "Tutte le Aree")]

    print(f"\n{BOLD}📂 SELECT TARGET JOB AREAS{RESET}")
    print(f"{DIM}{'─' * 50}{RESET}")
    print(f"  {CYAN}[0]{RESET} {BOLD}All Areas{RESET} {DIM}(recommended for wide search){RESET}")

    for idx, name in enumerate(area_names, start=1):
        print(f"  {CYAN}[{idx:2d}]{RESET} {name}")

    print(f"\n  {DIM}Select multiple areas with commas (e.g. 1, 2) or press ENTER for All Areas.{RESET}")

    while True:
        try:
            choice = input(f"  {CYAN}➜{RESET} Select area(s) [{GREEN}0-{len(area_names)}{RESET}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n\n  {RED}Operation cancelled.{RESET}")
            sys.exit(0)

        if not choice or choice == "0" or choice.lower() in ("all", "tutte"):
            print(f"  {GREEN}✓ Selected: All Areas{RESET}")
            all_keywords = config.get("search_keywords", [])
            return {
                "selected_area_names": ["All Areas"],
                "remotive_category": None,
                "jobicy_tag": None,
                "himalayas_keywords": all_keywords[:5],
                "rss_feeds": rss_all,
            }

        try:
            parts = [p.strip() for p in choice.split(",") if p.strip()]
            indices = [int(p) for p in parts]
            valid_indices = [i for i in indices if 1 <= i <= len(area_names)]

            if not valid_indices:
                print(f"  {RED}✗ No valid number entered. Please enter numbers from 0 to {len(area_names)}.{RESET}")
                continue

            selected_names = [area_names[i - 1] for i in valid_indices]
            print(f"  {GREEN}✓ Selected areas ({len(selected_names)}):{RESET} {', '.join(selected_names)}")

            remotive_cat = None
            jobicy_tag = None
            himalayas_kws: list[str] = []
            selected_feed_keys: set[str] = set()

            if len(selected_names) == 1:
                single_area = job_areas.get(selected_names[0], {})
                remotive_cat = single_area.get("remotive_category")
                jobicy_tag = single_area.get("jobicy_tag")

            for s_name in selected_names:
                area_data = job_areas.get(s_name, {})
                himalayas_kws.extend(area_data.get("himalayas_keywords", []))
                for fk in area_data.get("wwr_feeds", []):
                    selected_feed_keys.add(fk)

            seen_kw: set[str] = set()
            dedup_kws: list[str] = []
            for kw in himalayas_kws:
                if kw.lower() not in seen_kw:
                    seen_kw.add(kw.lower())
                    dedup_kws.append(kw)

            feeds_dict = {k: rss_all[k] for k in selected_feed_keys if k in rss_all}
            if not feeds_dict and rss_all:
                feeds_dict = rss_all

            return {
                "selected_area_names": selected_names,
                "remotive_category": remotive_cat,
                "jobicy_tag": jobicy_tag,
                "himalayas_keywords": dedup_kws[:6] if dedup_kws else None,
                "rss_feeds": feeds_dict,
            }

        except ValueError:
            print(f"  {RED}✗ Invalid input. Enter comma-separated numbers (e.g. 1, 2).{RESET}")


def interactive_location_prompt(config: dict[str, Any]) -> str:
    """
    Asks the user for their country/location to filter geographically incompatible jobs.

    Args:
        config: Configuration dictionary.

    Returns:
        User's location string.
    """
    default_loc = config.get("default_user_location", "Italy")

    print(f"\n{BOLD}🌍 CANDIDATE LOCATION FILTER{RESET}")
    print(f"{DIM}{'─' * 50}{RESET}")
    print(f"  Specify your country or region to filter out restricted postings.")
    print(f"  {DIM}(e.g. Italy, United States, United Kingdom, Europe, Worldwide){RESET}")
    print()

    try:
        user_loc = input(f"  {CYAN}➜{RESET} Your location [{GREEN}{default_loc}{RESET}]: ").strip()
    except (EOFError, KeyboardInterrupt):
        print(f"\n\n  {RED}Operation cancelled.{RESET}")
        sys.exit(0)

    if not user_loc:
        user_loc = default_loc

    print(f"  {GREEN}✓ Location set to: {user_loc}{RESET}")
    return user_loc


def main() -> None:
    """Main function — orchestrates the entire job hunting pipeline."""

    # ── Step 1: Banner ──
    print_banner()

    # ── Step 2: Load Configuration ──
    try:
        config = load_config()
        print(f"  {GREEN}✓ Configuration loaded successfully.{RESET}")
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"  {RED}✗ Configuration error: {e}{RESET}")
        sys.exit(1)

    # ── Step 3: Interactive CV Upload ──
    cv_path = interactive_cv_prompt()

    # ── Step 4: CV Parsing ──
    print(f"\n{BOLD}⚙️  PARSING CV...{RESET}")
    known_skills: list[str] = config.get("known_skills", [])
    parser = CVParser(known_skills=known_skills if known_skills else None)

    try:
        profile = parser.load(cv_path)
    except Exception as e:
        print(f"  {RED}✗ Error parsing CV: {e}{RESET}")
        sys.exit(1)

    # ── Step 5: Skills Confirmation ──
    display_profile_summary(profile)
    profile = confirm_profile(profile)

    # ── Step 6: Target Job Area Selection ──
    area_filters = select_job_areas(config)

    # ── Step 7: Candidate Location Filter ──
    user_location = interactive_location_prompt(config)

    # ── Step 8: Multi-Source Job Fetching ──
    print(f"\n{BOLD}🌐 FETCHING JOBS FROM ALL SOURCES...{RESET}")
    print(f"{DIM}{'─' * 50}{RESET}")

    fetcher = JobFetcher(config, area_filters=area_filters)
    try:
        all_offers = fetcher.fetch_all()
    except Exception as e:
        print(f"  {RED}✗ Critical error during fetch: {e}{RESET}")
        sys.exit(1)

    total_fetched = len(all_offers)
    print(f"\n  {GREEN}✓ Total raw jobs fetched: {BOLD}{total_fetched}{RESET}")

    if total_fetched == 0:
        print(f"\n  {YELLOW}⚠  No jobs retrieved. Please verify your internet connection.{RESET}")
        sys.exit(0)

    # ── Step 9: Historical Duplicate Scan & Exclusion ──
    print(f"\n{BOLD}🔍 SCANNING HISTORICAL ARCHIVE FOR DUPLICATES...{RESET}")
    print(f"{DIM}{'─' * 50}{RESET}")

    reporter = Reporter()
    csv_config_path = Path(config.get("output_csv_path", "results/job_matches.csv"))
    results_dir = csv_config_path.parent

    seen_urls = reporter.get_seen_urls(str(results_dir))
    print(f"  [OK] Historical jobs previously recorded: {BOLD}{len(seen_urls)}{RESET}")

    new_offers = [o for o in all_offers if o.url not in seen_urls]
    skipped_duplicates = len(all_offers) - len(new_offers)

    if skipped_duplicates > 0:
        print(f"  [INFO] Skipped {YELLOW}{skipped_duplicates}{RESET} duplicates already saved in previous runs.")
        print(f"  [OK] New unique jobs to evaluate: {BOLD}{len(new_offers)}{RESET}")
    else:
        print(f"  [OK] No duplicates found. All offers are new.")

    # ── Step 10: Hard Filtering, Location Matching & Composite Scoring ──
    print(f"\n{BOLD}🎯 HARD FILTERING, LOCATION MATCHING & SCORING...{RESET}")
    print(f"{DIM}{'─' * 50}{RESET}")

    matcher = JobMatcher(config)
    results = matcher.process(new_offers, profile.skills, user_location=user_location)

    # ── Step 11: Reports Generation ──
    print(f"\n{BOLD}📊 GENERATING REPORTS...{RESET}")
    print(f"{DIM}{'─' * 50}{RESET}")

    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_filename = f"job_matches_{timestamp}.csv"
    new_csv_path = results_dir / new_filename

    try:
        full_csv_path = reporter.save_csv(results, str(new_csv_path))
        print(f"  [OK] Timestamped CSV saved: {full_csv_path}{RESET}")
    except Exception as e:
        print(f"  [ERR] Error saving CSV: {e}{RESET}")

    # Terminal report
    reporter.print_terminal_report(
        results,
        total_fetched=total_fetched,
    )

    # Telegram summary dispatch
    from remote_job_hunter.telegram_notifier import TelegramNotifier
    tg_notifier = TelegramNotifier(config)
    if tg_notifier.is_configured and config.get("telegram_settings", {}).get("notify_on_matches", True):
        tg_notifier.send_match_summary(
            total_matched=len(results),
            top_offers=results,
            csv_path=str(full_csv_path) if "full_csv_path" in locals() else "",
        )
        print(f"\n  {GREEN}✓ Telegram summary alert & CSV sent to your Telegram chat!{RESET}")

    # ── Step 12: Automated & Assisted Application Assistant ──
    if results:
        print(f"\n{BOLD}🚀 AUTOMATED & ASSISTED APPLICATION DISPATCH{RESET}")
        print(f"{DIM}{'─' * 50}{RESET}")
        print(f"  The assistant can generate tailored AI cover letters, autofill standard ATS forms,")
        print(f"  and provide direct 1-click links for jobs requiring manual completion (CAPTCHAs/custom questions).")
        print()

        try:
            apply_choice = input(
                f"  {CYAN}➜{RESET} Launch application assistant for top matches? [{GREEN}Y{RESET}/N]: "
            ).strip().upper()
        except (EOFError, KeyboardInterrupt):
            print(f"\n  {RED}Skipping application assistant.{RESET}")
            apply_choice = "N"

        if apply_choice in ("Y", "YES", "", "S", "SI"):
            app_orchestrator = ApplicationOrchestrator(config)
            app_results = app_orchestrator.process_applications(results, max_applications=10)

            app_log_filename = f"application_log_{timestamp}.csv"
            app_log_path = results_dir / app_log_filename
            saved_log_path = app_orchestrator.save_application_log(app_results, str(app_log_path))
            print(f"\n  {GREEN}✓ Application summary log saved to: {saved_log_path}{RESET}\n")


if __name__ == "__main__":
    main()
