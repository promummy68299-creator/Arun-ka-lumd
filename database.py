import sqlite3
import datetime
from config import DB_NAME

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            joined_date TEXT
        )
    ''')
    
    # Plans table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            price TEXT,
            duration TEXT,
            group_link TEXT
        )
    ''')
    
    # Plan Assets table (Premium and Demo media links/file_ids)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS plan_assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id INTEGER,
            file_id TEXT,
            asset_type TEXT, -- 'premium' or 'demo'
            file_type TEXT,  -- 'video', 'photo', etc.
            FOREIGN KEY(plan_id) REFERENCES plans(id) ON DELETE CASCADE
        )
    ''')
    
    # Dynamic System Global Settings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS system_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    # Seed defaults if not present
    cursor.execute("INSERT OR IGNORE INTO system_settings (key, value) VALUES ('welcome_text', 'Welcome to our Premium VIP Hub! 🔥')")
    cursor.execute("INSERT OR IGNORE INTO system_settings (key, value) VALUES ('upi_id', '')")
    cursor.execute("INSERT OR IGNORE INTO system_settings (key, value) VALUES ('payee_name', 'Premium Bot Admin')")
    cursor.execute("INSERT OR IGNORE INTO system_settings (key, value) VALUES ('total_starts', '0')")
    
    conn.commit()
    conn.close()

def add_user(user_id, username, first_name):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    exists = cursor.fetchone()
    is_new = False
    if not exists:
        cursor.execute("INSERT INTO users (user_id, username, first_name, joined_date) VALUES (?, ?, ?, ?)",
                       (user_id, username, first_name, str(datetime.date.today())))
        is_new = True
    
    # Increment total starts metrics
    cursor.execute("SELECT value FROM system_settings WHERE key = 'total_starts'")
    starts = int(cursor.fetchone()[0])
    cursor.execute("UPDATE system_settings SET value = ? WHERE key = 'total_starts'", (str(starts + 1),))
    
    conn.commit()
    conn.close()
    return is_new

def get_all_users():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = [row[0] for row in cursor.fetchall()]
    conn.close()
    return users

def get_stats_data():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    
    today = str(datetime.date.today())
    cursor.execute("SELECT COUNT(*) FROM users WHERE joined_date = ?", (today,))
    today_users = cursor.fetchone()[0]
    
    week_ago = str(datetime.date.today() - datetime.timedelta(days=7))
    cursor.execute("SELECT COUNT(*) FROM users WHERE joined_date >= ?", (week_ago,))
    week_users = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM plans")
    total_plans = cursor.fetchone()[0]
    
    cursor.execute("SELECT value FROM system_settings WHERE key = 'total_starts'")
    total_starts = cursor.fetchone()[0]
    
    cursor.execute("SELECT value FROM system_settings WHERE key = 'last_broadcast'")
    last_bc_row = cursor.fetchone()
    last_bc = last_bc_row[0] if last_bc_row else "None Executed Yet"
    
    conn.close()
    return {
        "total_users": total_users,
        "today_users": today_users,
        "week_users": week_users,
        "total_plans": total_plans,
        "total_starts": total_starts,
        "last_broadcast": last_bc
    }

def get_setting(key):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM system_settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def set_setting(key, value):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO system_settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()

def db_add_plan(name, price, duration, group_link):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO plans (name, price, duration, group_link) VALUES (?, ?, ?, ?)",
                   (name, price, duration, group_link))
    plan_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return plan_id

def db_add_asset(plan_id, file_id, asset_type, file_type):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO plan_assets (plan_id, file_id, asset_type, file_type) VALUES (?, ?, ?, ?)",
                   (plan_id, file_id, asset_type, file_type))
    conn.commit()
    conn.close()

def db_get_plans():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, price, duration, group_link FROM plans")
    rows = cursor.fetchall()
    conn.close()
    return rows

def db_get_plan(plan_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, price, duration, group_link FROM plans WHERE id = ?", (plan_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def db_get_assets(plan_id, asset_type):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT file_id, file_type FROM plan_assets WHERE plan_id = ? AND asset_type = ?", (plan_id, asset_type))
    rows = cursor.fetchall()
    conn.close()
    return rows

def db_delete_plan(plan_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM plans WHERE id = ?", (plan_id,))
    cursor.execute("DELETE FROM plan_assets WHERE plan_id = ?", (plan_id,))
    conn.commit()
    conn.close()

def db_update_plan_field(plan_id, field, value):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(f"UPDATE plans SET {field} = ? WHERE id = ?", (value, plan_id))
    conn.commit()
    conn.close()

def db_clear_assets(plan_id, asset_type):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM plan_assets WHERE plan_id = ? AND asset_type = ?", (plan_id, asset_type))
    conn.commit()
    conn.close()
