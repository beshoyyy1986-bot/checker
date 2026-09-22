"""
AFUONA CHECKER BOT 
Developer: 𓆩𝗔𓆪𝗙𝗨𝗢𝗡𝗔
Telegram: https://t.me/afuonax
"""

from telethon import TelegramClient, events, Button
import requests
import random
import datetime
import json
import os
import re
import asyncio
import aiohttp
import aiofiles

# ==================== CONFIG ====================
API_ID = id
API_HASH = "hash"
BOT_TOKEN = "token"
API_BASE_URL = "https://xafuona.3utilities.com"
API_KEY = "afuona_2026"
SECOND_CHANNEL_LINK = "https://t.me/+kxhCcDXQgzQ5MjE0"

# Files
USER_SITES_FILE = "user_sites.json"
USER_PROXIES_FILE = "user_proxies.json"

# Limits
MAX_SITES = 10
MAX_PROXIES = 10

# File upload limits
MAX_SITES_FILE = 100
MAX_PROXIES_FILE = 100
MAX_CARDS_FILE = 1000

# Active processes
active_processes = {}

# ==================== CLIENT SETUP ====================
client = TelegramClient('afuona_bot', API_ID, API_HASH)

# ==================== HELPER FUNCTIONS ====================
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
        return {}

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
        type_match = re.match(r'^(socks5|socks4|https)://', proxy_str)
        if type_match:
            proxy_type = type_match.group(1)
            proxy_str = proxy_str.split('://', 1)[1]
    
    # user:pass@ip:port
    match = re.match(r'^([^:@]+):([^@]+)@([^:@]+):(\d+)$', proxy_str)
    if match:
        username, password, ip, port = match.groups()
        return f"{proxy_type}://{username}:{password}@{ip}:{port}"
    
    # ip:port:user:pass
    match = re.match(r'^([^:]+):(\d+):([^:]+):(.+)$', proxy_str)
    if match:
        ip, port, username, password = match.groups()
        return f"{proxy_type}://{username}:{password}@{ip}:{port}"
    
    # ip:port
    match = re.match(r'^([^:@]+):(\d+)$', proxy_str)
    if match:
        ip, port = match.groups()
        return f"{proxy_type}://{ip}:{port}"
    
    return None

async def test_proxy(proxy_url):
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get('http://api.ipify.org', proxy=proxy_url) as resp:
                if resp.status == 200:
                    ip = await resp.text()
                    return True, ip.strip()
                return False, f"HTTP {resp.status}"
    except Exception as e:
        return False, str(e)

async def get_bin_info(card_number):
    try:
        bin_num = card_number[:6]
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://lookup.binlist.net/{bin_num}", 
                                   headers={'Accept-Version': '3'}) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {
                        'brand': data.get('scheme', 'N/A'),
                        'type': data.get('type', 'N/A'),
                        'level': data.get('brand', 'N/A'),
                        'bank': data.get('bank', {}).get('name', 'N/A'),
                        'country': data.get('country', {}).get('name', 'N/A'),
                        'flag': data.get('country', {}).get('emoji', '🏳️')
                    }
    except:
        pass
    return {
        'brand': 'N/A',
        'type': 'N/A',
        'level': 'N/A',
        'bank': 'N/A',
        'country': 'N/A',
        'flag': '🏳️'
    }

def get_card_status(response_text, status_text):
    response_lower = response_text.lower()
    
    if "charged" in response_lower or "thank you" in response_lower or "order completed" in response_lower or "💎" in response_text:
        return "CHARGED 💎"
    
    if status_text == "Approved" or "insufficient" in response_lower:
        return "APPROVED ✅"
    
    if "3d" in response_lower or "secure" in response_lower:
        return "3D SECURE 🟡"
    
    return None

def format_bold(text):
    """Convert text to bold unicode characters"""
    bold_map = {
        'A': '𝗔', 'B': '𝗕', 'C': '𝗖', 'D': '𝗗', 'E': '𝗘', 'F': '𝗙', 'G': '𝗚', 'H': '𝗛', 'I': '𝗜',
        'J': '𝗝', 'K': '𝗞', 'L': '𝗟', 'M': '𝗠', 'N': '𝗡', 'O': '𝗢', 'P': '𝗣', 'Q': '𝗤', 'R': '𝗥',
        'S': '𝗦', 'T': '𝗧', 'U': '𝗨', 'V': '𝗩', 'W': '𝗪', 'X': '𝗫', 'Y': '𝗬', 'Z': '𝗭',
        'a': '𝗮', 'b': '𝗯', 'c': '𝗰', 'd': '𝗱', 'e': '𝗲', 'f': '𝗳', 'g': '𝗴', 'h': '𝗵', 'i': '𝗶',
        'j': '𝗷', 'k': '𝗸', 'l': '𝗹', 'm': '𝗺', 'n': '𝗻', 'o': '𝗼', 'p': '𝗽', 'q': '𝗾', 'r': '𝗿',
        's': '𝘀', 't': '𝘁', 'u': '𝘂', 'v': '𝘃', 'w': '𝘄', 'x': '𝘅', 'y': '𝘆', 'z': '𝘇',
        '0': '𝟬', '1': '𝟭', '2': '𝟮', '3': '𝟯', '4': '𝟰', '5': '𝟱', '6': '𝟲', '7': '𝟳', '8': '𝟴', '9': '𝟵'
    }
    
    result = ""
    for char in text:
        if char in bold_map:
            result += bold_map[char]
        else:
            result += char
    return result

# ==================== API FUNCTIONS ====================
async def check_card_via_api(card, site, proxy):
    try:
        site = site.replace('https://', '').replace('http://', '').split('/')[0]
        
        formatted_card = validate_card(card)
        if not formatted_card:
            return {"Response": "Invalid card format", "Status": "Error"}
        
        params = {
            'key': API_KEY,
            'site': site,
            'cc': formatted_card,
            'proxy': proxy
        }
        
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f"{API_BASE_URL}/process", params=params) as resp:
                if resp.status != 200:
                    return {"Response": f"HTTP {resp.status}", "Status": "Error"}
                
                return await resp.json()
    except Exception as e:
        return {"Response": str(e), "Status": "Error"}

async def test_site_via_api(site, proxy):
    try:
        site = site.replace('https://', '').replace('http://', '').split('/')[0]
        
        params = {
            'key': API_KEY,
            'site': site,
            'proxy': proxy
        }
        
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f"{API_BASE_URL}/test_site", params=params) as resp:
                if resp.status != 200:
                    return {"working": False, "response": f"HTTP {resp.status}"}
                
                return await resp.json()
    except Exception as e:
        return {"working": False, "response": str(e)}

# ==================== COMMAND HANDLERS ====================
@client.on(events.NewMessage(pattern='/start'))
async def start_command(event):
    await show_start_menu(event)

@client.on(events.NewMessage(pattern='/add'))
async def add_command(event):
    user_id = str(event.sender_id)
    
    text = event.raw_text[4:].strip()
    if not text:
        return await event.reply("❌ Usage: /add site1.com site2.com")
    
    sites_to_add = []
    for word in text.split():
        word = word.replace('https://', '').replace('http://', '').split('/')[0]
        if re.match(r'^[a-zA-Z0-9][a-zA-Z0-9\-]*\.[a-zA-Z]{2,}', word):
            sites_to_add.append(word)
    
    if not sites_to_add:
        return await event.reply("❌ No valid sites found!")
    
    proxies = await load_json(USER_PROXIES_FILE)
    user_proxies = proxies.get(user_id, [])
    
    if not user_proxies:
        return await event.reply("❌ You need at least one working proxy to test sites!")
    
    status_msg = await event.reply(f"🔄 Testing {len(sites_to_add)} sites...")
    
    proxy = random.choice(user_proxies)['url']
    working_sites = []
    
    for i, site in enumerate(sites_to_add, 1):
        await status_msg.edit(f"🔄 Testing [{i}/{len(sites_to_add)}]: {site}")
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
    
    await status_msg.edit(f"✅ Added {len(added)} working sites. Total: {len(current_sites)}/{MAX_SITES}")

