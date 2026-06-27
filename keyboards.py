from telebot.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)


# ─── Kullanıcı Klavyeleri ─────────────────────────────────

def main_menu(is_vip: bool, balance: int) -> ReplyKeyboardMarkup:
    m = ReplyKeyboardMarkup(resize_keyboard=True)
    m.row(
        KeyboardButton(f"💎 Bakiye: {balance} Puan"),
        KeyboardButton("👤 Profilim")
    )
    m.row(
        KeyboardButton("🛒 Mağaza"),
        KeyboardButton("👑 VIP Mağaza" if is_vip else "👑 VIP Ol")
    )
    m.row(
        KeyboardButton("🎁 Günlük Bonus"),
        KeyboardButton("📦 Siparişlerim")
    )
    m.row(
        KeyboardButton("🔄 Puan Transferi"),
        KeyboardButton("🎟️ Kupon Kodu")
    )
    m.row(
        KeyboardButton("⚡ Referans"),
        KeyboardButton("🆘 Destek")
    )
    m.row(
        KeyboardButton("🎁 Çekiliş"),
        KeyboardButton("💝 Bağış Yap")
    )
    return m


def back_menu() -> ReplyKeyboardMarkup:
    m = ReplyKeyboardMarkup(resize_keyboard=True)
    m.add(KeyboardButton("🏠 Ana Menü"))
    return m


def cancel_menu() -> ReplyKeyboardMarkup:
    m = ReplyKeyboardMarkup(resize_keyboard=True)
    m.add(KeyboardButton("❌ İptal"))
    return m


def yes_no_menu() -> ReplyKeyboardMarkup:
    m = ReplyKeyboardMarkup(resize_keyboard=True)
    m.row(KeyboardButton("✅ Evet"), KeyboardButton("❌ Hayır"))
    return m


def categories_menu(categories: list) -> ReplyKeyboardMarkup:
    m = ReplyKeyboardMarkup(resize_keyboard=True)
    cats = list(categories)
    for i in range(0, len(cats), 2):
        row = [KeyboardButton(f"{cats[i]['emoji']} {cats[i]['name']}")]
        if i + 1 < len(cats):
            row.append(KeyboardButton(f"{cats[i+1]['emoji']} {cats[i+1]['name']}"))
        m.row(*row)
    m.add(KeyboardButton("🏠 Ana Menü"))
    return m


def products_inline(products: list) -> InlineKeyboardMarkup:
    m = InlineKeyboardMarkup()
    for p in products:
        sold_out = p["stock"] == 0
        label = f"{'❌ ' if sold_out else ''}  {p['name']}  —  {p['price']} 💎"
        m.add(InlineKeyboardButton(label, callback_data=f"product_{p['id']}"))
    return m


def product_detail_inline(product_id: int, can_buy: bool) -> InlineKeyboardMarkup:
    m = InlineKeyboardMarkup()
    if can_buy:
        m.add(InlineKeyboardButton("✅ Satın Al", callback_data=f"buy_{product_id}"))
    else:
        m.add(InlineKeyboardButton("❌ Yetersiz Bakiye / Stok Yok", callback_data="noop"))
    m.add(InlineKeyboardButton("◀️ Kategorilere Dön", callback_data="back_store"))
    return m


def orders_inline(orders: list) -> InlineKeyboardMarkup:
    m = InlineKeyboardMarkup()
    icons = {"pending": "⏳", "processing": "🔄", "completed": "✅", "cancelled": "❌"}
    for o in orders:
        icon = icons.get(o["status"], "❓")
        m.add(InlineKeyboardButton(
            f"{icon} #{o['id']}  {o['product_name']}  —  {o['total_price']} 💎",
            callback_data=f"order_{o['id']}"
        ))
    return m


def giveaway_inline(giveaway_id: int) -> InlineKeyboardMarkup:
    m = InlineKeyboardMarkup()
    m.add(InlineKeyboardButton("🎉 Çekilişe Katıl!", callback_data=f"join_giveaway_{giveaway_id}"))
    return m


def confirm_transfer_inline(amount: int, to_user_id: int) -> InlineKeyboardMarkup:
    m = InlineKeyboardMarkup()
    m.row(
        InlineKeyboardButton("✅ Onayla", callback_data=f"confirm_transfer_{amount}_{to_user_id}"),
        InlineKeyboardButton("❌ İptal", callback_data="cancel_transfer")
    )
    return m


def join_channel_inline(channels: list) -> InlineKeyboardMarkup:
    m = InlineKeyboardMarkup()
    for ch in channels:
        link = ch if ch.startswith("http") else f"https://t.me/{ch.lstrip('@')}"
        m.add(InlineKeyboardButton(f"📢 {ch} Kanalına Katıl", url=link))
    m.add(InlineKeyboardButton("✅ Katıldım, Devam Et", callback_data="check_membership"))
    return m


# ─── Admin Klavyeleri ─────────────────────────────────────

def admin_menu() -> ReplyKeyboardMarkup:
    m = ReplyKeyboardMarkup(resize_keyboard=True)
    m.row(KeyboardButton("📊 İstatistikler"), KeyboardButton("📦 Bekleyen Siparişler"))
    m.row(KeyboardButton("➕ Kategori Ekle"), KeyboardButton("➕ Ürün Ekle"))
    m.row(KeyboardButton("🎟️ Kupon Oluştur"), KeyboardButton("🎁 Çekiliş Başlat"))
    m.row(KeyboardButton("📢 Kanal Öner"), KeyboardButton("🆘 Destek Talepleri"))
    m.row(KeyboardButton("🚫 Kullanıcı Engelle"), KeyboardButton("✅ Engel Kaldır"))
    m.row(KeyboardButton("🏠 Ana Menü"))
    return m


def founder_menu() -> ReplyKeyboardMarkup:
    m = ReplyKeyboardMarkup(resize_keyboard=True)
    m.row(KeyboardButton("📊 İstatistikler"), KeyboardButton("📦 Bekleyen Siparişler"))
    m.row(KeyboardButton("➕ Kategori Ekle"), KeyboardButton("➕ Ürün Ekle"))
    m.row(KeyboardButton("🎟️ Kupon Oluştur"), KeyboardButton("🎁 Çekiliş Başlat"))
    m.row(KeyboardButton("📢 Kanal Yönet"), KeyboardButton("🆘 Destek Talepleri"))
    m.row(KeyboardButton("👥 Admin Yönet"), KeyboardButton("⏳ Onay Bekleyenler"))
    m.row(KeyboardButton("🚫 Kullanıcı Engelle"), KeyboardButton("✅ Engel Kaldır"))
    m.row(KeyboardButton("🏠 Ana Menü"))
    return m


def pending_action_inline(action_id: int, action_desc: str) -> InlineKeyboardMarkup:
    m = InlineKeyboardMarkup()
    m.row(
        InlineKeyboardButton("✅ Onayla", callback_data=f"approve_action_{action_id}"),
        InlineKeyboardButton("❌ Reddet", callback_data=f"reject_action_{action_id}")
    )
    return m


def channel_list_inline(channels: list) -> InlineKeyboardMarkup:
    m = InlineKeyboardMarkup()
    for ch in channels:
        m.add(InlineKeyboardButton(f"🗑 {ch} Sil", callback_data=f"del_channel_{ch.lstrip('@')}"))
    m.add(InlineKeyboardButton("➕ Yeni Kanal Ekle", callback_data="add_new_channel"))
    return m
