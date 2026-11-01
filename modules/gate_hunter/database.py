"""
Gate Hunter Database Operations
"""
import os
import sqlite3
import time

# مسار قاعدة البيانات
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')
DB_FILE = os.path.join(DATA_DIR, 'gate_hunter.db')

def init_db():
    """إنشاء جداول قاعدة البيانات"""
    os.makedirs(DATA_DIR, exist_ok=True)
    con = sqlite3.connect(DB_FILE)
    con.executescript('''
        CREATE TABLE IF NOT EXISTS searches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT,
            country TEXT,
            urls_found INTEGER,
            ts REAL
        );

        CREATE TABLE IF NOT EXISTS scans (
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
    ''')
    con.commit()
    con.close()

def db_save_search(query, country, found):
    """حفظ عملية بحث"""
    os.makedirs(DATA_DIR, exist_ok=True)
    con = sqlite3.connect(DB_FILE)
    cur = con.execute(
        'INSERT INTO searches (query, country, urls_found, ts) VALUES (?, ?, ?, ?)',
        (query, country, found, time.time())
    )
    sid = cur.lastrowid
    con.commit()
    con.close()
    return sid

def db_save_scan(sid, url, gateways, security, score, has_form):
    """حفظ نتيجة فحص"""
    os.makedirs(DATA_DIR, exist_ok=True)
    con = sqlite3.connect(DB_FILE)
    con.execute(
        'INSERT INTO scans (search_id, url, gateways, security, score, has_form, ts) VALUES (?, ?, ?, ?, ?, ?, ?)',
        (sid, url, ','.join(gateways), ','.join(security), score, int(has_form), time.time())
    )
    con.commit()
    con.close()

def db_stats():
    """إحصائيات قاعدة البيانات"""
    os.makedirs(DATA_DIR, exist_ok=True)
    con = sqlite3.connect(DB_FILE)

    searches = con.execute('SELECT COUNT(*) FROM searches').fetchone()[0]
    total_sites = con.execute('SELECT COUNT(*) FROM scans').fetchone()[0]
    exposed = con.execute('SELECT COUNT(*) FROM scans WHERE score = 0').fetchone()[0]

    con.close()
    return searches, total_sites, exposed

def db_get_recent_scans(limit=50):
    """الحصول على آخر عمليات الفحص"""
    os.makedirs(DATA_DIR, exist_ok=True)
    con = sqlite3.connect(DB_FILE)

    rows = con.execute('''
        SELECT s.url, s.gateways, s.security, s.score, s.has_form, s.ts, sr.query
        FROM scans s
        JOIN searches sr ON s.search_id = sr.id
        ORDER BY s.ts DESC
        LIMIT ?
    ''', (limit,)).fetchall()

    con.close()
    return rows

def db_clear_old_data(days=30):
    """حذف البيانات القديمة"""
    os.makedirs(DATA_DIR, exist_ok=True)
    con = sqlite3.connect(DB_FILE)

    cutoff = time.time() - (days * 24 * 60 * 60)

    con.execute('DELETE FROM scans WHERE ts < ?', (cutoff,))
    con.execute('DELETE FROM searches WHERE ts < ?', (cutoff,))

    con.commit()
    con.close()
