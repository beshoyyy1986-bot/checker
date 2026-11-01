"""
Gate Hunter Configuration Manager
"""
import os
import json

# مسار ملف الإعدادات
CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config')
CONFIG_FILE = os.path.join(CONFIG_DIR, 'gate_hunter_config.json')

# الإعدادات الافتراضية
_DEFAULT_CONFIG = {
    'bd_customer_id':          '',
    'bd_zone':                 'serp_api',
    'bd_password':             '',
    'max_results':             20,
    'scan_timeout':            12,
    'deep_scan':                True,
    'send_protected':          True,
    'max_request_multiplier':  5,
}

def load_config():
    """تحميل الإعدادات"""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return {**_DEFAULT_CONFIG, **json.load(f)}
    return dict(_DEFAULT_CONFIG)

def save_config(config):
    """حفظ الإعدادات"""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

def get_config():
    """الحصول على الإعدادات الحالية"""
    return load_config()

def update_config(key, value):
    """تحديث إعداد واحد"""
    config = load_config()
    config[key] = value
    save_config(config)
    return config
