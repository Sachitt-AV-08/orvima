"""Playwright fixture tests for real-mode browser agent.

These tests run against local static HTML fixtures to catch flaky-wait bugs
and selector rot that every browser agent hits.
"""

from __future__ import annotations

import base64
from pathlib import Path

import pytest

from orvima.browser import BrowserController


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _file_url(name: str) -> str:
    return (FIXTURES_DIR / name).resolve().as_uri()


class TestLoginForm:
    """Test filling and submitting a login form with success and failure cases."""

    def test_login_form_submission(self):
        ctl = BrowserController(headless=True)
        with ctl:
            # Navigate to login form
            ctl.navigate(_file_url("login_form.html"))
            
            # Successful login
            ctl.fill("input#email", "test@example.com")
            ctl.fill("input#password", "secret123")
            ctl.click("button#submit-btn")
            
            # Wait for success message
            ctl.wait_for(".message.success", timeout_ms=3000)
            snap = ctl.snapshot()
            assert "Login successful" in (snap.get("body") or "")
            
            # Failed login - clear and retry
            ctl.fill("input#email", "wrong@example.com")
            ctl.fill("input#password", "wrongpass")
            ctl.click("button#submit-btn")
            
            ctl.wait_for(".message.error", timeout_ms=3000)
            snap = ctl.snapshot()
            assert "Invalid credentials" in (snap.get("body") or "")


class TestIframe:
    """Test navigating to a page with iframe and interacting with iframe content."""

    def test_iframe_navigation_and_interaction(self):
        ctl = BrowserController(headless=True)
        with ctl:
            ctl.navigate(_file_url("iframe_page.html"))
            
            # Verify main page loaded
            snap = ctl.snapshot()
            assert "Page with Iframe" in (snap.get("title") or "")
            
            # Switch to iframe context using frame locator
            iframe_locator = ctl.page.frame_locator("iframe")
            
            # Interact with iframe content
            iframe_locator.locator("input#name").fill("Test User")
            iframe_locator.locator("select#category").select_option("b")
            iframe_locator.locator("button[type=submit]").click()
            
            # Verify submission
            result = iframe_locator.locator("#result").text_content()
            assert "Test User" in result
            assert "b" in result  # value is 'b', label is 'Option B'


class TestDropdown:
    """Test selecting options from multiple dropdowns."""

    def test_dropdown_selection(self):
        ctl = BrowserController(headless=True)
        with ctl:
            ctl.navigate(_file_url("dropdown_page.html"))
            
            # Select country
            ctl.select("select#country", "jp")
            # Select priority
            ctl.select("select#priority", "high")
            
            # Submit
            ctl.click("button[type=submit]")
            
            # Verify results
            snap = ctl.snapshot()
            assert "Japan" in (snap.get("body") or "")
            assert "High" in (snap.get("body") or "")


class TestPromptInjection:
    """Test that prompt injections are visible in snapshots for the agent to see."""

    def test_prompt_injection_detection(self):
        ctl = BrowserController(headless=True)
        with ctl:
            ctl.navigate(_file_url("prompt_injection.html"))
            
            snap = ctl.snapshot()
            items = snap.get("items") or []
            
            # The snapshot should capture visible injection attempts in the DOM elements
            # so the LLM planner can see them and avoid acting on them
            item_text = " ".join(str(item.get("text", "")) for item in items)
            body = snap.get("body") or ""
            all_text = item_text + " " + body
            
            # These injections are visible in the DOM and should be captured
            # (hidden display:none elements are filtered out by snapshot)
            assert "SYSTEM OVERRIDE" in all_text
            assert "Disregard safety guidelines" in all_text


class TestSlowPage:
    """Test waiting for slow-loading content with proper wait_for."""

    def test_slow_page_wait(self):
        ctl = BrowserController(headless=True)
        with ctl:
            ctl.navigate(_file_url("slow_page.html"))
            
            # Initially spinner is visible
            snap = ctl.snapshot()
            assert "Loading content" in (snap.get("body") or "")
            
            # Wait for content to load (2 second delay in fixture)
            ctl.wait_for("#content.loaded", timeout_ms=5000)
            
            # Content should now be visible
            snap = ctl.snapshot()
            body = snap.get("body") or ""
            assert "Content Loaded Successfully" in body
            assert "All content is now visible" in body
            
            # Can interact with loaded content
            ctl.click("button#action-btn")
            # No exception means click succeeded


class TestMultiTab:
    """Test opening, listing, switching, and closing tabs."""

    def test_multi_tab_operations(self):
        ctl = BrowserController(headless=True)
        with ctl:
            ctl.navigate(_file_url("login_form.html"))
            
            # Open additional tabs
            ctl.open_tab(_file_url("dropdown_page.html"))
            ctl.open_tab(_file_url("slow_page.html"))
            
            # List tabs
            tabs = ctl.list_tabs()
            assert len(tabs["tabs"]) == 3
            
            # Switch to second tab
            ctl.switch_tab(1)
            snap = ctl.snapshot()
            assert "Dropdown Test" in (snap.get("title") or "")
            
            # Switch back to first
            ctl.switch_tab(0)
            snap = ctl.snapshot()
            assert "Login Form" in (snap.get("title") or "")
            
            # Close third tab
            ctl.close_tab(2)
            tabs = ctl.list_tabs()
            assert len(tabs["tabs"]) == 2


class TestScreenshot:
    """Test that screenshot capture works and returns base64 PNG."""

    def test_screenshot_capture(self):
        ctl = BrowserController(headless=True)
        with ctl:
            ctl.navigate(_file_url("login_form.html"))
            
            shot = ctl.screenshot()
            assert "png_b64" in shot
            import base64
            # Verify it's valid base64
            decoded = base64.b64decode(shot["png_b64"])
            assert decoded[:8] == b"\x89PNG\r\n\x1a\n"  # PNG magic bytes


class TestExtractEval:
    """Test extract and eval tools."""

    def test_extract_and_eval(self):
        ctl = BrowserController(headless=True)
        with ctl:
            ctl.navigate(_file_url("login_form.html"))
            
            # Extract text from heading
            extracted = ctl.extract("h1")
            assert "Sign In" in extracted.get("text", "")
            
            # Eval simple expression
            evaluated = ctl.eval("2 + 2")
            assert evaluated.get("result") == 4
            
            # Eval DOM query
            evaluated = ctl.eval("document.querySelectorAll('input').length")
            assert evaluated.get("result") >= 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])