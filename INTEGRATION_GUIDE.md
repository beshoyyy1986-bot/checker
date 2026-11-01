# 📘 Gate Hunter Integration Guide

## ✅ ما تم إنجازه

تم دمج بوت **Gate Hunter** بنجاح في المشروع الرئيسي **Checker Bot** كوحدة متكاملة داخل لوحة الأدمن.

---

## 🏗️ الهيكل الجديد

```
checker/
├── bot.py                          # البوت الرئيسي (محدث)
├── main.py                         # نقطة التشغيل
├── gate_cs.py                      # Playwright screenshots
├── requirements.txt                # محدث (beautifulsoup4 مضاف)
│
├── modules/                        # 📦 وحدات جديدة
│   ├── __init__.py
│   └── gate_hunter/                # 🎯 وحدة البوابة
│       ├── __init__.py
│       ├── signatures.py           # الثوابت (30 بوابة، 10 أنظمة حماية)
│       ├── config.py               # إدارة الإعدادات
│       ├── database.py             # عمليات قاعدة البيانات
│       ├── bright_data.py          # Bright Data SERP API
│       ├── scanner.py              # منطق الفحص العميق
│       ├── handlers.py             # Telegram Handlers
│       └── README.md               # توثيق الوحدة
│
├── config/                         # ⚙️ إعدادات
│   └── gate_hunter_config.json     # (يُنشأ تلقائياً)
│
├── data/                           # 📂 بيانات
│   ├── bot_database.db             # قاعدة بيانات البوت الرئيسي
│   └── gate_hunter.db              # قاعدة بيانات البوابة
│
└── gate_hunter_bot/                # ⚠️ قديم (يمكن حذفه)
    └── bot.py
```

---

## 🎯 التغييرات في bot.py

### 1. إضافة متغيرات State (السطر ~1615)

```python
# Gate Hunter State
gatehunter_user_state = {}   # {user_id: state_str}
gatehunter_user_data  = {}   # {user_id: temp_data}
```

### 2. إضافة زر البوابة في القائمة الرئيسية (السطر ~1727)

```python
def main_menu_kb(user_id=None):
    kb = types.InlineKeyboardMarkup(row_width=2)
    # ... الأزرار الأخرى ...
    
    # بوابة Gate Hunter
    kb.add(
        btn("🚪 Gate Hunter", STYLE_INFO, callback_data="gatehunter_main"),
    )
    
    # ... باقي الأزرار ...
    return kb
```

### 3. إضافة Message Handlers (السطر ~2138)

```python
@bot.message_handler(func=lambda m: gatehunter_user_state.get(m.from_user.id) in [
    'awaiting_query', 'awaiting_custom_num', 'awaiting_scan_confirm',
    'awaiting_bd_creds', 'awaiting_bd_zone', 'awaiting_def_num', 'awaiting_multiplier'
])
def handle_gatehunter_messages(message):
    # معالجة رسائل البوابة
    ...
```

### 4. إضافة Callback Handlers (السطر ~3183)

```python
@bot.callback_query_handler(func=lambda c: c.data.startswith('gatehunter_'))
def cb_gatehunter(call):
    # معالجة أزرار البوابة
    ...
```

### 5. تهيئة قاعدة البيانات عند البدء (السطر ~3873)

```python
def main():
    # تهيئة قاعدة بيانات البوابة
    from modules.gate_hunter.database import init_db as gatehunter_init_db
    gatehunter_init_db()
    
    # ... باقي الكود ...
```

---

## 🚀 كيفية الاستخدام

### للمستخدمين

1. **افتح البوت** في Telegram
2. **اضغط على** زر "🚪 Gate Hunter" في القائمة الرئيسية
3. **اختر** من القائمة:
   - 🔍 بحث جديد
   - 📋 دوركات جاهزة
   - 📊 الإحصائيات
   - ⚙️ الإعدادات

### للإداريين

#### إعداد Bright Data (مطلوب):

1. اضغط على ⚙️ الإعدادات
2. اضغط على 🔑 Bright Data Credentials
3. أرسل: `customer_id:password`
4. احفظ Zone Name

#### بدء البحث:

1. اضغط على 🔍 بحث جديد
2. اختر عدد النتائج (10-5000)
3. أرسل نص البحث أو Dork
4. أكد العملية
5. انتظر النتائج