@client.on(events.NewMessage(pattern='/rm'))
async def rm_command(event):
    user_id = str(event.sender_id)
    
    text = event.raw_text[3:].strip()
    if not text:
        return await event.reply("❌ Usage: /rm site.com or /rm all")
    
    sites_data = await load_json(USER_SITES_FILE)
    user_sites = sites_data.get(user_id, [])
    
    if not user_sites:
        return await event.reply("❌ You have no sites to remove!")
    
    if text.lower() == 'all':
        del sites_data[user_id]
        await save_json(USER_SITES_FILE, sites_data)
        return await event.reply(f"✅ Removed all {len(user_sites)} sites!")
    
    site_to_remove = text.replace('https://', '').replace('http://', '').split('/')[0]
    
    if site_to_remove in user_sites:
        user_sites.remove(site_to_remove)
        if user_sites:
            sites_data[user_id] = user_sites
        else:
            del sites_data[user_id]
        await save_json(USER_SITES_FILE, sites_data)
        await event.reply(f"✅ Removed: {site_to_remove}")
    else:
        await event.reply(f"❌ Site not found!")

@client.on(events.NewMessage(pattern='/mysites'))
async def mysites_command(event):
    user_id = str(event.sender_id)
    sites_data = await load_json(USER_SITES_FILE)
    user_sites = sites_data.get(user_id, [])
    
    if not user_sites:
        return await event.reply("❌ You have no saved sites!")
    
    text = f"📊 Your Sites ({len(user_sites)}/{MAX_SITES}):\n\n"
    for i, site in enumerate(user_sites, 1):
        text += f"{i}. {site}\n"
    
    await event.reply(text)

@client.on(events.NewMessage(pattern='/addproxy'))
async def addproxy_command(event):
    user_id = str(event.sender_id)
    
    if event.is_group:
        return await event.reply("🔒 This command only works in private chat!")
    
    text = event.raw_text[9:].strip()
    if not text:
        return await event.reply("❌ Usage: /addproxy ip:port or /addproxy ip:port:user:pass")
    
    proxies = await load_json(USER_PROXIES_FILE)
    user_proxies = proxies.get(user_id, [])
    
    proxy_url = parse_proxy(text)
    if not proxy_url:
        return await event.reply("❌ Invalid proxy format!")
    
    status_msg = await event.reply("🔄 Testing proxy...")
    is_working, ip = await test_proxy(proxy_url)
    
    if not is_working:
        return await status_msg.edit("❌ Proxy is not working!")
    
    exists = any(p['original'] == text for p in user_proxies)
    if exists:
        return await status_msg.edit("⚠️ Proxy already exists!")
    
    if len(user_proxies) >= MAX_PROXIES:
        return await status_msg.edit(f"❌ Max proxies limit ({MAX_PROXIES}) reached!")
    
    user_proxies.append({
        'original': text,
        'url': proxy_url,
        'ip': ip
    })
    
    proxies[user_id] = user_proxies
    await save_json(USER_PROXIES_FILE, proxies)
    
    await status_msg.edit(f"✅ Proxy added! (IP: {ip})")

@client.on(events.NewMessage(pattern='/rmproxy'))
async def rmproxy_command(event):
    user_id = str(event.sender_id)
    
    if event.is_group:
        return await event.reply("🔒 This command only works in private chat!")
    
    text = event.raw_text[8:].strip()
    
    proxies = await load_json(USER_PROXIES_FILE)
    user_proxies = proxies.get(user_id, [])
    
    if not user_proxies:
        return await event.reply("❌ You have no proxies to remove!")
    
    if not text:
        proxy_list = "Your proxies:\n\n"
        for i, p in enumerate(user_proxies, 1):
            proxy_list += f"{i}. {p['original']}\n"
        proxy_list += "\nUse /rmproxy [number] or /rmproxy all"
        return await event.reply(proxy_list)
    
    if text.lower() == 'all':
        del proxies[user_id]
        await save_json(USER_PROXIES_FILE, proxies)
        return await event.reply(f"✅ Removed all {len(user_proxies)} proxies!")
    
    try:
        index = int(text) - 1
        if 0 <= index < len(user_proxies):
            removed = user_proxies.pop(index)
            if user_proxies:
                proxies[user_id] = user_proxies
            else:
                del proxies[user_id]
            await save_json(USER_PROXIES_FILE, proxies)
            await event.reply(f"✅ Removed: {removed['original']}")
        else:
            await event.reply(f"❌ Invalid index! Choose 1-{len(user_proxies)}")
    except ValueError:
        await event.reply("❌ Please provide a valid number or 'all'")

@client.on(events.NewMessage(pattern='/myproxies'))
async def myproxies_command(event):
    user_id = str(event.sender_id)
    
    if event.is_group:
        return await event.reply("🔒 This command only works in private chat!")
    
    proxies = await load_json(USER_PROXIES_FILE)
    user_proxies = proxies.get(user_id, [])
    
    if not user_proxies:
        return await event.reply("❌ You have no saved proxies!")
    
    text = f"📊 Your Proxies ({len(user_proxies)}/{MAX_PROXIES}):\n\n"
    for i, p in enumerate(user_proxies, 1):
        text += f"{i}. {p['original']} (IP: {p['ip']})\n"
    
    await event.reply(text)

@client.on(events.NewMessage(pattern='/mtxt'))
async def mtxt_command(event):
    user_id = event.sender_id
    
    if user_id in active_processes:
        return await event.reply("```Lunch is on the way 🍑 wait until it cools down```")
    
    if not event.is_reply:
        return await event.reply("```Please reply to a .txt file with /mtxt```")
    
    replied = await event.get_reply_message()
    if not replied.document:
        return await event.reply("```That's not a file. Please reply to a .txt file.```")
    
    proxies = await load_json(USER_PROXIES_FILE)
    user_proxies = proxies.get(str(user_id), [])
    if not user_proxies:
        return await event.reply("❌ You need at least one working proxy!")
    
    sites = await load_json(USER_SITES_FILE)
    user_sites = sites.get(str(user_id), [])
    if not user_sites:
        return await event.reply("❌ You need at least one working site!")
    
    file_path = await replied.download_media()
    
    try:
        async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
            content = await f.read()
    except:
        async with aiofiles.open(file_path, 'r', encoding='latin-1') as f:
            content = await f.read()
    
    os.remove(file_path)
    
    cards = extract_cards(content)
    
    if not cards:
        return await event.reply("```❌ No valid cards found in file!```")
    
    lines = content.splitlines()
    if len(lines) > MAX_CARDS_FILE:
        return await event.reply(f"```❌ File too large! Max {MAX_CARDS_FILE} lines.```")
    
    if len(cards) > MAX_CARDS:
        cards = cards[:MAX_CARDS]
        await event.reply(f"```⚠️ Checking only first {MAX_CARDS} cards```")
    
    active_processes[user_id] = {'type': 'checking'}
    await event.reply(f"```🍑 Preparing to check {len(cards)} cards...```")
    
    await process_card_check(event, cards, user_sites, user_proxies)

