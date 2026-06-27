import os
import telebot
from dotenv import load_dotenv
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
import database as db
import keyboards as kb
from handlers.admin import register_admin_handlers

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
BOT_NAME = os.getenv("BOT_NAME", "Market")

if not TOKEN:
    raise SystemExit("❌ TELEGRAM_BOT_TOKEN ayarlanmamış! .env dosyasını kontrol edin.")

bot = telebot.TeleBot(TOKEN, parse_mode=None)
sessions = {}

db.init_db()
handle_admin_text, is_admin = register_admin_handlers(bot, sessions)


# ─── Kanal kontrolü ───────────────────────────────────────

def check_membership(user_id: int) -> bool:
    channels = db.get_all_channels()
    if not channels:
        return True
    for channel in channels:
        try:
            member = bot.get_chat_member(channel, user_id)
            if member.status in ("left", "kicked", "restricted"):
                return False
        except Exception:
            pass
    return True


def require_membership(message_or_call):
    channels = db.get_all_channels()
    if not channels:
        return True
    uid = message_or_call.from_user.id
    if check_membership(uid):
        return True
    chat_id = (message_or_call.chat.id
               if hasattr(message_or_call, "chat")
               else message_or_call.message.chat.id)
    bot.send_message(chat_id,
        f"⚠️ *Devam etmek için aşağıdaki kanallara katılman gerekiyor!*\n\n"
        f"Katıldıktan sonra ✅ butonuna bas.",
        parse_mode="Markdown",
        reply_markup=kb.join_channel_inline(channels))
    return False


# ─── /start ───────────────────────────────────────────────

@bot.message_handler(commands=["start"])
def start_handler(message):
    uid = message.from_user.id
    args = message.text.split()
    ref_code = args[1] if len(args) > 1 else None

    user, is_new = db.get_or_create_user(
        uid,
        message.from_user.first_name,
        message.from_user.username,
        message.from_user.last_name,
        ref_code
    )

    if user["is_banned"]:
        bot.send_message(message.chat.id, "🚫 *Hesabınız yasaklanmıştır.*", parse_mode="Markdown")
        return

    if not require_membership(message):
        return

    sessions[uid] = {"state": "main"}
    greeting = "🌟 *Tekrar hoş geldin*" if not is_new else "🎉 *Hoş geldin!*"

    bot.send_message(message.chat.id,
        f"{greeting}, *{user['first_name']}!*\n\n"
        f"🏪 *{BOT_NAME}*'e Hoş Geldiniz!\n\n"
        f"💎 Bakiye: *{user['balance']} Puan*\n\n"
        f"Aşağıdaki menüden işleminizi seçin:",
        parse_mode="Markdown",
        reply_markup=kb.main_menu(user["is_vip"], user["balance"])
    )


# ─── Yardımcı: profil mesajı ──────────────────────────────

def send_profile(chat_id, user):
    vip_txt = "👑 VIP" if user["is_vip"] else "👤 Normal"
    bot.send_message(chat_id,
        f"👤 *Profil Bilgilerin*\n\n"
        f"├ 📛 Ad: *{user['first_name']}*\n"
        f"├ 🔗 Kullanıcı: *{'@' + user['username'] if user['username'] else '—'}*\n"
        f"├ 💎 Bakiye: *{user['balance']} Puan*\n"
        f"├ 🏷 Durum: *{vip_txt}*\n"
        f"├ 🔑 Referans Kodum: `{user['referral_code']}`\n"
        f"├ 👥 Davet Edilen: *{user['referral_count']} kişi*\n"
        f"├ 💰 Toplam Harcama: *{user['total_spent']} Puan*\n"
        f"└ 📅 Kayıt Tarihi: *{user['created_at'][:10]}*",
        parse_mode="Markdown"
    )


# ─── Ana metin handler ────────────────────────────────────

