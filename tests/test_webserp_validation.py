"""Prevent HTTP/CLI completion from masquerading as usable search results."""

import unittest

from scripts.validate_webserp import classify_result


class ValidationTests(unittest.TestCase):
    def classify(self, signals=None, results=None, errors=None):
        return classify_result({"results": results or [], "unresponsive_engines": errors or []},
                               [{"http_status": 200, "signals": signals or {}}])

    def test_http_200_without_results_is_not_success_or_proven_empty(self):
        self.assertEqual(self.classify(), "empty_unclassified")

    def test_js_and_captcha_responses_are_not_empty_searches(self):
        for signal in ("enable_js", "captcha", "consent", "unusual_traffic"):
            with self.subTest(signal=signal):
                self.assertEqual(self.classify({signal: True}), "access_interstitial")

    def test_async_protocol_payload_without_results_is_not_empty_search(self):
        self.assertEqual(self.classify({"async_framed": True}), "unparsed_async_response")

    def test_only_explicit_empty_evidence_means_no_results(self):
        self.assertEqual(self.classify({"explicit_no_results": True}), "explicit_no_results")

    def test_hits_need_review_and_noscript_link_alone_does_not_override_them(self):
        self.assertEqual(self.classify({"enable_js": True}, results=[{"url": "https://example.invalid"}]),
                         "results_returned_requires_review")

    def test_provider_error_is_not_hidden_by_partial_results(self):
        self.assertEqual(self.classify(results=[{}], errors=[["google", "network error"]]), "provider_error")


if __name__ == "__main__":
    unittest.main()
