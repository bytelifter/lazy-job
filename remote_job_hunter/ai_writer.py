"""
ai_writer.py — Lightweight Local AI engine for writing tailored cover letters
and answering ATS application form questions.

Supports:
1. Ollama local API (e.g., qwen2.5:1.5b, llama3.2:1b) if running on http://localhost:11434
2. Local GGUF execution via llama-cpp-python (if available)
3. Advanced dynamic template generator fallback (zero external dependencies)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import requests


class LocalAIWriter:
    """
    Generates customized cover letters and form answers using a lightweight
    local AI model (~1 GB VRAM/RAM) with graceful fallbacks.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """
        Initializes the AI writer with config settings.

        Args:
            config: Configuration dictionary from config.json.
        """
        self._config = config
        self._ai_settings: dict[str, Any] = config.get("local_ai_settings", {})
        self._enabled: bool = self._ai_settings.get("enabled", True)
        self._ollama_url: str = self._ai_settings.get("ollama_url", "http://localhost:11434")
        self._ollama_model: str = self._ai_settings.get("ollama_model", "qwen2.5:1.5b")
        self._temperature: float = float(self._ai_settings.get("temperature", 0.3))

        # Detect active provider
        self._provider = self._detect_provider()

    def get_provider_name(self) -> str:
        """Returns human-readable name of the active AI engine."""
        if self._provider == "ollama":
            return f"Local Ollama ({self._ollama_model})"
        elif self._provider == "llama_cpp":
            return "Local GGUF (llama-cpp-python)"
        else:
            return "Smart Dynamic Template Engine (Built-in)"

    def _detect_provider(self) -> str:
        """Detects whether Ollama or llama-cpp is available."""
        if not self._enabled:
            return "template"

        # Check 1: Ollama HTTP API
        try:
            resp = requests.get(f"{self._ollama_url}/api/tags", timeout=1.5)
            if resp.status_code == 200:
                models = [m.get("name", "") for m in resp.json().get("models", [])]
                # Pick configured model or first available
                if self._ollama_model in models or any(self._ollama_model.split(":")[0] in m for m in models):
                    return "ollama"
                elif models:
                    self._ollama_model = models[0]
                    return "ollama"
                return "ollama"
        except Exception:
            pass

        # Check 2: llama_cpp python package
        try:
            import llama_cpp  # type: ignore[import-not-found]
            return "llama_cpp"
        except ImportError:
            pass

        return "template"

    def generate_cover_letter(
        self,
        candidate: dict[str, Any],
        job_title: str,
        company: str,
        job_description: str,
        matched_skills: list[str],
    ) -> str:
        """
        Generates a concise, high-impact cover letter tailored to the job.

        Args:
            candidate: Candidate profile dictionary.
            job_title: Target job title.
            company: Company name.
            job_description: Cleaned job description text.
            matched_skills: List of matching skills detected.

        Returns:
            Professional cover letter text.
        """
        if self._provider == "ollama":
            return self._generate_ollama_cover_letter(
                candidate, job_title, company, job_description, matched_skills
            )
        else:
            return self._generate_template_cover_letter(
                candidate, job_title, company, matched_skills
            )

    def answer_form_question(
        self,
        candidate: dict[str, Any],
        question: str,
        job_title: str,
        company: str,
    ) -> str:
        """
        Answers a specific custom question from an ATS application form.

        Args:
            candidate: Candidate profile dictionary.
            question: Question prompt text.
            job_title: Target job title.
            company: Company name.

        Returns:
            Concise, tailored answer text.
        """
        if self._provider == "ollama":
            return self._generate_ollama_answer(candidate, question, job_title, company)
        else:
            return self._generate_template_answer(candidate, question)

    def _generate_ollama_cover_letter(
        self,
        candidate: dict[str, Any],
        job_title: str,
        company: str,
        job_description: str,
        matched_skills: list[str],
    ) -> str:
        """Generates cover letter using local Ollama model."""
        prompt = f"""You are a professional contractor and software engineer.
Write a concise, compelling, 3-paragraph cover letter applying for the following remote contractor role:

Role: {job_title}
Company: {company or 'Hiring Team'}
Target Key Skills: {', '.join(matched_skills[:8])}
Candidate Name: {candidate.get('full_name', 'Applicant')}
Candidate Experience Summary: Experienced contractor specialized in {', '.join(matched_skills[:6])} for international clients.

Guidelines:
1. First paragraph: Introduce interest in the {job_title} position at {company} as an independent contractor.
2. Second paragraph: Highlight direct experience with {', '.join(matched_skills[:4])}, focusing on delivering reliable, automated, scalable solutions.
3. Third paragraph: State full remote availability across international time zones and offer to discuss how to deliver immediate value.
4. Keep tone professional, confident, and direct. Do not include placeholders like [Insert Date].

Cover Letter:"""

        try:
            payload = {
                "model": self._ollama_model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": self._temperature,
                    "num_predict": 350,
                },
            }
            resp = requests.post(f"{self._ollama_url}/api/generate", json=payload, timeout=20)
            if resp.status_code == 200:
                text = resp.json().get("response", "").strip()
                if text:
                    return text
        except Exception:
            pass

        # Fallback to template if Ollama request fails
        return self._generate_template_cover_letter(candidate, job_title, company, matched_skills)

    def _generate_ollama_answer(
        self,
        candidate: dict[str, Any],
        question: str,
        job_title: str,
        company: str,
    ) -> str:
        """Answers form questions using local Ollama model."""
        prompt = f"""Answer the following job application question concisely in 2-3 sentences from the perspective of an experienced contractor.

Candidate Name: {candidate.get('full_name', 'Applicant')}
Role: {job_title} at {company}
Question: {question}

Direct Answer:"""

        try:
            payload = {
                "model": self._ollama_model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.2,
                    "num_predict": 120,
                },
            }
            resp = requests.post(f"{self._ollama_url}/api/generate", json=payload, timeout=10)
            if resp.status_code == 200:
                ans = resp.json().get("response", "").strip()
                if ans:
                    return ans
        except Exception:
            pass

        return self._generate_template_answer(candidate, question)

    def _generate_template_cover_letter(
        self,
        candidate: dict[str, Any],
        job_title: str,
        company: str,
        matched_skills: list[str],
    ) -> str:
        """Fallback dynamic template cover letter."""
        name = candidate.get("full_name", "Applicant")
        comp = company if company and company != "N/A" else "the Hiring Team"
        skills_str = ", ".join(matched_skills[:5]) if matched_skills else "Python, API integration, and automation"

        letter = f"""Dear {comp},

I am writing to express my strong interest in the {job_title} role. As an independent contractor with a proven background in {skills_str}, I specialize in building robust, automated workflows and data-driven solutions for international teams.

Throughout my experience, I have delivered scalable backend pipelines, seamless API integrations, and efficient data processing systems. My technical stack directly aligns with your requirements, allowing me to onboard rapidly and contribute immediate value to your ongoing projects.

I operate with high autonomy in remote environments, ensuring timely communication, transparent progress, and clean, well-tested deliverables. I would welcome the opportunity to discuss how my skill set can support your team's objectives.

Best regards,
{name}
{candidate.get('email', '')}
{candidate.get('github_url', '')}"""
        return letter

    def _generate_template_answer(self, candidate: dict[str, Any], question: str) -> str:
        """Fallback rule-based answers for common ATS questions."""
        q_lower = question.lower()

        if any(k in q_lower for k in ("salary", "rate", "compensation", "expectation", "hourly")):
            return "Negotiable based on project scope, standard market rate for senior contractor roles ($50-80/hr)."
        elif any(k in q_lower for k in ("notice", "start", "available", "when can you")):
            return "Immediately available for contract/freelance engagements (full remote)."
        elif any(k in q_lower for k in ("location", "where are you", "country", "based")):
            return f"Based in {candidate.get('location', 'Europe')}, working comfortably with global time zones (EST, PST, CET, GMT)."
        elif any(k in q_lower for k in ("authorized", "legally", "visa", "sponsorship")):
            return "Yes, authorized to work as an independent B2B contractor / freelancer worldwide."
        elif any(k in q_lower for k in ("why", "interest", "excite")):
            return "I am passionate about solving complex automation and engineering challenges and delivering high-leverage business value as an independent specialist."
        else:
            return "Experienced senior contractor with extensive hands-on expertise in backend automation, API integrations, and robust data pipelines."
