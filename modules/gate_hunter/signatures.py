"""
Gate Hunter Signatures - Payment Gateways & Security Systems
"""

# بوابات الدفع — (اسم، regex دقيق)
PAYMENT_GATEWAYS = [
    ("Stripe",         r'stripe(?:\.js|\.com/v3|[_\-]?(?:key|pk_live|pk_test))|Stripe\s*\('),
    ("PayPal",         r'paypal(?:\.com|\.js|[_\-]?(?:client|button|sdk))'),
    ("Braintree",      r'braintree(?:\.js|[_\-]?(?:sdk|client|token)|paypal\.com/sdk/js)'),
    ("Square",         r'squareup\.com|square(?:\.js|[_\-]?(?:payments|up|cdn))|SqPaymentForm'),
    ("Authorize.Net",  r'authorize\.net|authorizenet|AcceptCore|accept\.authorize'),
    ("Adyen",          r'adyen(?:\.com|[_\-]?checkout|\.js|WebComponents)'),
    ("WooCommerce",    r'woocommerce|wc[_\-]?(?:cart|checkout|payment|add[_\-]to[_\-]cart)'),
    ("Shopify",        r'shopify(?:\.com|[_\-]?pay|[_\-]?cdn)|cdn\.shopify'),
    ("Magento",        r'magento|Mage/|checkout/onepage|checkout/cart'),
    ("2Checkout",      r'2checkout|2co\.com|verifone\.com'),
    ("Razorpay",       r'razorpay(?:\.com|\.js|[_\-]?(?:key|checkout|payment))'),
    ("NMI",            r'network(?:merchants|for\s*commerce)|nmi[_\-]?(?:gateway|token|hosted)'),
    ("CyberSource",    r'cybersource|flex\.cybersource|Cybersource'),
    ("Worldpay",       r'worldpay(?:\.com|Access|[_\-]?js|[_\-]?total)'),
    ("Klarna",         r'klarna(?:\.com|[_\-]?(?:payments|checkout)|\.js)'),
    ("PayFlow",        r'payflow(?:pro|link|gateway)|payflowpro'),
    ("Checkout.com",   r'checkout\.com|cko[_\-]?(?:token|frame|js|public)'),
    ("Moneris",        r'moneris(?:\.com|gateway|eselectplus|eSelectPlus)'),
    ("eWay",           r'eway(?:\.com\.au|RapidAPI|[_\-]?(?:payment|client))'),
    ("BigCommerce",    r'bigcommerce(?:\.com|[_\-]?payment|[_\-]?cart)'),
    ("OpenCart",       r'opencart.*(?:payment|checkout)|index\.php\?route=checkout'),
    ("Recurly",        r'recurly(?:\.com|\.js|[_\-]?(?:public|js))'),
    ("Cardknox",       r'cardknox|ifields\.cardknox'),
    ("Paytrace",       r'paytrace(?:\.com|[_\-]?api|[_\-]?token)'),
    ("CardConnect",    r'cardconnect(?:\.com|[_\-]?token|[_\-]?iframe)'),
    ("Heartland",      r'heartland(?:payment|[_\-]?systems|[_\-]?token)|securesubmit'),
    ("BlueSnap",       r'bluesnap(?:\.com|[_\-]?token|[_\-]?hosted)'),
    ("Payoneer",       r'payoneer(?:\.com|[_\-]?payment)'),
    ("Paymob",         r'paymob(?:\.com|[_\-]?payment|[_\-]?api)'),
    ("Tap",            r'tap(?:payments\.com|[_\-]?payment)|gosell\.io'),
    ("PrestaShop",     r'prestashop|presta(?:[_\-]?shop|[_\-]?module)'),
]