@bot.message_handler(func=lambda m: True)
def text_handler(message):
    uid = message.from_user.id
    text = message.text or ""
    user = db.get_user(uid)

    if not user:
        bot.send_message(message.chat.id, "Lütfen /start yazın.")
        return
    if user["is_banned"]:
        bot.send_message(message.chat.id, "🚫 *Hesabınız yasaklanmıştır.*", parse_mode="Markdown")
        return

    sess = sessions.get(uid, {"state": "main"})
    state = sess.get("state", "main")

    # Admin & Kurucu akışı
    if is_admin(uid) and (
        state.startswith(("add_", "complete_", "reply_", "set_", "ban_", "unban_",
                          "admin_suggest_", "founder_add_")) or
        state == "admin" or
        text in [
            "📊 İstatistikler", "📦 Bekleyen Siparişler", "➕ Kategori Ekle",
            "➕ Ürün Ekle", "🎟️ Kupon Oluştur", "🎁 Çekiliş Başlat",
            "📢 Kanal Yönet", "📢 Kanal Öner", "🆘 Destek Talepleri",
            "👥 Admin Yönet", "⏳ Onay Bekleyenler",
            "🚫 Kullanıcı Engelle", "✅ Engel Kaldır",
            "❌ İptal", "🗑 Kanalı Kaldır", "✅ Evet", "❌ Hayır"
        ]
    ):
        if handle_admin_text(message, sess):
            return

    if text != "🏠 Ana Menü":
        if not require_membership(message):
            return

    # ── Ana menü butonları ────────────────────────────────

    if text == "🏠 Ana Menü":
        sessions[uid] = {"state": "main"}
        user = db.get_user(uid)
        bot.send_message(message.chat.id, "🏠 *Ana Menü*",
            parse_mode="Markdown",
            reply_markup=kb.main_menu(user["is_vip"], user["balance"]))
        return

    if text.startswith("💎 Bakiye:"):
        bot.send_message(message.chat.id,
            f"💎 *Bakiye Bilgisi*\n\n"
            f"├ 💰 Mevcut Bakiye: *{user['balance']} Puan*\n"
            f"├ 🛍 Toplam Harcama: *{user['total_spent']} Puan*\n"
            f"└ 👥 Referans Kazancı: *{user['referral_count'] * 50} Puan*",
            parse_mode="Markdown")
        return

    if text == "👤 Profilim":
        send_profile(message.chat.id, user)
        return

    if text == "🛒 Mağaza":
        cats = db.get_categories(is_vip=user["is_vip"])
        if not cats:
            bot.send_message(message.chat.id, "🛒 Şu an ürün bulunmamaktadır.\n\nYakında eklenecek! 🔜")
            return
        sessions[uid] = {"state": "browsing_cats"}
        bot.send_message(message.chat.id, "🛒 *Mağaza*\n\nKategori seçin:",
            parse_mode="Markdown", reply_markup=kb.categories_menu(cats))
        return

    if text in ["👑 VIP Mağaza", "👑 VIP Ol"]:
        if not user["is_vip"]:
            need_refs = max(0, 20 - user["referral_count"])
            bot.send_message(message.chat.id,
                f"👑 *VIP Üyelik*\n\n"
                f"VIP olmak için:\n"
                f"1️⃣ *20 Referans* yap — Mevcut: *{user['referral_count']}/20* {'✅' if user['referral_count'] >= 20 else f'({need_refs} kişi kaldı)'}\n"
                f"2️⃣ *500 Puan* harca — Toplam: *{user['total_spent']} Puan*\n\n"
                f"✨ *VIP Avantajları:*\n"
                f"├ 👑 Özel VIP ürünlere erişim\n"
                f"├ 💎 %20 indirim\n"
                f"├ ⚡ Öncelikli destek\n"
                f"└ 🎁 Extra günlük bonus (75-100 Puan)",
                parse_mode="Markdown")
            return
        cats = db.get_categories(is_vip=True)
        sessions[uid] = {"state": "browsing_cats"}
        bot.send_message(message.chat.id, "👑 *VIP Mağaza*\n\nKategori seçin:",
            parse_mode="Markdown", reply_markup=kb.categories_menu(cats))
        return

    if text == "🎁 Günlük Bonus":
        result = db.claim_daily_bonus(user["id"])
        user = db.get_user(uid)
        if result["success"]:
            bot.send_message(message.chat.id,
                f"🎁 *Günlük Bonus Alındı!*\n\n"
                f"💎 Kazanılan: *+{result['amount']} Puan*\n"
                f"💰 Yeni Bakiye: *{result['new_balance']} Puan*\n\n"
                f"⏰ Yarın tekrar gel!",
                parse_mode="Markdown",
                reply_markup=kb.main_menu(user["is_vip"], user["balance"]))
        else:
            bot.send_message(message.chat.id,
                f"⏰ *Henüz Hazır Değil!*\n\n"
                f"🕐 Kalan Süre: *{result['hours']} saat {result['minutes']} dakika*",
                parse_mode="Markdown")
        return

    if text == "📦 Siparişlerim":
        orders = db.get_user_orders(user["id"])
        if not orders:
            bot.send_message(message.chat.id, "📭 *Henüz hiç siparişiniz yok.*\n\nMağazayı keşfet! 🛒", parse_mode="Markdown")
            return
        bot.send_message(message.chat.id, f"📦 *Siparişlerim* _(son {len(orders)})_\n\nDetay için tıkla:",
            parse_mode="Markdown", reply_markup=kb.orders_inline(orders))
        return

    if text == "🔄 Puan Transferi":
        sessions[uid] = {"state": "transfer_id"}
        bot.send_message(message.chat.id,
            f"🔄 *Puan Transferi*\n\n"
            f"💎 Bakiyeniz: *{user['balance']} Puan*\n\n"
            f"Alıcının Telegram ID'sini girin:",
            parse_mode="Markdown", reply_markup=kb.back_menu())
        return

    if text == "🎟️ Kupon Kodu":
        sessions[uid] = {"state": "enter_coupon"}
        bot.send_message(message.chat.id,
            "🎟️ *Kupon Kodu*\n\nKupon kodunuzu girin:",
            parse_mode="Markdown", reply_markup=kb.back_menu())
        return

    if text == "⚡ Referans":
        me = bot.get_me()
        bot.send_message(message.chat.id,
            f"⚡ *Referans Programı*\n\n"
            f"🔑 Kodun: `{user['referral_code']}`\n"
            f"👥 Davet ettiğin: *{user['referral_count']} kişi*\n"
            f"💎 Toplam kazanç: *{user['referral_count'] * 50} Puan*\n\n"
            f"🎁 Her kayıtta sana *+50 Puan* eklenir!\n"
            f"👑 *20 kişi davet et → VIP kazan!*\n\n"
            f"🔗 *Referans Linkin:*\n"
            f"`https://t.me/{me.username}?start={user['referral_code']}`",
            parse_mode="Markdown")
        return

    if text == "🆘 Destek":
        sessions[uid] = {"state": "support_subject"}
        bot.send_message(message.chat.id,
            "🆘 *Destek Merkezi*\n\n"
            "Talebinizin konusunu kısaca yazın:",
            parse_mode="Markdown", reply_markup=kb.back_menu())
        return

    if text == "🎁 Çekiliş":
        g = db.get_active_giveaway()
        if not g:
            bot.send_message(message.chat.id, "🎁 Şu an aktif çekiliş yok.\n\nYakında yeni çekilişler geliyor! 🔜")
            return
        bot.send_message(message.chat.id,
            f"🎉 *{g['title']}*\n\n"
            f"🏆 Ödül: *{g['prize']}*\n"
            f"⏰ Bitiş: *{g['end_at'][:16]}*\n\n"
            f"Şansını dene! 🍀",
            parse_mode="Markdown",
            reply_markup=kb.giveaway_inline(g["id"]))
        return

    if text == "💝 Bağış Yap":
        bot.send_message(message.chat.id,
            "💝 *Bağış Yap*\n\n"
            "Geliştirmeye destek olmak için admin ile iletişime geçebilirsiniz.",
            parse_mode="Markdown")
        return

    # ── Çok adımlı akışlar ───────────────────────────────

    if state == "browsing_cats":
        cats = db.get_categories(is_vip=user["is_vip"])
        cat = next((c for c in cats if f"{c['emoji']} {c['name']}" == text or c["name"] == text), None)
        if cat:
            products = db.get_products(cat["id"], is_vip=user["is_vip"])
            if not products:
                bot.send_message(message.chat.id, f"📭 *{cat['emoji']} {cat['name']}* kategorisinde henüz ürün yok.", parse_mode="Markdown")
                return
            bot.send_message(message.chat.id,
                f"*{cat['emoji']} {cat['name']}*\n\nBir ürün seçin:",
                parse_mode="Markdown",
                reply_markup=kb.products_inline(products))
        return

    if state == "transfer_id":
        try:
            target_tid = int(text)
        except ValueError:
            bot.send_message(message.chat.id, "❌ Geçersiz ID. Sayı girin:")
            return
        if target_tid == uid:
            bot.send_message(message.chat.id, "❌ Kendinize transfer yapamazsınız!")
            return
        target = db.get_user(target_tid)
        if not target:
            bot.send_message(message.chat.id, "❌ Bu Telegram ID'sine sahip kullanıcı bulunamadı.")
            return
        sessions[uid] = {"state": "transfer_amount", "target": target}
        bot.send_message(message.chat.id,
            f"👤 Alıcı: *{target['first_name']}*\n"
            f"💎 Bakiyeniz: *{user['balance']} Puan*\n\n"
            f"Göndermek istediğiniz miktarı girin:",
            parse_mode="Markdown")
        return

    if state == "transfer_amount":
        try:
            amount = int(text)
            assert amount > 0
        except Exception:
            bot.send_message(message.chat.id, "❌ Geçerli bir miktar girin:")
            return
        if amount > user["balance"]:
            bot.send_message(message.chat.id,
                f"❌ *Yetersiz Bakiye!*\n💎 Mevcut: *{user['balance']} Puan*",
                parse_mode="Markdown")
            return
        target = sess["target"]
        sessions[uid]["state"] = "transfer_confirm"
        sessions[uid]["amount"] = amount
        bot.send_message(message.chat.id,
            f"🔄 *Transfer Onayı*\n\n"
            f"├ 👤 Alıcı: *{target['first_name']}*\n"
            f"├ 💎 Miktar: *{amount} Puan*\n"
            f"└ 💰 Kalan: *{user['balance'] - amount} Puan*\n\n"
            f"Onaylıyor musunuz?",
            parse_mode="Markdown",
            reply_markup=kb.confirm_transfer_inline(amount, target["id"]))
        return

    if state == "enter_coupon":
        result = db.use_coupon(text, user["id"])
        if result["success"]:
            new_bal = db.add_balance(user["id"], result["amount"], "coupon", f"Kupon: {text.upper()}")
            sessions[uid] = {"state": "main"}
            user = db.get_user(uid)
            bot.send_message(message.chat.id,
                f"🎟️ *Kupon Kullanıldı!*\n\n"
                f"💎 Kazanılan: *+{result['amount']} Puan*\n"
                f"💰 Yeni Bakiye: *{new_bal} Puan*",
                parse_mode="Markdown",
                reply_markup=kb.main_menu(user["is_vip"], user["balance"]))
        else:
            bot.send_message(message.chat.id, f"❌ *{result['error']}*", parse_mode="Markdown")
        return

    if state == "support_subject":
        sessions[uid] = {"state": "support_message", "subject": text}
        bot.send_message(message.chat.id, "💬 Mesajınızı detaylı yazın:")
        return

    if state == "support_message":
        db.create_ticket(user["id"], sess.get("subject", "Destek"), text)
        sessions[uid] = {"state": "main"}
        user = db.get_user(uid)
        bot.send_message(message.chat.id,
            "✅ *Destek talebiniz alındı!*\n\nEn kısa sürede yanıtlanacaktır. 🙏",
            parse_mode="Markdown",
            reply_markup=kb.main_menu(user["is_vip"], user["balance"]))
        return

    sessions[uid] = {"state": "main"}
    bot.send_message(message.chat.id, "🏠",
        reply_markup=kb.main_menu(user["is_vip"], user["balance"]))


