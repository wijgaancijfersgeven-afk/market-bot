import os
import random
import string
from datetime import datetime, timedelta
import psycopg2
import psycopg2.extras

DATABASE_URL = os.getenv("DATABASE_URL")
FOUNDER_ID = 8254024103


def get_conn():
    conn = psycopg2.connect(DATABASE_URL)
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS admins (
        id SERIAL PRIMARY KEY,
        telegram_id BIGINT UNIQUE NOT NULL,
        added_by BIGINT NOT NULL,
        added_at TIMESTAMP DEFAULT NOW()
    )""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS pending_actions (
        id SERIAL PRIMARY KEY,
        action_type TEXT NOT NULL,
        requested_by BIGINT NOT NULL,
        target_id BIGINT,
        extra_data TEXT,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT NOW()
    )""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        telegram_id BIGINT UNIQUE NOT NULL,
        username TEXT,
        first_name TEXT NOT NULL,
        last_name TEXT,
        balance INTEGER DEFAULT 0,
        is_vip BOOLEAN DEFAULT FALSE,
        is_banned BOOLEAN DEFAULT FALSE,
        referral_code TEXT UNIQUE NOT NULL,
        referred_by INTEGER,
        referral_count INTEGER DEFAULT 0,
        total_spent INTEGER DEFAULT 0,
        last_daily_bonus TIMESTAMP,
        created_at TIMESTAMP DEFAULT NOW()
    )""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        emoji TEXT DEFAULT '🛒',
        description TEXT,
        is_vip_only BOOLEAN DEFAULT FALSE,
        is_active BOOLEAN DEFAULT TRUE,
        sort_order INTEGER DEFAULT 0
    )""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id SERIAL PRIMARY KEY,
        category_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        description TEXT,
        price INTEGER NOT NULL,
        stock INTEGER DEFAULT -1,
        content TEXT,
        is_vip_only BOOLEAN DEFAULT FALSE,
        is_active BOOLEAN DEFAULT TRUE,
        sold_count INTEGER DEFAULT 0,
        sort_order INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT NOW()
    )""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        product_name TEXT NOT NULL,
        quantity INTEGER DEFAULT 1,
        total_price INTEGER NOT NULL,
        status TEXT DEFAULT 'pending',
        delivered_content TEXT,
        note TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    )""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS coupons (
        id SERIAL PRIMARY KEY,
        code TEXT UNIQUE NOT NULL,
        value INTEGER NOT NULL,
        max_uses INTEGER DEFAULT 1,
        used_count INTEGER DEFAULT 0,
        is_active BOOLEAN DEFAULT TRUE,
        expires_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT NOW()
    )""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS coupon_usages (
        id SERIAL PRIMARY KEY,
        coupon_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        used_at TIMESTAMP DEFAULT NOW()
    )""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id SERIAL PRIMARY KEY,
        from_user_id BIGINT,
        to_user_id BIGINT NOT NULL,
        amount INTEGER NOT NULL,
        type TEXT NOT NULL,
        description TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    )""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS giveaways (
        id SERIAL PRIMARY KEY,
        title TEXT NOT NULL,
        prize TEXT NOT NULL,
        prize_amount INTEGER DEFAULT 0,
        is_active BOOLEAN DEFAULT TRUE,
        end_at TIMESTAMP NOT NULL,
        winner_id INTEGER,
        created_at TIMESTAMP DEFAULT NOW()
    )""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS giveaway_participants (
        id SERIAL PRIMARY KEY,
        giveaway_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        joined_at TIMESTAMP DEFAULT NOW()
    )""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS support_tickets (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL,
        subject TEXT NOT NULL,
        message TEXT NOT NULL,
        status TEXT DEFAULT 'open',
        admin_reply TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    )""")
    conn.commit()
    c.close()
    conn.close()
    print("✅ Veritabanı hazır.")


def _row(cursor):
    cols = [desc[0] for desc in cursor.description]
    row = cursor.fetchone()
    return dict(zip(cols, row)) if row else None


def _rows(cursor):
    cols = [desc[0] for desc in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


# ─── Yetki Sistemi ────────────────────────────────────────

def is_founder(telegram_id):
    return int(telegram_id) == FOUNDER_ID


def is_admin(telegram_id):
    if is_founder(telegram_id):
        return True
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id FROM admins WHERE telegram_id = %s", (int(telegram_id),))
    row = c.fetchone()
    c.close(); conn.close()
    return row is not None


def get_admins():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT telegram_id, added_by, added_at FROM admins ORDER BY added_at")
    rows = _rows(c)
    c.close(); conn.close()
    return rows


def add_admin(telegram_id, added_by):
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO admins (telegram_id, added_by) VALUES (%s, %s)",
                  (int(telegram_id), int(added_by)))
        conn.commit()
        result = True
    except psycopg2.IntegrityError:
        conn.rollback()
        result = False
    c.close(); conn.close()
    return result


def remove_admin(telegram_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM admins WHERE telegram_id = %s", (int(telegram_id),))
    conn.commit()
    c.close(); conn.close()


# ─── Onay Bekleyen İşlemler ──────────────────────────────

def create_pending_action(action_type, requested_by, target_id=None, extra_data=None):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO pending_actions (action_type, requested_by, target_id, extra_data) VALUES (%s, %s, %s, %s) RETURNING id",
        (action_type, int(requested_by), target_id, extra_data)
    )
    action_id = c.fetchone()[0]
    conn.commit()
    c.close(); conn.close()
    return action_id


def get_pending_action(action_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM pending_actions WHERE id = %s", (action_id,))
    row = _row(c)
    c.close(); conn.close()
    return row


def resolve_pending_action(action_id, status):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE pending_actions SET status = %s WHERE id = %s", (status, action_id))
    conn.commit()
    c.close(); conn.close()


def get_pending_actions_list():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM pending_actions WHERE status = 'pending' ORDER BY created_at DESC")
    rows = _rows(c)
    c.close(); conn.close()
    return rows


# ─── Kanallar ─────────────────────────────────────────────

def get_all_channels():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key LIKE 'channel_%'")
    rows = [r[0] for r in c.fetchall()]
    c.close(); conn.close()
    return rows


def add_channel(channel):
    key = f"channel_{channel.lstrip('@').lower()}"
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
              (key, channel))
    conn.commit()
    c.close(); conn.close()


def remove_channel(channel):
    key = f"channel_{channel.lstrip('@').lower()}"
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM settings WHERE key = %s", (key,))
    conn.commit()
    c.close(); conn.close()


# ─── Ayarlar ──────────────────────────────────────────────

def get_setting(key, default=None):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key = %s", (key,))
    row = c.fetchone()
    c.close(); conn.close()
    return row[0] if row else default


def set_setting(key, value):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
              (key, value))
    conn.commit()
    c.close(); conn.close()


def delete_setting(key):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM settings WHERE key = %s", (key,))
    conn.commit()
    c.close(); conn.close()


# ─── Kullanıcı ────────────────────────────────────────────

def _gen_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))


def get_or_create_user(telegram_id, first_name, username=None, last_name=None, referral_code=None):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE telegram_id = %s", (telegram_id,))
    user = _row(c)
    if user:
        c.close(); conn.close()
        return user, False

    code = _gen_code()
    while True:
        c.execute("SELECT id FROM users WHERE referral_code = %s", (code,))
        if not c.fetchone():
            break
        code = _gen_code()

    referred_by = None
    if referral_code:
        c.execute("SELECT * FROM users WHERE referral_code = %s AND telegram_id != %s", (referral_code, telegram_id))
        referrer = _row(c)
        if referrer:
            referred_by = referrer["id"]
            new_count = referrer["referral_count"] + 1
            new_vip = True if new_count >= 20 else referrer["is_vip"]
            c.execute("UPDATE users SET balance = balance + 50, referral_count = %s, is_vip = %s WHERE id = %s",
                      (new_count, new_vip, referrer["id"]))
            c.execute("INSERT INTO transactions (to_user_id, amount, type, description) VALUES (%s, 50, 'referral_bonus', %s)",
                      (referrer["id"], f"Referans bonusu — {first_name}"))

    c.execute("""INSERT INTO users (telegram_id, first_name, last_name, username, referral_code, referred_by)
                 VALUES (%s, %s, %s, %s, %s, %s) RETURNING *""",
              (telegram_id, first_name, last_name, username, code, referred_by))
    new_user = _row(c)
    conn.commit()
    c.close(); conn.close()
    return new_user, True


def get_user(telegram_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE telegram_id = %s", (telegram_id,))
    u = _row(c)
    c.close(); conn.close()
    return u


def get_user_by_id(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    u = _row(c)
    c.close(); conn.close()
    return u


def add_balance(user_id, amount, tx_type, description):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance + %s WHERE id = %s", (amount, user_id))
    c.execute("INSERT INTO transactions (to_user_id, amount, type, description) VALUES (%s, %s, %s, %s)",
              (user_id, amount, tx_type, description))
    c.execute("SELECT balance FROM users WHERE id = %s", (user_id,))
    bal = c.fetchone()[0]
    conn.commit()
    c.close(); conn.close()
    return bal


def deduct_balance(user_id, amount, tx_type, description):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE id = %s", (user_id,))
    row = c.fetchone()
    if not row or row[0] < amount:
        c.close(); conn.close()
        raise ValueError("Yetersiz bakiye")
    c.execute("UPDATE users SET balance = balance - %s, total_spent = total_spent + %s WHERE id = %s",
              (amount, amount, user_id))
    c.execute("INSERT INTO transactions (from_user_id, to_user_id, amount, type, description) VALUES (%s, %s, %s, %s, %s)",
              (user_id, user_id, -amount, tx_type, description))
    conn.commit()
    c.close(); conn.close()


def transfer_points(from_id, to_id, amount):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE id = %s", (from_id,))
    row = c.fetchone()
    if not row or row[0] < amount:
        c.close(); conn.close()
        raise ValueError("Yetersiz bakiye")
    c.execute("UPDATE users SET balance = balance - %s WHERE id = %s", (amount, from_id))
    c.execute("UPDATE users SET balance = balance + %s WHERE id = %s", (amount, to_id))
    c.execute("INSERT INTO transactions (from_user_id, to_user_id, amount, type, description) VALUES (%s, %s, %s, 'transfer', 'Puan transferi')",
              (from_id, to_id, amount))
    conn.commit()
    c.close(); conn.close()


def claim_daily_bonus(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT balance, is_vip, last_daily_bonus FROM users WHERE id = %s", (user_id,))
    user = c.fetchone()
    now = datetime.now()
    if user[2]:
        diff = now - user[2].replace(tzinfo=None)
        if diff.total_seconds() < 86400:
            remaining = timedelta(seconds=86400) - diff
            h = int(remaining.total_seconds() // 3600)
            m = int((remaining.total_seconds() % 3600) // 60)
            c.close(); conn.close()
            return {"success": False, "hours": h, "minutes": m}
    base = 75 if user[1] else 25
    bonus = base + random.randint(0, 25)
    c.execute("UPDATE users SET balance = balance + %s, last_daily_bonus = %s WHERE id = %s",
              (bonus, now, user_id))
    c.execute("INSERT INTO transactions (to_user_id, amount, type, description) VALUES (%s, %s, 'daily_bonus', 'Günlük bonus')",
              (user_id, bonus))
    c.execute("SELECT balance FROM users WHERE id = %s", (user_id,))
    new_bal = c.fetchone()[0]
    conn.commit()
    c.close(); conn.close()
    return {"success": True, "amount": bonus, "new_balance": new_bal}


def make_vip(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE users SET is_vip = TRUE WHERE id = %s", (user_id,))
    conn.commit()
    c.close(); conn.close()


def ban_user(user_id, banned=True):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE users SET is_banned = %s WHERE id = %s", (banned, user_id))
    conn.commit()
    c.close(); conn.close()


def get_all_users():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT telegram_id FROM users WHERE is_banned = FALSE")
    users = [r[0] for r in c.fetchall()]
    c.close(); conn.close()
    return users


def get_stats():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users"); total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE is_vip = TRUE"); vip = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE is_banned = TRUE"); banned = c.fetchone()[0]
    c.execute("SELECT COALESCE(SUM(balance), 0) FROM users"); total_bal = c.fetchone()[0]
    c.close(); conn.close()
    return {"total_users": total, "vip_users": vip, "banned_users": banned, "total_balance": total_bal}


# ─── Kategoriler & Ürünler ────────────────────────────────

def get_categories(is_vip=False):
    conn = get_conn()
    c = conn.cursor()
    if is_vip:
        c.execute("SELECT * FROM categories WHERE is_active = TRUE ORDER BY sort_order")
    else:
        c.execute("SELECT * FROM categories WHERE is_active = TRUE AND is_vip_only = FALSE ORDER BY sort_order")
    cats = _rows(c)
    c.close(); conn.close()
    return cats


def get_products(category_id, is_vip=False):
    conn = get_conn()
    c = conn.cursor()
    if is_vip:
        c.execute("SELECT * FROM products WHERE category_id = %s AND is_active = TRUE ORDER BY sort_order", (category_id,))
    else:
        c.execute("SELECT * FROM products WHERE category_id = %s AND is_active = TRUE AND is_vip_only = FALSE ORDER BY sort_order", (category_id,))
    products = _rows(c)
    c.close(); conn.close()
    return products


def get_product(product_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM products WHERE id = %s", (product_id,))
    r = _row(c)
    c.close(); conn.close()
    return r


def add_category(name, emoji, is_vip_only=False):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO categories (name, emoji, is_vip_only) VALUES (%s, %s, %s)",
              (name, emoji, is_vip_only))
    conn.commit()
    c.close(); conn.close()


def add_product(name, category_id, price, stock, description, content, is_vip_only):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO products (name, category_id, price, stock, description, content, is_vip_only) VALUES (%s, %s, %s, %s, %s, %s, %s)",
              (name, category_id, price, stock, description or None, content or None, is_vip_only))
    conn.commit()
    c.close(); conn.close()


# ─── Siparişler ────────────────────────────────────────────

def create_order(user_id, product):
    if product["stock"] == 0:
        raise ValueError("out_of_stock")
    conn = get_conn()
    c = conn.cursor()
    status = "completed" if product["content"] else "pending"
    c.execute("""INSERT INTO orders (user_id, product_id, product_name, total_price, status, delivered_content)
                 VALUES (%s, %s, %s, %s, %s, %s) RETURNING *""",
              (user_id, product["id"], product["name"], product["price"], status, product["content"]))
    order = _row(c)
    if product["stock"] > 0:
        c.execute("UPDATE products SET stock = stock - 1, sold_count = sold_count + 1 WHERE id = %s", (product["id"],))
    else:
        c.execute("UPDATE products SET sold_count = sold_count + 1 WHERE id = %s", (product["id"],))
    conn.commit()
    c.close(); conn.close()
    return order


def get_user_orders(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM orders WHERE user_id = %s ORDER BY created_at DESC LIMIT 20", (user_id,))
    orders = _rows(c)
    c.close(); conn.close()
    return orders


def get_order(order_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM orders WHERE id = %s", (order_id,))
    r = _row(c)
    c.close(); conn.close()
    return r


def get_pending_orders():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM orders WHERE status = 'pending' ORDER BY created_at DESC")
    orders = _rows(c)
    c.close(); conn.close()
    return orders


def complete_order(order_id, content):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE orders SET status = 'completed', delivered_content = %s WHERE id = %s", (content, order_id))
    conn.commit()
    c.close(); conn.close()


def get_order_stats():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*), COALESCE(SUM(total_price), 0) FROM orders")
    row = c.fetchone()
    c.execute("SELECT COUNT(*) FROM orders WHERE status = 'pending'")
    pending = c.fetchone()[0]
    c.close(); conn.close()
    return {"total": row[0], "revenue": row[1], "pending": pending}


# ─── Kuponlar ─────────────────────────────────────────────

def use_coupon(code, user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM coupons WHERE code = %s AND is_active = TRUE", (code.upper(),))
    coupon = _row(c)
    if not coupon:
        c.close(); conn.close()
        return {"success": False, "error": "Geçersiz kupon kodu!"}
    if coupon["expires_at"] and coupon["expires_at"].replace(tzinfo=None) < datetime.now():
        c.close(); conn.close()
        return {"success": False, "error": "Kupon kodunun süresi dolmuş!"}
    if coupon["used_count"] >= coupon["max_uses"]:
        c.close(); conn.close()
        return {"success": False, "error": "Bu kupon kodu tükenmiş!"}
    c.execute("SELECT id FROM coupon_usages WHERE coupon_id = %s AND user_id = %s", (coupon["id"], user_id))
    if c.fetchone():
        c.close(); conn.close()
        return {"success": False, "error": "Bu kuponu daha önce kullandınız!"}
    c.execute("UPDATE coupons SET used_count = used_count + 1 WHERE id = %s", (coupon["id"],))
    c.execute("INSERT INTO coupon_usages (coupon_id, user_id) VALUES (%s, %s)", (coupon["id"], user_id))
    conn.commit()
    c.close(); conn.close()
    return {"success": True, "amount": coupon["value"]}


def create_coupon(code, value, max_uses):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO coupons (code, value, max_uses) VALUES (%s, %s, %s)", (code.upper(), value, max_uses))
    conn.commit()
    c.close(); conn.close()


# ─── Çekiliş ─────────────────────────────────────────────

def get_active_giveaway():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM giveaways WHERE is_active = TRUE AND end_at > NOW() ORDER BY created_at DESC LIMIT 1")
    r = _row(c)
    c.close(); conn.close()
    return r


def join_giveaway(giveaway_id, user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id FROM giveaway_participants WHERE giveaway_id = %s AND user_id = %s", (giveaway_id, user_id))
    if c.fetchone():
        c.close(); conn.close()
        return False
    c.execute("INSERT INTO giveaway_participants (giveaway_id, user_id) VALUES (%s, %s)", (giveaway_id, user_id))
    conn.commit()
    c.close(); conn.close()
    return True


def create_giveaway(title, prize, prize_amount, end_hours):
    end_at = datetime.now() + timedelta(hours=end_hours)
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO giveaways (title, prize, prize_amount, end_at) VALUES (%s, %s, %s, %s)",
              (title, prize, prize_amount, end_at))
    conn.commit()
    c.close(); conn.close()


# ─── Destek ───────────────────────────────────────────────

def create_ticket(user_id, subject, message):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO support_tickets (user_id, subject, message) VALUES (%s, %s, %s)", (user_id, subject, message))
    conn.commit()
    c.close(); conn.close()


def get_open_tickets():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM support_tickets WHERE status = 'open' ORDER BY created_at DESC LIMIT 10")
    tickets = _rows(c)
    c.close(); conn.close()
    return tickets


def close_ticket(ticket_id, reply=None):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE support_tickets SET status = 'closed', admin_reply = %s WHERE id = %s", (reply, ticket_id))
    conn.commit()
    c.close(); conn.close()


def get_ticket_by_id(ticket_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM support_tickets WHERE id = %s", (ticket_id,))
    r = _row(c)
    c.close(); conn.close()
    return r
