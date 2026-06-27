import sqlite3
import random
import string
from datetime import datetime, timedelta

DB_PATH = "bot.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
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
        last_daily_bonus TEXT,
        created_at TEXT DEFAULT (datetime('now'))
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
        created_at TEXT DEFAULT (datetime('now'))
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
        created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS coupons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        value INTEGER NOT NULL,
        max_uses INTEGER DEFAULT 1,
        used_count INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        expires_at TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS coupon_usages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        coupon_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        used_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_user_id INTEGER,
        to_user_id INTEGER NOT NULL,
        amount INTEGER NOT NULL,
        type TEXT NOT NULL,
        description TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS giveaways (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        prize TEXT NOT NULL,
        prize_amount INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        end_at TEXT NOT NULL,
        winner_id INTEGER,
        created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS giveaway_participants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        giveaway_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        joined_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS support_tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        subject TEXT NOT NULL,
        message TEXT NOT NULL,
        status TEXT DEFAULT 'open',
        admin_reply TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    );
    """)
    conn.commit()
    conn.close()
    print("✅ Veritabanı hazır.")


# ─── Ayarlar ──────────────────────────────────────────────

def get_setting(key, default=None):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = c.fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(key, value):
    conn = get_conn()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", (key, value))
    conn.commit()
    conn.close()


def delete_setting(key):
    conn = get_conn()
    conn.execute("DELETE FROM settings WHERE key=?", (key,))
    conn.commit()
    conn.close()


# ─── Kullanıcı ────────────────────────────────────────────

def _gen_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))


def get_or_create_user(telegram_id, first_name, username=None, last_name=None, referral_code=None):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,))
    user = c.fetchone()
    if user:
        conn.close()
        return dict(user), False  # (user, is_new)

    code = _gen_code()
    while True:
        c.execute("SELECT id FROM users WHERE referral_code=?", (code,))
        if not c.fetchone():
            break
        code = _gen_code()

    referred_by = None
    if referral_code:
        c.execute("SELECT * FROM users WHERE referral_code=? AND telegram_id!=?", (referral_code, telegram_id))
        referrer = c.fetchone()
        if referrer:
            referred_by = referrer["id"]
            new_count = referrer["referral_count"] + 1
            new_vip = 1 if new_count >= 20 else referrer["is_vip"]
            c.execute("UPDATE users SET balance=balance+50, referral_count=?, is_vip=? WHERE id=?",
                      (new_count, new_vip, referrer["id"]))
            c.execute("INSERT INTO transactions (to_user_id, amount, type, description) VALUES (?,50,'referral_bonus',?)",
                      (referrer["id"], f"Referans bonusu — {first_name}"))

    c.execute("""INSERT INTO users (telegram_id, first_name, last_name, username, referral_code, referred_by)
                 VALUES (?,?,?,?,?,?)""", (telegram_id, first_name, last_name, username, code, referred_by))
    conn.commit()
    c.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,))
    new_user = dict(c.fetchone())
    conn.close()
    return new_user, True


def get_user(telegram_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,))
    u = c.fetchone()
    conn.close()
    return dict(u) if u else None


def get_user_by_id(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id=?", (user_id,))
    u = c.fetchone()
    conn.close()
    return dict(u) if u else None


def add_balance(user_id, amount, tx_type, description):
    conn = get_conn()
    conn.execute("UPDATE users SET balance=balance+? WHERE id=?", (amount, user_id))
    conn.execute("INSERT INTO transactions (to_user_id, amount, type, description) VALUES (?,?,?,?)",
                 (user_id, amount, tx_type, description))
    conn.commit()
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE id=?", (user_id,))
    bal = c.fetchone()["balance"]
    conn.close()
    return bal


def deduct_balance(user_id, amount, tx_type, description):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE id=?", (user_id,))
    row = c.fetchone()
    if not row or row["balance"] < amount:
        conn.close()
        raise ValueError("Yetersiz bakiye")
    conn.execute("UPDATE users SET balance=balance-?, total_spent=total_spent+? WHERE id=?", (amount, amount, user_id))
    conn.execute("INSERT INTO transactions (from_user_id, to_user_id, amount, type, description) VALUES (?,?,?,?,?)",
                 (user_id, user_id, -amount, tx_type, description))
    conn.commit()
    conn.close()


def transfer_points(from_id, to_id, amount):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE id=?", (from_id,))
    row = c.fetchone()
    if not row or row["balance"] < amount:
        conn.close()
        raise ValueError("Yetersiz bakiye")
    conn.execute("UPDATE users SET balance=balance-? WHERE id=?", (amount, from_id))
    conn.execute("UPDATE users SET balance=balance+? WHERE id=?", (amount, to_id))
    conn.execute("INSERT INTO transactions (from_user_id, to_user_id, amount, type, description) VALUES (?,?,?,'transfer','Puan transferi')",
                 (from_id, to_id, amount))
    conn.commit()
    conn.close()


def claim_daily_bonus(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT balance, is_vip, last_daily_bonus FROM users WHERE id=?", (user_id,))
    user = c.fetchone()
    now = datetime.now()
    if user["last_daily_bonus"]:
        last = datetime.fromisoformat(user["last_daily_bonus"])
        diff = now - last
        if diff.total_seconds() < 86400:
            remaining = timedelta(seconds=86400) - diff
            h = int(remaining.total_seconds() // 3600)
            m = int((remaining.total_seconds() % 3600) // 60)
            conn.close()
            return {"success": False, "hours": h, "minutes": m}
    base = 75 if user["is_vip"] else 25
    bonus = base + random.randint(0, 25)
    conn.execute("UPDATE users SET balance=balance+?, last_daily_bonus=? WHERE id=?", (bonus, now.isoformat(), user_id))
    conn.execute("INSERT INTO transactions (to_user_id, amount, type, description) VALUES (?,?,'daily_bonus','Günlük bonus')",
                 (user_id, bonus))
    conn.commit()
    c.execute("SELECT balance FROM users WHERE id=?", (user_id,))
    new_bal = c.fetchone()["balance"]
    conn.close()
    return {"success": True, "amount": bonus, "new_balance": new_bal}


def make_vip(user_id):
    conn = get_conn()
    conn.execute("UPDATE users SET is_vip=1 WHERE id=?", (user_id,))
    conn.commit()
    conn.close()


def ban_user(user_id, banned=True):
    conn = get_conn()
    conn.execute("UPDATE users SET is_banned=? WHERE id=?", (1 if banned else 0, user_id))
    conn.commit()
    conn.close()


def get_all_users():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT telegram_id FROM users WHERE is_banned=0")
    users = [row["telegram_id"] for row in c.fetchall()]
    conn.close()
    return users


def get_stats():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) as t FROM users")
    total = c.fetchone()["t"]
    c.execute("SELECT COUNT(*) as v FROM users WHERE is_vip=1")
    vip = c.fetchone()["v"]
    c.execute("SELECT COUNT(*) as b FROM users WHERE is_banned=1")
    banned = c.fetchone()["b"]
    c.execute("SELECT COALESCE(SUM(balance),0) as s FROM users")
    total_bal = c.fetchone()["s"]
    conn.close()
    return {"total_users": total, "vip_users": vip, "banned_users": banned, "total_balance": total_bal}


# ─── Kategoriler & Ürünler ────────────────────────────────

def get_categories(is_vip=False):
    conn = get_conn()
    c = conn.cursor()
    query = "SELECT * FROM categories WHERE is_active=1" + ("" if is_vip else " AND is_vip_only=0") + " ORDER BY sort_order"
    c.execute(query)
    cats = [dict(r) for r in c.fetchall()]
    conn.close()
    return cats


def get_products(category_id, is_vip=False):
    conn = get_conn()
    c = conn.cursor()
    query = "SELECT * FROM products WHERE category_id=? AND is_active=1" + ("" if is_vip else " AND is_vip_only=0") + " ORDER BY sort_order"
    c.execute(query, (category_id,))
    products = [dict(r) for r in c.fetchall()]
    conn.close()
    return products


def get_product(product_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM products WHERE id=?", (product_id,))
    r = c.fetchone()
    conn.close()
    return dict(r) if r else None


def add_category(name, emoji, is_vip_only=False):
    conn = get_conn()
    conn.execute("INSERT INTO categories (name, emoji, is_vip_only) VALUES (?,?,?)", (name, emoji, 1 if is_vip_only else 0))
    conn.commit()
    conn.close()


def add_product(name, category_id, price, stock, description, content, is_vip_only):
    conn = get_conn()
    conn.execute("INSERT INTO products (name, category_id, price, stock, description, content, is_vip_only) VALUES (?,?,?,?,?,?,?)",
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
    c.execute("INSERT INTO orders (user_id, product_id, product_name, total_price, status, delivered_content) VALUES (?,?,?,?,?,?)",
              (user_id, product["id"], product["name"], product["price"], status, product["content"]))
    order_id = c.lastrowid
    if product["stock"] > 0:
        conn.execute("UPDATE products SET stock=stock-1, sold_count=sold_count+1 WHERE id=?", (product["id"],))
    else:
        conn.execute("UPDATE products SET sold_count=sold_count+1 WHERE id=?", (product["id"],))
    conn.commit()
    c.execute("SELECT * FROM orders WHERE id=?", (order_id,))
    order = dict(c.fetchone())
    conn.close()
    return order


def get_user_orders(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM orders WHERE user_id=? ORDER BY created_at DESC LIMIT 20", (user_id,))
    orders = [dict(r) for r in c.fetchall()]
    conn.close()
    return orders


def get_order(order_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM orders WHERE id=?", (order_id,))
    r = c.fetchone()
    conn.close()
    return dict(r) if r else None


def get_pending_orders():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM orders WHERE status='pending' ORDER BY created_at DESC")
    orders = [dict(r) for r in c.fetchall()]
    conn.close()
    return orders


def complete_order(order_id, content):
    conn = get_conn()
    conn.execute("UPDATE orders SET status='completed', delivered_content=? WHERE id=?", (content, order_id))
    conn.commit()
    conn.close()


def get_order_stats():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) as total, COALESCE(SUM(total_price),0) as revenue FROM orders")
    row = dict(c.fetchone())
    c.execute("SELECT COUNT(*) as pending FROM orders WHERE status='pending'")
    pending = c.fetchone()["pending"]
    conn.close()
    return {"total": row["total"], "revenue": row["revenue"], "pending": pending}


# ─── Kuponlar ─────────────────────────────────────────────

def use_coupon(code, user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM coupons WHERE code=? AND is_active=1", (code.upper(),))
    coupon = c.fetchone()
    if not coupon:
        conn.close()
        return {"success": False, "error": "Geçersiz kupon kodu!"}
    coupon = dict(coupon)
    if coupon["expires_at"] and datetime.fromisoformat(coupon["expires_at"]) < datetime.now():
        conn.close()
        return {"success": False, "error": "Kupon kodunun süresi dolmuş!"}
    if coupon["used_count"] >= coupon["max_uses"]:
        conn.close()
        return {"success": False, "error": "Bu kupon kodu tükenmiş!"}
    c.execute("SELECT id FROM coupon_usages WHERE coupon_id=? AND user_id=?", (coupon["id"], user_id))
    if c.fetchone():
        conn.close()
        return {"success": False, "error": "Bu kuponu daha önce kullandınız!"}
    conn.execute("UPDATE coupons SET used_count=used_count+1 WHERE id=?", (coupon["id"],))
    conn.execute("INSERT INTO coupon_usages (coupon_id, user_id) VALUES (?,?)", (coupon["id"], user_id))
    conn.commit()
    conn.close()
    return {"success": True, "amount": coupon["value"]}


def create_coupon(code, value, max_uses):
    conn = get_conn()
    conn.execute("INSERT INTO coupons (code, value, max_uses) VALUES (?,?,?)", (code.upper(), value, max_uses))
    conn.commit()
    conn.close()


# ─── Çekiliş ─────────────────────────────────────────────

def get_active_giveaway():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM giveaways WHERE is_active=1 AND end_at > datetime('now') ORDER BY created_at DESC LIMIT 1")
    r = c.fetchone()
    conn.close()
    return dict(r) if r else None


def join_giveaway(giveaway_id, user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id FROM giveaway_participants WHERE giveaway_id=? AND user_id=?", (giveaway_id, user_id))
    if c.fetchone():
        conn.close()
        return False
    conn.execute("INSERT INTO giveaway_participants (giveaway_id, user_id) VALUES (?,?)", (giveaway_id, user_id))
    conn.commit()
    conn.close()
    return True


def create_giveaway(title, prize, prize_amount, end_hours):
    end_at = (datetime.now() + timedelta(hours=end_hours)).isoformat()
    conn = get_conn()
    conn.execute("INSERT INTO giveaways (title, prize, prize_amount, end_at) VALUES (?,?,?,?)",
                 (title, prize, prize_amount, end_at))
    conn.commit()
    conn.close()


# ─── Destek ───────────────────────────────────────────────

def create_ticket(user_id, subject, message):
    conn = get_conn()
    conn.execute("INSERT INTO support_tickets (user_id, subject, message) VALUES (?,?,?)", (user_id, subject, message))
    conn.commit()
    conn.close()


def get_open_tickets():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM support_tickets WHERE status='open' ORDER BY created_at DESC LIMIT 10")
    tickets = [dict(r) for r in c.fetchall()]
    conn.close()
    return tickets


def close_ticket(ticket_id, reply=None):
    conn = get_conn()
    conn.execute("UPDATE support_tickets SET status='closed', admin_reply=? WHERE id=?", (reply, ticket_id))
    conn.commit()
    conn.close()