@client.on(events.NewMessage(pattern='/ran'))
async def ran_command(event):
    user_id = event.sender_id
    
    if user_id in active_processes:
        return await event.reply("```Lunch is on the way 🍑 wait until it cools down```")
    
    if not event.is_reply:
        return await event.reply("```Please reply to a .txt file with /ran```")
    
    replied = await event.get_reply_message()
    if not replied.document:
        return await event.reply("```That's not a file. Please reply to a .txt file.```")
    
    proxies = await load_json(USER_PROXIES_FILE)
    user_proxies = proxies.get(str(user_id), [])
    if not user_proxies:
        return await event.reply("❌ You need at least one working proxy!")
    
    sites = await load_json(USER_SITES_FILE)
    user_sites = sites.get(str(user_id), [])
    if not user_sites:
        return await event.reply("❌ You need at least one working site!")
    
    file_path = await replied.download_media()
    
    try:
        async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
            content = await f.read()
    except:
        async with aiofiles.open(file_path, 'r', encoding='latin-1') as f:
            content = await f.read()
    
    os.remove(file_path)
    
    cards = extract_cards(content)
    
    if not cards:
        return await event.reply("```❌ No valid cards found in file!```")
    
    lines = content.splitlines()
    if len(lines) > MAX_CARDS_FILE:
        return await event.reply(f"```❌ File too large! Max {MAX_CARDS_FILE} lines.```")
    
    if len(cards) > MAX_CARDS:
        cards = cards[:MAX_CARDS]
        await event.reply(f"```⚠️ Checking only first {MAX_CARDS} cards```")
    
    active_processes[user_id] = {'type': 'checking'}
    await event.reply(f"```🍑 Preparing to check {len(cards)} cards with random sites...```")
    
    await process_card_check(event, cards, user_sites, user_proxies)

@client.on(events.NewMessage(pattern='/check'))
async def check_command(event):
    user_id = event.sender_id
    
    if user_id in active_processes:
        return await event.reply("```You already have an active process!```")
    
    proxies = await load_json(USER_PROXIES_FILE)
    user_proxies = proxies.get(str(user_id), [])
    if not user_proxies:
        return await event.reply("❌ You need at least one working proxy!")
    
    sites = await load_json(USER_SITES_FILE)
    user_sites = sites.get(str(user_id), [])
    if not user_sites:
        return await event.reply("❌ You have no sites to check!")
    
    active_processes[user_id] = {'type': 'testing_sites'}
    await event.reply(f"🔄 Testing {len(user_sites)} sites...")
    
    working = []
    dead = []
    proxy = random.choice(user_proxies)['url']
    
    for i, site in enumerate(user_sites, 1):
        try:
            await event.edit(f"🔄 Testing [{i}/{len(user_sites)}]: {site}")
        except:
            pass
        
        result = await test_site_via_api(site, proxy)
        if result.get('working'):
            working.append(site)
        else:
            dead.append(site)
        
        await asyncio.sleep(0.5)
    
    if dead:
        sites[str(user_id)] = working
        await save_json(USER_SITES_FILE, sites)
    
    result_text = f"""✅ Site Check Complete!

📊 Total: {len(user_sites)}
🟢 Working: {len(working)}
🔴 Dead: {len(dead)}"""
    
    await event.edit(result_text)
    active_processes.pop(user_id, None)

@client.on(events.NewMessage(pattern='/info'))
async def info_command(event):
    user_id = str(event.sender_id)
    user = await event.get_sender()
    
    sites = await load_json(USER_SITES_FILE)
    proxies = await load_json(USER_PROXIES_FILE)
    
    sites_count = len(sites.get(user_id, []))
    proxies_count = len(proxies.get(user_id, []))
    
    text = f"""
👤 User Information

User ID: `{event.sender_id}`
Username: @{user.username if user.username else 'N/A'}

📊 Statistics:
• Sites: {sites_count}/{MAX_SITES}
• Proxies: {proxies_count}/{MAX_PROXIES}
"""
    
    await event.reply(text)

# ==================== BOT START MENU ====================
@client.on(events.NewMessage)
async def handler(event):
    if event.message.text and event.message.text.startswith('/'):
        return
    
    user_id = event.sender_id
    
    if event.message.file:
        await handle_file_upload(event)
        return
    
    if user_id in active_processes:
        process_type = active_processes[user_id].get('type')
        if process_type in ['waiting_sites', 'waiting_proxies', 'waiting_cards']:
            await handle_text_input(event)
        return
    
    await show_start_menu(event)

async def show_start_menu(event):
    user = await event.get_sender()
    username = user.username if user.username else "User"
    first_name = user.first_name if user.first_name else "there"
    
    buttons = [
        [Button.url("𝙼𝙰𝙸𝙽 ", "https://t.me/afuonax"),
         Button.url("𝙲𝙰𝚁𝙳𝙸𝙽𝙶", SECOND_CHANNEL_LINK)],
        [Button.inline("💳 CHECK CARDS", b"check_cards"),
         Button.inline("🌐 ADD SITES", b"add_sites")],
        [Button.inline("🔌 ADD PROXY", b"add_proxies"),
         Button.inline("📋 MY SITES", b"my_sites")],
        [Button.inline("📋 MY PROXIES", b"my_proxies"),
         Button.inline("🧪 TEST SITES", b"test_sites")],
        [Button.inline("🧪 TEST PROXIES", b"test_proxies"),
         Button.inline("ℹ️ USER INFO", b"user_info")]
    ]
    
    
    for ext in ['jpg', 'jpeg', 'png']:
        if os.path.exists(f"bot_image.{ext}"):
            try:
                await client.send_file(
                    event.chat_id,
                    f"bot_image.{ext}",
                    caption=f"✨ 𝗪𝗲𝗹𝗰𝗼𝗺𝗲, {first_name}!\n 𝚍𝚘𝚗'𝚝 𝚏𝚘𝚛𝚐𝚎𝚝 𝚝𝚘 𝚜𝚞𝚋𝚜𝚌𝚛𝚒𝚋𝚎 𝚝𝚘 𝚝𝚑𝚎 𝚌𝚑𝚊𝚗𝚗𝚎𝚕𝚜 ‌♡⁩ ",
                    buttons=buttons
                )
                return  
            except:
                continue
    
    
    await event.reply(f"✨ 𝗪𝗲𝗹𝗰𝗼𝗺𝗲, {first_name}!\n𝚍𝚘𝚗'𝚝 𝚏𝚘𝚛𝚐𝚎𝚝 𝚝𝚘 𝚜𝚞𝚋𝚜𝚌𝚛𝚒𝚋𝚎 𝚝𝚘 𝚝𝚑𝚎 𝚌𝚑𝚊𝚗𝚗𝚎𝚕𝚜 ‌♡⁩ ", buttons=buttons)

# ==================== CALLBACK HANDLERS ====================
@client.on(events.CallbackQuery)
async def callback_handler(event):
    data = event.data.decode()
    user_id = event.sender_id
    
    if data == "main_menu":
        await show_main_menu(event)
    
    elif data == "back_to_start":
        await event.answer()
        await show_start_menu(event)
    
    elif data == "back_to_main":
        await event.answer()
        await show_main_menu(event)
    
    elif data == "check_cards":
        await event.answer()
        await show_check_cards_menu(event)
    
    elif data == "add_sites":
        await event.answer()
        await show_add_sites_menu(event)
    
    elif data == "add_proxies":
        await event.answer()
        await show_add_proxies_menu(event)
    
    elif data == "my_sites":
        await event.answer()
        await show_my_sites(event)
    
    elif data == "my_proxies":
        await event.answer()
        await show_my_proxies(event)
    
    elif data == "test_sites":
        await event.answer()
        await start_test_sites(event)
    
    elif data == "test_proxies":
        await event.answer()
        await start_test_proxies(event)
    
    elif data == "user_info":
        await event.answer()
        await show_user_info(event)
    
    elif data.startswith("removesite_"):
        site_index = int(data.split("_")[1])
        await remove_site_by_index(event, site_index)
    
    elif data.startswith("removeproxy_"):
        proxy_index = int(data.split("_")[1])
        await remove_proxy_by_index(event, proxy_index)
    
    elif data == "remove_all_sites":
        await remove_all_sites(event)
    elif data == "remove_all_proxies":
        await remove_all_proxies(event)
    
    elif data.startswith("stop:"):
        parts = data.split(":")
        if len(parts) == 2 and parts[1].isdigit():
            process_user_id = int(parts[1])
            if user_id == process_user_id:
                if process_user_id in active_processes:
                    active_processes.pop(process_user_id, None)
                    await event.answer("⛔ Stopped!", alert=True)
                    await event.edit("```⛔ Process stopped by user```")
                else:
                    await event.answer("❌ No active process!", alert=True)
            else:
                await event.answer("❌ Not your process!", alert=True)

