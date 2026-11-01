"""
Gate Hunter Telegram Handlers
"""
import time
import threading
import logging
from telebot import types

from .scanner import deep_scan_url
from .bright_data import search_dork
from .config import load_config, save_config, update_config
from .database import init_db, db_save_search, db_save_scan, db_stats
from .signatures import DORK_PRESETS, COUNTRIES, SEARCH_ENGINES

logger = logging.getLogger(__name__)

# State management
gatehunter_user_state = {}  # uid → state str
gatehunter_user_data = {}   # uid → temp dict

def _esc(text):
    """Escape Markdown special characters"""
    for c in r'\_*[]()~`>#+-=|{}.!':
        text = text.replace(c, '\\' + c)
    return text

def _progress_bar(done, total, width=14):
    """Generate progress bar"""
    pct = done / total if total else 0
    filled = int(width * pct)
    return f"{'█' * filled}{'░' * (width - filled)}  {int(pct * 100)}%"

def btn(text, data=None, url=None):
    """Create inline button"""
    if url:
        return types.InlineKeyboardButton(text, url=url)
    return types.InlineKeyboardButton(text, callback_data=data or text)

# ═══════════════════════════════════════════════════════════
#  KEYBOARDS
# ═══════════════════════════════════════════════════════════

MAIN_TEXT = (
    "🎯 *Gate Hunter - صائد البوابات*\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n"
    "🌍 بحث متقدم عبر *Bright Data SERP*\n"
    "🔍 يبحث من دول مختلفة بدوركات Google\n"
    "💳 كشف بوابات الدفع بدقة عالية\n"
    "🛡️ تحليل شامل لأنظمة الحماية\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n"
    "اختر من القائمة 👇"
)

def main_kb():
    """القائمة الرئيسية للبوابة"""
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        btn('🔍 بحث جديد',         'gatehunter_search'),
        btn('📋 دوركات جاهزة',     'gatehunter_dorks'),
    )
    kb.add(
        btn('📊 الإحصائيات',        'gatehunter_stats'),
        btn('⚙️ الإعدادات',         'gatehunter_settings'),
    )
    kb.add(btn('⬅️ القائمة الرئيسية', 'main_menu'))
    return kb

def search_kb():
    """قائمة البحث"""
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        btn('🔢 عدد النتائج',  'gatehunter_change_num'),
        btn('⬅️ رجوع',         'gatehunter_main'),
    )
    return kb

def num_kb(prefix='gatehunter_num_'):
    """قائمة اختيار العدد"""
    kb = types.InlineKeyboardMarkup(row_width=3)
    kb.add(
        btn('10', f'{prefix}10'),  btn('25', f'{prefix}25'),  btn('50', f'{prefix}50'),
        btn('100', f'{prefix}100'), btn('250', f'{prefix}250'), btn('500', f'{prefix}500'),
        btn('1000', f'{prefix}1000'),
    )
    kb.add(btn('✏️ رقم مخصص', f'{prefix}custom'))
    kb.add(btn('⬅️ رجوع', 'gatehunter_main'))
    return kb

def confirm_scan_kb(count):
    """قائمة تأكيد الفحص"""
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        btn(f'✅ فحص الـ {count} موقع', 'gatehunter_scan_yes'),
        btn('❌ إلغاء',                  'gatehunter_scan_no'),
    )
    return kb

def dorks_kb():
    """قائمة الدوركات الجاهزة"""
    kb = types.InlineKeyboardMarkup(row_width=1)
    for i, (label, _) in enumerate(DORK_PRESETS):
        kb.add(btn(label, f'gatehunter_dork_{i}'))
    kb.add(btn('⬅️ رجوع', 'gatehunter_main'))
    return kb

def settings_kb():
    """قائمة الإعدادات"""
    cfg = load_config()
    deep_label = '✅ مفعل' if cfg.get('deep_scan', True) else '❌ معطل'
    prot_label = '✅ مفعل' if cfg.get('send_protected', True) else '❌ معطل'

    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        btn('🔑 Bright Data Credentials',          'gatehunter_set_bd_creds'),
        btn('📝 اسم الـ Zone',                      'gatehunter_set_bd_zone'),
        btn('🔢 عدد النتائج الافتراضي',              'gatehunter_set_def_num'),
        btn('🔁 سقف محاولات البحث',                 'gatehunter_set_multiplier'),
        btn(f'🔬 الفحص العميق: {deep_label}',        'gatehunter_toggle_deep'),
        btn(f'🛡️ إظهار المحميات: {prot_label}',      'gatehunter_toggle_protected'),
    )
    kb.add(btn('⬅️ القائمة الرئيسية', 'gatehunter_main'))
    return kb

# ═══════════════════════════════════════════════════════════
#  HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════

