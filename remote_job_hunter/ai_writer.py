"""
ai_writer.py — Fully autonomous, self-contained local AI engine calibrated for 6GB VRAM.

Features:
1. Auto-starts local Ollama service silently in background if not already running.
2. Auto-downloads optimal models for 6GB VRAM:
   - Fast Model for Cover Letters & Form Answers: `qwen2.5:1.5b` (~980 MB, ~1.2 GB VRAM)
   - Heavy Model for Deep Decisions & Screening: `qwen2.5:7b` (~4.4 GB, ~4.9 GB VRAM, fits 100% in 6GB GPU)
3. Fallback to free Cloud APIs (Groq Llama-3.3-70B, Google Gemini Flash) if keys are provided.
4. Fallback to smart built-in rule engine if offline.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from typing import Any

import requests


class LocalAIWriter:
    """
    Independent local AI orchestrator managing background server execution,
    model pulls for 6GB VRAM, and AI inference.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """
        Initializes AI Writer, ensures local engine is running, and detects/pulls models.

        Args:
            config: Configuration dictionary from config.json.
        """
        self._config = config
        self._ai_settings: dict[str, Any] = config.get("local_ai_settings", {})
        self._enabled: bool = self._ai_settings.get("enabled", True)
        self._ollama_url: str = self._ai_settings.get("ollama_url", "http://localhost:11434")
        self._fast_model: str = self._ai_settings.get("fast_model", "qwen2.5:1.5b")
        self._decision_model: str = self._ai_settings.get("decision_model", "qwen2.5:7b")
        self._temperature: float = float(self._ai_settings.get("temperature", 0.2))

        # Cloud API keys
        api_keys = self._ai_settings.get("api_keys", {})
        self._groq_key: str = api_keys.get("groq_api_key") or os.environ.get("GROQ_API_KEY", "")
        self._gemini_key: str = api_keys.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY", "")

        # Cloud models
        cloud_models = self._ai_settings.get("cloud_models", {})
        self._groq_model: str = cloud_models.get("groq_model", "llama-3.3-70b-versatile")
        self._gemini_model: str = cloud_models.get("gemini_model", "gemini-1.5-flash")

        self._active_model_name = "Built-in Rule Engine"
        self._provider = self._init_and_detect_engine()

    def get_provider_name(self) -> str:
        """Returns human-readable name of active AI model."""
        return self._active_model_name

    def _ensure_ollama_running(self) -> bool:
        """Checks if Ollama server is running; if not, attempts to start it silently in background."""
        try:
            r = requests.get(f"{self._ollama_url}/api/tags", timeout=1.0)
            if r.status_code == 200:
                return True
        except Exception:
            pass

        # Try to find and start ollama.exe
        ollama_bin = "ollama"
        default_paths = [
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe"),
            os.path.expandvars(r"%PROGRAMFILES%\Ollama\ollama.exe"),
        ]
        for p in default_paths:
            if os.path.exists(p):
                ollama_bin = p
                break

        try:
            # Ensure .ollama config dir exists
            home_ollama = Path.home() / ".ollama"
            home_ollama.mkdir(parents=True, exist_ok=True)

            creationflags = 0
            if sys.platform == "win32":
                creationflags = 0x08000000  # CREATE_NO_WINDOW

            subprocess.Popen(
                [ollama_bin, "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creationflags,
            )

            # Wait up to 6 seconds for server startup
            for _ in range(12):
                time.sleep(0.5)
                try:
                    r = requests.get(f"{self._ollama_url}/api/tags", timeout=1.0)
                    if r.status_code == 200:
                        return True
                except Exception:
                    continue
        except Exception:
            pass

        return False

    def _pull_model_if_missing(self, model_name: str) -> bool:
        """Pulls the specified model from Ollama library if not already present."""
        try:
            r = requests.get(f"{self._ollama_url}/api/tags", timeout=2.0)
            if r.status_code == 200:
                installed = [m.get("name", "") for m in r.json().get("models", [])]
                if any(model_name in inst or inst.startswith(model_name.split(":")[0]) for inst in installed):
                    return True

            print(f"  📥 Auto-downloading local AI model '{model_name}' for your GPU (free & one-time)...")
            res = requests.post(
                f"{self._ollama_url}/api/pull",
                json={"name": model_name, "stream": False},
                timeout=300,
            )
            if res.status_code == 200:
                print(f"  ✅ Model '{model_name}' successfully downloaded & ready in GPU memory!")
                return True
        except Exception as e:
            print(f"  ⚠️ Note: Could not auto-pull '{model_name}': {e}")
        return False

    def _init_and_detect_engine(self) -> str:
        """Detects and prepares the most capable available AI engine."""
        if not self._enabled:
            self._active_model_name = "Smart Dynamic Template Engine (Built-in)"
            return "template"

        # Tier 1: Cloud APIs (if user configured keys)
        if self._groq_key:
            self._active_model_name = f"Groq Cloud ({self._groq_model})"
            return "groq"

        if self._gemini_key:
            self._active_model_name = f"Google Gemini ({self._gemini_model})"
            return "gemini"

        # Tier 2: Local Standalone GPU Engine (Ollama 6GB VRAM Optimized)
        if self._ensure_ollama_running():
            # Check for decision model (7B) or fast model (1.5B)
            try:
                r = requests.get(f"{self._ollama_url}/api/tags", timeout=2.0)
                installed = [m.get("name", "") for m in r.json().get("models", [])] if r.status_code == 200 else []

                # If no models installed, auto-pull the fast 1.5B model first for instant readiness
                if not installed:
                    self._pull_model_if_missing(self._fast_model)
                    installed = [self._fast_model]

                # Select active model
                if any(self._decision_model in m for m in installed):
                    self._active_ollama_model = self._decision_model
                elif any(self._fast_model in m for m in installed):
                    self._active_ollama_model = self._fast_model
                elif installed:
                    self._active_ollama_model = installed[0]
                else:
                    self._active_ollama_model = self._fast_model

                self._active_model_name = f"Standalone Local GPU ({self._active_ollama_model})"
                return "ollama"
            except Exception:
                pass

        self._active_model_name = "Smart Dynamic Template Engine (Built-in)"
        return "template"

    def _call_llm(self, prompt: str, system_prompt: str = "", max_tokens: int = 350, model_override: str | None = None) -> str:
        """Dispatches LLM prompt to active provider."""
        if self._provider == "groq":
            try:
                headers = {"Authorization": f"Bearer {self._groq_key}", "Content-Type": "application/json"}
                payload = {
                    "model": self._groq_model,
                    "messages": [
                        {"role": "system", "content": system_prompt or "You are a professional senior contractor."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": self._temperature,
                    "max_tokens": max_tokens,
                }
                res = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=15)
                if res.status_code == 200:
                    return res.json()["choices"][0]["message"]["content"].strip()
            except Exception:
                pass

        elif self._provider == "gemini":
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{self._gemini_model}:generateContent?key={self._gemini_key}"
                payload = {
                    "contents": [{"parts": [{"text": f"{system_prompt}\n\n{prompt}"}]}],
                    "generationConfig": {"temperature": self._temperature, "maxOutputTokens": max_tokens},
                }
                res = requests.post(url, json=payload, timeout=15)
                if res.status_code == 200:
                    return res.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            except Exception:
                pass

        elif self._provider == "ollama":
            try:
                target_model = model_override or getattr(self, "_active_ollama_model", self._fast_model)
                full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
                payload = {
                    "model": target_model,
                    "prompt": full_prompt,
                    "stream": False,
                    "options": {"temperature": self._temperature, "num_predict": max_tokens},
                }
                res = requests.post(f"{self._ollama_url}/api/generate", json=payload, timeout=25)
                if res.status_code == 200:
                    return res.json().get("response", "").strip()
            except Exception:
                pass

        return ""

    def deep_screen_job(
        self,
        candidate: dict[str, Any],
        job_title: str,
        company: str,
        job_description: str,
        salary_context: str = "",
        matched_skills: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Runs deep AI analysis to determine automation potential, blueprint, and red flags.
        """
        system = "You are a pragmatic, highly experienced senior contractor specializing in automated Python workflows, web scrapers, and maximum leverage."
        prompt = f"""Analyze the following remote contractor job offer to evaluate how easily a skilled Python/AI engineer can automate deliverables with minimal manual ongoing effort.

Target Role: {job_title}
Company: {company}
Posted Compensation: {salary_context or 'Not specified'}
Candidate Skills: {', '.join(matched_skills or [])}
Job Description:
\"\"\"{job_description[:1200]}\"\"\"

Respond with a JSON object:
- "automatability_score": (int 0-100)
- "automation_blueprint": (string, 1-2 sentences describing the exact Python/Scrapy/API architecture to automate this job)
- "red_flags": (list of strings, e.g. "Daily standups", "Live customer calls", "Manual approvals", or "None detected")
- "recommended_rate_usd": (string, e.g. "$40-$55/hr" or aligned with posted budget)
- "verdict": ("HIGHLY_AUTOMATABLE" if score >= 60 else "VIABLE" if score >= 40 else "MANUAL_HEAVY")

JSON:"""

        raw_resp = self._call_llm(prompt, system_prompt=system, max_tokens=250, model_override=self._decision_model)
        if raw_resp:
            try:
                clean = re.sub(r"^```json\s*|\s*```$", "", raw_resp.strip(), flags=re.MULTILINE)
                return json.loads(clean)
            except Exception:
                pass

        return {
            "automatability_score": 75 if any(k in job_description.lower() for k in ("scrap", "csv", "etl", "api", "clean")) else 45,
            "automation_blueprint": "Scheduled Python ETL pipeline + Playwright scraper to automate data extraction and processing.",
            "red_flags": ["Verify meeting cadence during interview."],
            "recommended_rate_usd": "$40-$55/hr" if not salary_context else salary_context,
            "verdict": "HIGHLY_AUTOMATABLE",
        }

    def generate_cover_letter(
        self,
        candidate: dict[str, Any],
        job_title: str,
        company: str,
        job_description: str,
        matched_skills: list[str],
        salary_context: str = "",
    ) -> str:
        """Generates a concise, authoritative cover letter tailored to the job."""
        skills_str = ", ".join(matched_skills[:8]) if matched_skills else "Python, APIs, Automation"
        comp_name = company if company and company != "N/A" else "the hiring team"

        system = "You are a confident, high-performing independent contractor delivering automated backend systems."
        prompt = f"""Write a concise, 3-paragraph cover letter applying for:
Role: {job_title} at {comp_name}
Skills to Highlight: {skills_str}
Candidate Name: {candidate.get('full_name', 'Samuele Columbu')}
Candidate Location: {candidate.get('location', 'Italy (Full Remote)')}
Job Requirements: {job_description[:400]}

Guidelines:
1. P1: Direct statement of interest for the {job_title} contractor position.
2. P2: Concrete experience with {skills_str}, focusing on shipping automated workflows and API integrations with speed and autonomy.
3. P3: Full remote availability across global time zones and readiness to discuss deliverables.
4. Under 180 words. Direct text only.

Cover Letter:"""

        resp = self._call_llm(prompt, system_prompt=system, max_tokens=300, model_override=self._fast_model)
        if resp:
            return resp

        return self._generate_template_cover_letter(candidate, job_title, company, matched_skills)

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
        """Answers ATS custom questions with confident contractor persona and full CV+Job context."""
        skills_str = ", ".join(matched_skills[:6]) if matched_skills else "Python, backend engineering, data automation"
        comp_name = company if company and company != "N/A" else "the company"

        system = "You are a skilled senior contractor answering application questions concisely, confidently, and realistically."
        prompt = f"""Role: {job_title} at {comp_name}
Relevant Skills: {skills_str}
Posted Salary/Budget: {salary_context or 'Not specified ($35-$50/hr standard contractor baseline)'}
Question Asked: {question}

Instructions:
1. Tone: Confident, clear, professional.
2. Salary/Compensation: If the job listed a budget ({salary_context}), anchor confidently within that range. If unlisted, quote $35-$50/hr.
3. Experience: Reference {skills_str} and production deliverables.
4. Length: 2 to 3 concise sentences. Direct answer only.

Answer:"""

        resp = self._call_llm(prompt, system_prompt=system, max_tokens=150, model_override=self._fast_model)
        if resp:
            return resp

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
        name = candidate.get("full_name", "Samuele Columbu")
        comp = company if company and company != "N/A" else "the Hiring Team"
        skills_str = ", ".join(matched_skills[:5]) if matched_skills else "Python, API automation, and data pipelines"

        return f"""Dear {comp},

I am applying for the {job_title} position as an independent contractor. With a strong background in {skills_str}, I specialize in building automated, reliable, and maintainable systems for distributed teams.

I focus on high-impact deliverables: developing automated data pipelines, orchestrating API integrations, and streamlining backend workflows with high autonomy and clean architecture. I get up to speed quickly with existing codebases and deliver immediate value.

I work comfortably across global time zones and am available for immediate contract engagements. I would welcome the opportunity to discuss how I can support {comp}'s technical milestones.

Best regards,
{name}
{candidate.get('email', 'columbusamuele@gmail.com')}
{candidate.get('github_url', 'https://github.com/bytelifter')}"""

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

        if any(k in q_lower for k in ("salary", "rate", "compensation", "expectation", "hourly", "desired pay")):
            if salary_context and salary_context != "N/A":
                return f"My target compensation is aligned with the posted budget for this role ({salary_context}), reflecting my delivery speed and autonomous execution."
            else:
                return "My target rate is $35-$50/hr (or equivalent milestone/monthly retainer based on project scope), commensurate with fast time-to-delivery and clean architecture."

        elif any(k in q_lower for k in ("notice", "start", "available", "when can you", "how soon")):
            return "Available immediately for full remote contract and freelance engagements with dedicated project allocation."

        elif any(k in q_lower for k in ("location", "where are you", "country", "based", "timezone", "time zone")):
            user_loc = candidate.get("location", "Italy / Europe")
            return f"Based in {user_loc}, with extensive experience collaborating asynchronously and synchronously across US and European time zones."

        elif any(k in q_lower for k in ("authorized", "legally", "visa", "sponsorship", "citizen")):
            return "Fully authorized to work internationally as an independent B2B contractor / freelancer with streamlined invoicing."

        elif any(k in q_lower for k in ("why", "interest", "excite", "fit", "tell us about")):
            comp_display = company if company and company != "N/A" else "this project"
            return f"The technical challenges at {comp_display} directly align with my expertise in {skills_str}. I enjoy diving into demanding problems and shipping robust, production-grade solutions."

        elif any(k in q_lower for k in ("experience", "years", "background", "project", "stack")):
            return f"Extensive hands-on production experience in {skills_str}, delivering automated workflows, reliable data processing, and clean API integrations."

        else:
            return f"Independent contractor specialized in {skills_str}, focused on autonomous execution, clear communication, and high-ROI technical deliverables."
