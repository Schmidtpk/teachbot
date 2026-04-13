"""
IID-TEST-SMOKE
Deployment health check for the live teachbot app on Railway.

HTTP check (default): GET the live URL, assert HTTP 2xx.
Playwright chat simulation (--full): send a real message and assert a response arrives.

Playwright is an optional dependency — only required for --full.
Install it with:
    pip install playwright
    playwright install chromium

CLI:
    python tests/smoke.py                     # HTTP ping only
    python tests/smoke.py --full              # HTTP + Playwright chat simulation
    python tests/smoke.py --url <custom-url>  # override target URL
"""

import argparse
import sys
import urllib.error
import urllib.request

LIVE_URL = "https://teachbot-production-2e85.up.railway.app"
HTTP_TIMEOUT = 15           # seconds
PLAYWRIGHT_TIMEOUT = 30_000  # milliseconds (Playwright uses ms)
TEST_QUESTION = "What is this course about? One sentence please."


def check_http(url: str) -> bool:
    """GET the URL and return True if the server responds with HTTP 2xx."""
    try:
        req = urllib.request.Request(
            url,
            method="GET",
            headers={"User-Agent": "teachbot-smoke-test/1.0"},
        )
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            print(f"[smoke] HTTP GET {url} → {resp.status}")
            return 200 <= resp.status < 300
    except urllib.error.HTTPError as e:
        print(f"[smoke] HTTP error: {e.code} {e.reason}")
        return False
    except urllib.error.URLError as e:
        print(f"[smoke] Connection failed: {e.reason}")
        return False
    except Exception as e:  # noqa: BLE001
        print(f"[smoke] Unexpected error: {e}")
        return False


def check_playwright(url: str) -> bool:
    """
    Full end-to-end chat simulation using a headless browser (Playwright).
    Navigates to the app, sends a test question, waits for a response.
    Returns True if a non-empty response arrives without error indicators.
    """
    try:
        from playwright.sync_api import TimeoutError as PWTimeout  # noqa: PLC0415
        from playwright.sync_api import sync_playwright  # noqa: PLC0415
    except ImportError:
        print(
            "[smoke] Playwright not installed.\n"
            "  Install with: pip install playwright && playwright install chromium"
        )
        return False

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            print(f"[smoke] Navigating to {url} ...")
            page.goto(url, timeout=PLAYWRIGHT_TIMEOUT, wait_until="networkidle")

            # Chainlit 2.x uses a textarea for the chat input
            input_selector = "textarea"
            print("[smoke] Waiting for chat input ...")
            page.wait_for_selector(input_selector, timeout=PLAYWRIGHT_TIMEOUT)

            print(f"[smoke] Sending: {TEST_QUESTION!r}")
            page.fill(input_selector, TEST_QUESTION)
            page.keyboard.press("Enter")

            # Wait for Chainlit to render a response step
            # Chainlit wraps messages in elements with class "step" or similar
            print("[smoke] Waiting for response ...")
            page.wait_for_function(
                # True once the page has more text than just the question
                f"() => document.body.innerText.length > {len(TEST_QUESTION) + 50}",
                timeout=PLAYWRIGHT_TIMEOUT,
            )
            # Give streaming a moment to finish
            page.wait_for_timeout(3_000)

            page_text = page.inner_text("body").lower()
            error_indicators = ["traceback", "500 internal server error", "unhandled exception"]
            for indicator in error_indicators:
                if indicator in page_text:
                    print(f"[smoke] Error indicator found in page: {indicator!r}")
                    browser.close()
                    return False

            print("[smoke] Response received — chat pipeline is working.")
            browser.close()
            return True

        except PWTimeout:
            print(
                f"[smoke] Timeout: no response within {PLAYWRIGHT_TIMEOUT / 1000:.0f}s."
            )
            browser.close()
            return False
        except Exception as e:  # noqa: BLE001
            print(f"[smoke] Playwright error: {e}")
            browser.close()
            return False


def main() -> None:
    parser = argparse.ArgumentParser(description="teachbot deployment smoke test")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Also run Playwright chat simulation (requires playwright install)",
    )
    parser.add_argument(
        "--url",
        default=LIVE_URL,
        help=f"Target URL (default: {LIVE_URL})",
    )
    args = parser.parse_args()

    # --- HTTP check (always) ---
    if not check_http(args.url):
        print("[smoke] FAIL: HTTP check failed.")
        sys.exit(1)
    print("[smoke] PASS: HTTP check OK.")

    # --- Playwright chat simulation (--full only) ---
    if args.full:
        if not check_playwright(args.url):
            print("[smoke] FAIL: Playwright chat simulation failed.")
            sys.exit(1)
        print("[smoke] PASS: Playwright chat simulation OK.")


if __name__ == "__main__":
    main()
