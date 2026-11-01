"""
Bright Data SERP API Integration
"""
import json
import random
import threading
import logging
import requests
from urllib.parse import urlparse, quote_plus, parse_qs, unquote
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

from .config import load_config
from .signatures import COUNTRIES, EXCLUDED_DOMAINS

logger = logging.getLogger(__name__)

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
        logger.warning(f"[BrightData] No proxy for country {country}")
        return []

    headers = {
        'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                       'AppleWebKit/537.36 (KHTML, like Gecko) '
                       'Chrome/124.0.0.0 Safari/537.36'),
        'Accept-Language': 'en-US,en;q=0.9',
    }

    url = _build_engine_url(engine_key, query, page)
    logger.info(f"[BrightData] Requesting URL: {url[:100]}...")
    logger.info(f"[BrightData] Using proxy: {proxies['http'][:80]}...")

    try:
        logger.info(f"[BrightData] Sending request to {engine_key}...")
        r = requests.get(url, headers=headers, proxies=proxies,
                         verify=False, timeout=15)
        logger.info(f"[BrightData] Response received: HTTP {r.status_code}, length={len(r.text)}")

        if r.status_code != 200:
            logger.warning(f"[BrightData] HTTP {r.status_code} for {engine_key}/{country}")
            logger.debug(f"[BrightData] Response body: {r.text[:500]}")
            return []

        # محاولة parse JSON أولاً
        try:
            data = r.json()
            logger.info(f"[BrightData] JSON parsed successfully, keys: {list(data.keys())[:5]}")
            urls = _extract_from_json(data, 50)
            if urls:
                logger.info(f"[BrightData] ✓ Found {len(urls)} URLs from {engine_key}/{country}")
                return urls
            else:
                logger.warning(f"[BrightData] JSON parsed but no URLs found")
        except (ValueError, json.JSONDecodeError) as e:
            logger.warning(f"[BrightData] JSON parse failed: {e}, trying HTML fallback")

        # خطة بديلة: HTML
        url_html = url.replace('&brd_json=1', '')
        logger.info(f"[BrightData] Trying HTML fallback: {url_html[:100]}...")
        r2 = requests.get(url_html, headers=headers, proxies=proxies,
                          verify=False, timeout=15)
        logger.info(f"[BrightData] HTML response: HTTP {r2.status_code}, length={len(r2.text)}")

        if r2.status_code != 200:
            logger.warning(f"[BrightData] HTML fallback also failed: HTTP {r2.status_code}")
            return []

        urls = _extract_from_html_fallback(r2.text, 50)
        logger.info(f"[BrightData] HTML fallback found {len(urls)} URLs from {engine_key}/{country}")
        return urls

    except requests.exceptions.Timeout:
        logger.error(f"[BrightData] ⏱️ TIMEOUT for {engine_key}/{country} after 15s")
        return []
    except requests.exceptions.ConnectionError as e:
        logger.error(f"[BrightData] 🔌 CONNECTION ERROR for {engine_key}/{country}: {str(e)[:200]}")
        return []
    except Exception as e:
        logger.error(f"[BrightData] ❌ UNEXPECTED ERROR for {engine_key}/{country}: {type(e).__name__}: {e}", exc_info=True)
        return []

def search_dork(query, target_count, progress_cb=None, max_multiplier=5, overall_timeout=180):
    """
    بحث شامل عبر Bright Data SERP API

    Args:
        query: كلمة البحث أو Dork
        target_count: العدد المطلوب من النتائج
        progress_cb: callback function(current, attempts, max)
        max_multiplier: مضاعف سقف المحاولات
        overall_timeout: سقف الوقت للبحث الكامل (ثواني)

    Returns:
        (urls, reached_target, attempts_used)
    """
    import time
    start_time = time.time()

    logger.info(f"[BrightData] ═══════════════════════════════════")
    logger.info(f"[BrightData] Starting search: query='{query}', target={target_count}")
    logger.info(f"[BrightData] Credentials: Customer ID={BD_CUSTOMER_ID[:8]}..., Zone={BD_ZONE}")
    logger.info(f"[BrightData] Overall timeout: {overall_timeout}s")

    engines = list(SEARCH_ENGINES.keys())
    countries = list(COUNTRIES.keys())
    seen_domains = set()
    results = []
    lock = threading.Lock()
    attempts = [0]
    max_requests = max(20, int(target_count * max_multiplier))

    logger.info(f"[BrightData] Max attempts: {max_requests}, Engines: {engines}")
    logger.info(f"[BrightData] Countries: {countries[:5]}... ({len(countries)} total)")

    def worker(engine_key, country, page):
        logger.info(f"[BrightData] → Worker started: {engine_key}/{country}/page{page}")
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
        logger.info(f"[BrightData] ← Worker finished: {engine_key}/{country}, added {added} URLs")
        return added

    page = 0
    with ThreadPoolExecutor(max_workers=10) as ex:
        while len(results) < target_count and attempts[0] < max_requests:
            # فحص الوقت الكلي
            elapsed = time.time() - start_time
            if elapsed > overall_timeout:
                logger.warning(f"[BrightData] ⏰ Overall timeout reached ({overall_timeout}s), stopping search")
                break

            batch = []
            batch_size = min(10, max_requests - attempts[0])

            logger.info(f"[BrightData] ━━━ Batch {page+1} ━━━")
            logger.info(f"[BrightData] Progress: {len(results)}/{target_count} results, {attempts[0]}/{max_requests} attempts")
            logger.info(f"[BrightData] Time elapsed: {elapsed:.1f}s / {overall_timeout}s")
            logger.info(f"[BrightData] Submitting {batch_size} parallel requests...")

            for i in range(batch_size):
                engine_key = random.choice(engines)
                country = random.choice(countries)
                logger.debug(f"[BrightData] Task {i+1}/{batch_size}: {engine_key}/{country}")
                batch.append(ex.submit(worker, engine_key, country, page))
                attempts[0] += 1

            logger.info(f"[BrightData] Waiting for {len(batch)} futures to complete...")
            completed_count = 0
            for f in as_completed(batch):
                try:
                    result = f.result(timeout=30)  # 30s timeout per future
                    completed_count += 1
                except Exception as e:
                    logger.error(f"[BrightData] Future failed: {type(e).__name__}: {e}")

            logger.info(f"[BrightData] Batch {page+1} complete: {completed_count}/{len(batch)} succeeded")

            if progress_cb:
                try:
                    progress_cb(len(results), attempts[0], max_requests)
                except Exception as e:
                    logger.error(f"[BrightData] Progress callback failed: {e}")

            if len(results) >= target_count:
                logger.info(f"[BrightData] ✓ Target reached: {len(results)} >= {target_count}")
                break

            page += 1
            logger.info(f"[BrightData] Moving to page {page+1}, results so far: {len(results)}")

    reached = len(results) >= target_count
    total_time = time.time() - start_time
    logger.info(f"[BrightData] ═══════════════════════════════════")
    logger.info(f"[BrightData] Search complete: {len(results)} results, {attempts[0]} attempts")
    logger.info(f"[BrightData] Target reached: {reached} ({len(results)}/{target_count})")
    logger.info(f"[BrightData] Unique domains found: {len(seen_domains)}")
    logger.info(f"[BrightData] Total time: {total_time:.1f}s")
    logger.info(f"[BrightData] ═══════════════════════════════════")

    return results[:target_count], reached, attempts[0]
