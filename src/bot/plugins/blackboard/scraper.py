"""Blackboard scraper using Playwright.

Adapted from the reference implementation. Handles login,
session persistence, and assignment extraction via page.evaluate().
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from dateutil import parser as dateutil_parser
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from src.bot.plugins.blackboard.models import BlackboardConfig


class ScrapingError(Exception):
    pass


class LoginError(ScrapingError):
    pass


ProgressFn = Callable[[str, str], None]


class BlackboardScraper:
    """Scrapes assignments from Blackboard using headless Playwright."""

    def __init__(
        self,
        config: BlackboardConfig,
        session_file_path: str | Path | None = None,
        on_progress: ProgressFn | None = None,
    ) -> None:
        self._config = config
        self._session_file_path = Path(session_file_path or "data/plugins/blackboard_session.json")
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._playwright = None
        self._on_progress = on_progress
        self._start_time = time.monotonic()
        self.steps: list[dict[str, Any]] = []

    def _log(self, level: str, msg: str) -> None:
        elapsed = time.monotonic() - self._start_time
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "elapsed_s": round(elapsed, 2),
            "level": level,
            "message": msg,
        }
        self.steps.append(entry)
        print(f"[BlackboardScraper] [{elapsed:6.2f}s] [{level}] {msg}", flush=True)
        if self._on_progress is not None:
            try:
                self._on_progress(level, msg)
            except Exception:
                pass

    async def _dismiss_consent_dialog(self) -> bool:
        """Click the Blackboard cookies/privacy consent button if visible."""
        for sel in (
            "#agree_button",
            "button:has-text('Aceptar')",
            "button:has-text('Accept')",
        ):
            try:
                loc = self._page.locator(sel).first
                if await loc.count() > 0 and await loc.is_visible():
                    self._log("INFO", f"Consent dialog: dismissing via {sel!r}")
                    await loc.click(timeout=5000)
                    await asyncio.sleep(1.2)
                    return True
            except Exception as exc:
                self._log("WARN", f"Consent dismiss {sel!r} error: {exc}")
        return False

    async def login(self) -> bool:
        """Authenticate to Blackboard. Returns True on success."""
        try:
            self._log("INFO", "Login: ensuring browser is up")
            await self._ensure_browser()
            login_url = self._config.blackboard_url.rstrip("/")
            self._log("INFO", f"Login: navigating to {login_url}")
            await self._page.goto(login_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(1.5)
            self._log("INFO", f"Login: landed at {self._page.url}")

            if await self._is_logged_in():
                self._log("OK", "Login: already authenticated (session valid)")
                await self._save_session()
                return True

            await self._dismiss_consent_dialog()

            self._log("INFO", "Login: clicking O365 login button with navigation wait")
            clicked = await self._click_o365_login_button_with_nav()
            if not clicked:
                self._log("ERROR", "Could not click O365 login button")
                return False

            if "microsoftonline" in self._page.url.lower() or "login.microsoft" in self._page.url.lower():
                self._log("INFO", "Login: on Microsoft, filling email")
                if not await self._microsoft_fill_email():
                    self._log("ERROR", "Failed to fill Microsoft email")
                    return False
                self._log("INFO", "Login: filling password")
                if not await self._microsoft_fill_password():
                    self._log("ERROR", "Failed to fill Microsoft password")
                    return False
                self._log("INFO", "Login: handling KMSI")
                await self._microsoft_handle_kmsi()

            if await self._is_logged_in():
                self._log("OK", f"Login: authenticated, url={self._page.url}")
                await self._save_session()
                return True

            self._log("ERROR", f"Login: not authenticated, final url={self._page.url}")
            return False
        except Exception as exc:
            self._log("ERROR", f"Login failed: {type(exc).__name__}: {exc}")
            return False

    async def _click_o365_login_button_with_nav(self) -> bool:
        """Click the SAML/O365 login link and wait for navigation."""
        selectors = (
            "a.icon-o365",
            "a[href*='auth-saml/saml/login']",
            "a:has-text('@senati.pe')",
            "a:has-text('Ingresa con tu correo')",
        )
        for sel in selectors:
            try:
                loc = self._page.locator(sel).first
                if await loc.count() == 0 or not await loc.is_visible():
                    continue
                self._log("INFO", f"Clicking {sel!r}, expecting navigation")
                async with self._page.expect_navigation(
                    wait_until="domcontentloaded", timeout=30000
                ):
                    await loc.click(timeout=10000)
                self._log("OK", f"Navigated to {self._page.url}")
                return True
            except Exception as exc:
                self._log("WARN", f"Click {sel!r} failed: {type(exc).__name__}: {exc}")
        return False

    async def _microsoft_fill_email(self) -> bool:
        try:
            email = self._page.locator("input[type='email'], input[name='loginfmt']").first
            await email.wait_for(state="visible", timeout=15000)
            await email.fill(self._config.blackboard_user)
            next_btn = self._page.locator("#idSIButton9, input[type='submit']").first
            await next_btn.click(timeout=10000)
            await self._page.wait_for_load_state("networkidle", timeout=20000)
            return True
        except Exception as exc:
            self._log("WARN", f"Microsoft email step failed: {exc}")
            return False

    async def _microsoft_fill_password(self) -> bool:
        try:
            pwd = self._page.locator("input[type='password']").first
            await pwd.wait_for(state="visible", timeout=20000)
            await pwd.fill(self._config.blackboard_pass)
            submit = self._page.locator(
                "input[type='submit'], button[type='submit'], #idSIButton9"
            ).first
            await submit.click(timeout=10000)
            await self._page.wait_for_load_state("networkidle", timeout=30000)
            return True
        except Exception as exc:
            self._log("WARN", f"Microsoft password step failed: {exc}")
            return False

    async def _microsoft_handle_kmsi(self) -> None:
        """Click 'No' on Microsoft's 'Stay signed in?' prompt if present."""
        try:
            back = self._page.locator(
                "#idBtn_Back, input[value='No'], button:has-text('No')"
            ).first
            if await back.count() > 0:
                await back.click(timeout=5000)
                await self._page.wait_for_load_state("networkidle", timeout=15000)
        except Exception as exc:
            self._log("WARN", f"KMSI handling: {exc}")

    async def scrape_assignments(self) -> list[dict[str, Any]]:
        """Scrape all assignments from Blackboard."""
        self._start_time = time.monotonic()
        self._log("INFO", f"Scrape start (headless={self._config.headless}, url={self._config.blackboard_url})")
        if not self._config.blackboard_user or not self._config.blackboard_pass:
            self._log("ERROR", "Credentials missing — set blackboard_user/blackboard_pass first")
            return []
        try:
            await self._ensure_browser()

            self._log("INFO", "Trying to restore saved session")
            restored = await self._try_restore_session()
            if not restored:
                self._log("INFO", "No saved session usable, performing fresh login")
                if not await self.login():
                    self._log("ERROR", "Login failed, aborting scrape")
                    return []
                await self._save_session()
            else:
                self._log("OK", "Session restored, skipping login")

            self._log("INFO", "Extracting assignments from current DOM")
            raw = await self._extract_assignments_from_dom()
            self._log("INFO", f"Initial DOM yielded {len(raw)} candidate(s)")

            if not raw:
                self._log("INFO", "No assignments yet, trying Ultra calendar")
                if await self._try_ultra_calendar():
                    await asyncio.sleep(2)
                    self._log("INFO", "Activating Ultra deadline view")
                    await self._activate_ultra_deadline_view()
                    await asyncio.sleep(2)
                    raw = await self._extract_assignments_from_dom()
                    self._log("INFO", f"Ultra calendar yielded {len(raw)} candidate(s)")

        except Exception as exc:
            if "EPIPE" in str(exc):
                self._log("WARN", "EPIPE detected, restarting browser and retrying")
                await self._close_browser_and_playwright()
                await self._ensure_browser()
                if not await self._try_restore_session():
                    if not await self.login():
                        return []
                    await self._save_session()
                raw = await self._extract_assignments_from_dom()
            else:
                self._log("ERROR", f"Scrape failed: {type(exc).__name__}: {exc}")
                return []

        assignments = []
        skipped_no_date = 0
        for item in raw:
            norm = self._normalize_assignment(item)
            if norm.get("due_date"):
                assignments.append(norm)
            else:
                skipped_no_date += 1
        if skipped_no_date:
            self._log("WARN", f"Skipped {skipped_no_date} item(s) without parseable due_date")
        self._log("OK", f"Scrape finished: {len(assignments)} assignment(s) ready")
        return assignments

    async def close(self) -> None:
        if self._context is not None:
            await self._context.close()
            self._context = None
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        self._page = None
        if self._playwright is not None:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            self._playwright = None

    # ── Private ──────────────────────────────────────────────────────────────

    async def _close_browser_and_playwright(self) -> None:
        if self._browser is not None:
            try:
                await self._browser.close()
            except Exception:
                pass
        if self._playwright is not None:
            try:
                await self._playwright.stop()
            except Exception:
                pass
        self._browser = None
        self._context = None
        self._page = None
        self._playwright = None

    async def _ensure_browser(self) -> None:
        if self._browser is not None:
            return
        self._log("INFO", "Launching Playwright Chromium")
        pw = await async_playwright().start()
        self._playwright = pw
        self._browser = await pw.chromium.launch(
            headless=self._config.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        )
        self._log("OK", "Chromium launched")
        self._context = await self._browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        self._page = await self._context.new_page()

    def _load_session(self) -> dict | None:
        if not self._session_file_path.exists():
            return None
        try:
            return json.loads(self._session_file_path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _save_session_to_disk(self, data: dict) -> None:
        self._session_file_path.parent.mkdir(parents=True, exist_ok=True)
        temp = self._session_file_path.with_suffix(".tmp")
        text = json.dumps(data, indent=2, ensure_ascii=False)
        temp.write_text(text, encoding="utf-8")
        try:
            temp.rename(self._session_file_path)
        except OSError:
            self._session_file_path.write_text(text, encoding="utf-8")
            temp.unlink(missing_ok=True)

    async def _try_restore_session(self) -> bool:
        session_data = self._load_session()
        if session_data is None:
            self._log("INFO", "No session file on disk")
            return False
        try:
            if "cookies" in session_data:
                self._log("INFO", f"Loading {len(session_data['cookies'])} saved cookie(s)")
                await self._context.add_cookies(session_data["cookies"])
            await self._page.goto(self._config.blackboard_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(1)
            ok = await self._is_logged_in()
            self._log("INFO" if ok else "WARN", f"Session restore: logged_in={ok}, url={self._page.url}")
            return ok
        except Exception as exc:
            self._log("WARN", f"Session restore raised: {type(exc).__name__}: {exc}")
            return False

    async def _save_session(self) -> None:
        try:
            cookies = await self._context.cookies()
            storage = await self._context.storage_state()
            self._save_session_to_disk({
                "cookies": cookies,
                "storage_state": storage,
                "saved_at": datetime.now(timezone.utc).isoformat(),
            })
        except Exception:
            pass

    async def _fill_login_form(self) -> None:
        current_url = self._page.url.lower()
        if "microsoftonline" in current_url or "login.microsoft" in current_url:
            await self._fill_microsoft_login()
            return

        # Check Microsoft fields
        ms_selectors = [
            "input[name='loginfmt']",
            "input[type='email']",
            "input[autocomplete='username']",
        ]
        for sel in ms_selectors:
            try:
                if await self._page.locator(sel).count() > 0:
                    await self._fill_microsoft_login()
                    return
            except Exception:
                continue

        await self._fill_blackboard_login()

    async def _fill_blackboard_login(self) -> None:
        user_selectors = ["#username", "#user_id", "input[name='username']", "input[type='text']"]
        pass_selectors = ["#password", "input[name='password']", "input[type='password']"]

        for sel in user_selectors:
            try:
                el = self._page.locator(sel).first
                if await el.count() > 0:
                    await el.fill(self._config.blackboard_user)
                    break
            except Exception:
                continue

        await asyncio.sleep(0.5)

        for sel in pass_selectors:
            try:
                el = self._page.locator(sel).first
                if await el.count() > 0:
                    await el.fill(self._config.blackboard_pass)
                    break
            except Exception:
                continue

    async def _fill_microsoft_login(self) -> None:
        email_selectors = ["input[name='loginfmt']", "input[type='email']", "input[name='email']"]
        for sel in email_selectors:
            try:
                el = self._page.locator(sel).first
                if await el.count() > 0:
                    await el.fill(self._config.blackboard_user)
                    break
            except Exception:
                continue

        await asyncio.sleep(0.5)

        next_selectors = ["#idSIButton9", "input[type='submit']", "button[type='submit']"]
        for sel in next_selectors:
            try:
                el = self._page.locator(sel).first
                if await el.count() > 0:
                    await el.click()
                    break
            except Exception:
                continue

        await asyncio.sleep(2)

        pass_selectors = ["input[type='password']", "input[name='passwd']", "#passwordInput"]
        for sel in pass_selectors:
            try:
                el = self._page.locator(sel).first
                if await el.count() > 0:
                    await el.fill(self._config.blackboard_pass)
                    break
            except Exception:
                continue

        await asyncio.sleep(0.5)

        for sel in next_selectors:
            try:
                el = self._page.locator(sel).first
                if await el.count() > 0:
                    await el.click()
                    break
            except Exception:
                continue

        await asyncio.sleep(1)

        try:
            back_btn = self._page.locator("#idBtn_Back").first
            if await back_btn.count() > 0:
                await back_btn.click()
        except Exception:
            pass

    async def _submit_login_form(self) -> None:
        selectors = ["button[type='submit']", "input[type='submit']", "#loginBtn", ".login-btn"]
        for sel in selectors:
            try:
                el = self._page.locator(sel).first
                if await el.count() > 0:
                    await el.click()
                    break
            except Exception:
                continue
        try:
            await self._page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await asyncio.sleep(1)

    async def _is_logged_in(self) -> bool:
        url = self._page.url.lower()
        login_indicators = ["login", "signin", "auth", "credential", "microsoftonline"]
        for ind in login_indicators:
            if ind in url:
                return False
        dashboard_indicators = ["dashboard", "home", "mybb", "courses", "calendar", "ultra"]
        for ind in dashboard_indicators:
            if ind in url:
                return True
        try:
            for sel in [".header-inner", ".global-nav", ".course-list", ".bb-home-link"]:
                if await self._page.locator(sel).count() > 0:
                    return True
        except Exception:
            pass
        return False

    async def _click_o365_login_button(self) -> bool:
        selectors = [
            "a.icon-o365",
            "a[href*='auth-saml/saml/login']",
            "a:has-text('@senati.pe')",
            "a:has-text('Ingresa con tu correo')",
            "button:has-text('O365')",
        ]
        for sel in selectors:
            try:
                btn = self._page.locator(sel).first
                if await btn.count() > 0 and await btn.is_visible():
                    await btn.click()
                    await asyncio.sleep(1)
                    return True
            except Exception:
                continue
        return False

    async def _try_ultra_calendar(self) -> bool:
        try:
            url = self._config.blackboard_url.rstrip("/") + "/ultra/calendar"
            await self._page.goto(url, wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(3)
            return True
        except Exception:
            return False

    async def _activate_ultra_deadline_view(self) -> bool:
        selectors = [
            "#bb-calendar1-deadline",
            "button:has-text('Fechas de vencimiento')",
            "button[id*='deadline']",
            "[aria-controls='deadlineContainer']",
        ]
        for sel in selectors:
            try:
                btn = self._page.locator(sel).first
                if await btn.count() > 0 and await btn.is_visible():
                    await btn.click()
                    await asyncio.sleep(4)
                    return True
            except Exception:
                continue
        return False

    async def _extract_assignments_from_dom(self) -> list[dict[str, Any]]:
        if self._page is None:
            return []
        try:
            data = await self._page.evaluate("""() => {
                const results = [];
                const bodyText = document.body?.innerText || '';
                const lines = bodyText.split('\\n').map(l => l.trim()).filter(l => l);
                for (let i = 0; i < lines.length - 1; i++) {
                    const currentLine = lines[i];
                    const nextLine = lines[i + 1];
                    if (nextLine.includes('Fecha de entrega') && nextLine.includes('\\u2219')) {
                        const title = currentLine;
                        const parts = nextLine.split('\\u2219');
                        const datePart = parts[0]?.trim() || '';
                        const coursePart = parts[1]?.trim() || '';
                        const dateMatch = datePart.match(/(\\d{1,2}\\/\\d{1,2}\\/\\d{2,4})\\s+(\\d{1,2}:\\d{2})/);
                        const dueDate = dateMatch ? dateMatch[1] + ' ' + dateMatch[2] : '';
                        const courseParts = coursePart.split(':');
                        const courseId = courseParts[0]?.trim() || '';
                        const courseName = courseParts.slice(1).join(':').trim() || '';
                        results.push({
                            title: title,
                            course_name: courseName,
                            course_id: courseId,
                            due_date: dueDate,
                            status: 'Pending',
                        });
                    }
                }
                return results;
            }""")
            return data if isinstance(data, list) else []
        except Exception as exc:
            print(f"[BlackboardScraper] DOM extraction failed: {exc}")
            return []

    def _normalize_assignment(self, raw: dict[str, Any]) -> dict[str, Any]:
        due_date: str | None = None
        raw_due = raw.get("due_date", "")
        if raw_due:
            for fmt in ("%d/%m/%y %H:%M", "%d/%m/%Y %H:%M", "%m/%d/%y %H:%M", "%m/%d/%Y %H:%M"):
                try:
                    dt = datetime.strptime(raw_due, fmt)
                    due_date = dt.replace(tzinfo=timezone.utc).isoformat()
                    break
                except ValueError:
                    continue
            else:
                try:
                    dt = dateutil_parser.isoparse(raw_due)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    due_date = dt.isoformat()
                except Exception:
                    due_date = None

        title = raw.get("title", "Unknown")[:500]
        course = raw.get("course_name", "Unknown")[:200]
        course_id = raw.get("course_id", "")
        composite = f"{course_id}|{title}"
        assignment_id = hashlib.sha256(composite.encode()).hexdigest()[:16]

        source_url = raw.get("source_url", "")
        if source_url and not source_url.startswith(("http://", "https://")):
            source_url = self._config.blackboard_url.rstrip("/") + source_url

        return {
            "assignment_id": assignment_id,
            "title": title,
            "course_name": course,
            "course_id": course_id,
            "due_date": due_date,
            "status": raw.get("status", "Pending"),
            "source_url": source_url,
        }
