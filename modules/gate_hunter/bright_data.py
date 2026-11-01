"""
Bright Data SERP API Integration
"""
import json
import random
import threading
import requests
from urllib.parse import urlparse, quote_plus, parse_qs, unquote
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

from .config import load_config
from .signatures import COUNTRIES, EXCLUDED_DOMAINS

# محركات البحث المدعومة
SEARCH_ENGINES = {
    'google': {
        'name': 'Google', 'base': 'https://www.google.com/search',
        'q': 'q', 'page_param': 'start', 'per_page': 10, 'mode': 'offset',
    },
    'bing': {
        'name': 'Bing', 'base': 'https://www.bing.com/search',
        'q': 'q', 'page_param': 'first', 'per_page': 10, 'mode': 'offset', 'offset_base': 1,
    },
    'yahoo': {
        'name': 'Yahoo', 'base': 'https://search.yahoo.com/search',
        'q': 'p', 'page_param': 'b', 'per_page': 10, 'mode': 'offset', 'offset_base': 1,
    },
    'duckduckgo': {
        'name': 'DuckDuckGo', 'base': 'https://duckduckgo.com/html/',
        'q': 'q', 'page_param': 's', 'per_page': 10, 'mode': 'offset',
    },
    'yandex': {
        'name': 'Yandex', 'base': 'https://yandex.com/search/',
        'q': 'text', 'page_param': 'p', 'per_page': 10, 'mode': 'page',
    },
}

# ═══════════════════════════════════════════════════════════
#  BRIGHT DATA CREDENTIALS (HARDCODED)
# ═══════════════════════════════════════════════════════════
BD_CUSTOMER_ID = '18055bd6-c696-4180-ac2d-e4e3d249dd11'
BD_ZONE = 'serp_api'
BD_PASSWORD = 'bbpx79u9d8sj'
BD_ACCOUNT_ID = 'hl_d9e540dc'
BD_USERNAME = 'dadysofy1@gmail.com'

def _build_proxy(country):
    """بناء proxy لـ Bright Data"""
    # استخدام بيانات hardcoded مباشرة
    cid = BD_CUSTOMER_ID
    z = BD_ZONE
    pw = BD_PASSWORD

    cc = (country or 'us').lower()
    user = f'brd-customer-{cid}-zone-{z}-country-{cc}'
    url = f'http://{user}:{pw}@brd.superproxy.io:22567'
    return {'http': url, 'https': url}

def _domain_ok(url):
    """التحقق من أن النطاق ليس من النطاقات المستبعدة"""
    domain = urlparse(url).netloc.lower()
    if not domain or len(domain) < 4:
        return False
    return not any(s in domain for s in EXCLUDED_DOMAINS)

def _extract_urls_recursive(node, bag, depth=0):
    """استخراج عام للروابط من أي JSON structure"""
    if depth > 6:
        return
    if isinstance(node, dict):
        for key in ('link', 'url', 'href'):
            v = node.get(key)
            if isinstance(v, str) and v.startswith('http'):
                bag.append(v)
        for v in node.values():
            _extract_urls_recursive(v, bag, depth + 1)
    elif isinstance(node, list):
        for item in node:
            _extract_urls_recursive(item, bag, depth + 1)

def _extract_from_json(data, max_urls):
    """يستخرج الروابط من JSON Bright Data SERP API"""
    seen, results = set(), []

    def _add(u):
        if not u or not _domain_ok(u):
            return
        d = urlparse(u).netloc.lower()
        if d not in seen:
            seen.add(d)
            results.append(u)

    for key in ('organic', 'results', 'organic_results', 'items'):
        for item in data.get(key, []) if isinstance(data, dict) else []:
            if len(results) >= max_urls:
                return results[:max_urls]
            if isinstance(item, dict):
                _add(item.get('link') or item.get('url'))

    if results:
        return results[:max_urls]

    raw = []
    _extract_urls_recursive(data, raw)
    for u in raw:
        if len(results) >= max_urls:
            break
        _add(u)
    return results[:max_urls]