# ==================== MENU DISPLAY FUNCTIONS 
async def show_main_menu(event):
    menu_text = f"""
┏━━━━━━━━━━━━━━━━┓
┃ 💳 {format_bold('Check Cards')} » /checkcards
┃ 🌐 {format_bold('Add Sites')} » /addsites
┃ 🔌 {format_bold('Add Proxy')} » /addproxy
┃ 📋 {format_bold('My Sites')} » /mysites
┃ 📋 {format_bold('My Proxies')} » /myproxies
┃ 🧪 {format_bold('Test Sites')} » /testsites
┃ ℹ️ {format_bold('User Info')} » /info
┗━━━━━━━━━━━━━━━━┛

"""
    
    buttons = [
        [Button.inline("💳 CHECK CARDS", b"check_cards"),
         Button.inline("🌐 ADD SITES", b"add_sites")],
        [Button.inline("🔌 ADD PROXY", b"add_proxies"),
         Button.inline("📋 MY SITES", b"my_sites")],
        [Button.inline("📋 MY PROXIES", b"my_proxies"),
         Button.inline("🧪 TEST SITES", b"test_sites")],
        [Button.inline("🧪 TEST PROXIES", b"test_proxies"),
         Button.inline("ℹ️ USER INFO", b"user_info")],
        [Button.inline("🔙 BACK TO START", b"back_to_start")]
    ]
    
    image_sent = False
    for ext in ['jpg', 'jpeg', 'png']:
        if os.path.exists(f"bot_image.{ext}"):
            try:
                await event.delete()
                await client.send_file(
                    event.chat_id,
                    f"bot_image.{ext}",
                    caption=menu_text,
                    buttons=buttons
                )
                image_sent = True
                break
            except:
                pass
    
    if not image_sent:
        await event.edit(menu_text, buttons=buttons)

async def show_check_cards_menu(event):
    menu_text = f"""
┏━━━━━━━━━━━━━━━━┓
┃ 📤 {format_bold('Send me a .txt file')}
┃    {format_bold('with your cards.')}
┃
┃ 📊 {format_bold('Limits:')}
┃ • {format_bold('Max cards per file')}: {MAX_CARDS_FILE}
┃ • {format_bold('Max saved cards')}: {MAX_CARDS}
┃
┃ 📝 {format_bold('Format')}: number|mm|yy|cvv
┃ ✦ {format_bold('Example')}: 4242424242424242|12|25|123
┗━━━━━━━━━━━━━━━━┛

"""
    
    buttons = [[Button.inline("🔙 BACK TO MAIN", b"back_to_main")]]
    
    image_sent = False
    for ext in ['jpg', 'jpeg', 'png']:
        if os.path.exists(f"bot_image.{ext}"):
            try:
                await event.delete()
                await client.send_file(
                    event.chat_id,
                    f"bot_image.{ext}",
                    caption=menu_text,
                    buttons=buttons
                )
                image_sent = True
                break
            except:
                pass
    
    if not image_sent:
        await event.edit(menu_text, buttons=buttons)
    
    active_processes[event.sender_id] = {'type': 'waiting_cards'}

async def show_add_sites_menu(event):
    menu_text = f"""
┏━━━━━━━━━━━━━━━━┓
┃ 📤 {format_bold('Send me a .txt file')}
┃    {format_bold('with your sites.')}
┃
┃ 📊 {format_bold('Limits:')}
┃ • {format_bold('Max sites per file')}: {MAX_SITES_FILE}
┃ • {format_bold('Max saved sites')}: {MAX_SITES}
┃
┃ ✦ {format_bold('Example')}:
┃   shop.com
┃   example.com
┃   test.com
┃
┃ ⚠️ {format_bold('Note')}: {format_bold('Only working sites will be saved.')}
┗━━━━━━━━━━━━━━━━┛

"""
    
    buttons = [[Button.inline("🔙 BACK TO MAIN", b"back_to_main")]]
    
    image_sent = False
    for ext in ['jpg', 'jpeg', 'png']:
        if os.path.exists(f"bot_image.{ext}"):
            try:
                await event.delete()
                await client.send_file(
                    event.chat_id,
                    f"bot_image.{ext}",
                    caption=menu_text,
                    buttons=buttons
                )
                image_sent = True
                break
            except:
                pass
    
    if not image_sent:
        await event.edit(menu_text, buttons=buttons)
    
    active_processes[event.sender_id] = {'type': 'waiting_sites'}

async def show_add_proxies_menu(event):
    menu_text = f"""
┏━━━━━━━━━━━━━━━━┓
┃ 📤 {format_bold('Send me a .txt file')}
┃    {format_bold('with your proxies.')}
┃
┃ 📊 {format_bold('Limits:')}
┃ • {format_bold('Max proxies per file')}: {MAX_PROXIES_FILE}
┃ • {format_bold('Max saved proxies')}: {MAX_PROXIES}
┃
┃ 🔧 {format_bold('Formats supported')}:
┃ • ip:port
┃ • ip:port:user:pass
┃ • user:pass@ip:port
┃ • socks5://ip:port
┃
┃ ⚠️ {format_bold('Note')}: {format_bold('Only working proxies will be saved.')}
┗━━━━━━━━━━━━━━━━┛

"""
    
    buttons = [[Button.inline("🔙 BACK TO MAIN", b"back_to_main")]]
    
    image_sent = False
    for ext in ['jpg', 'jpeg', 'png']:
        if os.path.exists(f"bot_image.{ext}"):
            try:
                await event.delete()
                await client.send_file(
                    event.chat_id,
                    f"bot_image.{ext}",
                    caption=menu_text,
                    buttons=buttons
                )
                image_sent = True
                break
            except:
                pass
    
    if not image_sent:
        await event.edit(menu_text, buttons=buttons)
    
    active_processes[event.sender_id] = {'type': 'waiting_proxies'}

async def show_my_sites(event):
    user_id = str(event.sender_id)
    sites_data = await load_json(USER_SITES_FILE)
    user_sites = sites_data.get(user_id, [])
    
    if not user_sites:
        menu_text = f"""

┏━━━━━━━━━━━━━━━━┓
┃ ❌ {format_bold('You have no saved sites.')}
┃
┃ {format_bold('Use "🌐 ADD SITES" to add some.')}
┗━━━━━━━━━━━━━━━━┛
"""
        buttons = [[Button.inline("🔙 BACK TO MAIN", b"back_to_main")]]
        
        image_sent = False
        for ext in ['jpg', 'jpeg', 'png']:
            if os.path.exists(f"bot_image.{ext}"):
                try:
                    await event.delete()
                    await client.send_file(
                        event.chat_id,
                        f"bot_image.{ext}",
                        caption=menu_text,
                        buttons=buttons
                    )
                    image_sent = True
                    break
                except:
                    pass
        
        if not image_sent:
            await event.edit(menu_text, buttons=buttons)
        return
    
    site_list = ""
    for i, site in enumerate(user_sites, 1):
        site_list += f" {i}. `{site}`\n"
    
    menu_text = f"""
┏━━━━━━━━━━━━━━━━┓
┃ 📊 {format_bold('Total')}: {len(user_sites)}/{MAX_SITES}
┃
{site_list}┗━━━━━━━━━━┛

"""
    
    buttons = []
    
    for i in range(1, min(6, len(user_sites) + 1)):
        buttons.append([Button.inline(f"🗑️ {format_bold(f'Remove #{i}')}", f"removesite_{i-1}".encode())])
    
    if len(user_sites) > 5:
        buttons.append([Button.inline(f"🗑️ {format_bold('Remove All')}", b"remove_all_sites")])
    
    buttons.append([Button.inline("🔙 BACK TO MAIN", b"back_to_main")])
    
    image_sent = False
    for ext in ['jpg', 'jpeg', 'png']:
        if os.path.exists(f"bot_image.{ext}"):
            try:
                await event.delete()
                await client.send_file(
                    event.chat_id,
                    f"bot_image.{ext}",
                    caption=menu_text,
                    buttons=buttons
                )
                image_sent = True
                break
            except:
                pass
    
    if not image_sent:
        await event.edit(menu_text, buttons=buttons)

