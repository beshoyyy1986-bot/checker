"""
utils/identity.py
─────────────────
توليد هويات وبيانات مشتركة لكل البوابات:
  - UA pool (Chrome متزامن مع sec-ch-ua)
  - بيانات الشخصية (اسم، إيميل، عنوان، تليفون)
"""
import random
import string
import uuid
import secrets

# ── Rotating UA pool — UA + sec-ch-ua دائماً متطابقين ─────────────────────
# WAF أغلب المواقع تتحقق إن Chrome version في UA == version في sec-ch-ua
UA_POOL = [
    {
        "ua":       "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
        "ch_ua":    '"Chromium";v="136", "Google Chrome";v="136", "Not-A.Brand";v="99"',
        "platform": '"Windows"',
        "mobile":   "?0",
    },
    {
        "ua":       "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
        "ch_ua":    '"Chromium";v="134", "Google Chrome";v="134", "Not-A.Brand";v="99"',
        "platform": '"Windows"',
        "mobile":   "?0",
    },
    {
        "ua":       "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
        "ch_ua":    '"Chromium";v="136", "Google Chrome";v="136", "Not-A.Brand";v="99"',
        "platform": '"macOS"',
        "mobile":   "?0",
    },
    {
        "ua":       "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
        "ch_ua":    '"Chromium";v="134", "Google Chrome";v="134", "Not-A.Brand";v="99"',
        "platform": '"macOS"',
        "mobile":   "?0",
    },
    {
        "ua":       "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
        "ch_ua":    '"Chromium";v="136", "Google Chrome";v="136", "Not-A.Brand";v="99"',
        "platform": '"Linux"',
        "mobile":   "?0",
    },
    {
        "ua":       "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
        "ch_ua":    '"Chromium";v="135", "Google Chrome";v="135", "Not-A.Brand";v="99"',
        "platform": '"Windows"',
        "mobile":   "?0",
    },
]

# Backward-compat alias (كود قديم بيستخدم CW_UA_POOL)
CW_UA_POOL = UA_POOL

# ── Identity data pools ────────────────────────────────────────────────────
_DOMAINS = ["hotmail.com"] * 3 + ["outlook.com"] * 3 + ["yahoo.com"] * 2 + ["gmail.com"]

_FIRSTS = [
    "James", "Oliver", "Liam", "Noah", "Emma", "Sophia", "Lucas",
    "Henry", "Ella", "Grace", "Mason", "Ethan", "Chloe", "Ryan",
    "Aiden", "Mia", "Jacob", "Emily", "Logan", "Abigail", "Michael",
    "Isabella", "Alexander", "Charlotte", "Benjamin", "Ava", "Daniel",
]

_LASTS = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia",
    "Miller", "Davis", "Wilson", "Taylor", "Anderson", "Thomas",
    "Jackson", "White", "Harris", "Martin", "Thompson", "Moore",
    "Young", "Allen", "King", "Wright", "Hill", "Scott", "Green",
]

_US_ZIPS = [
    ("10022", "NY"), ("90210", "CA"), ("60601", "IL"), ("77001", "TX"),
    ("85001", "AZ"), ("19101", "PA"), ("30301", "GA"), ("98101", "WA"),
    ("80201", "CO"), ("33101", "FL"), ("02101", "MA"), ("55401", "MN"),
    ("94102", "CA"), ("30303", "GA"), ("75201", "TX"), ("97201", "OR"),
]

_ACCEPT_LANGUAGES = [
    "en-US,en;q=0.9",
    "en-US,en;q=0.8,en-GB;q=0.7",
    "en-US,en;q=0.9,fr;q=0.8",
]


def get_random_ua() -> dict:
    """Return a random UA profile (ua, ch_ua, platform, mobile)."""
    return random.choice(UA_POOL)


def generate_identity() -> dict:
    """
    Generate a random US person identity.
    Returns dict with: first, last, name, email, zip, state, phone.
    """
    first = random.choice(_FIRSTS)
    last  = random.choice(_LASTS)
    slug  = "".join(random.choices(string.ascii_lowercase, k=6))
    email = f"{slug}{random.randint(10, 999)}@{random.choice(_DOMAINS)}"
    zp, st = random.choice(_US_ZIPS)
    phone  = f"+1{random.randint(2020000000, 9999999999)}"
    return {
        "first": first,
        "last":  last,
        "name":  f"{first} {last}",
        "email": email,
        "zip":   zp,
        "state": st,
        "phone": phone,
    }


def new_stripe_ids() -> dict:
    """Generate Stripe-style GUIDs for requests."""
    def _uid():
        return str(uuid.uuid4()) + secrets.token_hex(3)
    return {
        "guid": _uid(),
        "muid": _uid(),
        "sid":  _uid(),
        "cid":  str(uuid.uuid4()),
    }


def get_accept_language() -> str:
    return random.choice(_ACCEPT_LANGUAGES)