def _extract_from_html_fallback(html, max_urls):
    """خطة بديلة فقط لو JSON فشل"""
    soup = BeautifulSoup(html, 'html.parser')
    seen, results = set(), []

    def _add(u):
        u = u.split('&sa=')[0].strip()
        if not _domain_ok(u):
            return
        d = urlparse(u).netloc.lower()
        if d not in seen:
            seen.add(d)
            results.append(u)

    for a in soup.find_all('a', href=True):
        if len(results) >= max_urls:
            break
        href = a['href']
        if href.startswith('/url?q='):
            raw = parse_qs(urlparse(href).query).get('q', [None])[0]
            if raw:
                _add(unquote(raw))
        elif href.startswith('http'):
            _add(href)

    return results

def _build_engine_url(engine_key, query, page):
    """بناء URL للبحث في محرك"""
    e = SEARCH_ENGINES[engine_key]
    if e['mode'] == 'offset':
        offset = page * e['per_page'] + e.get('offset_base', 0)
        pval = offset
    else:
        pval = page
    return f"{e['base']}?{e['q']}={quote_plus(query)}&{e['page_param']}={pval}&brd_json=1"

def _fetch_serp_page(engine_key, query, country, page):
    """يجلب صفحة نتائج واحدة من محرك ودولة محددين"""
    proxies = _build_proxy(country)
    if not proxies:
        return []

    headers = {
        'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                       'AppleWebKit/537.36 (KHTML, like Gecko) '
                       'Chrome/124.0.0.0 Safari/537.36'),
        'Accept-Language': 'en-US,en;q=0.9',
    }

    url = _build_engine_url(engine_key, query, page)

    try:
        r = requests.get(url, headers=headers, proxies=proxies,
                         verify=False, timeout=25)
        if r.status_code != 200:
            return []

        try:
            data = r.json()
            urls = _extract_from_json(data, 50)
            if urls:
                return urls
        except (ValueError, json.JSONDecodeError):
            pass

        url_html = url.replace('&brd_json=1', '')
        r2 = requests.get(url_html, headers=headers, proxies=proxies,
                          verify=False, timeout=25)
        return _extract_from_html_fallback(r2.text, 50)

    except Exception:
        return []

def search_dork(query, target_count, progress_cb=None, max_multiplier=5):
    """
    بحث شامل عبر Bright Data SERP API

    Args:
        query: كلمة البحث أو Dork
        target_count: العدد المطلوب من النتائج
        progress_cb: callback function(current, attempts, max)
        max_multiplier: مضاعف سقف المحاولات

    Returns:
        (urls, reached_target, attempts_used)
    """
    # Bright Data credentials hardcoded - جاهزة للاستخدام مباشرة
    engines = list(SEARCH_ENGINES.keys())
    countries = list(COUNTRIES.keys())
    seen_domains = set()
    results = []
    lock = threading.Lock()
    attempts = [0]
    max_requests = max(20, int(target_count * max_multiplier))

    def worker(engine_key, country, page):
        urls = _fetch_serp_page(engine_key, query, country, page)
        added = 0
        with lock:
            for u in urls:
                if len(results) >= target_count:
                    break
                d = urlparse(u).netloc.lower()
                if d and d not in seen_domains:
                    seen_domains.add(d)
                    results.append(u)
                    added += 1
        return added

    page = 0
    with ThreadPoolExecutor(max_workers=10) as ex:
        while len(results) < target_count and attempts[0] < max_requests:
            batch = []
            batch_size = min(10, max_requests - attempts[0])

            for _ in range(batch_size):
                engine_key = random.choice(engines)
                country = random.choice(countries)
                batch.append(ex.submit(worker, engine_key, country, page))
                attempts[0] += 1

            for f in as_completed(batch):
                try:
                    f.result()
                except Exception:
                    pass

            if progress_cb:
                progress_cb(len(results), attempts[0], max_requests)

            if len(results) >= target_count:
                break

            page += 1

    reached = len(results) >= target_count
    return results[:target_count], reached, attempts[0]
