"""Standalone scraper test — read creds from DB, attempt login, dump screenshots.

Run:
    uv run python scripts/test_scrape.py

Outputs:
    /tmp/bb_scrape/step_*.png  — screenshots after each milestone
    /tmp/bb_scrape/page_*.html — saved DOM snapshots
    stdout log with timestamps
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

from playwright.async_api import async_playwright


OUT_DIR = Path("/tmp/bb_scrape")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


async def snapshot(page, name: str) -> None:
    try:
        await page.screenshot(path=str(OUT_DIR / f"{name}.png"), full_page=True)
    except Exception as exc:
        log(f"screenshot {name} failed: {exc}")
    try:
        html = await page.content()
        (OUT_DIR / f"{name}.html").write_text(html, encoding="utf-8")
    except Exception as exc:
        log(f"html dump {name} failed: {exc}")


async def main() -> int:
    # Load creds from DB
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from src.bot.plugins.blackboard.database import BlackboardDatabase  # noqa: E402

    db = BlackboardDatabase("data/plugins/blackboard.db")
    await db.init_db()
    cfg = await db.get_config()
    user = cfg.get("blackboard_user", "")
    pwd = cfg.get("blackboard_pass", "")
    url = cfg.get("blackboard_url", "https://senati.blackboard.com")
    await db.close()

    if not user or not pwd:
        log("ERROR: blackboard_user/blackboard_pass missing in DB")
        return 1

    log(f"Using user={user} url={url}")

    async with async_playwright() as pw:
        log("Launching chromium")
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        ctx = await browser.new_context(
            viewport={"width": 1366, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = await ctx.new_page()

        try:
            log(f"Goto {url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(1.5)
            log(f"At {page.url}, title={await page.title()}")
            await snapshot(page, "01_landing")

            # Dismiss Blackboard consent dialog if present
            consent_sels = [
                "#agree_button",
                "button:has-text('Aceptar')",
                "button:has-text('Accept')",
            ]
            for sel in consent_sels:
                try:
                    loc = page.locator(sel).first
                    if await loc.count() > 0 and await loc.is_visible():
                        log(f"Dismissing consent via {sel!r}")
                        await loc.click(timeout=5000)
                        await asyncio.sleep(1.5)
                        break
                except Exception as exc:
                    log(f"consent dismiss {sel!r} error: {exc}")

            await snapshot(page, "01b_consent_dismissed")

            # Find O365 / SAML login button
            candidates = [
                "a.icon-o365",
                "a[href*='auth-saml/saml/login']",
                "a:has-text('correo institucional')",
                "a:has-text('@senati.pe')",
                "a:has-text('Ingresa con tu correo')",
                "a:has-text('Senati')",
                "a:has-text('SENATI')",
                "button:has-text('Microsoft')",
                "button:has-text('O365')",
            ]
            clicked_sel: str | None = None
            for sel in candidates:
                try:
                    loc = page.locator(sel).first
                    count = await loc.count()
                    if count == 0:
                        continue
                    visible = await loc.is_visible()
                    log(f"Selector {sel!r}: count={count} visible={visible}")
                    if visible:
                        async with page.expect_navigation(
                            wait_until="domcontentloaded", timeout=30000
                        ):
                            await loc.click()
                        clicked_sel = sel
                        log(f"Clicked {sel!r}, now at {page.url}")
                        break
                except Exception as exc:
                    log(f"selector {sel!r} error: {type(exc).__name__}: {exc}")
                    continue

            if not clicked_sel:
                # Maybe the login form is already inline (no Microsoft)
                log("No O365 button clicked — dumping DOM for analysis")
            await snapshot(page, "02_after_click")
            log(f"URL after click: {page.url}")

            # Wait for either Microsoft login or course shell
            try:
                await page.wait_for_url(
                    lambda u: "microsoftonline" in u
                    or "login.microsoft" in u
                    or "/ultra/" in u
                    or "saml" in u,
                    timeout=30000,
                )
                log(f"Reached gate: {page.url}")
            except Exception:
                log(f"No gate reached, stuck at {page.url}")

            await snapshot(page, "03_after_wait")

            # If on Microsoft, fill email
            if "microsoft" in page.url.lower() or "login.live" in page.url.lower():
                log("Microsoft page detected, filling email")
                email_sel = "input[type='email'], input[name='loginfmt']"
                await page.locator(email_sel).first.fill(user)
                log("email filled, clicking Next")
                await page.locator("#idSIButton9, input[type='submit']").first.click()
                await page.wait_for_load_state("networkidle", timeout=20000)
                await snapshot(page, "04_email_submitted")

                log(f"After email submit: {page.url}")
                # Password page (could be redirected to FederationRedirect)
                if "federation" in page.url.lower() or "adfs" in page.url.lower() or "senati" in page.url.lower():
                    log("On federation redirect, looking for password input")
                pass_sel = "input[type='password']"
                try:
                    await page.locator(pass_sel).first.wait_for(state="visible", timeout=20000)
                    await page.locator(pass_sel).first.fill(pwd)
                    log("password filled, submitting")
                    sub = "input[type='submit'], button[type='submit'], #idSIButton9"
                    await page.locator(sub).first.click()
                    await page.wait_for_load_state("networkidle", timeout=30000)
                    await snapshot(page, "05_password_submitted")
                except Exception as exc:
                    log(f"password step failed: {type(exc).__name__}: {exc}")
                    await snapshot(page, "05_password_failed")

                # KMSI "Stay signed in?" page
                try:
                    back = page.locator("#idBtn_Back, input[value='No'], button:has-text('No')").first
                    if await back.count() > 0:
                        log("KMSI page, clicking No")
                        await back.click()
                        await page.wait_for_load_state("networkidle", timeout=20000)
                        await snapshot(page, "06_kmsi_dismissed")
                except Exception as exc:
                    log(f"KMSI step error: {exc}")

            log(f"Final URL: {page.url}")
            await snapshot(page, "07_final")

            # Try navigate to Ultra calendar to extract assignments
            ultra_url = url.rstrip("/") + "/ultra/calendar"
            log(f"Navigating to Ultra calendar: {ultra_url}")
            try:
                await page.goto(ultra_url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(3)
                await snapshot(page, "08_ultra_calendar")
                log(f"Ultra at {page.url}")
            except Exception as exc:
                log(f"Ultra navigation failed: {exc}")

            # Try the deadline view
            try:
                for sel in [
                    "#bb-calendar1-deadline",
                    "button:has-text('Fechas de vencimiento')",
                    "[aria-controls='deadlineContainer']",
                ]:
                    loc = page.locator(sel).first
                    if await loc.count() > 0 and await loc.is_visible():
                        log(f"Clicking deadline view selector {sel!r}")
                        await loc.click()
                        await asyncio.sleep(4)
                        break
            except Exception as exc:
                log(f"deadline view error: {exc}")
            await snapshot(page, "09_deadline_view")

            # Extract from DOM
            data = await page.evaluate(
                """() => {
                const results = [];
                const bodyText = document.body?.innerText || '';
                const lines = bodyText.split('\\n').map(l => l.trim()).filter(l => l);
                for (let i = 0; i < lines.length - 1; i++) {
                    const cur = lines[i];
                    const nxt = lines[i + 1];
                    if (nxt.includes('Fecha de entrega') && nxt.includes('\\u2219')) {
                        const parts = nxt.split('\\u2219');
                        const datePart = (parts[0] || '').trim();
                        const coursePart = (parts[1] || '').trim();
                        const m = datePart.match(/(\\d{1,2}\\/\\d{1,2}\\/\\d{2,4})\\s+(\\d{1,2}:\\d{2})/);
                        const due = m ? m[1] + ' ' + m[2] : '';
                        const cp = coursePart.split(':');
                        const cid = (cp[0] || '').trim();
                        const cname = cp.slice(1).join(':').trim();
                        results.push({ title: cur, course_name: cname, course_id: cid, due_date: due });
                    }
                }
                return results;
            }"""
            )
            log(f"DOM extraction yielded {len(data)} assignment(s)")
            for a in data[:5]:
                log(f"  - {a.get('title')!r} due={a.get('due_date')} course={a.get('course_name')}")

        finally:
            await browser.close()

    log(f"Done. Screenshots and HTML dumps in {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
