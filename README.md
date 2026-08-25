# LazyJob (LazyJobHunter) 🎯

Automated CLI batch pipeline designed for discovering, filtering, and scoring **high-value remote contractor and freelance positions**.

---

## ✨ Features

- **Interactive CV Ingestion**: Parses your CV (`.pdf`, `.txt`, `.json`) using regex pattern matching and auto-extracts technical skills and years of experience.
- **Multi-Source Parallel Aggregation**: Concurrently queries **Remotive**, **Himalayas**, **Jobicy**, and **We Work Remotely (RSS)** with retry & exponential backoff.
- **Target Area Selection**: Select specific job fields (e.g. *Software Development*, *AI & ML*, *DevOps*, *Data & Analytics*, *Design*, *Marketing*, or *All Areas*).
- **Geographic Compatibility Filter**: Automatically filters out jobs geographically restricted to regions outside your location (e.g., permits *Worldwide*, *Europe/EU*, or *Italy*, while excluding *US-Only* or *LATAM-Only* if you're in Europe).
- **Hard Contractor Filtering**: Strictly includes Contractor / Freelance / B2B positions, discarding permanent on-site/hybrid listings.
- **Smart Composite Scoring**: Scores jobs from 0 to 100 based on:
  - Skill overlap (0–60 pts)
  - Sector relevance (0–20 pts)
  - High-value budget/salary indicators (0–20 pts)
- **Automatic De-duplication**: Scans previous search outputs to exclude already discovered listings.
- **Export & Terminal Reporting**:
  - Timestamped Excel-compatible CSV output (`results/job_matches_YYYYMMDD_HHMMSS.csv`)
  - ANSI colored terminal report with statistics breakdown

---

## 🚀 Getting Started

### 1. Prerequisites

Ensure you have Python 3.9+ installed.

### 2. Installation

Clone the repository and install dependencies:

```bash
git clone https://github.com/bytelifter/lazy-job.git
cd lazy-job
pip install -r requirements.txt
```

### 3. Usage

Run the main pipeline:

```bash
python main.py
```

Follow the interactive prompts:
1. Provide the path to your CV (e.g., `test_cv.txt` or `my_cv.pdf`).
2. Review and confirm/modify detected skills.
3. Select your target job area(s).
4. Enter your location (e.g., `Italy`, `United States`, or `Worldwide`).

---

## ⚙️ Configuration

All endpoints, keywords, sector definitions, salary thresholds, and geographic mappings are fully customizable in [`remote_job_hunter/config.json`](remote_job_hunter/config.json).

---

## 📄 License

MIT License. Feel free to use and customize for your own job hunting automation!
