"""
fetcher.py — Modulo per il recupero parallelo di offerte di lavoro
da API pubbliche e feed RSS.

Fonti integrate:
1. Remotive API
2. Himalayas Jobs API
3. Jobicy API
4. We Work Remotely RSS
"""

from __future__ import annotations

import html
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class JobOffer:
    """Rappresenta un'offerta di lavoro normalizzata da qualsiasi fonte."""

    title: str = ""
    company: str = ""
    url: str = ""
    description: str = ""
    job_type: str = ""
    salary: str = ""
    location: str = ""
    source: str = ""
    tags: list[str] = field(default_factory=list)
    pub_date: str = ""


class JobFetcher:
    """
    Aggregatore multi-sorgente per offerte di lavoro remoto.

    Esegue fetch paralleli da tutte le API configurate,
    con gestione robusta di timeout, retry e fallimenti parziali.
    """

    DEFAULT_HEADERS: dict[str, str] = {
        "User-Agent": (
            "LazyJobHunter/1.0 "
            "(Automated Remote Job Aggregator; Python/requests)"
        ),
        "Accept": "application/json",
    }

    def __init__(self, config: dict[str, Any], area_filters: dict[str, Any] | None = None) -> None:
        """
        Inizializza il fetcher con la configurazione e i filtri per area.

        Args:
            config: Dizionario di configurazione da config.json.
            area_filters: Filtri per area generati da merge delle aree selezionate.
                          Struttura: {
                              "remotive_category": str | None,
                              "jobicy_tag": str | None,
                              "himalayas_keywords": list[str],
                              "rss_feeds": dict[str, str],
                          }
        """
        self._config = config
        self._endpoints: dict[str, str] = config.get("api_endpoints", {})
        self._timeout: int = config.get("fetch_timeout_seconds", 15)
        self._max_retries: int = config.get("max_retries", 3)
        self._keywords: list[str] = config.get("search_keywords", [])

        # Filtri area-specifici
        if area_filters:
            self._remotive_category: str | None = area_filters.get("remotive_category")
            self._jobicy_tag: str | None = area_filters.get("jobicy_tag")
            self._himalayas_keywords: list[str] = area_filters.get("himalayas_keywords") or self._keywords[:5]
            self._rss_feeds: dict[str, str] = area_filters.get("rss_feeds", {})
        else:
            # Fallback: tutti i feed di default, nessun filtro categoria
            self._remotive_category = None
            self._jobicy_tag = None
            self._himalayas_keywords = self._keywords[:5] or ["python remote"]
            self._rss_feeds = config.get("rss_feeds_all", config.get("rss_feeds", {}))

        self._jobspy_config: dict[str, Any] = config.get("jobspy_settings", {})
        self._jobspy_enabled: bool = self._jobspy_config.get("enabled", True)

    def fetch_all(self) -> list[JobOffer]:
        """
        Recupera offerte da tutte le fonti in parallelo (Remotive, Himalayas, Jobicy, WWR RSS, LinkedIn, Indeed).

        Returns:
            Lista aggregata di JobOffer da tutte le fonti.
        """
        import requests  # noqa: F811 — imported here to keep module-level imports clean

        self._session = requests.Session()
        self._session.headers.update(self.DEFAULT_HEADERS)

        all_offers: list[JobOffer] = []
        tasks: dict[str, Any] = {}

        with ThreadPoolExecutor(max_workers=5) as executor:
            tasks["Remotive"] = executor.submit(self._fetch_remotive)
            tasks["Himalayas"] = executor.submit(self._fetch_himalayas)
            tasks["Jobicy"] = executor.submit(self._fetch_jobicy)
            tasks["WWR RSS"] = executor.submit(self._fetch_wwr_rss)

            if self._jobspy_enabled:
                tasks["LinkedIn & Indeed (JobSpy)"] = executor.submit(self._fetch_jobspy)

            for source_name, future in tasks.items():
                try:
                    result = future.result(timeout=75)
                    all_offers.extend(result)
                    print(f"  [OK] {source_name}: {len(result)} jobs retrieved")
                except Exception as e:
                    print(f"  [ERR] {source_name}: error - {e}")

        self._session.close()
        return all_offers

    # ──────────────────────────────────────────────
    #  REMOTIVE
    # ──────────────────────────────────────────────

    def _fetch_remotive(self) -> list[JobOffer]:
        """
        Recupera offerte dall'API Remotive.

        Endpoint: GET https://remotive.com/api/remote-jobs[?category=slug]

        Returns:
            Lista di JobOffer normalizzate.
        """
        url = self._endpoints.get("remotive", "https://remotive.com/api/remote-jobs")
        params: dict[str, Any] = {}
        if self._remotive_category:
            params["category"] = self._remotive_category
        data = self._http_get_json(url, params=params if params else None)

        if not data:
            return []

        jobs_raw: list[dict[str, Any]] = data.get("jobs", [])
        offers: list[JobOffer] = []

        for job in jobs_raw:
            try:
                offer = JobOffer(
                    title=str(job.get("title", "")).strip(),
                    company=str(job.get("company_name", "")).strip(),
                    url=str(job.get("url", "")).strip(),
                    description=self._clean_html(str(job.get("description", ""))),
                    job_type=str(job.get("job_type", "")).strip(),
                    salary=str(job.get("salary", "")).strip(),
                    location=str(job.get("candidate_required_location", "")).strip(),
                    source="Remotive",
                    tags=[str(t).lower() for t in job.get("tags", []) if t],
                    pub_date=str(job.get("publication_date", "")).strip(),
                )
                if offer.title:
                    offers.append(offer)
            except Exception:
                continue

        return offers

    # ──────────────────────────────────────────────
    #  HIMALAYAS
    # ──────────────────────────────────────────────

    def _fetch_himalayas(self) -> list[JobOffer]:
        """
        Recupera offerte dall'API Himalayas Jobs.

        Esegue una query per ciascuna keyword area-specifica.
        Endpoint: GET https://himalayas.app/jobs/api/search?q={keyword}&limit=N

        Returns:
            Lista di JobOffer normalizzate (deduplicate per URL).
        """
        base_url = self._endpoints.get(
            "himalayas", "https://himalayas.app/jobs/api/search"
        )
        limit = self._config.get("himalayas_limit", 50)
        seen_urls: set[str] = set()
        offers: list[JobOffer] = []

        # Usa le keyword area-specifiche (già limitate nel costruttore)
        keywords_to_search = self._himalayas_keywords or ["python remote"]

        for keyword in keywords_to_search:
            params = {"q": keyword, "limit": limit}
            data = self._http_get_json(base_url, params=params)

            if not data:
                continue

            jobs_raw: list[dict[str, Any]] = data.get("jobs", [])

            for job in jobs_raw:
                try:
                    app_link = str(job.get("applicationLink", job.get("guid", ""))).strip()

                    if app_link in seen_urls:
                        continue
                    seen_urls.add(app_link)

                    emp_type = str(job.get("employmentType", "")).strip()
                    categories = [str(c) for c in job.get("categories", []) if c]
                    seniority = [str(s) for s in job.get("seniority", []) if s]
                    loc_restrictions = [str(l) for l in job.get("locationRestrictions", []) if l]

                    salary_str = ""
                    min_sal = job.get("minSalary")
                    max_sal = job.get("maxSalary")
                    currency = job.get("currency", "")
                    period = job.get("salaryPeriod", "")
                    if min_sal or max_sal:
                        parts = []
                        if currency:
                            parts.append(str(currency))
                        if min_sal:
                            parts.append(str(min_sal))
                        if max_sal:
                            parts.append(f"- {max_sal}")
                        if period:
                            parts.append(f"/{period}")
                        salary_str = " ".join(parts)

                    offer = JobOffer(
                        title=str(job.get("title", "")).strip(),
                        company=str(job.get("companyName", "")).strip(),
                        url=app_link,
                        description=self._clean_html(str(job.get("description", ""))),
                        job_type=emp_type,
                        salary=salary_str,
                        location=", ".join(loc_restrictions) if loc_restrictions else "Worldwide",
                        source="Himalayas",
                        tags=[c.lower().replace("-", " ") for c in categories] + [s.lower() for s in seniority],
                        pub_date=self._timestamp_to_date(job.get("pubDate")),
                    )
                    if offer.title:
                        offers.append(offer)
                except Exception:
                    continue

            # Small delay between keyword queries to be polite
            time.sleep(0.3)

        return offers

    # ──────────────────────────────────────────────
    #  JOBICY
    # ──────────────────────────────────────────────

    def _fetch_jobicy(self) -> list[JobOffer]:
        """
        Recupera offerte dall'API Jobicy.

        Endpoint: GET https://jobicy.com/api/v2/remote-jobs?count=N[&tag=area]
        Nota: il parametro geo=all causa HTTP 400, quindi omesso.

        Returns:
            Lista di JobOffer normalizzate.
        """
        base_url = self._endpoints.get(
            "jobicy", "https://jobicy.com/api/v2/remote-jobs"
        )
        count = self._config.get("jobicy_count", 50)
        params: dict[str, Any] = {"count": count}
        if self._jobicy_tag:
            params["tag"] = self._jobicy_tag

        data = self._http_get_json(base_url, params=params)

        if not data:
            return []

        jobs_raw: list[dict[str, Any]] = data.get("jobs", [])
        offers: list[JobOffer] = []

        for job in jobs_raw:
            try:
                job_types = job.get("jobType", [])
                if isinstance(job_types, list):
                    job_type_str = ", ".join(str(t) for t in job_types)
                else:
                    job_type_str = str(job_types)

                industries = job.get("jobIndustry", [])
                if isinstance(industries, list):
                    industry_tags = [str(i).lower() for i in industries]
                else:
                    industry_tags = [str(industries).lower()] if industries else []

                offer = JobOffer(
                    title=str(job.get("jobTitle", "")).strip(),
                    company=str(job.get("companyName", "")).strip(),
                    url=str(job.get("url", "")).strip(),
                    description=self._clean_html(str(job.get("jobDescription", ""))),
                    job_type=job_type_str,
                    salary="",
                    location=str(job.get("jobGeo", "")).strip(),
                    source="Jobicy",
                    tags=industry_tags,
                    pub_date=str(job.get("pubDate", "")).strip(),
                )
                if offer.title:
                    offers.append(offer)
            except Exception:
                continue

        return offers

    # ──────────────────────────────────────────────
    #  WE WORK REMOTELY RSS
    # ──────────────────────────────────────────────

    def _fetch_wwr_rss(self) -> list[JobOffer]:
        """
        Recupera offerte dai feed RSS di We Work Remotely.

        Utilizza feedparser per il parsing XML/RSS.

        Returns:
            Lista di JobOffer normalizzate.
        """
        try:
            import feedparser
        except ImportError:
            print("  [WARN] feedparser is not installed. Skipping WWR RSS.")
            return []

        offers: list[JobOffer] = []
        seen_urls: set[str] = set()

        # _rss_feeds è già stato filtrato per area nel costruttore
        for feed_name, feed_url in self._rss_feeds.items():
            try:
                feed = feedparser.parse(feed_url)

                if feed.bozo and not feed.entries:
                    continue

                for entry in feed.entries:
                    try:
                        link = str(entry.get("link", "")).strip()
                        if link in seen_urls:
                            continue
                        seen_urls.add(link)

                        title = str(entry.get("title", "")).strip()
                        summary = self._clean_html(str(entry.get("summary", entry.get("description", ""))))

                        # WWR titles often contain company: "Company: Job Title"
                        company = ""
                        if ":" in title:
                            parts = title.split(":", 1)
                            company = parts[0].strip()

                        pub_date = ""
                        if entry.get("published"):
                            pub_date = str(entry.get("published", ""))

                        offer = JobOffer(
                            title=title,
                            company=company,
                            url=link,
                            description=summary,
                            job_type="",
                            salary="",
                            location="Remote",
                            source="We Work Remotely",
                            tags=[feed_name.replace("wwr_", "").lower()],
                            pub_date=pub_date,
                        )
                        if offer.title:
                            offers.append(offer)
                    except Exception:
                        continue

            except Exception:
                continue

        return offers

    # ──────────────────────────────────────────────
    #  HTTP HELPERS
    # ──────────────────────────────────────────────

    def _http_get_json(
        self,
        url: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """
        Esegue una richiesta GET con retry e gestione errori.

        Args:
            url: URL dell'endpoint.
            params: Parametri query string.

        Returns:
            Dizionario JSON della risposta, o None in caso di errore.
        """
        import requests

        last_error: Exception | None = None

        for attempt in range(1, self._max_retries + 1):
            try:
                response = requests.get(
                    url,
                    params=params,
                    headers=self.DEFAULT_HEADERS,
                    timeout=self._timeout,
                    allow_redirects=True,
                )
                response.raise_for_status()
                return response.json()

            except requests.exceptions.Timeout:
                last_error = TimeoutError(f"Timeout dopo {self._timeout}s")
            except requests.exceptions.HTTPError as e:
                last_error = e
                # Non fare retry su errori client (4xx) tranne 429
                if response.status_code != 429 and 400 <= response.status_code < 500:
                    break
            except requests.exceptions.ConnectionError as e:
                last_error = e
            except requests.exceptions.JSONDecodeError as e:
                last_error = e
                break  # Se il JSON non è valido, non serve riprovare
            except Exception as e:
                last_error = e

            if attempt < self._max_retries:
                wait = 2 ** attempt  # Exponential backoff: 2, 4, 8 seconds
                time.sleep(wait)

        return None

    @staticmethod
    def _clean_html(text: str) -> str:
        """
        Rimuove i tag HTML e decodifica le entità.

        Args:
            text: Testo potenzialmente contenente HTML.

        Returns:
            Testo pulito senza tag HTML.
        """
        # Remove HTML tags
        clean = re.sub(r"<[^>]+>", " ", text)
        # Decode HTML entities
        clean = html.unescape(clean)
        # Normalize whitespace
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean

    @staticmethod
    def _timestamp_to_date(timestamp: Any) -> str:
        """
        Converte un timestamp Unix in una stringa data.

        Args:
            timestamp: Timestamp Unix (int o float).

        Returns:
            Stringa nel formato YYYY-MM-DD, o stringa vuota se non valido.
        """
        if timestamp is None:
            return ""
        try:
            dt = datetime.fromtimestamp(int(timestamp))
            return dt.strftime("%Y-%m-%d")
        except (ValueError, TypeError, OSError):
            return str(timestamp)

    # ──────────────────────────────────────────────
    #  JOBSPY (LinkedIn, Indeed, Glassdoor, ZipRecruiter)
    # ──────────────────────────────────────────────

    def _fetch_jobspy(self) -> list[JobOffer]:
        """
        Recupera offerte in tempo reale da LinkedIn, Indeed, Glassdoor e ZipRecruiter
        utilizzando la libreria python-jobspy.

        Returns:
            Lista di JobOffer normalizzate.
        """
        if not self._jobspy_enabled:
            return []

        try:
            from jobspy import scrape_jobs
        except ImportError:
            return []

        sites = self._jobspy_config.get("sites", ["linkedin", "indeed", "glassdoor"])
        results_wanted = int(self._jobspy_config.get("results_wanted_per_search", 20))
        search_terms = self._himalayas_keywords[:2] or ["python remote", "data analyst remote"]

        offers: list[JobOffer] = []
        seen_urls: set[str] = set()

        for term in search_terms:
            try:
                df = scrape_jobs(
                    site_name=sites,
                    search_term=f"{term} remote",
                    location="Italy",
                    is_remote=True,
                    results_wanted=results_wanted,
                    hours_old=168,
                )

                if df is None or df.empty:
                    continue

                for _, row in df.iterrows():
                    url = str(row.get("job_url", "")).strip()
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)

                    # Build salary string
                    min_amt = row.get("min_amount")
                    max_amt = row.get("max_amount")
                    interval = str(row.get("interval", "")).lower()
                    salary_str = ""
                    if min_amt is not None and not (isinstance(min_amt, float) and str(min_amt) == "nan"):
                        try:
                            min_val = int(min_amt)
                            if max_amt is not None and not (isinstance(max_amt, float) and str(max_amt) == "nan"):
                                max_val = int(max_amt)
                                salary_str = f"${min_val:,} - ${max_val:,} /{interval}".strip()
                            else:
                                salary_str = f"${min_val:,} /{interval}".strip()
                        except (ValueError, TypeError):
                            pass

                    site_source = str(row.get("site", "JobSpy")).capitalize()

                    offer = JobOffer(
                        title=str(row.get("title", "")).strip(),
                        company=str(row.get("company", "")).strip(),
                        url=url,
                        description=self._clean_html(str(row.get("description", ""))),
                        job_type=str(row.get("job_type", "contract")).strip(),
                        salary=salary_str,
                        location=str(row.get("location", "Remote")).strip(),
                        source=site_source,
                        tags=[term.lower(), "remote", "linkedin/indeed"],
                        pub_date=str(row.get("date_posted", ""))[:10],
                    )
                    if offer.title and offer.company:
                        offers.append(offer)

            except Exception:
                continue

        return offers
