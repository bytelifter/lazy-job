"""
ai_writer.py — Lightweight Local AI engine for writing tailored cover letters
and answering ATS application form questions.

Operates with the persona of a skilled, confident, senior independent contractor:
- Knows their market value, clear on compensation (competitive, fair senior contractor rates).
- Focuses on ROI, immediate delivery, autonomous execution, and clean architecture.
- Contextualizes every answer using BOTH the candidate's CV and the target job offer.
"""

from __future__ import annotations

import json
import os
import re
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
        salary_context: str = "",
    ) -> str:
        """
        Generates a concise, authoritative cover letter tailored to the job.

        Args:
            candidate: Candidate profile dictionary.
            job_title: Target job title.
            company: Company name.
            job_description: Cleaned job description text.
            matched_skills: List of matching skills detected.
            salary_context: Stated salary/compensation range if available.

        Returns:
            Professional cover letter text.
        """
        if self._provider == "ollama":
            return self._generate_ollama_cover_letter(
                candidate, job_title, company, job_description, matched_skills, salary_context
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
        job_description: str = "",
        salary_context: str = "",
        matched_skills: list[str] | None = None,
    ) -> str:
        """
        Answers a specific custom question from an ATS application form
        using BOTH the candidate's CV background and the job offer context.

        Tone: Confident, skilled contractor who knows what they want,
        values their work appropriately (fair/competitive rate without overshooting),
        and directly addresses the question with technical substance.

        Args:
            candidate: Candidate profile dictionary.
            question: Question prompt text.
            job_title: Target job title.
            company: Company name.
            job_description: Job requirements context.
            salary_context: Stated salary from posting.
            matched_skills: Relevant skills matched.

        Returns:
            Concise, tailored answer text.
        """
        if self._provider == "ollama":
            return self._generate_ollama_answer(
                candidate, question, job_title, company, job_description, salary_context, matched_skills
            )
        else:
            return self._generate_template_answer(
                candidate, question, job_title, company, salary_context, matched_skills
            )

    def _generate_ollama_cover_letter(
        self,
        candidate: dict[str, Any],
        job_title: str,
        company: str,
        job_description: str,
        matched_skills: list[str],
        salary_context: str = "",
    ) -> str:
        """Generates cover letter using local Ollama model."""
        skills_str = ", ".join(matched_skills[:8]) if matched_skills else "Python, APIs, Automation"
        comp_name = company if company and company != "N/A" else "the hiring team"

        prompt = f"""You are writing as a senior, highly competent independent contractor applying for a remote role.
Tone: Confident, direct, professional, value-driven. No generic fluff, no desperation. You know your skills and what you bring to the table.

Target Role: {job_title}
Company: {comp_name}
Key Skills to Highlight: {skills_str}
Candidate Name: {candidate.get('full_name', 'Applicant')}
Candidate Location: {candidate.get('location', 'Europe (Full Remote)')}
Job Requirements Summary: {job_description[:400]}

Instructions:
1. Paragraph 1: Direct statement of interest for the {job_title} contractor position, highlighting specialized background in {skills_str}.
2. Paragraph 2: Concrete mention of delivering reliable, automated, scalable systems with minimal onboarding time and autonomous execution.
3. Paragraph 3: Availability for full remote engagement across international time zones and readiness to discuss deliverables.
4. Keep it under 200 words. Do not include template placeholders like [Date] or [Phone Number].

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

        return self._generate_template_cover_letter(candidate, job_title, company, matched_skills)

    def _generate_ollama_answer(
        self,
        candidate: dict[str, Any],
        question: str,
        job_title: str,
        company: str,
        job_description: str = "",
        salary_context: str = "",
        matched_skills: list[str] | None = None,
    ) -> str:
        """Answers form questions using local Ollama model with full CV & Job context."""
        skills_str = ", ".join(matched_skills[:6]) if matched_skills else "Python, backend engineering, data automation"
        comp_name = company if company and company != "N/A" else "the company"

        prompt = f"""You are answering an application form question as a senior independent contractor applying for:
Role: {job_title} at {comp_name}
Relevant Candidate Skills: {skills_str}
Job Budget/Salary Info: {salary_context if salary_context else 'Not specified (Standard senior market: $60-$85/hr)'}
Question Asked: {question}

