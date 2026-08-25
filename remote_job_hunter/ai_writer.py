"""
ai_writer.py — Advanced AI engine for job selection, deep automatability screening,
cover letter generation, and ATS form question answering.

Supports multi-tier models:
1. Cloud High-Intelligence APIs (Groq Llama-3.3-70B, Google Gemini Flash, OpenAI)
2. Local Ollama advanced models (Qwen 2.5 7B/14B, Llama 3.1 8B, Mistral, Qwen 1.5B, Llama 3.2 1B)
3. Local GGUF execution via llama-cpp-python
4. Intelligent dynamic template engine fallback
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
    Multi-tier AI Engine supporting both local SLMs and advanced cloud models
    for deep screening, automation blueprinting, and application dispatch.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """
        Initializes the AI engine with multi-tier model detection.

        Args:
            config: Configuration dictionary from config.json.
        """
        self._config = config
        self._ai_settings: dict[str, Any] = config.get("local_ai_settings", {})
        self._enabled: bool = self._ai_settings.get("enabled", True)
        self._ollama_url: str = self._ai_settings.get("ollama_url", "http://localhost:11434")
        self._preferred_models: list[str] = self._ai_settings.get("preferred_models", [
            "qwen2.5:7b", "llama3.1:8b", "qwen2.5:14b", "mistral:7b", "qwen2.5:1.5b", "llama3.2:1b"
        ])
        self._temperature: float = float(self._ai_settings.get("temperature", 0.2))

        # API Keys (from config or environment)
        api_keys = self._ai_settings.get("api_keys", {})
        self._groq_key: str = api_keys.get("groq_api_key") or os.environ.get("GROQ_API_KEY", "")
        self._gemini_key: str = api_keys.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY", "")
        self._openai_key: str = api_keys.get("openai_api_key") or os.environ.get("OPENAI_API_KEY", "")

        # Cloud models
        cloud_models = self._ai_settings.get("cloud_models", {})
        self._groq_model: str = cloud_models.get("groq_model", "llama-3.3-70b-versatile")
        self._gemini_model: str = cloud_models.get("gemini_model", "gemini-1.5-flash")
        self._openai_model: str = cloud_models.get("openai_model", "gpt-4o-mini")

        self._active_model_name = "Built-in Rule Engine"
        self._provider = self._detect_provider()

    def get_provider_name(self) -> str:
        """Returns human-readable name of the active AI model."""
        return self._active_model_name

    def _detect_provider(self) -> str:
        """Detects the best available model provider (Cloud -> Local Ollama -> GGUF -> Template)."""
        if not self._enabled:
            self._active_model_name = "Smart Dynamic Template Engine (Built-in)"
            return "template"

        # Tier 1: Groq Cloud API (Free, super fast Llama 3.3 70B)
        if self._groq_key:
            self._active_model_name = f"Groq Cloud ({self._groq_model})"
            return "groq"

        # Tier 2: Google Gemini API (Free tier Flash)
        if self._gemini_key:
            self._active_model_name = f"Google Gemini ({self._gemini_model})"
            return "gemini"

        # Tier 3: OpenAI API
        if self._openai_key:
            self._active_model_name = f"OpenAI ({self._openai_model})"
            return "openai"

        # Tier 4: Ollama Local (Auto-detect most powerful model on PC)
        try:
            resp = requests.get(f"{self._ollama_url}/api/tags", timeout=1.5)
            if resp.status_code == 200:
                installed = [m.get("name", "") for m in resp.json().get("models", [])]
                for pref in self._preferred_models:
                    for inst in installed:
                        if pref == inst or pref.split(":")[0] == inst.split(":")[0]:
                            self._ollama_model = inst
                            self._active_model_name = f"Local Ollama ({inst})"
                            return "ollama"
                if installed:
                    self._ollama_model = installed[0]
                    self._active_model_name = f"Local Ollama ({installed[0]})"
                    return "ollama"
        except Exception:
            pass

        self._active_model_name = "Smart Dynamic Template Engine (Built-in)"
        return "template"

    def _call_llm(self, prompt: str, system_prompt: str = "", max_tokens: int = 350) -> str:
        """Unified LLM caller dispatching to the active provider."""
        if self._provider == "groq":
            try:
                headers = {"Authorization": f"Bearer {self._groq_key}", "Content-Type": "application/json"}
                payload = {
                    "model": self._groq_model,
                    "messages": [
                        {"role": "system", "content": system_prompt or "You are a professional senior contractor and automation engineer."},
                        {"role": "user", "content": prompt}
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
                full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
                payload = {
                    "model": self._ollama_model,
                    "prompt": full_prompt,
                    "stream": False,
                    "options": {"temperature": self._temperature, "num_predict": max_tokens},
                }
                res = requests.post(f"{self._ollama_url}/api/generate", json=payload, timeout=20)
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
        Performs deep AI analysis on a job posting to determine:
        1. Real automatability potential (0-100%)
        2. Exact step-by-step automation blueprint (scripts, cron, LLMs)
        3. Red flags (micromanagement, meeting traps)
        4. Optimal target hourly rate.

        Returns:
            Dictionary with deep screening insights.
        """
        system = "You are a pragmatic, highly experienced senior contractor specializing in automated workflows, Python scripting, and maximum leverage."
        prompt = f"""Analyze the following remote contractor job offer to evaluate how easily a skilled Python/AI engineer can automate the deliverables and execute the contract with minimal ongoing manual labor.

Target Role: {job_title}
Company: {company}
Posted Compensation: {salary_context or 'Not specified'}
Relevant Candidate Skills: {', '.join(matched_skills or [])}
Job Description:
\"\"\"{job_description[:1200]}\"\"\"

Output a valid JSON object with the following keys:
- "automatability_score": (int between 0 and 100, where 100 means 90%+ of the tasks can be written once in a script/cron/AI workflow)
- "automation_blueprint": (string, 1-2 sentences describing the exact Python/LangChain/API script architecture to automate this job)
- "red_flags": (list of strings, e.g. "Daily 1-hour standups", "Live customer calls", "Complex manual approvals", or "None detected")
- "recommended_rate_usd": (string, realistic senior contractor rate to quote, e.g. "$45-$60/hr" or matching posted budget)
- "verdict": ("HIGHLY_AUTOMATABLE" if score >= 65 else "MODERATE" if score >= 40 else "MANUAL_HEAVY")

JSON Response:"""

        raw_resp = self._call_llm(prompt, system_prompt=system, max_tokens=250)
        if raw_resp:
            try:
                # Extract JSON if enclosed in markdown code blocks
                clean = re.sub(r"^```json\s*|\s*```$", "", raw_resp.strip(), flags=re.MULTILINE)
                data = json.loads(clean)
                return data
            except Exception:
                pass

        # Fallback heuristic blueprint
        return {
            "automatability_score": 75 if any(k in job_description.lower() for k in ("scrap", "csv", "etl", "api", "clean")) else 45,
            "automation_blueprint": "Scheduled Python ETL pipeline + Playwright scraper to automate data collection and processing.",
            "red_flags": ["Verify meeting cadence during initial interview."],
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

        system = "You are a confident, high-performing independent contractor who delivers automated, scalable solutions."
        prompt = f"""Write a concise, 3-paragraph cover letter applying for:
Role: {job_title} at {comp_name}
Skills to Highlight: {skills_str}
Candidate Name: {candidate.get('full_name', 'Samuele Columbu')}
Candidate Location: {candidate.get('location', 'Italy (Full Remote)')}
Job Requirements: {job_description[:400]}

Guidelines:
1. P1: Direct, confident statement of interest for the {job_title} contractor position.
2. P2: Highlight concrete experience with {skills_str}, focusing on shipping resilient, automated backend systems with rapid delivery and high autonomy.
3. P3: Full remote availability across global time zones and readiness to discuss project deliverables.
4. Keep under 180 words. No date or placeholder tokens.

Cover Letter:"""

        resp = self._call_llm(prompt, system_prompt=system, max_tokens=300)
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
Posted Salary/Budget: {salary_context or 'Not specified ($40-$55/hr standard junior/mid contractor baseline)'}
Question Asked: {question}

Instructions:
1. Tone: Confident, competent, clear-minded. You know your worth and your craft.
2. Salary/Compensation: If the job listed a budget ({salary_context}), anchor confidently within that range. If unlisted, quote a fair, competitive rate ($35-$50/hr or equivalent milestone structure).
3. Experience: Reference {skills_str} and production-grade deliverables.
4. Length: 2 to 3 concise, punchy sentences. Direct answer only.

Answer:"""

        resp = self._call_llm(prompt, system_prompt=system, max_tokens=150)
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
