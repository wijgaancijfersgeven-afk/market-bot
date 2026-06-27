import os
import sqlite3
import random
import string
from datetime import datetime, timedelta

DB_PATH = os.getenv("DB_PATH", "market.db")
FOUNDER_ID = 8254024103


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER UNIQUE NOT NULL,
        added_by INTEGER NOT NULL,
        added_at TIMESTAMP DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS pending_actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        action_type TEXT NOT NULL,
        requested_by INTEGER NOT NULL,
        target_id INTEGER,
        extra_data TEXT,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER UNIQUE NOT NULL,
        username TEXT,
        first_name TEXT NOT NULL,
        last_name TEXT,
        balance INTEGER DEFAULT 0,
        is_vip INTEGER DEFAULT 0,
        is_banned INTEGER DEFAULT 0,
        referral_code TEXT UNIQUE NOT NULL,
        referred_by INTEGER,
        referral_count INTEGER DEFAULT 0,
        total_spent INTEGER DEFAULT 0,
        last_daily_bonus TIMESTAMP,
        created_at TIMESTAMP DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        emoji TEXT DEFAULT '🛒',
        description TEXT,
        is_vip_only INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        sort_order INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        description TEXT,
        price INTEGER NOT NULL,
        stock INTEGER DEFAULT -1,
        content TEXT,
        is_vip_only INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        sold_count INTEGER DEFAULT 0,
        sort_order INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        product_name TEXT NOT NULL,
        quantity INTEGER DEFAULT 1,
        total_price INTEGER NOT NULL,
        status TEXT DEFAULT 'pending',
        delivered_content TEXT,
        note TEXT,
        created_at TIMESTAMP DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS coupons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        value INTEGER NOT NULL,
        max_uses INTEGER DEFAULT 1,
        used_count INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        expires_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS coupon_usages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        coupon_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        used_at TIMESTAMP DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_user_id INTEGER,
        to_user_id INTEGER NOT NULL,
        amount INTEGER NOT NULL,
        type TEXT NOT NULL,
        description TEXT,
        created_at TIMESTAMP DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS giveaways (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        prize TEXT NOT NULL,
        prize_amount INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        end_at TIMESTAMP NOT NULL,
        winner_id INTEGER,
        created_at TIMESTAMP DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS giveaway_participants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        giveaway_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        joined_at TIMESTAMP DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS support_tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        subject TEXT NOT NULL,
        message TEXT NOT NULL,
        status TEXT DEFAULT 'open',
        admin_reply TEXT,
        created_at TIMESTAMP DEFAULT (datetime('now'))
    );
    """)
    conn.commit()
    conn.close()
    print("✅ Veritabanı hazır.")


def _row(cursor):
    row = cursor.fetchone()
    return dict(row) if row else None


def _rows(cursor):
    return [dict(r) for r in cursor.fetchall()]


# ─── Yetki Sistemi ────────────────────────────────────────

def is_founder(telegram_id):
    return int(telegram_id) == FOUNDER_ID


def is_admin(telegram_id):
    if is_founder(telegram_id):
        return True
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id FROM admins WHERE telegram_id = ?", (int(telegram_id),))
    row = c.fetchone()
    conn.close()
    return row is not None


def get_admins():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT telegram_id, added_by, added_at FROM admins ORDER BY added_at")
    rows = _rows(c)
    conn.close()
    return rows


def add_admin(telegram_id, added_by):
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO admins (telegram_id, added_by) VALUES (?, ?)", (int(telegram_id), int(added_by)))
        conn.commit()
        result = True
    except sqlite3.IntegrityError:
        result = False
    conn.close()
    return result


def remove_admin(telegram_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM admins WHERE telegram_id = ?", (int(telegram_id),))
    conn.commit()
    conn.close()


# ─── Onay Bekleyen İşlemler ──────────────────────────────

def create_pending_action(action_type, requested_by, target_id=None, extra_data=None):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO pending_actions (action_type, requested_by, target_id, extra_data) VALUES (?, ?, ?, ?)",
        (action_type, int(requested_by), target_id, extra_data)
    )
    conn.commit()
    action_id = c.lastrowid
    conn.close()
    return action_id


def get_pending_action(action_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM pending_actions WHERE id = ?", (action_id,))
    row = _row(c)
    conn.close()
    return row


def resolve_pending_action(action_id, status):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE pending_actions SET status = ? WHERE id = ?", (status, action_id))
    conn.commit()
    conn.close()


def get_pending_actions_list():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM pending_actions WHERE status = 'pending' ORDER BY created_at DESC")
    rows = _rows(c)
    conn.close()
    return rows


# ─── Kanallar ─────────────────────────────────────────────

def get_all_channels():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key LIKE 'channel_%'")
    rows = [r["value"] for r in c.fetchall()]
    conn.close()
    return rows


def add_channel(channel):
    key = f"channel_{channel.lstrip('@').lower()}"
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, channel))
    conn.commit()
    conn.close()


def remove_channel(channel):
    key = f"channel_{channel.lstrip('@').lower()}"
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM settings WHERE key = ?", (key,))
    conn.commit()
    conn.close()


# ─── Ayarlar ──────────────────────────────────────────────

def get_setting(key, default=None):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = c.fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(key, value):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()


def delete_setting(key):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM settings WHERE key = ?", (key,))
    conn.commit()
    conn.close()


# ─── Kullanıcı ────────────────────────────────────────────

def _gen_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))


def get_or_create_user(telegram_id, first_name, username=None, last_name=None, referral_code=None):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
    user = _row(c)
    if user:
        conn.close()
        return user, False

    code = _gen_code()
    while True:
        c.execute("SELECT id FROM users WHERE referral_code = ?", (code,))
        if not c.fetchone():
            break
        code = _gen_code()

    referred_by = None
    if referral_code:
        c.execute("SELECT * FROM users WHERE referral_code = ? AND telegram_id != ?", (referral_code, telegram_id))
        referrer = _row(c)
        if referrer:
            referred_by = referrer["id"]
            new_count = referrer["referral_count"] + 1
            new_vip = 1 if new_count >= 20 else referrer["is_vip"]
            c.execute("UPDATE users SET balance = balance + 50, referral_count = ?, is_vip = ? WHERE id = ?",
                      (new_count, new_vip, referrer["id"]))
            c.execute("INSERT INTO transactions (to_user_id, amount, type, description) VALUES (?, 50, 'referral_bonus', ?)",
                      (referrer["id"], f"Referans bonusu — {first_name}"))

    c.execute("""INSERT INTO users (telegram_id, first_name, last_name, username, referral_code, referred_by)
                 VALUES (?, ?, ?, ?, ?, ?)""",
              (telegram_id, first_name, last_name, username, code, referred_by))
    conn.commit()
    c.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
    new_user = _row(c)
    conn.close()
    return new_user, True


def get_user(telegram_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
    u = _row(c)
    conn.close()
    return u


def get_user_by_id(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    u = _row(c)
    conn.close()
    return u


def add_balance(user_id, amount, tx_type, description):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (amount, user_id))
    c.execute("INSERT INTO transactions (to_user_id, amount, type, description) VALUES (?, ?, ?, ?)",
              (user_id, amount, tx_type, description))
    c.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
    bal = c.fetchone()[0]
    conn.commit()
    conn.close()
    return bal


def deduct_balance(user_id, amount, tx_type, description):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
    row = c.fetchone()
    if not row or row[0] < amount:
        conn.close()
        raise ValueError("Yetersiz bakiye")
    c.execute("UPDATE users SET balance = balance - ?, total_spent = total_spent + ? WHERE id = ?",
              (amount, amount, user_id))
    c.execute("INSERT INTO transactions (from_user_id, to_user_id, amount, type, description) VALUES (?, ?, ?, ?, ?)",
              (user_id, user_id, -amount, tx_type, description))
    conn.commit()
    conn.close()


def transfer_points(from_id, to_id, amount):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE id = ?", (from_id,))
    row = c.fetchone()
    if not row or row[0] < amount:
        conn.close()
        raise ValueError("Yetersiz bakiye")
    c.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (amount, from_id))
    c.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (amount, to_id))
    c.execute("INSERT INTO transactions (from_user_id, to_user_id, amount, type, description) VALUES (?, ?, ?, 'transfer', 'Puan transferi')",
              (from_id, to_id, amount))
    conn.commit()
    conn.close()


def claim_daily_bonus(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT balance, is_vip, last_daily_bonus FROM users WHERE id = ?", (user_id,))
    user = c.fetchone()
    now = datetime.now()
    if user[2]:
        last = datetime.fromisoformat(user[2])
        diff = now - last
        if diff.total_seconds() < 86400:
            remaining = timedelta(seconds=86400) - diff
            h = int(remaining.total_seconds() // 3600)
            m = int((remaining.total_seconds() % 3600) // 60)
            conn.close()
            return {"success": False, "hours": h, "minutes": m}
    base = 75 if user[1] else 25
    bonus = base + random.randint(0, 25)
    c.execute("UPDATE users SET balance = balance + ?, last_daily_bonus = ? WHERE id = ?",
              (bonus, now.isoformat(), user_id))
    c.execute("INSERT INTO transactions (to_user_id, amount, type, description) VALUES (?, ?, 'daily_bonus', 'Günlük bonus')",
              (user_id, bonus))
    c.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
    new_bal = c.fetchone()[0]
    conn.commit()
    conn.close()
    return {"success": True, "amount": bonus, "new_balance": new_bal}


def make_vip(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE users SET is_vip = 1 WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()


def ban_user(user_id, banned=True):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE users SET is_banned = ? WHERE id = ?", (1 if banned else 0, user_id))
    conn.commit()
    conn.close()


def get_all_users():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT telegram_id FROM users WHERE is_banned = 0")
    users = [r[0] for r in c.fetchall()]
    conn.close()
    return users


def get_stats():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users"); total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE is_vip = 1"); vip = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE is_banned = 1"); banned = c.fetchone()[0]
    c.execute("SELECT COALESCE(SUM(balance), 0) FROM users"); total_bal = c.fetchone()[0]
    conn.close()
    return {"total_users": total, "vip_users": vip, "banned_users": banned, "total_balance": total_bal}


# ─── Kategoriler & Ürünler ────────────────────────────────

def get_categories(is_vip=False):
    conn = get_conn()
    c = conn.cursor()
    if is_vip:
        c.execute("SELECT * FROM categories WHERE is_active = 1 ORDER BY sort_order")
    else:
        c.execute("SELECT * FROM categories WHERE is_active = 1 AND is_vip_only = 0 ORDER BY sort_order")
    cats = _rows(c)
    conn.close()
    return cats


def get_products(category_id, is_vip=False):
    conn = get_conn()
    c = conn.cursor()
    if is_vip:
        c.execute("SELECT * FROM products WHERE category_id = ? AND is_active = 1 ORDER BY sort_order", (category_id,))
    else:
        c.execute("SELECT * FROM products WHERE category_id = ? AND is_active = 1 AND is_vip_only = 0 ORDER BY sort_order", (category_id,))
    products = _rows(c)
    conn.close()
    return products


def get_product(product_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    r = _row(c)
    conn.close()
    return r


def add_category(name, emoji, is_vip_only=False):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO categories (name, emoji, is_vip_only) VALUES (?, ?, ?)", (name, emoji, 1 if is_vip_only else 0))
    conn.commit()
    conn.close()


def get_all_products():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM products ORDER BY category_id, sort_order")
    products = _rows(c)
    conn.close()
    return products


def delete_product(product_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()


def toggle_product_active(product_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE products SET is_active = NOT is_active WHERE id = ?", (product_id,))
    conn.commit()
    c.execute("SELECT is_active FROM products WHERE id = ?", (product_id,))
    row = c.fetchone()
    conn.close()
    return bool(row[0]) if row else False


def update_product_stock(product_id, stock):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE products SET stock = ? WHERE id = ?", (stock, product_id))
    conn.commit()
    conn.close()


def get_all_categories():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM categories ORDER BY sort_order")
    cats = _rows(c)
    conn.close()
    return cats


def delete_category(category_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM products WHERE category_id = ?", (category_id,))
    c.execute("DELETE FROM categories WHERE id = ?", (category_id,))
    conn.commit()
    conn.close()


def toggle_category_active(category_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE categories SET is_active = NOT is_active WHERE id = ?", (category_id,))
    conn.commit()
    c.execute("SELECT is_active FROM categories WHERE id = ?", (category_id,))
    row = c.fetchone()
    conn.close()
    return bool(row[0]) if row else False


def add_product(name, category_id, price, stock, description, content, is_vip_only):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO products (name, category_id, price, stock, description, content, is_vip_only) VALUES (?, ?, ?, ?, ?, ?, ?)",
              (name, category_id, price, stock, description or None, content or None, 1 if is_vip_only else 0))
    conn.commit()
    conn.close()


# ─── Siparişler ────────────────────────────────────────────

def create_order(user_id, product):
    if product["stock"] == 0:
        raise ValueError("out_of_stock")
    conn = get_conn()
    c = conn.cursor()
    status = "completed" if product["content"] else "pending"
    c.execute("""INSERT INTO orders (user_id, product_id, product_name, total_price, status, delivered_content)
                 VALUES (?, ?, ?, ?, ?, ?)""",
              (user_id, product["id"], product["name"], product["price"], status, product["content"]))
    conn.commit()
    order_id = c.lastrowid
    if product["stock"] > 0:
        c.execute("UPDATE products SET stock = stock - 1, sold_count = sold_count + 1 WHERE id = ?", (product["id"],))
    else:
        c.execute("UPDATE products SET sold_count = sold_count + 1 WHERE id = ?", (product["id"],))
    conn.commit()
    c.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    order = _row(c)
    conn.close()
    return order


def get_user_orders(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC LIMIT 20", (user_id,))
    orders = _rows(c)
    conn.close()
    return orders


def get_order(order_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    r = _row(c)
    conn.close()
    return r


def get_pending_orders():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM orders WHERE status = 'pending' ORDER BY created_at DESC")
    orders = _rows(c)
    conn.close()
    return orders


def complete_order(order_id, content):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE orders SET status = 'completed', delivered_content = ? WHERE id = ?", (content, order_id))
    conn.commit()
    conn.close()


def get_order_stats():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*), COALESCE(SUM(total_price), 0) FROM orders")
    row = c.fetchone()
    c.execute("SELECT COUNT(*) FROM orders WHERE status = 'pending'")
    pending = c.fetchone()[0]
    conn.close()
    return {"total": row[0], "revenue": row[1], "pending": pending}


# ─── Kuponlar ─────────────────────────────────────────────

def use_coupon(code, user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM coupons WHERE code = ? AND is_active = 1", (code.upper(),))
    coupon = _row(c)
    if not coupon:
        conn.close()
        return {"success": False, "error": "Geçersiz kupon kodu!"}
    if coupon["expires_at"] and datetime.fromisoformat(coupon["expires_at"]) < datetime.now():
        conn.close()
        return {"success": False, "error": "Kupon kodunun süresi dolmuş!"}
    if coupon["used_count"] >= coupon["max_uses"]:
        conn.close()
        return {"success": False, "error": "Bu kupon kodu tükenmiş!"}
    c.execute("SELECT id FROM coupon_usages WHERE coupon_id = ? AND user_id = ?", (coupon["id"], user_id))
    if c.fetchone():
        conn.close()
        return {"success": False, "error": "Bu kuponu daha önce kullandınız!"}
    c.execute("UPDATE coupons SET used_count = used_count + 1 WHERE id = ?", (coupon["id"],))
    c.execute("INSERT INTO coupon_usages (coupon_id, user_id) VALUES (?, ?)", (coupon["id"], user_id))
    conn.commit()
    conn.close()
    return {"success": True, "amount": coupon["value"]}


def create_coupon(code, value, max_uses):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO coupons (code, value, max_uses) VALUES (?, ?, ?)", (code.upper(), value, max_uses))
    conn.commit()
    conn.close()


# ─── Çekiliş ─────────────────────────────────────────────

def get_active_giveaway():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM giveaways WHERE is_active = 1 AND end_at > datetime('now') ORDER BY created_at DESC LIMIT 1")
    r = _row(c)
    conn.close()
    return r


def join_giveaway(giveaway_id, user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id FROM giveaway_participants WHERE giveaway_id = ? AND user_id = ?", (giveaway_id, user_id))
    if c.fetchone():
        conn.close()
        return False
    c.execute("INSERT INTO giveaway_participants (giveaway_id, user_id) VALUES (?, ?)", (giveaway_id, user_id))
    conn.commit()
    conn.close()
    return True


def create_giveaway(title, prize, prize_amount, end_hours):
    end_at = (datetime.now() + timedelta(hours=end_hours)).isoformat()
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO giveaways (title, prize, prize_amount, end_at) VALUES (?, ?, ?, ?)",
              (title, prize, prize_amount, end_at))
    conn.commit()
    conn.close()


# ─── Destek ───────────────────────────────────────────────

def create_ticket(user_id, subject, message):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO support_tickets (user_id, subject, message) VALUES (?, ?, ?)", (user_id, subject, message))
    conn.commit()
    conn.close()


def get_open_tickets():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM support_tickets WHERE status = 'open' ORDER BY created_at DESC LIMIT 10")
    tickets = _rows(c)
    conn.close()
    return tickets


def close_ticket(ticket_id, reply=None):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE support_tickets SET status = 'closed', admin_reply = ? WHERE id = ?", (reply, ticket_id))
    conn.commit()
    conn.close()


def get_ticket_by_id(ticket_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM support_tickets WHERE id = ?", (ticket_id,))
    r = _row(c)
    conn.close()
    return r