# تواقيع أنظمة الحماية — headers + HTML
SECURITY_SIGNATURES = {
    'Cloudflare': {
        'headers_keys':   {'cf-ray', 'cf-cache-status', 'cf-request-id', 'cf-connecting-ip'},
        'server_match':   'cloudflare',
        'html_patterns':  [r'challenges\.cloudflare\.com', r'__cf_bm', r'cf-please-wait',
                           r'cloudflare-static', r'turnstile\.cloudflare\.com'],
        'weight': 35,
    },
    'Akamai': {
        'headers_keys':   {'x-akamai-transformed', 'akamai-origin-hop', 'x-check-cacheable'},
        'server_match':   '',
        'html_patterns':  [r'akamai\.net', r'akamaistream', r'akadns\.net'],
        'weight': 35,
    },
    'Imperva': {
        'headers_keys':   {'x-iinfo', 'x-cdn'},
        'server_match':   '',
        'html_patterns':  [r'imperva(?:\.com)?', r'incapsula', r'visid_incap', r'nlbi_'],
        'weight': 35,
    },
    'Sucuri': {
        'headers_keys':   {'x-sucuri-id', 'x-sucuri-cache'},
        'server_match':   'sucuri',
        'html_patterns':  [r'sucuri(?:\.net|firewall|cloudproxy)', r'sitelock'],
        'weight': 30,
    },
    'reCAPTCHA': {
        'headers_keys':   set(),
        'server_match':   '',
        'html_patterns':  [r'recaptcha/api\.js', r'g-recaptcha', r'recaptcha-token',
                           r'protected\s+by\s+recaptcha'],
        'weight': 25,
    },
    'hCaptcha': {
        'headers_keys':   set(),
        'server_match':   '',
        'html_patterns':  [r'hcaptcha\.com', r'h-captcha', r'hcaptcha-token'],
        'weight': 25,
    },
    'Turnstile': {
        'headers_keys':   set(),
        'server_match':   '',
        'html_patterns':  [r'turnstile\.cloudflare\.com', r'cf-turnstile'],
        'weight': 20,
    },
    '3D Secure': {
        'headers_keys':   set(),
        'server_match':   '',
        'html_patterns':  [r'cardinalcommerce', r'3ds-method', r'3d-secure'],
        'weight': 15,
    },
    'Kount': {
        'headers_keys':   set(),
        'server_match':   '',
        'html_patterns':  [r'kount\.com', r'kount_fraud'],
        'weight': 10,
    },
    'Signifyd': {
        'headers_keys':   set(),
        'server_match':   '',
        'html_patterns':  [r'signifyd\.com', r'signifyd-fingerprint'],
        'weight': 10,
    },
}

# مسارات صفحات الدفع
CHECKOUT_PATHS = [
    '/checkout',
    '/cart',
    '/shop/checkout',
    '/order',
    '/pay',
    '/payment',
    '/my-account/add-payment-method',
    '/en/checkout',
    '/store/checkout',
    '/?page_id=checkout',
    '/index.php?route=checkout/checkout',
    '/checkout/onepage/',
    '/buy',
    '/purchase',
]

# دوركات جاهزة للبحث
DORK_PRESETS = [
    ('🛒 WooCommerce Checkouts',    'intext:"woocommerce" inurl:checkout'),
    ('💳 Stripe Sites',             'intext:"stripe" inurl:checkout'),
    ('🏪 Shopify Stores',           'inurl:myshopify.com/checkout'),
    ('🏬 Magento Stores',           'inurl:"magento" inurl:"checkout/onepage"'),
    ('🅿️ PayPal Checkout',          'intext:"paypal" inurl:checkout'),
    ('🛍️ OpenCart',                 'intext:"opencart" inurl:checkout'),
    ('💲 Authorize.Net Sites',      'intext:"authorize.net" inurl:checkout'),
    ('🌐 Razorpay Sites',           'intext:"razorpay" inurl:payment'),
    ('🔵 Braintree Sites',          'intext:"braintree" inurl:checkout'),
    ('🟣 Adyen Sites',              'intext:"adyen" inurl:checkout'),
]

# الدول المدعومة
COUNTRIES = {
    'us': '🇺🇸 USA',      'gb': '🇬🇧 UK',       'de': '🇩🇪 Germany',
    'fr': '🇫🇷 France',    'ca': '🇨🇦 Canada',    'au': '🇦🇺 Australia',
    'br': '🇧🇷 Brazil',    'in': '🇮🇳 India',     'nl': '🇳🇱 Netherlands',
    'jp': '🇯🇵 Japan',     'sg': '🇸🇬 Singapore', 'ae': '🇦🇪 UAE',
    'it': '🇮🇹 Italy',     'es': '🇪🇸 Spain',     'mx': '🇲🇽 Mexico',
    'ru': '🇷🇺 Russia',    'tr': '🇹🇷 Turkey',    'za': '🇿🇦 South Africa',
    'se': '🇸🇪 Sweden',    'pl': '🇵🇱 Poland',
}

# محركات البحث
SEARCH_ENGINES = {
    'google':     'https://www.google.com/search',
    'bing':       'https://www.bing.com/search',
    'yahoo':      'https://search.yahoo.com/search',
    'duckduckgo': 'https://duckduckgo.com/html/',
    'yandex':     'https://yandex.com/search/',
}

# نطاقات يجب استبعادها
EXCLUDED_DOMAINS = [
    'google.com', 'facebook.com', 'amazon.com', 'wikipedia.org',
    'youtube.com', 'twitter.com', 'instagram.com', 'linkedin.com',
    'pinterest.com', 'reddit.com', 'github.com', 'stackoverflow.com',
]
