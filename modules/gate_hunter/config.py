"""
Gate Hunter Configuration Manager
"""
import os
import json

# مسار ملف الإعدادات - يستخدم DATA_DIR من البيئة
DATA_DIR = os.environ.get('DATA_DIR', os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
CONFIG_FILE = os.path.join(DATA_DIR, 'gate_hunter_config.json')

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
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return {**_DEFAULT_CONFIG, **json.load(f)}
        except Exception:
            pass
    return dict(_DEFAULT_CONFIG)

def save_config(config):
    """حفظ الإعدادات"""
    try:
        # تأكد من وجود المجلد
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False

def get_config():
    """الحصول على الإعدادات الحالية"""
    return load_config()

def update_config(key, value):
    """تحديث إعداد واحد"""
    config = load_config()
    config[key] = value
    save_config(config)
    return config
