"""
Gate Hunter Deep Scanner - Payment Gateway & Security Detection
"""
import re
import requests
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup

from .config import load_config
from .signatures import PAYMENT_GATEWAYS, SECURITY_SIGNATURES, CHECKOUT_PATHS

# أوزان أنظمة الحماية (للحساب score)
SECURITY_WEIGHTS = {
    'Cloudflare': 35,
    'Akamai': 35,
    'Imperva': 35,
    'Sucuri': 30,
    'reCAPTCHA': 25,
    'hCaptcha': 25,
    'Turnstile': 20,
    '3D Secure': 15,
    'Kount': 10,
    'Signifyd': 10,
}

# Headers للفحص
_SCAN_HEADERS = {
    'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                   'AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36'),
    'Accept': 'text/html,application/xhtml+xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}

def _fetch(url, timeout=None):
    """يجلب صفحة → (html, resp_headers, status)"""
    cfg = load_config()
    t = timeout or cfg.get('scan_timeout', 12)
    try:
        r = requests.get(url, headers=_SCAN_HEADERS, timeout=t,
                         allow_redirects=True, verify=False)
        return r.text, dict(r.headers), r.status_code
    except Exception:
        return None, {}, 0

def _detect_security(html, resp_headers):
    """
    كشف الحماية من:
    1. HTTP Response Headers
    2. Server header
    3. محتوى الـ HTML
    → (list of names, score 0-100)
    """
    found = []
    h_lower = {k.lower(): v.lower() for k, v in resp_headers.items()}
    html_l = html.lower() if html else ''

    for name, sigs in SECURITY_SIGNATURES.items():
        detected = False

        # فحص Headers بالاسم
        if any(k in h_lower for k in sigs['headers_keys']):
            detected = True

        # فحص Server header
        if not detected and sigs.get('server_match'):
            if sigs['server_match'] in h_lower.get('server', ''):
                detected = True

        # فحص محتوى الـ HTML
        if not detected:
            for pat in sigs.get('html_patterns', []):
                if re.search(pat, html_l):
                    detected = True
                    break

        if detected:
            found.append(name)

    score = min(100, sum(SECURITY_WEIGHTS.get(s, 10) for s in found))
    return found, score

def _detect_gateways(html, page_url=None):
    """
    كشف بوابات الدفع بمستويين من الثقة:
    - strong: script src / form action / iframe src → دليل تقني فعلي
    - weak:   ذكر الاسم في نص الصفحة فقط → ممكن يكون مجرد مقال/إعلان

    يرجع list من tuples: (اسم البوابة, 'strong' أو 'weak')
    """
    if not html:
        return []

    strong, weak = {}, {}
    soup = BeautifulSoup(html, 'html.parser')

    # --- src السكريبتات (دليل قوي) ---
    for script in soup.find_all('script', src=True):
        src = script.get('src', '')
        for name, pattern in PAYMENT_GATEWAYS:
            if name not in strong and re.search(pattern, src, re.I):
                strong[name] = True

    # --- action الفورمات (دليل قوي) ---
    for form in soup.find_all('form', action=True):
        action = form.get('action', '')
        for name, pattern in PAYMENT_GATEWAYS:
            if name not in strong and re.search(pattern, action, re.I):
                strong[name] = True

    # --- iframes (دليل قوي جداً) ---
    for iframe in soup.find_all('iframe', src=True):
        src = iframe.get('src', '')
        for name, pattern in PAYMENT_GATEWAYS:
            if name not in strong and re.search(pattern, src, re.I):
                strong[name] = True

    # --- نص الصفحة الكامل (دليل ضعيف فقط) ---
    for name, pattern in PAYMENT_GATEWAYS:
        if name not in strong and re.search(pattern, html, re.I):
            weak[name] = True

    result = [(n, 'strong') for n in strong] + [(n, 'weak') for n in weak if n not in strong]
    return result

def _detect_platform_fingerprint(root_url, timeout=6):
    """
    يستعلم endpoints رسمية لمنصات التجارة الإلكترونية —
    دليل قاطع 100% (مش heuristic) إن المنصة موجودة فعلياً
    """
    confirmed = []
    checks = [
        ('WooCommerce', '/wp-json/wc/store/v1/products?per_page=1'),
        ('Shopify',     '/products.json'),
        ('Magento',     '/rest/V1/store/storeConfigs'),
        ('PrestaShop',  '/api'),
        ('BigCommerce', '/api/storefront/carts'),
    ]

    for name, path in checks:
        try:
            r = requests.get(root_url + path, headers=_SCAN_HEADERS,
                             timeout=timeout, verify=False)
            if r.status_code in (200, 401, 403) and len(r.text) > 20:
                confirmed.append(name)
        except Exception:
            continue

    return confirmed

def _has_card_form(html):
    """يتحقق من وجود فورم إدخال بيانات كارت فعلي"""
    if not html:
        return False

    soup = BeautifulSoup(html, 'html.parser')

    # طريقة 1: حقول إدخال مرتبطة بالكارت
    card_inputs = soup.find_all('input', attrs={
        'name': re.compile(r'card.?number|cardnum|cc.?num|pan|credit.?card', re.I),
    }) + soup.find_all('input', attrs={
        'id': re.compile(r'card.?number|cardnum|cc.?num|pan', re.I),
    }) + soup.find_all('input', attrs={
        'placeholder': re.compile(r'card\s*number|1234|0000', re.I),
    })

    if card_inputs:
        return True

    # طريقة 2: iframes خاصة بالدفع
    for iframe in soup.find_all('iframe', src=True):
        src = iframe.get('src', '')
        if re.search(r'stripe|braintree|square|adyen|paypal|authorize|checkout', src, re.I):
            return True

    # طريقة 3: بحث في الـ HTML مباشرة
    patterns = [
        r'<input[^>]*(?:type=["\']?(?:tel|number|text)["\'][^>]*)>(?:.*?)?'
        r'(?:card.?number|cvv|expir)',
        r'data-[^=]*=["\'][^"\']*(?:card|payment|billing)',
        r'class=["\'][^"\']*(?:card-number|card-input|payment-field)',
    ]

    return any(re.search(p, html, re.I | re.S) for p in patterns)

def _find_checkout_links(html, base_url):
    """يبحث عن روابط الـ Checkout المضمنة في الصفحة"""
    if not html:
        return []

    soup = BeautifulSoup(html, 'html.parser')
    links = set()
    kws = ['checkout', 'cart', 'payment', 'pay-now', 'buy-now', 'order', 'purchase']
    root = f"{urlparse(base_url).scheme}://{urlparse(base_url).netloc}"

    for a in soup.find_all('a', href=True):
        href = a['href'].lower()
        if any(k in href for k in kws):
            full = urljoin(base_url, a['href'])
            if urlparse(full).netloc == urlparse(base_url).netloc:
                links.add(full)

    return list(links)[:5]

def deep_scan_url(url):
    """
    الفحص العميق الكامل متعدد المراحل:
    1. الصفحة الرئيسية (headers + html)
    2. روابط Checkout المكتشفة من الصفحة نفسها
    3. مسارات Checkout الشائعة كـ fallback
    4. فحص API endpoints رسمية للمنصة
    5. دمج النتائج بمستويات ثقة

    → (result dict, status_code)
    """
    cfg = load_config()
    timeout = cfg.get('scan_timeout', 12)
    parsed = urlparse(url)
    root = f"{parsed.scheme}://{parsed.netloc}"

    home_html, home_headers, home_status = _fetch(url, timeout)
    if home_html is None:
        return None, 'FETCH_FAILED'

    security, score = _detect_security(home_html, home_headers)
    gate_hits = dict(_detect_gateways(home_html, url))
    has_form = _has_card_form(home_html)

    if cfg.get('deep_scan', True):
        checkout_urls = _find_checkout_links(home_html, url)
        for path in CHECKOUT_PATHS:
            co_url = root + path
            if co_url not in checkout_urls:
                checkout_urls.append(co_url)

        for co_url in checkout_urls[:8]:
            if co_url == url:
                continue

            co_html, co_headers, co_status = _fetch(co_url, max(6, timeout // 2))
            if not co_html or co_status not in (200, 301, 302):
                continue

            for name, confidence in _detect_gateways(co_html, co_url):
                if name not in gate_hits or (confidence == 'strong' and gate_hits[name] == 'weak'):
                    gate_hits[name] = confidence

            co_sec, co_score = _detect_security(co_html, co_headers)
            for s in co_sec:
                if s not in security:
                    security.append(s)
            score = max(score, co_score)

            if not has_form:
                has_form = _has_card_form(co_html)

            # دليل قوي + فورم فعلي = كفاية
            if any(c == 'strong' for c in gate_hits.values()) and has_form:
                break

        # فحص Fingerprints رسمية
        platform_hits = _detect_platform_fingerprint(root)
        for name in platform_hits:
            gate_hits[name] = 'confirmed'

    if not gate_hits:
        return None, 'NO_GATE'

    # ترتيب: confirmed أولاً، بعدين strong، بعدين weak
    order = {'confirmed': 0, 'strong': 1, 'weak': 2}
    sorted_gates = sorted(gate_hits.items(), key=lambda x: order.get(x[1], 3))

    strong_count = sum(1 for _, c in sorted_gates if c in ('confirmed', 'strong'))
    reliability = 'high' if strong_count > 0 else 'low'

    return {
        'url': url,
        'gateways': [n for n, c in sorted_gates],
        'gateway_conf': {n: c for n, c in sorted_gates},
        'reliability': reliability,
        'security': security,
        'score': score,
        'has_form': has_form,
        'status': home_status,
    }, 'OK'