---

## 📊 الميزات المدمجة

### ✅ بحث متقدم
- 5 محركات بحث (Google, Bing, Yahoo, DuckDuckGo, Yandex)
- 20 دولة (Geo-targeting عبر البروكسي)
- بحث متعدد الصفحات
- استخراج ذكي للروابط

### ✅ فحص عميق
- 30+ بوابة دفع
- 10 أنظمة حماية
- مستويات ثقة (Confirmed/Strong/Weak)
- فحص API endpoints للمنصات

### ✅ إعدادات قابلة للتخصيص
- عدد النتائج الافتراضي
- سقف محاولات البحث
- تفعيل/تعطيل الفحص العميق
- إظهار/إخفاء المواقع المحمية

### ✅ إحصائيات مفصلة
- عدد عمليات البحث
- عدد المواقع المفحوصة
- عدد المواقع المكشوفة/المحمية

---

## 🔧 الصيانة والتحديث

### إضافة بوابة دفع جديدة

عدل `modules/gate_hunter/signatures.py`:

```python
PAYMENT_GATEWAYS = [
    # ... البوابات الموجودة ...
    ("NewGateway", r'newgateway(?:\.com|\.js)'),
]
```

### إضافة نظام حماية جديد

عدل `modules/gate_hunter/signatures.py`:

```python
SECURITY_SIGNATURES = {
    # ... الأنظمة الموجودة ...
    'NewSecurity': {
        'headers_keys': {'x-new-security'},
        'server_match': 'newsecurity',
        'html_patterns': [r'newsecurity\.com'],
        'weight': 25,
    },
}
```

### تعديل الإعدادات الافتراضية

عدل `modules/gate_hunter/config.py`:

```python
_DEFAULT_CONFIG = {
    'bd_customer_id': '',
    'bd_zone': 'serp_api',
    'bd_password': '',
    'max_results': 50,  # غير الرقم هنا
    # ...
}
```

---

## 🐛 حل المشاكل

### ❌ "Bright Data غير مُهيأ"

**الحل:**
1. افتح الإعدادات
2. أضف Bright Data Credentials
3. تأكد من صحة البيانات

### ❌ "لم يتم العثور على نتائج"

**الحل:**
1. جرب دورك مختلف
2. زد عدد النتائج
3. تأكد من اتصال Bright Data

### ❌ "فشل الفحص"

**الحل:**
1. تحقق من رابط الموقع
2. جرب مع/بدون deep_scan
3. انتظر قليلاً وأعد المحاولة

---

## 📝 ملاحظات مهمة

### ⚠️ الأداء
- **البحث**: 10-30 ثانية لكل 100 نتيجة
- **الفحص**: 5-15 ثانية لكل موقع
- **الـ Concurrency**: 10 workers للبحث، 5 للفحص

### ⚠️ الاستخدام
- يتطلب Bright Data credentials
- يستخدم proxies عبر Bright Data
- يحفظ جميع النتائج في قاعدة البيانات

### ⚠️ الحدود
- الحد الأقصى للنتائج: 5000
- Timeout للفحص: 12 ثانية (قابل للتعديل)
- المحاولات القصوى: target × multiplier

---

## 🔄 التحديثات المستقبلية

- [ ] تصدير النتائج (CSV/JSON)
- [ ] إحصائيات بالرسوم البيانية
- [ ] جدولة عمليات البحث
- [ ] إشعارات المواقع الجديدة
- [ ] دعم proxies إضافية

---

## 🗑️ حذف البوت القديم

بعد التأكد من أن كل شيء يعمل بشكل صحيح، يمكنك حذف:

```bash
rm -rf gate_hunter_bot/
```

---

## 👨‍💻 الدعم

للمشاكل أو الاستفسارات:
- راجع التوثيق في `modules/gate_hunter/README.md`
- تحقق من السجلات (logs) في وحدة التحكم

---

## ✅ اختبار التكامل

لاختبار أن كل شيء يعمل:

```bash
# 1. استيراد الوحدة
python -c "from modules.gate_hunter import deep_scan_url; print('✅ OK')"

# 2. تشغيل البوت
python bot.py

# 3. في Telegram، اضغط على 🚪 Gate Hunter
```

---

**تم التكامل بنجاح! 🎉**
