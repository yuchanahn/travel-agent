"""Real DOM checks with local synthetic pages; no Google requests."""

import importlib.util
import tempfile
import unittest
from pathlib import Path

from travel_agent.google_browser import clean_hits, inspect_page


class URLTests(unittest.TestCase):
    def test_unwrap_deduplicate_and_reject_internal_or_credential_links(self):
        rows = [{"title": "Python", "href": "https://www.google.com/url?q=https%3A%2F%2Fpython.org%2F"},
                {"title": "Duplicate", "href": "https://python.org/#section"},
                {"title": "Internal", "href": "https://accounts.google.com/"},
                {"title": "Credentials", "href": "https://user:secret@example.invalid/"},
                {"title": "Script", "href": "javascript:alert(1)"}]
        self.assertEqual(clean_hits(rows), [{"title": "Python", "url": "https://python.org/", "snippet": ""}])


@unittest.skipUnless(importlib.util.find_spec("playwright"), "Optional [browser] dependency missing")
class DOMTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.runtime = sync_playwright().start()
        try:
            cls.browser = cls.runtime.chromium.launch(channel="chrome", headless=True)
        except Exception:
            cls.runtime.stop()
            raise

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.runtime.stop()

    def setUp(self):
        self.page = self.browser.new_page()
        self.page.route("**/*", lambda route: route.abort())

    def tearDown(self):
        self.page.close()

    def test_title_uses_its_own_anchor_not_first_block_link(self):
        self.page.set_content('<div id="search"><div class="MjjYud">'
                              '<a href="https://wrong.invalid/">Other link</a>'
                              '<a href="https://python.org/"><h3>Python official</h3></a>'
                              '<div class="VwiC3b">Synthetic snippet</div></div></div>')
        status, hits = inspect_page(self.page)
        self.assertEqual(status, "ok")
        self.assertEqual(hits, [{"title": "Python official", "url": "https://python.org/", "snippet": "Synthetic snippet"}])

    def test_heading_without_result_link_is_not_success(self):
        self.page.set_content('<div id="search"><h3>No link</h3></div>')
        self.assertEqual(inspect_page(self.page), ("no_search_markup", []))

    def test_access_check_wins_over_search_shaped_content(self):
        self.page.set_content('<form id="captcha-form"></form><div id="search">'
                              '<a href="https://python.org/"><h3>Fixture</h3></a></div>')
        self.assertEqual(inspect_page(self.page), ("access_interstitial", []))

    def test_dedicated_profile_persists_synthetic_cookie_across_launches(self):
        with tempfile.TemporaryDirectory() as folder:
            profile = str(Path(folder) / "profile")
            context = self.runtime.chromium.launch_persistent_context(profile, channel="chrome", headless=True)
            context.add_cookies([{"name": "synthetic", "value": "fixture", "domain": "example.invalid",
                                 "path": "/", "expires": 2_000_000_000}])
            context.close()
            context = self.runtime.chromium.launch_persistent_context(profile, channel="chrome", headless=True)
            try:
                self.assertTrue(any(c["name"] == "synthetic" and c["value"] == "fixture" for c in context.cookies()))
            finally:
                context.close()


if __name__ == "__main__":
    unittest.main()
