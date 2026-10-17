"""One explicit identity for HTTP headers and the bounded JavaScript experiment."""

PROFILE = "chrome133a"
USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36")
PLATFORM = "MacIntel"
HTTP_HEADERS = {"User-Agent": USER_AGENT, "sec-ch-ua-platform": '"macOS"',
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9"}