async def show_my_proxies(event):
    user_id = str(event.sender_id)
    proxies_data = await load_json(USER_PROXIES_FILE)
    user_proxies = proxies_data.get(user_id, [])
    
    if not user_proxies:
        menu_text = f"""
┏━━━━━━━━━━━━━━━┓
┃ ❌ {format_bold('You have no saved proxies.')}
┃
┃ {format_bold('Use "🔌 ADD PROXIES" to add some.')}
┗━━━━━━━━━━━━━━━┛

𖣐━━━━━━━━━━━━━━𖣐
"""
        buttons = [[Button.inline("🔙 BACK TO MAIN", b"back_to_main")]]
        
        image_sent = False
        for ext in ['jpg', 'jpeg', 'png']:
            if os.path.exists(f"bot_image.{ext}"):
                try:
                    await event.delete()
                    await client.send_file(
                        event.chat_id,
                        f"bot_image.{ext}",
                        caption=menu_text,
                        buttons=buttons
                    )
                    image_sent = True
                    break
                except:
                    pass
        
        if not image_sent:
            await event.edit(menu_text, buttons=buttons)
        return
    
    proxy_list = ""
    for i, proxy in enumerate(user_proxies, 1):
        proxy_list += f" {i}. `{proxy['original']}`\n"
    
    menu_text = f"""

┏━━━━━━━━━━━━━━━━┓
┃ 📊 {format_bold('Total')}: {len(user_proxies)}/{MAX_PROXIES}
┃
{proxy_list}┗━━━━━━━━━┛

"""
    
    buttons = []
    
    for i in range(1, min(6, len(user_proxies) + 1)):
        buttons.append([Button.inline(f"🗑️ {format_bold(f'Remove #{i}')}", f"removeproxy_{i-1}".encode())])
    
    if len(user_proxies) > 5:
        buttons.append([Button.inline(f"🗑️ {format_bold('Remove All')}", b"remove_all_proxies")])
    
    buttons.append([Button.inline("🔙 BACK TO MAIN", b"back_to_main")])
    
    image_sent = False
    for ext in ['jpg', 'jpeg', 'png']:
        if os.path.exists(f"bot_image.{ext}"):
            try:
                await event.delete()
                await client.send_file(
                    event.chat_id,
                    f"bot_image.{ext}",
                    caption=menu_text,
                    buttons=buttons
                )
                image_sent = True
                break
            except:
                pass
    
    if not image_sent:
        await event.edit(menu_text, buttons=buttons)

async def show_user_info(event):
    user_id = str(event.sender_id)
    user = await event.get_sender()
    
    sites_data = await load_json(USER_SITES_FILE)
    proxies_data = await load_json(USER_PROXIES_FILE)
    
    sites_count = len(sites_data.get(user_id, []))
    proxies_count = len(proxies_data.get(user_id, []))
    
    menu_text = f"""
┏━━━━━━━━━━━━━━━━┓
┃ 🆔 {format_bold('User ID')}: `{event.sender_id}`
┃ 🧑 {format_bold('Username')}: @{user.username if user.username else 'N/A'}
┃ 📛 {format_bold('Name')}: {user.first_name or 'N/A'}
┃
┃ 📊 {format_bold('Statistics')}:
┃ 🌐 {format_bold('Sites')}: {sites_count}/{MAX_SITES}
┃ 🔌 {format_bold('Proxies')}: {proxies_count}/{MAX_PROXIES}
┗━━━━━━━━━━━━━━━━┛
"""
    
    buttons = [[Button.inline("🔙 BACK TO MAIN", b"back_to_main")]]
    
    image_sent = False
    for ext in ['jpg', 'jpeg', 'png']:
        if os.path.exists(f"bot_image.{ext}"):
            try:
                await event.delete()
                await client.send_file(
                    event.chat_id,
                    f"bot_image.{ext}",
                    caption=menu_text,
                    buttons=buttons
                )
                image_sent = True
                break
            except:
                pass
    
    if not image_sent:
        await event.edit(menu_text, buttons=buttons)

async def start_test_sites(event):
    user_id = str(event.sender_id)
    int_user_id = event.sender_id
    
    if int_user_id in active_processes and active_processes[int_user_id].get('type') not in ['waiting_sites', 'waiting_proxies', 'waiting_cards']:
        await event.answer("❌ You already have an active process! Wait for it to finish.", alert=True)
        return
    
    proxies_data = await load_json(USER_PROXIES_FILE)
    user_proxies = proxies_data.get(user_id, [])
    
    if not user_proxies:
        await event.answer("❌ You need at least one working proxy to test sites!", alert=True)
        return
    
    sites_data = await load_json(USER_SITES_FILE)
    user_sites = sites_data.get(user_id, [])
    
    if not user_sites:
        await event.answer("❌ You have no sites to test!", alert=True)
        return
    
    active_processes[int_user_id] = {'type': 'testing_sites'}
    
    await event.edit("🍑 Preparing to test your sites...")
    
    working_sites = []
    dead_sites = []
    proxy = random.choice(user_proxies)['url']
    
    total = len(user_sites)
    for i, site in enumerate(user_sites, 1):
        try:
            await event.edit(f"🍑 Testing sites... [{i}/{total}]")
        except:
            pass
        
        result = await test_site_via_api(site, proxy)
        
        if result.get('working'):
            working_sites.append(site)
        else:
            dead_sites.append(site)
        
        await asyncio.sleep(0.5)
    
    if dead_sites:
        sites_data[user_id] = working_sites
        await save_json(USER_SITES_FILE, sites_data)
    
    text = f"""
𖣐━━━━━━━━━━━━━━𖣐
✅ {format_bold('SITE TEST COMPLETE')}
𖣐━━━━━━━━━━━━━━𖣐

📊 {format_bold('Total Tested')}: {total}
🟢 {format_bold('Working')}: {len(working_sites)}
🔴 {format_bold('Dead')}: {len(dead_sites)}

"""
    
    if dead_sites:
        text += f"🔴 {format_bold('Dead Sites Removed')}:\n"
        for site in dead_sites[:5]:
            text += f"• `{site}`\n"
        if len(dead_sites) > 5:
            text += f"... and {len(dead_sites)-5} more\n"
    
    buttons = [[Button.inline("🔙 BACK TO MAIN", b"back_to_main")]]
    
    await event.edit(text, buttons=buttons)
    
    active_processes.pop(int_user_id, None)

