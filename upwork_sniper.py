#!/usr/bin/env python3
"""
upwork_sniper.py — Root CLI entrypoint for the Upwork Gig Sniper.

Usage:
  python upwork_sniper.py          # Runs a single scan and alerts Telegram with new gigs
  python upwork_sniper.py --loop   # Runs continuous monitoring loop every 15 minutes
"""

import sys
from main import load_config
from remote_job_hunter.upwork_sniper import UpworkSniper

def main() -> None:
    config = load_config()
    sniper = UpworkSniper(config)

    if "--loop" in sys.argv or "-l" in sys.argv or "--daemon" in sys.argv:
        sniper.run_loop()
    else:
        sniper.run_once()

if __name__ == "__main__":
    main()
