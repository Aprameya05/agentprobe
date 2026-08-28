"""
AgentProbe -- Playwright browser session

Thin wrapper around a Playwright browser instance.
Provides get_page_summary() for the Claude loop and execute_action()
for executing Claude's decisions.
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)


class BrowserSession:
    """
    Async context manager. One session per audit.

    Usage:
        async with BrowserSession() as session:
            await session.page.goto(url)
            summary = await session.get_page_summary()
    """

    def __init__(self):
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    async def __aenter__(self) -> "BrowserSession":
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--single-process",
                "--no-zygote",
            ],
        )
        self._context = await self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (compatible; AgentProbe/1.0; "
                "+https://github.com/Aprameya05/agentprobe)"
            ),
            viewport={"width": 1280, "height": 900},
            java_script_enabled=True,
        )
        self.page = await self._context.new_page()

        # Block heavy media to speed up page loads
        await self.page.route(
            "**/*.{png,jpg,jpeg,gif,svg,mp4,webm,woff,woff2,ttf,eot}",
            lambda route: route.abort(),
        )
        return self

    async def __aexit__(self, *args) -> None:
        if self.page:
            await self.page.close()
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    # -----------------------------------------------------------------------
    # Page summary for Claude
    # -----------------------------------------------------------------------

    async def get_page_summary(self) -> dict[str, Any]:
        """
        Extract a concise, structured summary of the current page state.
        Keeps token count low (~800-1200 tokens) while giving Claude
        enough signal to make a good decision.
        """
        try:
            return await self.page.evaluate("""() => {
                function visible(el) {
                    const r = el.getBoundingClientRect();
                    return r.width > 0 && r.height > 0 && el.offsetParent !== null;
                }
                function text(el) {
                    return (el.innerText || el.textContent || '').trim().slice(0, 100);
                }
                function label(el) {
                    return (
                        el.getAttribute('aria-label') ||
                        el.getAttribute('title') ||
                        el.getAttribute('placeholder') ||
                        el.name ||
                        text(el)
                    ).trim().slice(0, 80);
                }

                // Key links (nav, CTAs, footer)
                const links = Array.from(document.querySelectorAll('a[href]'))
                    .filter(visible)
                    .map(a => ({ text: text(a), href: a.href }))
                    .filter(l => l.text && !l.href.startsWith('javascript'))
                    .slice(0, 25);

                // Buttons and button-like elements
                const buttons = Array.from(document.querySelectorAll(
                    'button, [role="button"], input[type="submit"], input[type="button"], a.btn, a.button'
                ))
                    .filter(visible)
                    .map(b => ({ label: label(b), tag: b.tagName.toLowerCase() }))
                    .filter(b => b.label)
                    .slice(0, 20);

                // Form inputs
                const inputs = Array.from(document.querySelectorAll(
                    'input:not([type="hidden"]), textarea, select'
                ))
                    .filter(visible)
                    .map(i => ({
                        type: i.type || i.tagName.toLowerCase(),
                        name: i.name || i.id || i.getAttribute('aria-label') || i.placeholder || '',
                        required: i.required
                    }))
                    .slice(0, 10);

                // Headings (page structure signal)
                const headings = Array.from(document.querySelectorAll('h1, h2, h3'))
                    .map(h => ({ level: h.tagName, text: text(h) }))
                    .filter(h => h.text)
                    .slice(0, 8);

                // Visible body text (first 1500 chars)
                const bodyText = document.body.innerText.slice(0, 1500);

                // Price/number signals
                const priceEls = Array.from(document.querySelectorAll(
                    '[class*="price"], [class*="cost"], [class*="plan"], [data-price]'
                ))
                    .map(e => text(e))
                    .filter(t => t && t.match(/[\$€£¥\d]/))
                    .slice(0, 8);

                return {
                    url: window.location.href,
                    title: document.title,
                    headings,
                    links,
                    buttons,
                    inputs,
                    prices: priceEls,
                    body_snippet: bodyText,
                };
            }""")
        except Exception as e:
            return {"error": str(e), "url": self.page.url}

    # -----------------------------------------------------------------------
    # Action execution
    # -----------------------------------------------------------------------

    async def execute_action(
        self,
        action: str,
        target: Optional[str],
        value: Optional[str],
    ) -> bool:
        """
        Execute Claude's decided action.
        Returns True if the agent went back (backtrack signal).
        """
        went_back = False

        if action == "navigate":
            url = target or ""
            if url.startswith("back"):
                await self.page.go_back()
                went_back = True
            elif url:
                if not url.startswith("http"):
                    base = self.page.url.split("/")[0:3]
                    url = "/".join(base) + ("" if url.startswith("/") else "/") + url
                await self.page.goto(url, wait_until="domcontentloaded", timeout=20000)
            await asyncio.sleep(1)

        elif action == "click":
            if not target:
                return False
            try:
                # Try CSS selector first
                await self.page.click(target, timeout=5000)
            except Exception:
                try:
                    # Try by text
                    await self.page.get_by_text(target, exact=False).first.click(timeout=4000)
                except Exception:
                    try:
                        # Try by role
                        await self.page.locator(f"text={target}").first.click(timeout=3000)
                    except Exception:
                        pass
            await asyncio.sleep(1)

        elif action == "type":
            if target and value:
                try:
                    await self.page.fill(target, value, timeout=5000)
                except Exception:
                    try:
                        await self.page.locator(f"placeholder={target}").fill(value, timeout=3000)
                    except Exception:
                        pass

        elif action == "scroll":
            await self.page.evaluate("window.scrollBy(0, 500)")
            await asyncio.sleep(0.5)

        elif action == "wait":
            await asyncio.sleep(2)

        return went_back