async def start_test_proxies(event):
    user_id = str(event.sender_id)
    int_user_id = event.sender_id
    
    if int_user_id in active_processes and active_processes[int_user_id].get('type') not in ['waiting_sites', 'waiting_proxies', 'waiting_cards']:
        await event.answer("❌ You already have an active process! Wait for it to finish.", alert=True)
        return
    
    proxies_data = await load_json(USER_PROXIES_FILE)
    user_proxies = proxies_data.get(user_id, [])
    
    if not user_proxies:
        await event.answer("❌ You have no proxies to test!", alert=True)
        return
    
    active_processes[int_user_id] = {'type': 'testing_proxies'}
    
    await event.edit("🍑 Preparing to test your proxies...")
    
    working_proxies = []
    dead_proxies = []
    
    total = len(user_proxies)
    for i, proxy_data in enumerate(user_proxies, 1):
        try:
            await event.edit(f"🍑 Testing proxies... [{i}/{total}]")
        except:
            pass
        
        is_working, _ = await test_proxy(proxy_data['url'])
        
        if is_working:
            working_proxies.append(proxy_data)
        else:
            dead_proxies.append(proxy_data)
        
        await asyncio.sleep(0.5)
    
    if dead_proxies:
        proxies_data[user_id] = working_proxies
        await save_json(USER_PROXIES_FILE, proxies_data)
    
    text = f"""
𖣐━━━━━━━━━━━━━━𖣐
✅ {format_bold('PROXY TEST COMPLETE')}
𖣐━━━━━━━━━━━━━━𖣐

📊 {format_bold('Total Tested')}: {total}
🟢 {format_bold('Working')}: {len(working_proxies)}
🔴 {format_bold('Dead')}: {len(dead_proxies)}

"""
    
    if dead_proxies:
        text += f"🔴 {format_bold('Dead Proxies Removed')}:\n"
        for proxy in dead_proxies[:5]:
            text += f"• `{proxy['original']}`\n"
        if len(dead_proxies) > 5:
            text += f"... and {len(dead_proxies)-5} more\n"
    
    buttons = [[Button.inline("🔙 BACK TO MAIN", b"back_to_main")]]
    
    await event.edit(text, buttons=buttons)
    
    active_processes.pop(int_user_id, None)

async def remove_site_by_index(event, index):
    user_id = str(event.sender_id)
    sites_data = await load_json(USER_SITES_FILE)
    user_sites = sites_data.get(user_id, [])
    
    if 0 <= index < len(user_sites):
        removed = user_sites.pop(index)
        
        if user_sites:
            sites_data[user_id] = user_sites
        else:
            del sites_data[user_id]
        
        await save_json(USER_SITES_FILE, sites_data)
        await event.answer(f"✅ Removed: {removed}", alert=True)
        await show_my_sites(event)
    else:
        await event.answer("❌ Invalid index!", alert=True)

async def remove_proxy_by_index(event, index):
    user_id = str(event.sender_id)
    proxies_data = await load_json(USER_PROXIES_FILE)
    user_proxies = proxies_data.get(user_id, [])
    
    if 0 <= index < len(user_proxies):
        removed = user_proxies.pop(index)
        
        if user_proxies:
            proxies_data[user_id] = user_proxies
        else:
            del proxies_data[user_id]
        
        await save_json(USER_PROXIES_FILE, proxies_data)
        await event.answer(f"✅ Removed: {removed['original']}", alert=True)
        await show_my_proxies(event)
    else:
        await event.answer("❌ Invalid index!", alert=True)

async def remove_all_sites(event):
    user_id = str(event.sender_id)
    sites_data = await load_json(USER_SITES_FILE)
    
    if user_id in sites_data:
        count = len(sites_data[user_id])
        del sites_data[user_id]
        await save_json(USER_SITES_FILE, sites_data)
        await event.answer(f"✅ Removed all {count} sites!", alert=True)
    else:
        await event.answer("❌ No sites to remove!", alert=True)
    
    await show_my_sites(event)

async def remove_all_proxies(event):
    user_id = str(event.sender_id)
    proxies_data = await load_json(USER_PROXIES_FILE)
    
    if user_id in proxies_data:
        count = len(proxies_data[user_id])
        del proxies_data[user_id]
        await save_json(USER_PROXIES_FILE, proxies_data)
        await event.answer(f"✅ Removed all {count} proxies!", alert=True)
    else:
        await event.answer("❌ No proxies to remove!", alert=True)
    
    await show_my_proxies(event)

# ==================== FILE HANDLING ====================
async def handle_file_upload(event):
    user_id = event.sender_id
    
    if user_id not in active_processes:
        await event.reply("❌ Please use the buttons first.")
        return
    
    process_type = active_processes[user_id].get('type')
    
    if process_type == 'waiting_cards':
        await process_cards_file(event)
    elif process_type == 'waiting_sites':
        await process_sites_file(event)
    elif process_type == 'waiting_proxies':
        await process_proxies_file(event)
    else:
        await event.reply("❌ Invalid state. Please start over.")

async def process_sites_file(event):
    user_id = event.sender_id
    str_user_id = str(user_id)
    file_path = await event.message.download_media()
    
    try:
        async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
            content = await f.read()
    except:
        async with aiofiles.open(file_path, 'r', encoding='latin-1') as f:
            content = await f.read()
    
    os.remove(file_path)
    
    lines = content.splitlines()
    if len(lines) > MAX_SITES_FILE:
        await event.reply(
            f"━━━━━━━━━━━━━━\n"
            f"❌ FILE TOO LARGE\n"
            f"━━━━━━━━━━━━━\n\n"
            f"Your file has {len(lines)} sites.\n"
            f"Maximum allowed is {MAX_SITES_FILE} sites."
        )
        active_processes.pop(user_id, None)
        return
    
    sites_to_test = []
    for line in lines:
        line = line.strip()
        if line:
            line = line.replace('https://', '').replace('http://', '').split('/')[0]
            if re.match(r'^[a-zA-Z0-9][a-zA-Z0-9\-]*\.[a-zA-Z]{2,}', line):
                sites_to_test.append(line)
    
    if not sites_to_test:
        await event.reply(
            "━━━━━━━━━━━━━━\n"
            "❌ NO VALID SITES\n"
            "━━━━━━━━━━━━━\n\n"
            "No valid sites found in your file."
        )
        active_processes.pop(user_id, None)
        return
    
    proxies_data = await load_json(USER_PROXIES_FILE)
    user_proxies = proxies_data.get(str_user_id, [])
    
    if not user_proxies:
        await event.reply(
            "━━━━━━━━━━━━━━\n"
            "❌ NO PROXY\n"
            "━━━━━━━━━━━━━\n\n"
            "You need at least one working proxy to test sites.\n"
            "Add proxies first."
        )
        active_processes.pop(user_id, None)
        return
    
    status_msg = await event.reply(f"🍑 Testing {len(sites_to_test)} sites...")
    
    proxy = random.choice(user_proxies)['url']
    working_sites = []
    
    for i, site in enumerate(sites_to_test, 1):
        try:
            await status_msg.edit(f"🍑 Testing sites... [{i}/{len(sites_to_test)}]")
        except:
            pass
        
        result = await test_site_via_api(site, proxy)
        
        if result.get('working'):
            working_sites.append(site)
        
        await asyncio.sleep(0.5)
    
    sites_data = await load_json(USER_SITES_FILE)
    current_sites = sites_data.get(str_user_id, [])
    
    added = []
    for site in working_sites:
        if site not in current_sites and len(current_sites) < MAX_SITES:
            current_sites.append(site)
            added.append(site)
        if len(current_sites) >= MAX_SITES:
            break
    
    if added:
        sites_data[str_user_id] = current_sites
        await save_json(USER_SITES_FILE, sites_data)
    
    response = f"""
━━━━━━━━━━━━━━━━━
✅ SITES PROCESSED
━━━━━━━━━━━━━━━━━

📊 Total in file: {len(sites_to_test)}
🟢 Working: {len(working_sites)}
✅ Added to your list: {len(added)}
📊 Total now: {len(current_sites)}/{MAX_SITES}

"""
    
    if added:
        response += "Added:\n"
        for site in added[:5]:
            response += f"• `{site}`\n"
        if len(added) > 5:
            response += f"... and {len(added)-5} more\n"
    
    buttons = [[Button.inline("🔙 BACK", b"back_to_main")]]
    
    await status_msg.edit(response, buttons=buttons)
    
    active_processes.pop(user_id, None)