# ─── Callback handler ─────────────────────────────────────

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    uid = call.from_user.id
    data = call.data
    user = db.get_user(uid)

    if not user:
        bot.answer_callback_query(call.id, "Lütfen /start yazın.")
        return
    if user["is_banned"]:
        bot.answer_callback_query(call.id, "🚫 Hesabınız yasaklandı.")
        return

    sess = sessions.get(uid, {"state": "main"})

    # ── Kanal üyelik kontrolü ─────────────────────────────

    if data == "check_membership":
        if check_membership(uid):
            bot.answer_callback_query(call.id, "✅ Üyelik onaylandı!")
            bot.edit_message_text(
                f"✅ *Teşekkürler! Artık botu kullanabilirsin.*\n\n/start yazarak devam et.",
                call.message.chat.id, call.message.message_id, parse_mode="Markdown")
        else:
            bot.answer_callback_query(call.id, "❌ Henüz tüm kanallara katılmadınız!", show_alert=True)
        return

    if data not in ["check_membership"] and not data.startswith("approve_action_") and not data.startswith("reject_action_") and not data.startswith("add_new_channel") and not data.startswith("del_channel_"):
        if not check_membership(uid):
            channels = db.get_all_channels()
            bot.answer_callback_query(call.id, "⚠️ Önce kanallara katılmalısınız!", show_alert=True)
            bot.send_message(call.message.chat.id,
                "⚠️ *Devam etmek için kanallara katılman gerekiyor!*",
                parse_mode="Markdown",
                reply_markup=kb.join_channel_inline(channels))
            return

    # ── Kurucu onay/red işlemleri ─────────────────────────

    if data.startswith("approve_action_") and db.is_founder(uid):
        action_id = int(data.replace("approve_action_", ""))
        action = db.get_pending_action(action_id)
        if not action or action["status"] != "pending":
            bot.answer_callback_query(call.id, "Bu işlem artık geçerli değil.")
            return
        db.resolve_pending_action(action_id, "approved")
        bot.answer_callback_query(call.id, "✅ Onaylandı!")

        if action["action_type"] == "ban_user":
            target = db.get_user_by_id(action["target_id"])
            if target:
                db.ban_user(target["id"], True)
                try:
                    bot.send_message(target["telegram_id"], "🚫 Hesabınız engellenmiştir.")
                except Exception:
                    pass
            bot.edit_message_text(
                f"✅ *Onaylandı* — Kullanıcı engellendi: *{action['extra_data']}*",
                call.message.chat.id, call.message.message_id, parse_mode="Markdown")
            try:
                bot.send_message(action["requested_by"],
                    f"✅ *Engelleme isteğiniz onaylandı.*\nKullanıcı: *{action['extra_data']}*",
                    parse_mode="Markdown")
            except Exception:
                pass

        elif action["action_type"] == "unban_user":
            target = db.get_user_by_id(action["target_id"])
            if target:
                db.ban_user(target["id"], False)
                try:
                    bot.send_message(target["telegram_id"], "✅ Hesabınızın engeli kaldırıldı.")
                except Exception:
                    pass
            bot.edit_message_text(
                f"✅ *Onaylandı* — Engel kaldırıldı: *{action['extra_data']}*",
                call.message.chat.id, call.message.message_id, parse_mode="Markdown")
            try:
                bot.send_message(action["requested_by"],
                    f"✅ *Engel kaldırma isteğiniz onaylandı.*\nKullanıcı: *{action['extra_data']}*",
                    parse_mode="Markdown")
            except Exception:
                pass

        elif action["action_type"] == "add_channel":
            channel = action["extra_data"]
            db.add_channel(channel)
            bot.edit_message_text(
                f"✅ *Onaylandı* — Kanal eklendi: *{channel}*",
                call.message.chat.id, call.message.message_id, parse_mode="Markdown")
            try:
                bot.send_message(action["requested_by"],
                    f"✅ *Kanal ekleme isteğiniz onaylandı.*\nKanal: *{channel}*",
                    parse_mode="Markdown")
            except Exception:
                pass
        return

    if data.startswith("reject_action_") and db.is_founder(uid):
        action_id = int(data.replace("reject_action_", ""))
        action = db.get_pending_action(action_id)
        if not action or action["status"] != "pending":
            bot.answer_callback_query(call.id, "Bu işlem artık geçerli değil.")
            return
        db.resolve_pending_action(action_id, "rejected")
        bot.answer_callback_query(call.id, "❌ Reddedildi.")
        bot.edit_message_text(
            f"❌ *Reddedildi* — İşlem iptal edildi.",
            call.message.chat.id, call.message.message_id, parse_mode="Markdown")
        try:
            bot.send_message(action["requested_by"],
                f"❌ *İsteğiniz reddedildi.*\nDetay: {action['extra_data']}",
                parse_mode="Markdown")
        except Exception:
            pass
        return

    # ── Kanal silme (Kurucu) ──────────────────────────────

    if data.startswith("del_channel_") and db.is_founder(uid):
        ch_slug = data.replace("del_channel_", "")
        channel = f"@{ch_slug}"
        db.remove_channel(channel)
        bot.answer_callback_query(call.id, f"✅ {channel} silindi!")
        channels = db.get_all_channels()
        if channels:
            ch_list = "\n".join([f"• {ch}" for ch in channels])
            bot.edit_message_text(
                f"📢 *Zorunlu Kanallar*\n\n{ch_list}",
                call.message.chat.id, call.message.message_id,
                parse_mode="Markdown",
                reply_markup=kb.channel_list_inline(channels))
        else:
            bot.edit_message_text(
                "📢 *Zorunlu Kanallar*\n\nHenüz kanal yok.",
                call.message.chat.id, call.message.message_id, parse_mode="Markdown")
        return

    if data == "add_new_channel" and db.is_founder(uid):
        sessions[uid] = {"state": "founder_add_channel"}
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id,
            "➕ Eklemek istediğiniz kanalı girin (örn: @kanaladi):",
            parse_mode="Markdown",
            reply_markup=__import__("keyboards").cancel_menu())
        return

    # ── Ürün & satın alma ─────────────────────────────────

    if data.startswith("product_"):
        pid = int(data.replace("product_", ""))
        product = db.get_product(pid)
        if not product:
            bot.answer_callback_query(call.id, "Ürün bulunamadı!")
            return
        if product["is_vip_only"] and not user["is_vip"]:
            bot.answer_callback_query(call.id, "👑 Bu ürün sadece VIP üyelere özeldir!", show_alert=True)
            return
        discount = int(product["price"] * 0.2) if user["is_vip"] else 0
        final_price = product["price"] - discount
        can_buy = product["stock"] != 0 and user["balance"] >= final_price
        stock_txt = "∞ Sınırsız" if product["stock"] == -1 else ("❌ Tükendi" if product["stock"] == 0 else f"{product['stock']} adet")
        vip_line = f"\n⚡ ~~{product['price']}~~ → *{final_price} Puan* _(VIP %20 indirim)_" if discount > 0 else f"\n💰 Fiyat: *{final_price} Puan*"
        desc_line = f"\n📝 _{product['description']}_" if product["description"] else ""
        bot.answer_callback_query(call.id)
        bot.edit_message_text(
            f"📦 *{product['name']}*{desc_line}{vip_line}\n📊 Stok: *{stock_txt}*",
            call.message.chat.id, call.message.message_id,
            parse_mode="Markdown",
            reply_markup=kb.product_detail_inline(product["id"], can_buy))
        return

    if data.startswith("buy_"):
        pid = int(data.replace("buy_", ""))
        product = db.get_product(pid)
        if not product:
            bot.answer_callback_query(call.id, "Ürün bulunamadı!")
            return
        discount = int(product["price"] * 0.2) if user["is_vip"] else 0
        final_price = product["price"] - discount
        if user["balance"] < final_price:
            bot.answer_callback_query(call.id, f"❌ Yetersiz bakiye! ({user['balance']}/{final_price} Puan)", show_alert=True)
            return
        if product["stock"] == 0:
            bot.answer_callback_query(call.id, "❌ Bu ürün stokta yok!", show_alert=True)
            return
        try:
            db.deduct_balance(user["id"], final_price, "purchase", f"{product['name']} satın alındı")
            order = db.create_order(user["id"], product)
            user = db.get_user(uid)
            bot.answer_callback_query(call.id, "✅ Satın alma başarılı!")
            content_txt = f"\n\n📋 *Teslim İçeriği:*\n`{order['delivered_content']}`" if order["delivered_content"] else "\n\n⏳ *Siparişiniz işleme alındı.*\nEn kısa sürede teslim edilecektir."
            bot.edit_message_text(
                f"✅ *Satın Alma Başarılı!*\n\n"
                f"📦 Ürün: *{product['name']}*\n"
                f"💰 Ödenen: *{final_price} Puan*\n"
                f"🔢 Sipariş No: *#{order['id']}*{content_txt}",
                call.message.chat.id, call.message.message_id, parse_mode="Markdown")
            bot.send_message(call.message.chat.id, "🏠",
                reply_markup=kb.main_menu(user["is_vip"], user["balance"]))
        except ValueError as e:
            bot.answer_callback_query(call.id, str(e), show_alert=True)
        return

    if data.startswith("order_"):
        oid = int(data.replace("order_", ""))
        order = db.get_order(oid)
        if not order or order["user_id"] != user["id"]:
            bot.answer_callback_query(call.id, "Sipariş bulunamadı!")
            return
        icons = {"pending": "⏳ Bekliyor", "processing": "🔄 İşleniyor", "completed": "✅ Tamamlandı", "cancelled": "❌ İptal"}
        content_txt = f"\n\n📋 *Teslim İçeriği:*\n`{order['delivered_content']}`" if order["delivered_content"] else ""
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id,
            f"📦 *Sipariş #{order['id']}*\n\n"
            f"├ 🛍 Ürün: *{order['product_name']}*\n"
            f"├ 💰 Ödenen: *{order['total_price']} Puan*\n"
            f"├ 📊 Durum: *{icons.get(order['status'], order['status'])}*\n"
            f"└ 📅 Tarih: *{order['created_at'][:16]}*{content_txt}",
            parse_mode="Markdown")
        return

    if data.startswith("join_giveaway_"):
        gid = int(data.replace("join_giveaway_", ""))
        joined = db.join_giveaway(gid, user["id"])
        if joined:
            bot.answer_callback_query(call.id, "🎉 Çekilişe katıldınız!")
            bot.edit_message_text(
                "🎉 *Çekilişe Katıldınız!*\n\nKazananlar açıklandığında bildirim alacaksınız. Bol şans! 🍀",
                call.message.chat.id, call.message.message_id, parse_mode="Markdown")
        else:
            bot.answer_callback_query(call.id, "⚠️ Bu çekilişe zaten katıldınız!", show_alert=True)
        return

    if data.startswith("confirm_transfer_"):
        parts = data.replace("confirm_transfer_", "").split("_")
        amount, to_id = int(parts[0]), int(parts[1])
        to_user = db.get_user_by_id(to_id)
        if not to_user:
            bot.answer_callback_query(call.id, "Kullanıcı bulunamadı!")
            return
        try:
            db.transfer_points(user["id"], to_id, amount)
            user = db.get_user(uid)
            bot.answer_callback_query(call.id, "✅ Transfer tamamlandı!")
            bot.edit_message_text(
                f"✅ *Transfer Başarılı!*\n\n"
                f"├ 👤 Alıcı: *{to_user['first_name']}*\n"
                f"├ 💎 Gönderilen: *{amount} Puan*\n"
                f"└ 💰 Yeni Bakiye: *{user['balance']} Puan*",
                call.message.chat.id, call.message.message_id, parse_mode="Markdown")
            sessions[uid] = {"state": "main"}
            bot.send_message(call.message.chat.id, "🏠",
                reply_markup=kb.main_menu(user["is_vip"], user["balance"]))
            try:
                bot.send_message(to_user["telegram_id"],
                    f"💎 *{user['first_name']}* sana *{amount} Puan* gönderdi!",
                    parse_mode="Markdown")
            except Exception:
                pass
        except ValueError as e:
            bot.answer_callback_query(call.id, str(e), show_alert=True)
        return

    if data == "cancel_transfer":
        sessions[uid] = {"state": "main"}
        bot.answer_callback_query(call.id, "İptal edildi")
        bot.edit_message_text("❌ *Transfer iptal edildi.*",
            call.message.chat.id, call.message.message_id, parse_mode="Markdown")
        return

    if data == "back_store":
        cats = db.get_categories(is_vip=user["is_vip"])
        bot.answer_callback_query(call.id)
        sessions[uid] = {"state": "browsing_cats"}
        bot.send_message(call.message.chat.id, "🛒 *Mağaza*\n\nKategori seçin:",
            parse_mode="Markdown", reply_markup=kb.categories_menu(cats))
        return

    # ── Admin callbackler ─────────────────────────────────

    if data.startswith("admin_order_"):
        if not is_admin(uid):
            bot.answer_callback_query(call.id, "❌ Yetkisiz")
            return
        oid = int(data.replace("admin_order_", ""))
        sessions[uid] = {"state": f"complete_order_{oid}"}
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id,
            f"📦 *Sipariş #{oid}*\n\nTeslim içeriğini girin:",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add(KeyboardButton("❌ İptal")))
        return

    if data.startswith("reply_ticket_"):
        if not is_admin(uid):
            bot.answer_callback_query(call.id, "❌ Yetkisiz")
            return
        tid = int(data.replace("reply_ticket_", ""))
        sessions[uid] = {"state": f"reply_ticket_{tid}"}
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "✍️ Yanıtınızı girin:",
            reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add(KeyboardButton("❌ İptal")))
        return

    if data.startswith("close_ticket_"):
        if not is_admin(uid):
            bot.answer_callback_query(call.id, "❌ Yetkisiz")
            return
        tid = int(data.replace("close_ticket_", ""))
        db.close_ticket(tid)
        bot.answer_callback_query(call.id, "✅ Talep kapatıldı")
        bot.edit_message_text(f"🔒 *Talep #{tid} kapatıldı.*",
            call.message.chat.id, call.message.message_id, parse_mode="Markdown")
        return

    if data == "noop":
        bot.answer_callback_query(call.id)
        return

    bot.answer_callback_query(call.id)


# ─── Başlat ───────────────────────────────────────────────

if __name__ == "__main__":
    print(f"🚀 {BOT_NAME} Bot başlatıldı!")
    print(f"👑 Kurucu ID: {db.FOUNDER_ID}")
    bot.infinity_polling(timeout=30, long_polling_timeout=20)
