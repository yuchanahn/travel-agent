import importlib.util
import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from travel_agent.google_http import allowed_redirect, load_cookies, parse_page, result_url, save_cookies, search


FIXTURE = b'<div class="MjjYud"><a href="https://wrong.invalid/">Unrelated</a><a href="https://python.org/"><h3>Python</h3></a><div class="VwiC3b">Synthetic snippet</div></div>'


class ParserTests(unittest.TestCase):
    def test_title_and_url_belong_to_same_anchor(self):
        self.assertEqual(parse_page(FIXTURE, "https://www.google.com/search", 200),
                         ("ok", [{"title": "Python", "url": "https://python.org/", "snippet": "Synthetic snippet"}]))

    def test_links_are_unwrapped_deduplicated_and_sanitized(self):
        self.assertEqual(result_url('/url?q=https%3A%2F%2Fpython.org%2F%23frag'), "https://python.org/")
        for url in ["/search?q=more", "https://accounts.google.com/", "javascript:alert(1)", "https://u:secret@example.invalid/"]:
            self.assertIsNone(result_url(url))
        self.assertEqual(len(parse_page(FIXTURE + FIXTURE, "https://www.google.com/search", 200)[1]), 1)
        self.assertTrue(allowed_redirect("https://www.google.com/search?q=test", {"www.google.com"}))
        for target in ["http://www.google.com/", "https://www.google.com:9000/", "https://u:p@www.google.com/", "https://www.google.com.attacker.invalid/"]:
            self.assertFalse(allowed_redirect(target, {"www.google.com"}))

    def test_access_checks_and_js_pages_are_not_search_results(self):
        self.assertEqual(parse_page(FIXTURE, "https://www.google.com/sorry/index?private=token", 429), ("access_interstitial", []))
        self.assertEqual(parse_page(b'<form id="captcha-form"></form>' + FIXTURE, "https://www.google.com/search", 200), ("access_interstitial", []))
        self.assertEqual(parse_page(b'<a href="/httpservice/retry/enablejs">Enable</a>', "https://www.google.com/search", 200), ("javascript_required", []))
        self.assertEqual(parse_page(b'<h3>No link</h3>', "https://www.google.com/search", 200), ("no_search_markup", []))


@unittest.skipUnless(importlib.util.find_spec("curl_cffi"), "Optional HTTP dependency missing")
class SessionTests(unittest.TestCase):
    def test_cookie_domain_path_secure_expiry_survive_disk_round_trip(self):
        from curl_cffi.requests import Cookies
        cookies = Cookies()
        cookies.set("fixture", "secret-value", domain="www.google.com", path="/search", secure=True)
        cookie = next(iter(cookies.jar))
        cookie.expires = int(time.time()) + 300
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "cookies.txt"
            save_cookies(cookies.jar, path)
            loaded = next(iter(load_cookies(path)))
            self.assertEqual((loaded.domain, loaded.path, loaded.secure, loaded.expires),
                             (cookie.domain, cookie.path, True, cookie.expires))
            cookie.expires = 1
            save_cookies(cookies.jar, path)
            self.assertEqual(len(load_cookies(path)), 0)

    def test_two_independent_searches_reuse_cookie_file_without_leaking_values(self):
        from curl_cffi.requests import Cookies
        initialized, requests = [], []

        class FakeSession:
            def __init__(self, **kwargs):
                self.cookies = Cookies(kwargs["cookies"])
                initialized.append(len(self.cookies.jar))

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def get(self, url, **kwargs):
                requests.append((url, kwargs))
                self.cookies.set("fixture", "secret-value", domain="www.google.com")
                return SimpleNamespace(url=url, content=FIXTURE if url.endswith("/search") else b"<html></html>", status_code=200, headers={})

        with tempfile.TemporaryDirectory() as folder, patch("curl_cffi.requests.Session", FakeSession):
            path = Path(folder) / "cookies.txt"
            first = search("Python official website", cookie_file=path)
            second = search("Python official website", cookie_file=path)
        self.assertEqual(initialized, [0, 1])
        self.assertTrue(first["web_search_performed"] and second["web_search_performed"])
        self.assertNotIn("secret-value", json.dumps(first))
        self.assertEqual(len(requests), 4)
        self.assertTrue(all(not kwargs["allow_redirects"] for _, kwargs in requests))

    def test_external_redirect_is_rejected_before_request(self):
        from curl_cffi.requests import Cookies
        response = SimpleNamespace(url="https://www.google.com/", status_code=302, content=b"", headers={"location": "https://outside.invalid/?secret=private"})
        with tempfile.TemporaryDirectory() as folder, patch("curl_cffi.requests.Session") as factory:
            client = factory.return_value.__enter__.return_value
            client.cookies = Cookies()
            client.get.return_value = response
            report = search("test", cookie_file=Path(folder) / "cookies.txt")
            self.assertEqual(client.get.call_count, 1)
        self.assertEqual(report["status"], "unsupported_redirect")
        self.assertNotIn("private", json.dumps(report))


@unittest.skipUnless(importlib.util.find_spec("quickjs"), "Optional JavaScript experiment missing")
class JavaScriptTests(unittest.TestCase):
    def test_captures_cookie_and_redirect_without_exposing_host_apis(self):
        from travel_agent.google_javascript import evaluate_challenge
        state = evaluate_challenge(b'''<script>document.cookie='SG_SS=fixture; expires=Wed, 01 Jan 2031 00:00:00 GMT; path=/';
            location.replace(location.pathname + location.search);
            if(typeof process !== 'undefined' || typeof require !== 'undefined') throw Error('host exposed');</script>''', "https://www.google.com/search?q=test")
        self.assertEqual(state["cookies"], {"SG_SS": "fixture"})
        self.assertEqual(state["redirects"], ["/search?q=test"])
        self.assertEqual(state["diagnostics"]["errors"], [])
        self.assertNotIn("fixture", json.dumps(state["diagnostics"]))

    def test_script_error_does_not_leak_its_message(self):
        from travel_agent.google_javascript import evaluate_challenge
        state = evaluate_challenge(b"<script>throw Error('private-token')</script>", "https://www.google.com/")
        self.assertEqual(state["diagnostics"]["errors"], [{"stage": "script", "index": 0}])
        self.assertNotIn("private-token", json.dumps(state["diagnostics"]))

    def test_infinite_computation_is_interrupted(self):
        from travel_agent.google_javascript import evaluate_challenge
        start = time.perf_counter()
        state = evaluate_challenge(b"<script>while(true){}</script>", "https://www.google.com/")
        self.assertLess(time.perf_counter() - start, 4)
        self.assertEqual(state["diagnostics"]["errors"], [{"stage": "script", "index": 0}])


if __name__ == "__main__":
    unittest.main()