async def process_proxies_file(event):
    user_id = event.sender_id
    str_user_id = str(user_id)
    file_path = await event.message.download_media()
    
    try:
        async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
            content = await f.read()
    except:
        async with aiofiles.open(file_path, 'r', encoding='latin-1') as f:
            content = await f.read()
    
    os.remove(file_path)
    
    lines = content.splitlines()
    if len(lines) > MAX_PROXIES_FILE:
        await event.reply(
            f"━━━━━━━━━━━━━━\n"
            f"❌ FILE TOO LARGE\n"
            f"━━━━━━━━━━━━━\n\n"
            f"Your file has {len(lines)} proxies.\n"
            f"Maximum allowed is {MAX_PROXIES_FILE} proxies."
        )
        active_processes.pop(user_id, None)
        return
    
    proxies_to_test = []
    for line in lines:
        line = line.strip()
        if line:
            proxy_url = parse_proxy(line)
            if proxy_url:
                proxies_to_test.append((line, proxy_url))
    
    if not proxies_to_test:
        await event.reply(
            "━━━━━━━━━━━━━━\n"
            "❌ NO VALID PROXIES\n"
            "━━━━━━━━━━━━━\n\n"
            "No valid proxies found in your file."
        )
        active_processes.pop(user_id, None)
        return
    
    status_msg = await event.reply(f"🍑 Testing {len(proxies_to_test)} proxies...")
    
    working_proxies = []
    
    for i, (original, url) in enumerate(proxies_to_test, 1):
        try:
            await status_msg.edit(f"🍑 Testing proxies... [{i}/{len(proxies_to_test)}]")
        except:
            pass
        
        is_working, ip = await test_proxy(url)
        
        if is_working:
            working_proxies.append({
                'original': original,
                'url': url,
                'ip': ip
            })
        
        await asyncio.sleep(0.5)
    
    proxies_data = await load_json(USER_PROXIES_FILE)
    current_proxies = proxies_data.get(str_user_id, [])
    
    added = []
    for proxy in working_proxies:
        exists = any(p['original'] == proxy['original'] for p in current_proxies)
        if not exists and len(current_proxies) < MAX_PROXIES:
            current_proxies.append(proxy)
            added.append(proxy['original'])
        if len(current_proxies) >= MAX_PROXIES:
            break
    
    if added:
        proxies_data[str_user_id] = current_proxies
        await save_json(USER_PROXIES_FILE, proxies_data)
    
    response = f"""
━━━━━━━━━━━━━━━━━
✅ PROXIES PROCESSED
━━━━━━━━━━━━━━━━━

📊 Total in file: {len(proxies_to_test)}
🟢 Working: {len(working_proxies)}
✅ Added to your list: {len(added)}
📊 Total now: {len(current_proxies)}/{MAX_PROXIES}

"""
    
    if added:
        response += "Added:\n"
        for proxy in added[:5]:
            response += f"• `{proxy}`\n"
        if len(added) > 5:
            response += f"... and {len(added)-5} more\n"
    
    buttons = [[Button.inline("🔙 BACK", b"back_to_main")]]
    
    await status_msg.edit(response, buttons=buttons)
    
    active_processes.pop(user_id, None)

async def process_cards_file(event):
    user_id = event.sender_id
    str_user_id = str(user_id)
    file_path = await event.message.download_media()
    
    try:
        async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
            content = await f.read()
    except:
        async with aiofiles.open(file_path, 'r', encoding='latin-1') as f:
            content = await f.read()
    
    os.remove(file_path)
    
    lines = content.splitlines()
    if len(lines) > MAX_CARDS_FILE:
        await event.reply(
            f"━━━━━━━━━━━━━━\n"
            f"❌ FILE TOO LARGE\n"
            f"━━━━━━━━━━━━━\n\n"
            f"Your file has {len(lines)} cards.\n"
            f"Maximum allowed is {MAX_CARDS_FILE} cards."
        )
        active_processes.pop(user_id, None)
        return
    
    cards = extract_cards(content)
    
    if not cards:
        await event.reply(
            "━━━━━━━━━━━━━━\n"
            "❌ NO VALID CARDS\n"
            "━━━━━━━━━━━━━\n\n"
            "No valid cards found in your file."
        )
        active_processes.pop(user_id, None)
        return
    
    if len(cards) > MAX_CARDS:
        cards = cards[:MAX_CARDS]
        await event.reply(f"⚠️ File has more than {MAX_CARDS} cards. Checking only first {MAX_CARDS}.")
    
    sites_data = await load_json(USER_SITES_FILE)
    proxies_data = await load_json(USER_PROXIES_FILE)
    
    user_sites = sites_data.get(str_user_id, [])
    user_proxies = proxies_data.get(str_user_id, [])
    
    if not user_sites:
        await event.reply(
            "━━━━━━━━━━━━━━\n"
            "❌ NO SITES\n"
            "━━━━━━━━━━━━━\n\n"
            "You have no saved sites.\n"
            "Add sites first using '🌐 ADD SITES'."
        )
        active_processes.pop(user_id, None)
        return
    
    if not user_proxies:
        await event.reply(
            "━━━━━━━━━━━━━━\n"
            "❌ NO PROXIES\n"
            "━━━━━━━━━━━━━\n\n"
            "You have no saved proxies.\n"
            "Add proxies first using '🔌 ADD PROXIES'."
        )
        active_processes.pop(user_id, None)
        return
    
    active_processes[user_id]['type'] = 'checking_cards'
    
    await process_card_check(event, cards, user_sites, user_proxies)

async def process_card_check(event, cards, sites, proxies):
    user_id = event.sender_id
    total = len(cards)
    checked = 0
    approved = 0
    charged = 0
    threed = 0
    declined = 0
    status_msg = await event.reply("```🍑 Preparing your lunch...```")
    
    try:
        for card in cards:  
            if user_id not in active_processes or active_processes[user_id].get('type') != 'checking_cards':
                break
            
            if not sites:
                break
            
            site = random.choice(sites)
            proxy = random.choice(proxies)['url']
            
            
            result = await check_card_via_api(card, site, proxy)
            
            checked += 1
            
            if isinstance(result, Exception):
                declined += 1
                await asyncio.sleep(3)
                continue
            
            status = get_card_status(result.get('Response', ''), result.get('Status', ''))
            
            if status:
                if "CHARGED" in status:
                    charged += 1
                elif "APPROVED" in status:
                    approved += 1
                elif "3D" in status:
                    threed += 1
                
                bin_info = await get_bin_info(card.split('|')[0])
                
                card_msg = f"""
{status}

CC ⇾ `{card}`
Gateway ⇾ {result.get('Gateway', 'Unknown')}
Response ⇾ {result.get('Response', 'Unknown')}
Price ⇾ {result.get('Price', '-')} 💸

```BIN Info: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
Bank: {bin_info['bank']}
Country: {bin_info['country']} {bin_info['flag']}```
"""
                await event.reply(card_msg)
            else:
                declined += 1
            
            progress_text = f"""```🍑 Progress```"""
            buttons = [
                [Button.inline(f"Card ➜ {card[:12]}****", f"none_{user_id}")],
                [Button.inline(f"Response ➜ {result.get('Response', '')[:25]}...", f"none_{user_id}")],
                [Button.inline(f"Site ➜ [1]", f"none_{user_id}")],
                [Button.inline(f"CHARGE ➜ [ {charged} ] 💎", f"none_{user_id}")],
                [Button.inline(f"Approve ➜ [ {approved} ] 🔥", f"none_{user_id}")],
                [Button.inline(f"3D SECURE ➜ [ {threed} ] 🟡", f"none_{user_id}")],
                [Button.inline(f"Decline ➜ [ {declined} ] ❌", f"none_{user_id}")],
                [Button.inline(f"Progress ➜ [{checked}/{total}] ✅", f"none_{user_id}")],
                [Button.inline("⛔ Stop", f"stop:{user_id}")]
            ]
            
            try:
                await status_msg.edit(progress_text, buttons=buttons)
            except:
                pass
            
            await asyncio.sleep(3)  
    
    finally:
        if user_id in active_processes:
            active_processes.pop(user_id, None)
        
        final = f"""```✅ CHECK COMPLETE!

Total Cards: {total}
CHARGED 💎 : {charged}
APPROVED ✅ : {approved}
3D SECURE 🟡 : {threed}
DECLINED ❌ : {declined}```"""
        
        await status_msg.edit(final)

