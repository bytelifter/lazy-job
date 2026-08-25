"""
matcher.py — Modulo per il filtraggio rigido e lo scoring delle offerte.

Applica una pipeline di filtri sequenziali:
1. Filtro parole chiave bloccanti (ibrido, on-site, ecc.)
2. Filtro esclusivo contractor/freelance
3. Scoring basato su skill match, settore target e valore economico
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .fetcher import JobOffer


@dataclass
class ScoredOffer:
    """Offerta con punteggio di match e metadati di scoring."""

    # Dati dall'offerta originale
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

    # Risultati dello scoring
    match_score: int = 0
    matched_skills: list[str] = field(default_factory=list)
    sector: str = "General"
    is_high_value: bool = False

    # Automatable & Delegation Index (Take the bag without manual labor)
    automatability_score: int = 0
    automation_strategy: str = "Standard implementation"
    is_highly_automatable: bool = False

    @classmethod
    def from_job_offer(cls, offer: JobOffer, **scoring_kwargs: Any) -> ScoredOffer:
        """
        Crea un ScoredOffer da un JobOffer esistente.

        Args:
            offer: L'offerta originale.
            **scoring_kwargs: Campi di scoring aggiuntivi.

        Returns:
            Nuova istanza ScoredOffer.
        """
        return cls(
            title=offer.title,
            company=offer.company,
            url=offer.url,
            description=offer.description,
            job_type=offer.job_type,
            salary=offer.salary,
            location=offer.location,
            source=offer.source,
            tags=offer.tags,
            pub_date=offer.pub_date,
            **scoring_kwargs,
        )


class JobMatcher:
    """
    Motore di filtraggio e scoring per offerte di lavoro.

    Applica filtri rigidi (blocked, contractor-only, remote-only)
    e poi assegna un punteggio composito basato su:
    - Corrispondenza skill (0-60 punti)
    - Settore target (0-20 punti)
    - Valore economico (0-20 punti)
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """
        Inizializza il matcher con la configurazione.

        Args:
            config: Dizionario di configurazione da config.json.
        """
        self._config = config
        self._blocked: list[str] = [
            kw.lower() for kw in config.get("blocked_keywords", [])
        ]
        self._contractor_kw: list[str] = [
            kw.lower() for kw in config.get("contractor_keywords", [])
        ]
        self._contractor_types: list[str] = [
            t.lower() for t in config.get("contractor_type_values", [])
        ]
        self._target_sectors: dict[str, list[str]] = config.get("target_sectors", {})
        self._high_value: dict[str, Any] = config.get("high_value_indicators", {})
        self._min_score: int = config.get("min_match_score", 40)

        # Geographic config
        self._geo_config: dict[str, Any] = config.get("geographic_regions", {})
        self._worldwide_terms: list[str] = [
            t.lower() for t in self._geo_config.get("worldwide_terms", ["worldwide", "anywhere", "global", "remote"])
        ]
        self._regions_map: dict[str, list[str]] = {
            k.lower(): [v.lower() for v in vals]
            for k, vals in self._geo_config.get("regions", {}).items()
        }

        # Automatable / Delegation configuration
        self._auto_indicators: dict[str, Any] = config.get("automatable_indicators", {})
        self._manual_penalties: dict[str, Any] = config.get("manual_work_penalties", {})

    def process(
        self,
        offers: list[JobOffer],
        user_skills: list[str],
        user_location: str | None = None,
    ) -> list[ScoredOffer]:
        """
        Esegue l'intera pipeline di filtraggio e scoring.

        Args:
            offers: Lista grezza di offerte da tutte le fonti.
            user_skills: Lista delle competenze dell'utente (lowercase).
            user_location: Posizione/paese dell'utente per il filtro geografico.

        Returns:
            Lista di ScoredOffer ordinata per match_score decrescente.
        """
        # Step 1: Blocked keywords filter
        filtered = self._filter_blocked(offers)
        blocked_count = len(offers) - len(filtered)

        # Step 2: Contractor-only filter
        contractor_filtered = self._filter_contractor_only(filtered)
        non_contractor_count = len(filtered) - len(contractor_filtered)

        # Step 3: Geographic location compatibility filter
        geo_filtered = self._filter_location(contractor_filtered, user_location)
        geo_excluded_count = len(contractor_filtered) - len(geo_filtered)

        # Step 4: Scoring
        scored = self._score_and_rank(geo_filtered, user_skills)

        # Step 5: Min score filter
        final = self._apply_min_score(scored)
        below_score_count = len(scored) - len(final)

        # Filtering stats
        print(f"\n  📊 Filtering Pipeline Stats:")
        print(f"     Total raw offers received:   {len(offers)}")
        print(f"     Discarded (blocked/on-site): {blocked_count}")
        print(f"     Discarded (non-contractor):  {non_contractor_count}")
        print(f"     Discarded (incompatible geo):{geo_excluded_count} (User location: {user_location or 'Worldwide'})")
        print(f"     Below score threshold ({self._min_score}):  {below_score_count}")
        print(f"     ✅ Final matched offers:     {len(final)}")

        return final

    def _filter_location(
        self,
        offers: list[JobOffer],
        user_location: str | None,
    ) -> list[JobOffer]:
        """
        Filtra le offerte in base alla compatibilità geografica.
        Se il candidato è in Italia/Europa:
        - Accetta: Worldwide, Anywhere, Global, Europe, EU, EMEA, Italy, o senza restrizioni.
        - Esclude: US Only, Canada only, LATAM only, APAC only, Spain only, ecc.

        Args:
            offers: Lista di offerte filtrate per tipo.
            user_location: Paese o regione dell'utente (es. 'Italy', 'Europe', 'Worldwide').

        Returns:
            Lista di offerte geograficamente compatibili con l'utente.
        """
        if not user_location:
            return offers

        loc_clean = user_location.strip().lower()
        if loc_clean in ("worldwide", "anywhere", "all", "global", "any", ""):
            return offers

        # Trova le regioni a cui appartiene il paese dell'utente
        user_regions: set[str] = set()
        user_country_aliases: set[str] = {loc_clean}

        for region_name, country_list in self._regions_map.items():
            if any(loc_clean == c or loc_clean in c for c in country_list):
                user_regions.add(region_name)
                # Aggiungi i termini regionali principali (es. europe, eu, emea)
                if region_name == "europe":
                    user_country_aliases.update(["europe", "eu", "emea", "european union"])
                elif region_name == "north_america":
                    user_country_aliases.update(["north america", "usa", "us", "united states", "america"])
                elif region_name == "latin_america":
                    user_country_aliases.update(["latin america", "latam", "south america"])
                elif region_name == "asia_pacific":
                    user_country_aliases.update(["asia", "pacific", "apac"])

        # Costruisci set di tutti gli altri paesi per rilevare restrizioni esclusive
        other_exclusive_locations: set[str] = set()
        for region_name, country_list in self._regions_map.items():
            if region_name not in user_regions:
                # Se l'utente non è in questa regione, aggiungi il nome regione e i paesi
                if region_name == "north_america":
                    other_exclusive_locations.update(["usa only", "us only", "us/canada", "united states only", "north america"])
                elif region_name == "latin_america":
                    other_exclusive_locations.update(["latam only", "latin america only", "south america"])
                elif region_name == "asia_pacific":
                    other_exclusive_locations.update(["apac only", "asia only", "australia only"])

        result: list[JobOffer] = []

        for offer in offers:
            offer_loc = offer.location.strip().lower()
            offer_text = f"{offer.title} {offer.location}".lower()

            # 1. Controlla se la location menziona direttamente il paese o la macro-regione dell'utente (es. Italy, Europe, EU, EMEA)
            # Gestisce sia singoli paesi che liste tipo "Germany, Italy, France"
            is_explicitly_user_region = False
            for alias in user_country_aliases:
                if len(alias) <= 3:
                    pattern = rf"\b{re.escape(alias)}\b"
                    if re.search(pattern, offer_loc) or re.search(pattern, offer.title.lower()):
                        is_explicitly_user_region = True
                        break
                else:
                    if alias in offer_loc or alias in offer.title.lower():
                        is_explicitly_user_region = True
                        break

            if is_explicitly_user_region:
                result.append(offer)
                continue

            # 2. Se è aperta a tutto il mondo / Anywhere / Global / Remote puro (e non c'è esclusione esplicita di altre regioni)
            is_worldwide = not offer_loc or any(w in offer_loc for w in self._worldwide_terms)
            if is_worldwide:
                # Controlla che non ci sia una restrizione nascosta ad altre regioni (es. "US Only", "LATAM Only")
                if not any(excl in offer_text for excl in other_exclusive_locations):
                    result.append(offer)
                    continue

            # 3. Se la location è specificata per altri paesi/regioni senza menzionare Italy, Europe o Worldwide -> Scarta
            # (es. "South Africa", "Saudi Arabia", "Germany", "France", "United States", "Costa Rica", "Egypt")

        return result

    def _filter_blocked(self, offers: list[JobOffer]) -> list[JobOffer]:
        """
        Rimuove le offerte contenenti parole chiave bloccanti.

        Cerca le keyword bloccanti nel titolo, descrizione,
        tipo di lavoro e location.

        Args:
            offers: Lista di offerte da filtrare.

        Returns:
            Lista filtrata senza offerte bloccate.
        """
        result: list[JobOffer] = []

        for offer in offers:
            searchable = " ".join([
                offer.title,
                offer.description[:2000],  # Limita per performance
                offer.job_type,
                offer.location,
            ]).lower()

            is_blocked = False
            for keyword in self._blocked:
                if keyword in searchable:
                    is_blocked = True
                    break

            if not is_blocked:
                result.append(offer)

        return result

    def _filter_contractor_only(self, offers: list[JobOffer]) -> list[JobOffer]:
        """
        Mantiene solo le offerte aperte a contractor/freelance.

        Verifica tramite:
        1. Il campo job_type contro i valori contractor noti
        2. Presenza di keyword contractor nel titolo o descrizione

        Args:
            offers: Lista di offerte pre-filtrate.

        Returns:
            Lista contenente solo offerte contractor/freelance.
        """
        result: list[JobOffer] = []

        for offer in offers:
            # Check 1: job_type diretto
            job_type_lower = offer.job_type.lower()
            type_match = any(
                ct in job_type_lower for ct in self._contractor_types
            )

            if type_match:
                result.append(offer)
                continue

            # Check 2: keyword nella descrizione e titolo
            searchable = f"{offer.title} {offer.description[:3000]}".lower()
            keyword_match = any(
                kw in searchable for kw in self._contractor_kw
            )

            if keyword_match:
                result.append(offer)

        return result

    def _score_and_rank(
        self,
        offers: list[JobOffer],
        user_skills: list[str],
    ) -> list[ScoredOffer]:
        """
        Calcola il punteggio composito per ogni offerta.

        Componenti del punteggio:
        - Skill Match (0-60): % di skill utente trovate × 60
        - Sector Bonus (0-20): +20 se rientra in un settore target
        - High-Value Bonus (0-20): +20 se indicatori di alto valore

        Args:
            offers: Lista di offerte filtrate.
            user_skills: Competenze dell'utente.

        Returns:
            Lista di ScoredOffer con punteggi assegnati.
        """
        scored: list[ScoredOffer] = []
        user_skills_lower = [s.lower() for s in user_skills]

        for offer in offers:
            searchable = f"{offer.title} {offer.description} {' '.join(offer.tags)}".lower()

            # ── Skill Match Score (0-60) ──
            matched: list[str] = []
            for skill in user_skills_lower:
                if " " in skill:
                    if skill in searchable:
                        matched.append(skill)
                else:
                    pattern = rf"\b{re.escape(skill)}\b"
                    if re.search(pattern, searchable):
                        matched.append(skill)

            if user_skills_lower:
                skill_ratio = len(matched) / len(user_skills_lower)
            else:
                skill_ratio = 0.0
            skill_score = int(skill_ratio * 60)

            # ── Sector Bonus (0-20) ──
            sector_name = "General"
            sector_score = 0
            for sector, keywords in self._target_sectors.items():
                sector_match_count = sum(
                    1 for kw in keywords if kw.lower() in searchable
                )
                if sector_match_count >= 2:
                    sector_name = sector
                    sector_score = 20
                    break
                elif sector_match_count == 1 and sector_score == 0:
                    sector_name = sector
                    sector_score = 10

            # ── High-Value Bonus (0-20) ──
            is_high_value = False
            value_score = 0

            # Check salary string
            salary_value = self._parse_salary_value(offer.salary)
            if salary_value is not None:
                hourly_min = self._high_value.get("hourly_min_usd", 40)
                annual_min = self._high_value.get("annual_min_usd", 70000)

                if salary_value >= annual_min or salary_value >= hourly_min:
                    is_high_value = True
                    value_score = 20

            # Check high-value keywords in description
            if not is_high_value:
                hv_keywords: list[str] = self._high_value.get("keywords", [])
                for hv_kw in hv_keywords:
                    if hv_kw.lower() in searchable:
                        is_high_value = True
                        value_score = 15
                        break

            # Check salary patterns in description
            if not is_high_value:
                salary_patterns: list[str] = self._high_value.get("salary_patterns", [])
                for pattern in salary_patterns:
                    try:
                        if re.search(pattern, searchable):
                            is_high_value = True
                            value_score = 15
                            break
                    except re.error:
                        continue

            # ── Automatable & Delegation Score (0-100) ──
            auto_score, auto_strategy, is_highly_auto = self._calculate_automatability(searchable)

            # ── Total Match Score ──
            total = min(skill_score + sector_score + value_score, 100)

            scored_offer = ScoredOffer.from_job_offer(
                offer,
                match_score=total,
                matched_skills=matched,
                sector=sector_name,
                is_high_value=is_high_value,
                automatability_score=auto_score,
                automation_strategy=auto_strategy,
                is_highly_automatable=is_highly_auto,
            )
            scored.append(scored_offer)

        # Ordina per score decrescente (e prioritizza posizioni altamente automatizzabili)
        scored.sort(key=lambda o: (o.is_highly_automatable, o.match_score), reverse=True)
        return scored

    def _calculate_automatability(self, searchable: str) -> tuple[int, str, bool]:
        """
        Calcola l'indice di automazione e identificazione di lavori scriptabili/delegabili.

        Returns:
            Tuple con (score_0_100, strategia_consigliata, is_highly_automatable).
        """
        score = 15  # Baseline score for software roles
        best_strategy = "Standard asynchronous execution"
        highest_category_weight = 0

        for cat_name, cat_data in self._auto_indicators.items():
            weight = cat_data.get("weight", 20)
            keywords = cat_data.get("keywords", [])
            matches = sum(1 for kw in keywords if kw.lower() in searchable)

            if matches > 0:
                score += min(matches * (weight // 2), weight)
                if weight > highest_category_weight:
                    highest_category_weight = weight
                    best_strategy = cat_data.get("strategy", best_strategy)

        # Apply penalties for meeting-heavy / manual management roles
        penalty_kws = self._manual_penalties.get("keywords", [])
        penalty_val = self._manual_penalties.get("penalty_per_match", 15)
        for pkw in penalty_kws:
            if pkw.lower() in searchable:
                score -= penalty_val

        final_score = max(5, min(score, 100))
        is_highly_auto = final_score >= 50

        return final_score, best_strategy, is_highly_auto

    def _apply_min_score(self, offers: list[ScoredOffer]) -> list[ScoredOffer]:
        """
        Filtra le offerte sotto la soglia minima di punteggio.

        Args:
            offers: Lista di ScoredOffer.

        Returns:
            Lista contenente solo le offerte sopra la soglia.
        """
        return [o for o in offers if o.match_score >= self._min_score]

    @staticmethod
    def _parse_salary_value(salary_str: str) -> float | None:
        """
        Tenta di estrarre un valore numerico dalla stringa salario.

        Gestisce formati come: "$120/hour", "120k", "$80,000 - $100,000",
        "€50/h", "USD 100 - 150 /hourly"

        Args:
            salary_str: Stringa del salario dall'offerta.

        Returns:
            Valore numerico estratto, o None se non parsabile.
        """
        if not salary_str or salary_str.lower() in ("", "none", "n/a"):
            return None

        clean = salary_str.replace(",", "").replace(" ", "").lower()

        # Pattern: "$120/hour" or "€50/h"
        hourly_match = re.search(r"[\$€£](\d+(?:\.\d+)?)\s*/?\s*(?:h|hour|hr|ora)", clean)
        if hourly_match:
            return float(hourly_match.group(1))

        # Pattern: "120k" annual
        k_match = re.search(r"[\$€£]?(\d+)k", clean)
        if k_match:
            return float(k_match.group(1)) * 1000

        # Pattern: "$80000" or "80000-100000"
        num_match = re.findall(r"[\$€£]?(\d{4,})", clean)
        if num_match:
            values = [float(n) for n in num_match]
            return max(values)  # Take the highest value

        # Pattern: just a number like "$120" (likely hourly)
        simple_match = re.search(r"[\$€£](\d{2,3})(?:\s|$|/)", salary_str)
        if simple_match:
            return float(simple_match.group(1))

        return None