def format_scan_result(result):
    """تنسيق نتيجة الفحص"""
    if not result:
        return "❌ لا توجد نتائج"

    url = result['url']
    gateways = result['gateways']
    gateway_conf = result['gateway_conf']
    security = result['security']
    score = result['score']
    has_form = result['has_form']

    # أيقونات الثقة
    conf_icons = {
        'confirmed': '✅',
        'strong': '🟢',
        'weak': '🟡'
    }

    # تنسيق البوابات
    gates_str = ', '.join([
        f"{conf_icons.get(gateway_conf.get(g, 'weak'), '🟡')}{g}"
        for g in gateways
    ])

    # تنسيق الحماية
    if security:
        sec_str = ' + '.join(security)
        protection = f"🔒 {sec_str}"
    else:
        protection = "🟢 *لا يوجد*"

    # الحماية
    if score == 0:
        header = "✅ *موقع مكشوف!*\n"
    else:
        dots = '🔴' * min(5, score // 20)
        header = f"🛡️ *محمي* {dots} `{score}%`\n"

    # فورم الكارت
    form_str = "✅ نعم" if has_form else "❌ لا"

    # الموثوقية
    reliability = result.get('reliability', 'low')
    if reliability == 'high':
        rel_str = "🟢 دليل تقني مباشر (script/form/iframe)"
    else:
        rel_str = "🟡 ذكر نصي فقط"

    caption = (
        f"{header}"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🌐 `{url}`\n"
        f"💳 البوابات: {gates_str}\n"
        f"📝 فورم كارت: {form_str}\n"
        f"🔬 الموثوقية: {rel_str}\n"
        f"🛡️ الحماية: {protection}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )

    return caption

def run_scan_for_user(bot, uid, chat_id, urls, msg_id=None):
    """تشغيل الفحص في thread منفصل"""
    init_db()

    cfg = load_config()
    send_protected = cfg.get('send_protected', True)

    # حفظ البحث
    sid = db_save_search('bulk_scan', 'multi', len(urls))

    total = len(urls)
    done = [0]
    exposed = [0]
    protected = [0]
    no_gate = [0]
    failed = [0]

    lock = threading.Lock()
    start_time = time.time()

    def update_progress():
        """تحديث رسالة التقدم"""
        with lock:
            pct = _progress_bar(done[0], total)
            elapsed = time.time() - start_time

            caption = (
                f"🔍 *جاري الفحص...*\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📊 التقدم: {pct}\n"
                f"✅ مكشوف: *{exposed[0]}*\n"
                f"🛡️ محمي: *{protected[0]}*\n"
                f"❌ لا بوابة: *{no_gate[0]}*\n"
                f"⚠️ فشل: *{failed[0]}*\n"
                f"⏱️ الوقت: {int(elapsed)}s\n"
                f"━━━━━━━━━━━━━━━━━━━━━━"
            )

            try:
                bot.edit_message_text(
                    caption,
                    chat_id=chat_id,
                    message_id=msg_id,
                    parse_mode='Markdown'
                )
            except Exception:
                pass

    def process_url(url):
        """فحص URL واحد"""
        result, status = deep_scan_url(url)

        with lock:
            done[0] += 1

        if status == 'FETCH_FAILED':
            with lock:
                failed[0] += 1
            return

        if status == 'NO_GATE':
            with lock:
                no_gate[0] += 1
            return

        # حفظ النتيجة
        gateways = result['gateways']
        security = result['security']
        score = result['score']
        has_form = result['has_form']

        db_save_scan(sid, url, gateways, security, score, has_form)

        if score == 0:
            with lock:
                exposed[0] += 1
        else:
            with lock:
                protected[0] += 1

        # إرسال النتيجة
        if score == 0 or send_protected:
            caption = format_scan_result(result)
            try:
                bot.send_message(chat_id, caption, parse_mode='Markdown')
            except Exception as e:
                logger.error(f"Error sending result: {e}")

        # تحديث التقدم كل 5 نتائج
        if done[0] % 5 == 0:
            update_progress()

    # تشغيل الفحص بشكل متوازي
    from concurrent.futures import ThreadPoolExecutor, as_completed

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(process_url, url): url for url in urls}

        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                logger.error(f"Error in scan: {e}")

    # ملخص نهائي
    elapsed = time.time() - start_time
    summary = (
        f"🏁 *انتهى الفحص!*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 الإجمالي:             *{total}*\n"
        f"✅ مكشوف (بلا حماية): *{exposed[0]}*\n"
        f"🛡️ محمي:                *{protected[0]}*\n"
        f"❌ لا بوابة دفع:         *{no_gate[0]}*\n"
        f"⚠️ فشل الاتصال:         *{failed[0]}*\n"
        f"⏱️ الوقت الإجمالي:       {int(elapsed)}s\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔥 *Gate Hunter*"
    )

    try:
        bot.send_message(chat_id, summary, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error sending summary: {e}")
