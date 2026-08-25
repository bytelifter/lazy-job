"""
cv_parser.py — Modulo per il parsing del CV e l'estrazione delle competenze.

Supporta file PDF (.pdf), testo (.txt) e JSON (.json).
Estrae automaticamente le competenze tecniche tramite pattern matching
e le normalizza in una lista di stringhe pulite.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class UserProfile:
    """Profilo utente estratto dal CV."""

    skills: list[str] = field(default_factory=list)
    experience_years: int | None = None
    raw_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serializza il profilo in un dizionario."""
        return {
            "skills": self.skills,
            "experience_years": self.experience_years,
        }


class CVParser:
    """Parser per file CV con estrazione automatica delle competenze."""

    SUPPORTED_EXTENSIONS: set[str] = {".pdf", ".txt", ".json"}

    def __init__(self, known_skills: list[str] | None = None) -> None:
        """
        Inizializza il parser con la lista di skill conosciute.

        Args:
            known_skills: Lista di competenze da cercare nel testo.
                          Se None, usa un set di default.
        """
        self._known_skills: list[str] = known_skills or self._default_skills()

    @staticmethod
    def _default_skills() -> list[str]:
        """Restituisce un set di competenze tecniche di default."""
        return [
            "python", "sql", "pandas", "numpy", "excel",
            "git", "api", "rest", "json", "xml", "csv",
            "selenium", "scrapy", "beautifulsoup", "requests",
            "flask", "fastapi", "django", "automation",
            "web scraping", "data analysis", "etl",
            "aws", "gcp", "azure", "docker", "linux",
            "bash", "powershell", "javascript", "typescript",
        ]

    def load(self, file_path: str) -> UserProfile:
        """
        Carica e analizza un file CV.

        Args:
            file_path: Percorso del file CV.

        Returns:
            UserProfile con le competenze estratte.

        Raises:
            FileNotFoundError: Se il file non esiste.
            ValueError: Se l'estensione non è supportata.
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        extension = path.suffix.lower()
        if extension not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported extension '{extension}'. "
                f"Accepted formats: {', '.join(sorted(self.SUPPORTED_EXTENSIONS))}"
            )

        if extension == ".pdf":
            return self._parse_pdf(path)
        elif extension == ".txt":
            return self._parse_txt(path)
        elif extension == ".json":
            return self._parse_json(path)
        else:
            raise ValueError(f"Unsupported format: {extension}")

    def _parse_pdf(self, path: Path) -> UserProfile:
        """
        Estrae testo da un file PDF usando pdfplumber.

        Args:
            path: Percorso del file PDF.

        Returns:
            UserProfile con le competenze estratte dal PDF.
        """
        try:
            import pdfplumber
        except ImportError:
            raise ImportError(
                "The 'pdfplumber' library is required for PDF files. "
                "Install it via: pip install pdfplumber"
            )

        text_parts: list[str] = []

        try:
            with pdfplumber.open(path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
        except Exception as e:
            raise RuntimeError(f"Error reading PDF '{path}': {e}") from e

        full_text = "\n".join(text_parts)
        if not full_text.strip():
            print(f"  [WARN] No text could be extracted from PDF '{path.name}'.")

        skills = self._extract_skills(full_text)
        experience = self._extract_experience(full_text)

        return UserProfile(
            skills=skills,
            experience_years=experience,
            raw_text=full_text,
        )

    def _parse_txt(self, path: Path) -> UserProfile:
        """
        Legge un file di testo e ne estrae le competenze.

        Args:
            path: Percorso del file TXT.

        Returns:
            UserProfile con le competenze estratte dal testo.
        """
        try:
            full_text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                full_text = path.read_text(encoding="latin-1")
            except Exception as e:
                raise RuntimeError(
                    f"Errore nella lettura del file '{path}': {e}"
                ) from e

        skills = self._extract_skills(full_text)
        experience = self._extract_experience(full_text)

        return UserProfile(
            skills=skills,
            experience_years=experience,
            raw_text=full_text,
        )

    def _parse_json(self, path: Path) -> UserProfile:
        """
        Legge un file JSON strutturato come profilo utente.

        Formato atteso:
        {
            "skills": ["python", "sql", ...],
            "experience_years": 5
        }

        Args:
            path: Percorso del file JSON.

        Returns:
            UserProfile costruito dai dati JSON.
        """
        try:
            raw = path.read_text(encoding="utf-8")
            data: dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f"Il file JSON '{path}' non è valido: {e}") from e
        except Exception as e:
            raise RuntimeError(
                f"Errore nella lettura del file '{path}': {e}"
            ) from e

        skills_raw: list[str] = data.get("skills", [])
        skills = [s.strip().lower() for s in skills_raw if isinstance(s, str) and s.strip()]

        experience: int | None = data.get("experience_years")
        if experience is not None:
            try:
                experience = int(experience)
            except (ValueError, TypeError):
                experience = None

        return UserProfile(
            skills=skills,
            experience_years=experience,
            raw_text=json.dumps(data, indent=2),
        )

    def _extract_skills(self, text: str) -> list[str]:
        """
        Estrae le competenze dal testo tramite pattern matching.

        Cerca ciascuna skill nota nel testo come parola intera
        (case-insensitive) e restituisce le corrispondenze uniche.

        Args:
            text: Testo completo del CV.

        Returns:
            Lista ordinata di competenze trovate (lowercase).
        """
        text_lower = text.lower()
        found: set[str] = set()

        for skill in self._known_skills:
            # Per skill multi-parola, cerca la frase esatta
            # Per skill singola, cerca come parola intera (word boundary)
            skill_lower = skill.lower()
            if " " in skill_lower:
                if skill_lower in text_lower:
                    found.add(skill_lower)
            else:
                pattern = rf"\b{re.escape(skill_lower)}\b"
                if re.search(pattern, text_lower):
                    found.add(skill_lower)

        return sorted(found)

    def _extract_experience(self, text: str) -> int | None:
        """
        Tenta di estrarre gli anni di esperienza dal testo.

        Cerca pattern come "5 years of experience", "5+ anni", ecc.

        Args:
            text: Testo completo del CV.

        Returns:
            Numero di anni se trovato, None altrimenti.
        """
        patterns: list[str] = [
            r"(\d{1,2})\+?\s*(?:years?|anni|ans)\s*(?:of\s+)?(?:experience|esperienza|expérience)",
            r"(?:experience|esperienza|expérience)\s*(?:of\s+)?(\d{1,2})\+?\s*(?:years?|anni|ans)",
            r"(\d{1,2})\+?\s*(?:years?|anni)\s*(?:in\s+(?:the\s+)?(?:field|industry|sector))",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return int(match.group(1))
                except (ValueError, IndexError):
                    continue

        return None
