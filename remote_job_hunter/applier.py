"""
applier.py — Automated & Assisted Application Dispatcher.

Handles:
1. Direct Email applications via SMTP (with PDF CV attachment and AI cover letter)
2. ATS Web Form inspection & auto-filling via Playwright (Greenhouse, Lever, etc.)
3. Anti-bot & CAPTCHA detection (Cloudflare Turnstile, reCAPTCHA, hCaptcha)
4. Graceful Manual Action fallback with direct 1-click links and ready-to-paste AI cover letters
5. Logging of all application statuses to CSV
"""

from __future__ import annotations

import csv
import email
import email.mime.application
import email.mime.multipart
import email.mime.text
import os
import re
import smtplib
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .ai_writer import LocalAIWriter

if TYPE_CHECKING:
    from .matcher import ScoredOffer


@dataclass
class ApplicationResult:
    """Represents the outcome of an application attempt."""

    job_title: str
    company: str
    channel: str  # 'Email' | 'ATS_Form' | 'Direct_Web'
    status: str  # 'SENT' | 'DRAFT_PREPARED' | 'AUTO_FILLED' | 'MANUAL_REQUIRED' | 'FAILED'
    details: str
    direct_link: str
    cover_letter: str = ""
    timestamp: str = ""


class EmailDispatcher:
    """Handles direct email application dispatch via SMTP."""

    def __init__(self, config: dict[str, Any], ai_writer: LocalAIWriter) -> None:
        self._config = config
        self._smtp_cfg: dict[str, Any] = config.get("smtp_settings", {})
        self._candidate: dict[str, Any] = config.get("candidate_profile", {})
        self._ai_writer = ai_writer

    def extract_email(self, offer: ScoredOffer) -> str | None:
        """Extracts email address from job description or URL if present."""
        if "mailto:" in offer.url.lower():
            match = re.search(r"mailto:([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)", offer.url)
            if match:
                return match.group(1)

        searchable = f"{offer.description} {offer.url}"
        emails = re.findall(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b", searchable)
        # Filter out generic/dummy emails
        valid_emails = [
            e for e in emails
            if not any(d in e.lower() for d in ("example.com", "weworkremotely.com", "himalayas.app", "remotive.com", "jobicy.com"))
        ]
        return valid_emails[0] if valid_emails else None

    def send_application(
        self,
        recipient_email: str,
        offer: ScoredOffer,
        cover_letter: str,
    ) -> ApplicationResult:
        """Builds and optionally sends an application email with PDF attachment."""
        sender_email = self._smtp_cfg.get("sender_email", self._candidate.get("email", ""))
        subject = f"Application for {offer.title} - {self._candidate.get('full_name', 'Applicant')}"
        is_dry_run = self._smtp_cfg.get("dry_run", True)
        is_enabled = self._smtp_cfg.get("enabled", False)

        # Build MIME Message
        msg = email.mime.multipart.MIMEMultipart()
        msg["From"] = sender_email
        msg["To"] = recipient_email
        msg["Subject"] = subject
        msg.attach(email.mime.text.MIMEText(cover_letter, "plain", "utf-8"))

        # Attach PDF CV if exists
        cv_path = Path(self._candidate.get("cv_pdf_path", "test_cv.txt"))
        if cv_path.exists() and cv_path.suffix.lower() == ".pdf":
            try:
                with cv_path.open("rb") as f:
                    part = email.mime.application.MIMEApplication(f.read(), Name=cv_path.name)
                part["Content-Disposition"] = f'attachment; filename="{cv_path.name}"'
                msg.attach(part)
            except Exception:
                pass

        if not is_enabled or is_dry_run:
            return ApplicationResult(
                job_title=offer.title,
                company=offer.company,
                channel="Email",
                status="DRAFT_PREPARED",
                details=f"Email draft prepared for {recipient_email} (Dry Run active).",
                direct_link=f"mailto:{recipient_email}?subject={subject}",
                cover_letter=cover_letter,
            )

        # Actual SMTP Send
        try:
            host = self._smtp_cfg.get("smtp_host", "smtp.gmail.com")
            port = int(self._smtp_cfg.get("smtp_port", 587))
            pwd = self._smtp_cfg.get("sender_password", "")

            with smtplib.SMTP(host, port, timeout=15) as server:
                server.starttls()
                server.login(sender_email, pwd)
                server.send_message(msg)

            return ApplicationResult(
                job_title=offer.title,
                company=offer.company,
                channel="Email",
                status="SENT",
                details=f"Email successfully sent to {recipient_email}.",
                direct_link=offer.url,
                cover_letter=cover_letter,
            )
        except Exception as e:
            return ApplicationResult(
                job_title=offer.title,
                company=offer.company,
                channel="Email",
                status="FAILED",
                details=f"SMTP send error: {e}",
                direct_link=offer.url,
                cover_letter=cover_letter,
            )


class WebFormDispatcher:
    """Inspects and autofills standard ATS web application forms using Playwright."""

    CAPTCHA_SELECTORS = [
        "iframe[src*='recaptcha']",
        "iframe[src*='turnstile']",
        "iframe[src*='hcaptcha']",
        ".cf-turnstile",
        ".g-recaptcha",
        "#turnstile-widget",
        "[data-sitekey]",
        "div[class*='captcha']",
        "div[id*='captcha']",
    ]

    def __init__(self, config: dict[str, Any], ai_writer: LocalAIWriter) -> None:
        self._config = config
        self._candidate: dict[str, Any] = config.get("candidate_profile", {})
        self._ai_writer = ai_writer

    def apply_or_inspect(
        self,
        offer: ScoredOffer,
        cover_letter: str,
    ) -> ApplicationResult:
        """Inspects application web page for CAPTCHAs, custom questions, or autofills standard ATS forms."""
        try:
            from playwright.sync_api import sync_playwright  # noqa: F401
        except ImportError:
            return ApplicationResult(
                job_title=offer.title,
                company=offer.company,
                channel="ATS_Form",
                status="MANUAL_REQUIRED",
                details="Playwright not installed. Direct link and AI cover letter ready.",
                direct_link=offer.url,
                cover_letter=cover_letter,
            )

        # Inspect form using Playwright headless browser
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
                page = context.new_page()

                try:
                    page.goto(offer.url, timeout=25000, wait_until="domcontentloaded")
                    page.wait_for_timeout(2000)
                except Exception:
                    browser.close()
                    return ApplicationResult(
                        job_title=offer.title,
                        company=offer.company,
                        channel="Direct_Web",
                        status="MANUAL_REQUIRED",
                        details="Page required complex navigation or login. Direct link and AI pitch ready.",
                        direct_link=offer.url,
                        cover_letter=cover_letter,
                    )

                page_content = page.content().lower()

                # Check 1: Detect CAPTCHA
                has_captcha = False
                for sel in self.CAPTCHA_SELECTORS:
                    try:
                        if page.locator(sel).count() > 0:
                            has_captcha = True
                            break
                    except Exception:
                        pass

                if has_captcha or "captcha" in page_content or "cf-turnstile" in page_content:
                    browser.close()
                    return ApplicationResult(
                        job_title=offer.title,
                        company=offer.company,
                        channel="ATS_Form",
                        status="MANUAL_REQUIRED",
                        details="CAPTCHA (Cloudflare/reCAPTCHA) detected. Direct link & AI cover letter ready for 1-click apply.",
                        direct_link=offer.url,
                        cover_letter=cover_letter,
                    )

                # Check 2: Detect ATS Platform
                is_lever = "jobs.lever.co" in page.url or "lever" in page_content
                is_greenhouse = "boards.greenhouse.io" in page.url or "greenhouse" in page_content
                is_workable = "apply.workable.com" in page.url or "workable" in page_content

                # Check 3: Autofill Lever form if standard
                if is_lever:
                    result = self._autofill_lever(page, offer, cover_letter)
                    browser.close()
                    return result

                # Check 4: Autofill Greenhouse form if standard
                elif is_greenhouse:
                    result = self._autofill_greenhouse(page, offer, cover_letter)
                    browser.close()
                    return result

                # Generic form inspection: check for custom mandatory inputs
                textareas = page.locator("textarea:visible").count()
                required_inputs = page.locator("input[required]:visible").count()

                browser.close()

                if required_inputs > 6 or textareas > 2:
                    return ApplicationResult(
                        job_title=offer.title,
                        company=offer.company,
                        channel="ATS_Form",
                        status="MANUAL_REQUIRED",
                        details="Custom application questions detected. Direct link & AI cover letter ready.",
                        direct_link=offer.url,
                        cover_letter=cover_letter,
                    )

                return ApplicationResult(
                    job_title=offer.title,
                    company=offer.company,
                    channel="Direct_Web",
                    status="MANUAL_REQUIRED",
                    details="External job portal. Direct link and custom AI cover letter ready.",
                    direct_link=offer.url,
                    cover_letter=cover_letter,
                )

        except Exception as e:
            return ApplicationResult(
                job_title=offer.title,
                company=offer.company,
                channel="Direct_Web",
                status="MANUAL_REQUIRED",
                details=f"Inspection finished ({e}). Direct link & tailored pitch ready.",
                direct_link=offer.url,
                cover_letter=cover_letter,
            )

    def _autofill_lever(self, page: Any, offer: ScoredOffer, cover_letter: str) -> ApplicationResult:
        """Autofills Lever ATS application form and answers custom questions."""
        try:
            if page.locator("input[name='name']").count() > 0:
                page.fill("input[name='name']", self._candidate.get("full_name", ""))
                page.fill("input[name='email']", self._candidate.get("email", ""))
                if page.locator("input[name='phone']").count() > 0:
                    page.fill("input[name='phone']", self._candidate.get("phone", ""))
                if page.locator("input[name='org']").count() > 0:
                    page.fill("input[name='org']", "Independent Contractor")
                if page.locator("input[name='urls[LinkedIn]']").count() > 0:
                    page.fill("input[name='urls[LinkedIn]']", self._candidate.get("linkedin_url", ""))
                if page.locator("input[name='urls[GitHub]']").count() > 0:
                    page.fill("input[name='urls[GitHub]']", self._candidate.get("github_url", ""))
                if page.locator("textarea[name='comments']").count() > 0:
                    page.fill("textarea[name='comments']", cover_letter)

                # Attach Resume if PDF
                cv_path = Path(self._candidate.get("cv_pdf_path", "test_cv.txt"))
                if cv_path.exists() and cv_path.suffix.lower() == ".pdf":
                    file_input = page.locator("input[type='file']")
                    if file_input.count() > 0:
                        file_input.set_input_files(str(cv_path.resolve()))

                # Answer any additional custom question textareas
                custom_textareas = page.locator("textarea:not([name='comments']):visible")
                count_ta = custom_textareas.count()
                for i in range(count_ta):
                    ta = custom_textareas.nth(i)
                    label_text = ta.evaluate("el => el.closest('div')?.innerText || el.placeholder || ''")
                    if label_text:
                        ans = self._ai_writer.answer_form_question(
                            candidate=self._candidate,
                            question=label_text[:120],
                            job_title=offer.title,
                            company=offer.company,
                            job_description=offer.description,
                            salary_context=offer.salary,
                            matched_skills=offer.matched_skills,
                        )
                        ta.fill(ans)

                return ApplicationResult(
                    job_title=offer.title,
                    company=offer.company,
                    channel="ATS_Form (Lever)",
                    status="AUTO_FILLED",
                    details="Lever form successfully autofilled (Name, Email, Resume, GitHub, AI Cover Letter & Q&A).",
                    direct_link=offer.url,
                    cover_letter=cover_letter,
                )
        except Exception:
            pass

        return ApplicationResult(
            job_title=offer.title,
            company=offer.company,
            channel="ATS_Form (Lever)",
            status="MANUAL_REQUIRED",
            details="Lever custom verification required. Direct link & AI cover letter ready.",
            direct_link=offer.url,
            cover_letter=cover_letter,
        )

    def _autofill_greenhouse(self, page: Any, offer: ScoredOffer, cover_letter: str) -> ApplicationResult:
        """Autofills Greenhouse ATS application form and answers custom questions."""
        try:
            if page.locator("#first_name").count() > 0:
                page.fill("#first_name", self._candidate.get("first_name", "Mario"))
                page.fill("#last_name", self._candidate.get("last_name", "Rossi"))
                page.fill("#email", self._candidate.get("email", ""))
                if page.locator("#phone").count() > 0:
                    page.fill("#phone", self._candidate.get("phone", ""))

                # Attach Resume
                cv_path = Path(self._candidate.get("cv_pdf_path", "test_cv.txt"))
                if cv_path.exists() and cv_path.suffix.lower() == ".pdf":
                    file_input = page.locator("input[type='file']")
                    if file_input.count() > 0:
                        file_input.set_input_files(str(cv_path.resolve()))

                # Answer custom questions on Greenhouse
                custom_inputs = page.locator(".field:has(textarea), .field:has(input[type='text'])")
                for i in range(min(custom_inputs.count(), 5)):
                    field_elem = custom_inputs.nth(i)
                    label = field_elem.locator("label").inner_text() if field_elem.locator("label").count() > 0 else ""
                    if label and not any(ign in label.lower() for ign in ("name", "email", "phone", "resume", "cv")):
                        ans = self._ai_writer.answer_form_question(
                            candidate=self._candidate,
                            question=label,
                            job_title=offer.title,
                            company=offer.company,
                            job_description=offer.description,
                            salary_context=offer.salary,
                            matched_skills=offer.matched_skills,
                        )
                        target_input = field_elem.locator("textarea, input[type='text']")
                        if target_input.count() > 0 and not target_input.input_value():
                            target_input.fill(ans)

                return ApplicationResult(
                    job_title=offer.title,
                    company=offer.company,
                    channel="ATS_Form (Greenhouse)",
                    status="AUTO_FILLED",
                    details="Greenhouse form successfully autofilled with AI answers.",
                    direct_link=offer.url,
                    cover_letter=cover_letter,
                )
        except Exception:
            pass

        return ApplicationResult(
            job_title=offer.title,
            company=offer.company,
            channel="ATS_Form (Greenhouse)",
            status="MANUAL_REQUIRED",
            details="Greenhouse custom questions detected. Direct link & AI pitch ready.",
            direct_link=offer.url,
            cover_letter=cover_letter,
        )


class ApplicationOrchestrator:
    """Coordinates batch application workflow for top matched jobs."""

    def __init__(self, config: dict[str, Any]) -> None:
        self._config = config
        self._ai_writer = LocalAIWriter(config)
        self._email_applier = EmailDispatcher(config, self._ai_writer)
        self._web_applier = WebFormDispatcher(config, self._ai_writer)
        self._candidate: dict[str, Any] = config.get("candidate_profile", {})

    def process_applications(
        self,
        offers: list[ScoredOffer],
        max_applications: int = 10,
    ) -> list[ApplicationResult]:
        """
        Executes application workflow on the top matching jobs.

        Args:
            offers: List of ScoredOffer ordered by match score.
            max_applications: Maximum number of applications to process in batch.

        Returns:
            List of ApplicationResult records.
        """
        results: list[ApplicationResult] = []
        target_offers = offers[:max_applications]

        print(f"\n  🤖 Active AI Writer Engine: {self._ai_writer.get_provider_name()}")
        print(f"  🎯 Processing applications for top {len(target_offers)} matching positions...\n")

        for idx, offer in enumerate(target_offers, 1):
            print(f"  [{idx:02d}/{len(target_offers):02d}] Evaluating: {offer.title} @ {offer.company} (Score: {offer.match_score}/100)")

            # 1. Generate AI Cover Letter tailored to this specific job
            cover_letter = self._ai_writer.generate_cover_letter(
                candidate=self._candidate,
                job_title=offer.title,
                company=offer.company,
                job_description=offer.description,
                matched_skills=offer.matched_skills,
                salary_context=offer.salary,
            )

            # 2. Check for direct email contact
            recipient_email = self._email_applier.extract_email(offer)

            if recipient_email:
                print(f"       ✉️  Direct email detected: {recipient_email}")
                res = self._email_applier.send_application(recipient_email, offer, cover_letter)
            else:
                print(f"       🌐 Inspecting web portal: {offer.source}")
                res = self._web_applier.apply_or_inspect(offer, cover_letter)

            res.timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            results.append(res)

            # Print outcome
            status_badge = f"[{res.status}]"
            print(f"       Status: {status_badge} — {res.details}")
            if res.status == "MANUAL_REQUIRED":
                print(f"       🔗 Direct 1-Click Link: {res.direct_link}")

            time.sleep(0.5)

        return results

    def save_application_log(
        self,
        results: list[ApplicationResult],
        output_path: str,
    ) -> str:
        """
        Saves application results to CSV log.

        Args:
            results: List of ApplicationResult records.
            output_path: Target CSV file path.

        Returns:
            Absolute path of created log file.
        """
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        columns = ["Timestamp", "Job Title", "Company", "Channel", "Status", "Details", "Direct Link", "AI Cover Letter"]

        with path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            for r in results:
                writer.writerow([
                    r.timestamp,
                    r.job_title,
                    r.company,
                    r.channel,
                    r.status,
                    r.details,
                    r.direct_link,
                    r.cover_letter,
                ])

        return str(path.resolve())