async def handle_text_input(event):
    user_id = event.sender_id
    
    if user_id not in active_processes:
        return
    
    process_type = active_processes[user_id].get('type')
    
    if process_type == 'waiting_sites':
        await process_sites_text(event)
    elif process_type == 'waiting_proxies':
        await process_proxies_text(event)
    else:
        await event.reply("❌ Please send a file instead.")

async def process_sites_text(event):
    user_id = event.sender_id
    str_user_id = str(user_id)
    text = event.message.text.strip()
    
    lines = text.splitlines()
    if len(lines) > MAX_SITES_FILE:
        await event.reply(
            f"━━━━━━━━━━━━━━\n"
            f"❌ TOO MANY SITES\n"
            f"━━━━━━━━━━━━━\n\n"
            f"You sent {len(lines)} sites.\n"
            f"Maximum allowed is {MAX_SITES_FILE} sites."
        )
        active_processes.pop(user_id, None)
        return
    
    sites_to_test = []
    for line in lines:
        line = line.strip()
        if line:
            line = line.replace('https://', '').replace('http://', '').split('/')[0]
            if re.match(r'^[a-zA-Z0-9][a-zA-Z0-9\-]*\.[a-zA-Z]{2,}', line):
                sites_to_test.append(line)
    
    if not sites_to_test:
        await event.reply(
            "━━━━━━━━━━━━━━\n"
            "❌ NO VALID SITES\n"
            "━━━━━━━━━━━━━\n\n"
            "No valid sites found."
        )
        active_processes.pop(user_id, None)
        return
    
    proxies_data = await load_json(USER_PROXIES_FILE)
    user_proxies = proxies_data.get(str_user_id, [])
    
    if not user_proxies:
        await event.reply(
            "━━━━━━━━━━━━━━\n"
            "❌ NO PROXY\n"
            "━━━━━━━━━━━━━\n\n"
            "You need at least one working proxy to test sites.\n"
            "Add proxies first."
        )
        active_processes.pop(user_id, None)
        return
    
    status_msg = await event.reply(f"🍑 Testing {len(sites_to_test)} sites...")
    
    proxy = random.choice(user_proxies)['url']
    working_sites = []
    
    for i, site in enumerate(sites_to_test, 1):
        try:
            await status_msg.edit(f"🍑 Testing sites... [{i}/{len(sites_to_test)}]")
        except:
            pass
        
        result = await test_site_via_api(site, proxy)
        
        if result.get('working'):
            working_sites.append(site)
        
        await asyncio.sleep(0.5)
    
    sites_data = await load_json(USER_SITES_FILE)
    current_sites = sites_data.get(str_user_id, [])
    
    added = []
    for site in working_sites:
        if site not in current_sites and len(current_sites) < MAX_SITES:
            current_sites.append(site)
            added.append(site)
        if len(current_sites) >= MAX_SITES:
            break
    
    if added:
        sites_data[str_user_id] = current_sites
        await save_json(USER_SITES_FILE, sites_data)
    
    response = f"""
━━━━━━━━━━━━━━━━━
✅ SITES PROCESSED
━━━━━━━━━━━━━━━━━

📊 Total sent: {len(sites_to_test)}
🟢 Working: {len(working_sites)}
✅ Added to your list: {len(added)}
📊 Total now: {len(current_sites)}/{MAX_SITES}

"""
    
    if added:
        response += "Added:\n"
        for site in added[:5]:
            response += f"• `{site}`\n"
        if len(added) > 5:
            response += f"... and {len(added)-5} more\n"
    
    buttons = [[Button.inline("🔙 BACK", b"back_to_main")]]
    
    await status_msg.edit(response, buttons=buttons)
    
    active_processes.pop(user_id, None)

async def process_proxies_text(event):
    user_id = event.sender_id
    str_user_id = str(user_id)
    text = event.message.text.strip()
    
    lines = text.splitlines()
    if len(lines) > MAX_PROXIES_FILE:
        await event.reply(
            f"━━━━━━━━━━━━━━\n"
            f"❌ TOO MANY PROXIES\n"
            f"━━━━━━━━━━━━━\n\n"
            f"You sent {len(lines)} proxies.\n"
            f"Maximum allowed is {MAX_PROXIES_FILE} proxies."
        )
        active_processes.pop(user_id, None)
        return
    
    proxies_to_test = []
    for line in lines:
        line = line.strip()
        if line:
            proxy_url = parse_proxy(line)
            if proxy_url:
                proxies_to_test.append((line, proxy_url))
    
    if not proxies_to_test:
        await event.reply(
            "━━━━━━━━━━━━━━\n"
            "❌ NO VALID PROXIES\n"
            "━━━━━━━━━━━━━\n\n"
            "No valid proxies found."
        )
        active_processes.pop(user_id, None)
        return
    
    status_msg = await event.reply(f"🍑 Testing {len(proxies_to_test)} proxies...")
    
    working_proxies = []
    
    for i, (original, url) in enumerate(proxies_to_test, 1):
        try:
            await status_msg.edit(f"🍑 Testing proxies... [{i}/{len(proxies_to_test)}]")
        except:
            pass
        
        is_working, ip = await test_proxy(url)
        
        if is_working:
            working_proxies.append({
                'original': original,
                'url': url,
                'ip': ip
            })
        
        await asyncio.sleep(0.5)
    
    proxies_data = await load_json(USER_PROXIES_FILE)
    current_proxies = proxies_data.get(str_user_id, [])
    
    added = []
    for proxy in working_proxies:
        exists = any(p['original'] == proxy['original'] for p in current_proxies)
        if not exists and len(current_proxies) < MAX_PROXIES:
            current_proxies.append(proxy)
            added.append(proxy['original'])
        if len(current_proxies) >= MAX_PROXIES:
            break
    
    if added:
        proxies_data[str_user_id] = current_proxies
        await save_json(USER_PROXIES_FILE, proxies_data)
    
    response = f"""
━━━━━━━━━━━━━━━━━━
✅ PROXIES PROCESSED
━━━━━━━━━━━━━━━━━━

📊 Total sent: {len(proxies_to_test)}
🟢 Working: {len(working_proxies)}
✅ Added to your list: {len(added)}
📊 Total now: {len(current_proxies)}/{MAX_PROXIES}

"""
    
    if added:
        response += "Added:\n"
        for proxy in added[:5]:
            response += f"• `{proxy}`\n"
        if len(added) > 5:
            response += f"... and {len(added)-5} more\n"
    
    buttons = [[Button.inline("🔙 BACK", b"back_to_main")]]
    
    await status_msg.edit(response, buttons=buttons)
    
    active_processes.pop(user_id, None)

# ==================== MAIN ====================
async def main():
    print("""
Developer: 𓆩𝗔𓆪𝗙𝗨𝗢𝗡𝗔
Telegram: @afuonax
Starting bot...
""")
    
    await client.start(bot_token=BOT_TOKEN)
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