Persona Guidelines:
1. Tone: Confident, skilled, clear-minded. You know your craft, your market value, and what you want.
2. Compensation/Salary questions: Request fair, solid, competitive compensation. If the job listed a salary range ({salary_context}), align confidently with the upper-mid range. If no salary was listed, state a realistic, competitive senior contractor rate ($60-$85/hr or €50-€75/hr / equivalent monthly), open to discussing milestone-based deliverables. Never undersell yourself and do not ask for ridiculous numbers.
3. Technical/Experience questions: Answer directly, referencing {skills_str} and practical production experience.
4. Availability/Location: Full remote availability, seamless international time zone coverage.
5. Length: 2 to 3 concise, punchy sentences. Direct answer only, no preamble.

Answer:"""

        try:
            payload = {
                "model": self._ollama_model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.2,
                    "num_predict": 150,
                },
            }
            resp = requests.post(f"{self._ollama_url}/api/generate", json=payload, timeout=12)
            if resp.status_code == 200:
                ans = resp.json().get("response", "").strip()
                if ans:
                    return ans
        except Exception:
            pass

        return self._generate_template_answer(
            candidate, question, job_title, company, salary_context, matched_skills
        )

    def _generate_template_cover_letter(
        self,
        candidate: dict[str, Any],
        job_title: str,
        company: str,
        matched_skills: list[str],
    ) -> str:
        """Fallback dynamic template cover letter with senior contractor tone."""
        name = candidate.get("full_name", "Applicant")
        comp = company if company and company != "N/A" else "the Hiring Team"
        skills_str = ", ".join(matched_skills[:5]) if matched_skills else "Python, API automation, and data pipelines"

        letter = f"""Dear {comp},

I am applying for the {job_title} position as an independent contractor. With a strong track record across {skills_str}, I specialize in designing and shipping clean, automated, and maintainable systems for distributed teams.

I focus on high-impact deliverables: building resilient data pipelines, orchestrating seamless API integrations, and streamlining backend operations with minimal oversight. I quickly get up to speed with existing architectures and operate with full autonomy in remote settings.

I work comfortably across international time zones and am available for immediate contract engagements. I welcome the opportunity to discuss how I can contribute to {comp}'s upcoming milestones.

Best regards,
{name}
{candidate.get('email', '')}
{candidate.get('github_url', '')}"""
        return letter

    def _generate_template_answer(
        self,
        candidate: dict[str, Any],
        question: str,
        job_title: str = "",
        company: str = "",
        salary_context: str = "",
        matched_skills: list[str] | None = None,
    ) -> str:
        """Fallback rule-based answers with confident senior contractor persona."""
        q_lower = question.lower()
        skills_str = ", ".join(matched_skills[:4]) if matched_skills else "Python, automation, and API integration"

        # Salary / Rate Question
        if any(k in q_lower for k in ("salary", "rate", "compensation", "expectation", "hourly", "desired pay")):
            if salary_context and salary_context != "N/A":
                return f"My target compensation is aligned with the posted budget for this role ({salary_context}), reflecting my senior delivery speed and autonomous execution."
            else:
                return "My target rate is $65-$85/hr (or equivalent milestone/monthly retainer based on project scope), commensurate with senior contractor expertise and fast time-to-delivery."

        # Availability / Start Date
        elif any(k in q_lower for k in ("notice", "start", "available", "when can you", "how soon")):
            return "Available immediately for full remote contract and freelance engagements with full-time or dedicated project allocation."

        # Location / Timezone
        elif any(k in q_lower for k in ("location", "where are you", "country", "based", "timezone", "time zone")):
            user_loc = candidate.get("location", "Europe")
            return f"Based in {user_loc}, with extensive experience collaborating asynchronously and synchronously with US, European, and global teams."

        # Work Authorization / Contractor B2B
        elif any(k in q_lower for k in ("authorized", "legally", "visa", "sponsorship", "citizen")):
            return "Fully authorized to work internationally as an independent B2B contractor / consultant with streamlined invoicing."

        # Why this role / company
        elif any(k in q_lower for k in ("why", "interest", "excite", "fit", "tell us about")):
            comp_display = company if company and company != "N/A" else "this project"
            return f"The technical challenges at {comp_display} directly align with my expertise in {skills_str}. I enjoy diving into demanding problems and shipping robust, production-grade solutions."

        # Experience / Technical depth
        elif any(k in q_lower for k in ("experience", "years", "background", "project", "stack")):
            return f"Extensive hands-on production experience in {skills_str}, delivering high-throughput data processing, automated workflows, and clean API integrations."

        # Default fallback
        else:
            return f"Senior contractor specialized in {skills_str}, focused on autonomous execution, clear communication, and high-ROI technical deliverables."
