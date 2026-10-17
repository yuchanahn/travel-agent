import importlib.util
import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import unquote

from travel_agent.google_http import allowed_redirect, document_cookies, load_cookies, parse_page, result_url, sanitized_wire_headers, save_cookies, search


FIXTURE = b'<div class="MjjYud"><a href="https://wrong.invalid/">Unrelated</a><a href="https://python.org/"><h3>Python</h3></a><div class="VwiC3b">Synthetic snippet</div></div>'


class ParserTests(unittest.TestCase):
    def test_wire_diagnostics_exclude_cookie_values_and_query_tokens(self):
        headers = b'GET /search?sei=private HTTP/2\r\nCookie: SG_SS=secret; NID=private\r\nReferer: https://www.google.com/search?sei=private\r\nSec-Fetch-Site: same-origin\r\n'
        result = sanitized_wire_headers(headers)
        self.assertEqual(result["cookie_names"], ["SG_SS", "NID"])
        self.assertEqual(result["sg_ss_lengths"], [6])
        self.assertEqual(result["referer_path"], "/search")
        self.assertNotIn("private", json.dumps(result))
        self.assertNotIn("secret", json.dumps(result))
        self.assertIsNone(sanitized_wire_headers(b'CONNECT www.google.com:443 HTTP/1.1\r\n'))

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
    def test_script_cookie_view_filters_real_curl_http_only_flags_and_scope(self):
        from curl_cffi.requests import Cookies
        cookies = Cookies()
        for name in ["visible", "hidden", "standard", "wrong_path", "expired"]:
            cookies.set(name, "fixture", domain="www.google.com", path="/other" if name == "wrong_path" else "/")
        for cookie in cookies.jar:
            if cookie.name == "visible":
                cookie._rest = {"http_only": "False"}
            elif cookie.name == "hidden":
                cookie._rest = {"http_only": "True"}
            elif cookie.name == "standard":
                cookie._rest = {"HttpOnly": None}
            elif cookie.name == "expired":
                cookie.expires = 1
        self.assertEqual(document_cookies(cookies.jar, "https://www.google.com/search"), {"visible": "fixture"})

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
        self.assertEqual(requests[1][1]["headers"], {"Referer": "https://www.google.com/", "Sec-Fetch-Site": "same-origin"})

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
    def test_promises_finish_before_timers_and_navigation_abandons_them(self):
        from travel_agent.google_javascript import evaluate_challenge
        state = evaluate_challenge(b'''<script>
            setTimeout(()=>{document.cookie='SG_SS=wrong';navigator.sendBeacon('/gen_204?cad=sg_trbl')},0);
            Promise.resolve().then(()=>Promise.resolve()).then(()=>{
                document.cookie='SG_SS=right';location.replace('/search?q=test');
            });</script>''', "https://www.google.com/search?q=test")
        self.assertEqual(state["cookies"]["SG_SS"], "right")
        self.assertEqual(state["diagnostics"]["timers_executed"], 0)
        self.assertEqual(state["diagnostics"]["beacon_codes"], [])

    def test_identity_initial_cookies_relative_clock_and_delayed_timer(self):
        from travel_agent.google_javascript import evaluate_challenge
        from travel_agent.google_identity import USER_AGENT, PLATFORM, HTTP_HEADERS
        state = evaluate_challenge(b'''<script>
            document.cookie='ua='+encodeURIComponent(navigator.userAgent);
            document.cookie='platform='+navigator.platform;
            document.cookie='clock='+(performance.now()<1000);
            if(!document.cookie.includes('visible=fixture'))throw Error('cookie missing');
            var cancelled=setTimeout(()=>{throw Error('cancelled')},0);clearTimeout(cancelled);
            setTimeout(()=>{document.cookie='SG_SS=ok';location.replace('/search?q=test')},10);
            setTimeout(()=>navigator.sendBeacon('/gen_204?cad=sg_trbl'),2000);
            </script>''', "https://www.google.com/search?q=test", initial_cookies={"visible": "fixture"})
        self.assertEqual(unquote(state["cookies"]["ua"]), HTTP_HEADERS["User-Agent"])
        self.assertEqual(unquote(state["cookies"]["ua"]), USER_AGENT)
        self.assertEqual(state["cookies"]["platform"], PLATFORM)
        self.assertEqual(state["cookies"]["clock"], "true")
        self.assertEqual(state["cookies"]["SG_SS"], "ok")
        self.assertEqual(state["diagnostics"]["errors"], [])
        self.assertEqual(state["diagnostics"]["timers_executed"], 1)

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
