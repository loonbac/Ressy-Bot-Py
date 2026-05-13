"""Blackboard scraper using Playwright.

Adapted from the reference implementation. Handles login,
session persistence, and assignment extraction via page.evaluate().
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dateutil import parser as dateutil_parser
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from src.bot.plugins.blackboard.models import BlackboardConfig


class ScrapingError(Exception):
    pass


class LoginError(ScrapingError):
    pass


class BlackboardScraper:
    """Scrapes assignments from Blackboard using headless Playwright."""

    def __init__(
        self,
        config: BlackboardConfig,
        session_file_path: str | Path | None = None,
    ) -> None:
        self._config = config
        self._session_file_path = Path(session_file_path or "data/plugins/blackboard_session.json")
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._playwright = None

    async def login(self) -> bool:
        """Authenticate to Blackboard. Returns True on success."""
        try:
            await self._ensure_browser()
            login_url = self._config.blackboard_url.rstrip("/")
            await self._page.goto(login_url, wait_until="domcontentloaded")
            await asyncio.sleep(1)

            if await self._is_logged_in():
                await self._save_session()
                return True

            await self._click_o365_login_button()
            await asyncio.sleep(2)

            if "/ultra/" in self._page.url.lower():
                await self._save_session()
                return True

            # Wait for Microsoft login page
            try:
                await self._page.wait_for_url("**login.microsoftonline.com**", timeout=15000)
            except Exception:
                pass

            if "/ultra/" in self._page.url.lower():
                await self._save_session()
                return True

            await self._fill_login_form()
            await self._submit_login_form()

            if await self._is_logged_in():
                await self._save_session()
                return True

            return False
        except Exception as exc:
            print(f"[BlackboardScraper] Login failed: {exc}")
            return False

    async def scrape_assignments(self) -> list[dict[str, Any]]:
        """Scrape all assignments from Blackboard."""
        try:
            await self._ensure_browser()

            if not await self._try_restore_session():
                if not await self.login():
                    return []
                await self._save_session()

            raw = await self._extract_assignments_from_dom()

            if not raw:
                # Try Ultra calendar
                if await self._try_ultra_calendar():
                    await asyncio.sleep(2)
                    await self._activate_ultra_deadline_view()
                    await asyncio.sleep(2)
                    raw = await self._extract_assignments_from_dom()

        except Exception as exc:
            if "EPIPE" in str(exc):
                await self._close_browser_and_playwright()
                await self._ensure_browser()
                if not await self._try_restore_session():
                    if not await self.login():
                        return []
                    await self._save_session()
                raw = await self._extract_assignments_from_dom()
            else:
                print(f"[BlackboardScraper] Scrape failed: {exc}")
                return []

        assignments = []
        for item in raw:
            norm = self._normalize_assignment(item)
            if norm.get("due_date"):
                assignments.append(norm)
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
            return False
        try:
            if "cookies" in session_data:
                await self._context.add_cookies(session_data["cookies"])
            await self._page.goto(self._config.blackboard_url, wait_until="domcontentloaded")
            await asyncio.sleep(1)
            if await self._is_logged_in():
                return True
            return False
        except Exception:
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
