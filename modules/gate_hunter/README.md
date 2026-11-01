# 🔌 Gate Hunter Module

وحدة متكاملة لفحص بوابات الدفع وأنظمة الحماية في المواقع الإلكترونية.

## 📁 الهيكل

```
modules/gate_hunter/
├── __init__.py          # تصدير الدوال الرئيسية
├── signatures.py        # ثوابت البوابات وأنظمة الحماية
├── config.py            # إدارة الإعدادات (config.json)
├── database.py          # عمليات قاعدة البيانات
├── bright_data.py       # Bright Data SERP API Integration
├── scanner.py           # منطق الفحص العميق
└── handlers.py          # Telegram Handlers للبوابة
```

## 🎯 الميزات

### 1. بحث متقدم عبر Bright Data SERP
- دعم 5 محركات بحث: Google, Bing, Yahoo, DuckDuckGo, Yandex
- Geo-targeting عبر 20 دولة
- بحث متعدد الصفحات (Pagination)
- استخراج ذكي للروابط من JSON و HTML

### 2. فحص عميق للمواقع
- كشف 30+ بوابة دفع (Stripe, PayPal, Braintree, ...)
- كشف 10 أنظمة حماية (Cloudflare, Akamai, Imperva, ...)
- فحص متعدد المراحل:
  - الصفحة الرئيسية
  - روابط Checkout المكتشفة
  - مسارات Checkout الشائعة
  - API endpoints رسمية للمنصات

### 3. مستويات الثقة
- ✅ **Confirmed**: دليل قاطع من API endpoints
- 🟢 **Strong**: دليل تقني (script/form/iframe)
- 🟡 **Weak**: ذكر نصي فقط

### 4. إدارة الإعدادات
- Bright Data Credentials
- Zone Name
- عدد النتائج الافتراضي
- سقف محاولات البحث
- تفعيل/تعطيل الفحص العميق
- إظهار/إخفاء المواقع المحمية

## 🔧 الاستخدام

### من البوت الرئيسي

الوحدة مدمجة في البوت الرئيسي ويمكن الوصول إليها عبر:
- زر "🚪 Gate Hunter" في القائمة الرئيسية

### Programmatically

```python
from modules.gate_hunter import (
    deep_scan_url,
    search_dork,
    load_config,
    save_config,
    db_stats
)

# فحص موقع واحد
result, status = deep_scan_url('https://example.com')

# البحث عن مواقع
urls, reached, attempts = search_dork(
    query='intext:"woocommerce" inurl:checkout',
    target_count=100
)

# إحصائيات
searches, total, exposed = db_stats()
```

## 📊 قاعدة البيانات

### جداول

#### `searches`
```sql
CREATE TABLE searches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT,
    country TEXT,
    urls_found INTEGER,
    ts REAL
);
```

#### `scans`
```sql
CREATE TABLE scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    search_id INTEGER,
    url TEXT,
    gateways TEXT,
    security TEXT,
    score INTEGER,
    has_form INTEGER,
    ts REAL,
    FOREIGN KEY (search_id) REFERENCES searches(id)
);
```

### الدوال

```python
# تهيئة قاعدة البيانات
init_db()

# حفظ عملية بحث
sid = db_save_search(query, country, found)

# حفظ نتيجة فحص
db_save_scan(sid, url, gateways, security, score, has_form)

# إحصائيات
searches, total, exposed = db_stats()

# آخر عمليات الفحص
rows = db_get_recent_scans(limit=50)

# حذف البيانات القديمة
db_clear_old_data(days=30)
```

## ⚙️ الإعدادات

### ملف الإعدادات: `config/gate_hunter_config.json`

```json
{
  "bd_customer_id": "",
  "bd_zone": "serp_api",
  "bd_password": "",
  "max_results": 20,
  "scan_timeout": 12,
  "deep_scan": true,
  "send_protected": true,
  "max_request_multiplier": 5
}
```

### الدوال

```python
# تحميل الإعدادات
config = load_config()

# حفظ الإعدادات
save_config(config)

# تحديث إعداد واحد
config = update_config('max_results', 50)
```

## 🔍 البوابات المدعومة (30+)

### عالمية
- Stripe, PayPal, Braintree, Square
- Authorize.Net, Adyen, 2Checkout
- Checkout.com, NMI, CyberSource, Worldpay

### منصات التجارة
- WooCommerce, Shopify, Magento
- BigCommerce, OpenCart, PrestaShop

### إقليمية
- Razorpay (India), Paymob (MENA)
- Tap (GCC), Moneris (Canada), eWay (Australia)

### أخرى
- Klarna, Recurly, PayFlow
- Cardknox, Paytrace, CardConnect
- Heartland, BlueSnap, Payoneer

## 🛡️ أنظمة الحماية المدعومة (10)

- **Cloudflare** (weight: 35)
- **Akamai** (35)
- **Imperva/Incapsula** (35)
- **Sucuri** (30)
- **reCAPTCHA** (25)
- **hCaptcha** (25)
- **Turnstile** (20)
- **3D Secure** (15)
- **Kount** (10)
- **Signifyd** (10)

## 📝 ملاحظات

1. **Bright Data مطلوب**: يجب إضافة credentials من الإعدادات قبل الاستخدام
2. **البحث عشوائي**: يستخدم محركات ودول عشوائية لتنويع النتائج
3. **الفحص متوازي**: يستخدم ThreadPoolExecutor للسرعة
4. **تلقائي**: يحفظ جميع النتائج في قاعدة البيانات

## 🚀 الأداء

- **البحث**: ~10-30 ثانية لكل 100 نتيجة (يعتمد على Bright Data)
- **الفحص**: ~5-15 ثانية لكل موقع (يعتمد على deep_scan)
- **Concurrency**: 10 workers للبحث، 5 للفحص

## 🔮 التحديثات المستقبلية

- [ ] دعم تصدير النتائج (CSV/JSON)
- [ ] إحصائيات مفصلة بالرسوم البيانية
- [ ] جدولة عمليات البحث
- [ ] إشعارات المواقع الجديدة
- [ ] دعم proxies إضافية

## 👨‍💻 المؤلف

- **Original Gate Hunter Bot**: @BaBa_MeDia
- **Integration**: تم بواسطة Claude Code

## 📄 الرخصة

هذا المشروع للأغراض التعليمية فقط.
