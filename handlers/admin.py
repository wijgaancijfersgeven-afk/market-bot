import telebot
import database as db
from keyboards import admin_menu, cancel_menu, yes_no_menu


def register_admin_handlers(bot: telebot.TeleBot, sessions: dict, ADMIN_IDS: list):

    def is_admin(uid):
        return uid in ADMIN_IDS

    # ── Komutlar ──────────────────────────────────────────

    @bot.message_handler(commands=["admin"])
    def admin_cmd(message):
        if not is_admin(message.from_user.id):
            bot.send_message(message.chat.id, "❌ Yetkisiz erişim.")
            return
        sessions[message.from_user.id] = {"state": "admin"}
        bot.send_message(message.chat.id,
            "🔧 *Admin Paneli*\n\nHoş geldin, yönetici.",
            parse_mode="Markdown", reply_markup=admin_menu())

    @bot.message_handler(commands=["vip"])
    def vip_cmd(message):
        if not is_admin(message.from_user.id):
            return
        parts = message.text.split()
        if len(parts) < 2:
            bot.send_message(message.chat.id, "Kullanım: `/vip <telegram_id>`", parse_mode="Markdown")
            return
        target = db.get_user(int(parts[1]))
        if not target:
            bot.send_message(message.chat.id, "❌ Kullanıcı bulunamadı!")
            return
        db.make_vip(target["id"])
        bot.send_message(message.chat.id, f"✅ *{target['first_name']}* VIP yapıldı!", parse_mode="Markdown")
        try:
            bot.send_message(int(parts[1]), "🎉 *VIP üyeliğiniz aktif edildi!* 👑\n\nArtık VIP ayrıcalıklarından yararlanabilirsiniz.", parse_mode="Markdown")
        except:
            pass

    @bot.message_handler(commands=["addpoints"])
    def addpoints_cmd(message):
        if not is_admin(message.from_user.id):
            return
        parts = message.text.split()
        if len(parts) < 3:
            bot.send_message(message.chat.id, "Kullanım: `/addpoints <telegram_id> <miktar>`", parse_mode="Markdown")
            return
        target = db.get_user(int(parts[1]))
        if not target:
            bot.send_message(message.chat.id, "❌ Kullanıcı bulunamadı!")
            return
        amount = int(parts[2])
        new_bal = db.add_balance(target["id"], amount, "admin_add", "Admin tarafından eklendi")
        bot.send_message(message.chat.id,
            f"✅ *{target['first_name']}*'e *{amount} Puan* eklendi.\n💰 Yeni bakiye: *{new_bal} Puan*",
            parse_mode="Markdown")
        try:
            bot.send_message(int(parts[1]),
                f"💎 *Hesabınıza {amount} Puan eklendi!*\n💰 Yeni Bakiye: *{new_bal} Puan*",
                parse_mode="Markdown")
        except:
            pass

    @bot.message_handler(commands=["ban"])
    def ban_cmd(message):
        if not is_admin(message.from_user.id):
            return
        parts = message.text.split()
        if len(parts) < 2:
            bot.send_message(message.chat.id, "Kullanım: `/ban <telegram_id>`", parse_mode="Markdown")
            return
        target = db.get_user(int(parts[1]))
        if not target:
            bot.send_message(message.chat.id, "❌ Kullanıcı bulunamadı!")
            return
        db.ban_user(target["id"], True)
        bot.send_message(message.chat.id, f"🚫 *{target['first_name']}* banlandı!", parse_mode="Markdown")

    @bot.message_handler(commands=["unban"])
    def unban_cmd(message):
        if not is_admin(message.from_user.id):
            return
        parts = message.text.split()
        if len(parts) < 2:
            bot.send_message(message.chat.id, "Kullanım: `/unban <telegram_id>`", parse_mode="Markdown")
            return
        target = db.get_user(int(parts[1]))
        if not target:
            bot.send_message(message.chat.id, "❌ Kullanıcı bulunamadı!")
            return
        db.ban_user(target["id"], False)
        bot.send_message(message.chat.id, f"✅ *{target['first_name']}* banı kaldırıldı!", parse_mode="Markdown")

    @bot.message_handler(commands=["broadcast"])
    def broadcast_cmd(message):
        if not is_admin(message.from_user.id):
            return
        text = message.text.replace("/broadcast", "", 1).strip()
        if not text:
            bot.send_message(message.chat.id, "Kullanım: `/broadcast <mesaj>`", parse_mode="Markdown")
            return
        users = db.get_all_users()
        bot.send_message(message.chat.id, f"📢 Yayın başlıyor... *{len(users)} kullanıcı*", parse_mode="Markdown")
        sent, failed = 0, 0
        for uid in users:
            try:
                bot.send_message(uid, f"📢 *Duyuru*\n\n{text}", parse_mode="Markdown")
                sent += 1
            except:
                failed += 1
        bot.send_message(message.chat.id, f"✅ Gönderildi: *{sent}*\n❌ Başarısız: *{failed}*", parse_mode="Markdown")

    # ── Admin metin akışları ───────────────────────────────

    def handle_admin_text(message, sess):
        state = sess.get("state", "")
        text = message.text
        uid = message.from_user.id

        if text == "❌ İptal":
            sessions[uid] = {"state": "admin"}
            bot.send_message(message.chat.id, "❌ İptal edildi.", reply_markup=admin_menu())
            return True

        # ── Ana panel butonları ────────────────────────────

        if text == "📊 İstatistikler":
            s = db.get_stats()
            o = db.get_order_stats()
            channel = db.get_setting("required_channel", "Ayarlanmadı")
            bot.send_message(message.chat.id,
                f"📊 *İstatistikler*\n\n"
                f"┌ 👥 Toplam Kullanıcı: *{s['total_users']}*\n"
                f"├ 👑 VIP: *{s['vip_users']}*\n"
                f"├ 🚫 Banlı: *{s['banned_users']}*\n"
                f"└ 💎 Toplam Puan: *{s['total_balance']}*\n\n"
                f"┌ 📦 Toplam Sipariş: *{o['total']}*\n"
                f"├ ⏳ Bekleyen: *{o['pending']}*\n"
                f"└ 💰 Toplam Ciro: *{o['revenue']} Puan*\n\n"
                f"📢 Zorunlu Kanal: *{channel}*",
                parse_mode="Markdown")
            return True

        if text == "📦 Bekleyen Siparişler":
            orders = db.get_pending_orders()
            if not orders:
                bot.send_message(message.chat.id, "✅ Bekleyen sipariş yok!")
                return True
            from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
            markup = InlineKeyboardMarkup()
            for o in orders[:10]:
                markup.add(InlineKeyboardButton(
                    f"#{o['id']} — {o['product_name']} ({o['total_price']} 💎)",
                    callback_data=f"admin_order_{o['id']}"
                ))
            bot.send_message(message.chat.id, f"📦 *Bekleyen Siparişler ({len(orders)} adet):*",
                parse_mode="Markdown", reply_markup=markup)
            return True

        if text == "➕ Kategori Ekle":
            sessions[uid] = {"state": "add_cat_name"}
            bot.send_message(message.chat.id, "📁 *Yeni Kategori*\n\nKategori adını girin:", parse_mode="Markdown", reply_markup=cancel_menu())
            return True

        if text == "➕ Ürün Ekle":
            cats = db.get_categories(is_vip=True)
            if not cats:
                bot.send_message(message.chat.id, "❌ Önce kategori eklemelisiniz!")
                return True
            sessions[uid] = {"state": "add_prod_name", "data": {}}
            bot.send_message(message.chat.id, "📦 *Yeni Ürün*\n\nÜrün adını girin:", parse_mode="Markdown", reply_markup=cancel_menu())
            return True

        if text == "🎟️ Kupon Oluştur":
            sessions[uid] = {"state": "add_coupon_code"}
            bot.send_message(message.chat.id, "🎟️ *Yeni Kupon*\n\nKupon kodunu girin (büyük harf):", parse_mode="Markdown", reply_markup=cancel_menu())
            return True

        if text == "🎁 Çekiliş Başlat":
            sessions[uid] = {"state": "add_giveaway_title", "data": {}}
            bot.send_message(message.chat.id, "🎁 *Yeni Çekiliş*\n\nÇekiliş başlığını girin:", parse_mode="Markdown", reply_markup=cancel_menu())
            return True

        if text == "📢 Kanal Ayarla":
            current = db.get_setting("required_channel")
            current_txt = f"Mevcut: *{current}*" if current else "Henüz ayarlanmadı."
            sessions[uid] = {"state": "set_channel"}
            from telebot.types import ReplyKeyboardMarkup, KeyboardButton
            m = ReplyKeyboardMarkup(resize_keyboard=True)
            if current:
                m.row(KeyboardButton("🗑 Kanalı Kaldır"), KeyboardButton("❌ İptal"))
            else:
                m.add(KeyboardButton("❌ İptal"))
            bot.send_message(message.chat.id,
                f"📢 *Zorunlu Kanal Ayarı*\n\n{current_txt}\n\n"
                f"Kanal kullanıcı adını girin (örn: `@kanalim`):",
                parse_mode="Markdown", reply_markup=m)
            return True

        if text == "🆘 Destek Talepleri":
            tickets = db.get_open_tickets()
            if not tickets:
                bot.send_message(message.chat.id, "✅ Açık destek talebi yok!")
                return True
            from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
            for t in tickets:
                user = db.get_user_by_id(t["user_id"])
                markup = InlineKeyboardMarkup()
                markup.row(
                    InlineKeyboardButton("✍️ Yanıtla", callback_data=f"reply_ticket_{t['id']}"),
                    InlineKeyboardButton("🔒 Kapat", callback_data=f"close_ticket_{t['id']}")
                )
                bot.send_message(message.chat.id,
                    f"🆘 *Talep #{t['id']}*\n"
                    f"👤 {user['first_name'] if user else '?'} "
                    f"({'@' + user['username'] if user and user['username'] else 'yok'})\n"
                    f"📌 Konu: {t['subject']}\n"
                    f"💬 Mesaj: {t['message']}\n"
                    f"📅 {t['created_at'][:16]}",
                    parse_mode="Markdown", reply_markup=markup)
            return True

        # ── Çok adımlı akışlar ────────────────────────────

        if state == "set_channel":
            if text == "🗑 Kanalı Kaldır":
                db.delete_setting("required_channel")
                sessions[uid] = {"state": "admin"}
                bot.send_message(message.chat.id, "✅ Zorunlu kanal kaldırıldı.", reply_markup=admin_menu())
            else:
                channel = text.strip()
                if not channel.startswith("@") and not channel.startswith("http"):
                    channel = "@" + channel
                db.set_setting("required_channel", channel)
                sessions[uid] = {"state": "admin"}
                bot.send_message(message.chat.id,
                    f"✅ Zorunlu kanal ayarlandı: *{channel}*\n\nKullanıcılar bu kanala üye olmadan botu kullanamazlar.",
                    parse_mode="Markdown", reply_markup=admin_menu())
            return True

        if state == "add_cat_name":
            sessions[uid] = {"state": "add_cat_emoji", "data": {"name": text}}
            bot.send_message(message.chat.id, "Emoji seçin (örn: 🛒 📱 💻):")
            return True

        if state == "add_cat_emoji":
            sessions[uid]["data"]["emoji"] = text
            sessions[uid]["state"] = "add_cat_vip"
            bot.send_message(message.chat.id, "Bu kategori sadece VIP'lere mi özel?", reply_markup=yes_no_menu())
            return True

        if state == "add_cat_vip":
            d = sessions[uid]["data"]
            db.add_category(d["name"], d["emoji"], text == "✅ Evet")
            sessions[uid] = {"state": "admin"}
            bot.send_message(message.chat.id,
                f"✅ *{d['emoji']} {d['name']}* kategorisi eklendi!",
                parse_mode="Markdown", reply_markup=admin_menu())
            return True

        if state == "add_prod_name":
            sessions[uid]["data"]["name"] = text
            sessions[uid]["state"] = "add_prod_cat"
            cats = db.get_categories(is_vip=True)
            from telebot.types import ReplyKeyboardMarkup, KeyboardButton
            m = ReplyKeyboardMarkup(resize_keyboard=True)
            for cat in cats:
                m.add(KeyboardButton(f"{cat['emoji']} {cat['name']}"))
            m.add(KeyboardButton("❌ İptal"))
            bot.send_message(message.chat.id, "Kategori seçin:", reply_markup=m)
            return True

        if state == "add_prod_cat":
            cats = db.get_categories(is_vip=True)
            cat = next((c for c in cats if f"{c['emoji']} {c['name']}" == text or c["name"] == text), None)
            if not cat:
                bot.send_message(message.chat.id, "❌ Geçersiz kategori, tekrar seçin.")
                return True
            sessions[uid]["data"]["category_id"] = cat["id"]
            sessions[uid]["state"] = "add_prod_price"
            bot.send_message(message.chat.id, "💰 Fiyat girin (puan olarak):", reply_markup=cancel_menu())
            return True

        if state == "add_prod_price":
            try:
                sessions[uid]["data"]["price"] = int(text)
            except:
                bot.send_message(message.chat.id, "❌ Sayı girin:")
                return True
            sessions[uid]["state"] = "add_prod_stock"
            bot.send_message(message.chat.id, "📊 Stok girin:\n_(-1 = sınırsız)_", parse_mode="Markdown")
            return True

        if state == "add_prod_stock":
            try:
                sessions[uid]["data"]["stock"] = int(text)
            except:
                bot.send_message(message.chat.id, "❌ Sayı girin:")
                return True
            sessions[uid]["state"] = "add_prod_desc"
            bot.send_message(message.chat.id, "📝 Açıklama girin:\n_(Yok için: -)_", parse_mode="Markdown")
            return True

        if state == "add_prod_desc":
            sessions[uid]["data"]["description"] = None if text in ["-", "Yok"] else text
            sessions[uid]["state"] = "add_prod_content"
            bot.send_message(message.chat.id,
                "📋 Otomatik teslim içeriği girin:\n_(Manuel teslim için: -)_",
                parse_mode="Markdown")
            return True

        if state == "add_prod_content":
            sessions[uid]["data"]["content"] = None if text in ["-", "Yok"] else text
            sessions[uid]["state"] = "add_prod_vip"
            bot.send_message(message.chat.id, "Bu ürün sadece VIP'lere mi özel?", reply_markup=yes_no_menu())
            return True

        if state == "add_prod_vip":
            d = sessions[uid]["data"]
            db.add_product(d["name"], d["category_id"], d["price"], d["stock"],
                           d.get("description"), d.get("content"), text == "✅ Evet")
            sessions[uid] = {"state": "admin"}
            bot.send_message(message.chat.id,
                f"✅ *{d['name']}* ürünü başarıyla eklendi!\n\n"
                f"💰 Fiyat: *{d['price']} Puan*\n"
                f"📊 Stok: *{'Sınırsız' if d['stock'] == -1 else d['stock']}*\n"
                f"📋 Teslim: *{'Otomatik' if d.get('content') else 'Manuel'}*",
                parse_mode="Markdown", reply_markup=admin_menu())
            return True

        if state == "add_coupon_code":
            sessions[uid] = {"state": "add_coupon_value", "data": {"code": text.upper()}}
            bot.send_message(message.chat.id, "💎 Kupon değerini girin (puan):")
            return True

        if state == "add_coupon_value":
            try:
                sessions[uid]["data"]["value"] = int(text)
            except:
                bot.send_message(message.chat.id, "❌ Sayı girin:")
                return True
            sessions[uid]["state"] = "add_coupon_uses"
            bot.send_message(message.chat.id, "🔢 Maksimum kullanım sayısı:")
            return True

        if state == "add_coupon_uses":
            try:
                max_uses = int(text)
            except:
                bot.send_message(message.chat.id, "❌ Sayı girin:")
                return True
            d = sessions[uid]["data"]
            db.create_coupon(d["code"], d["value"], max_uses)
            sessions[uid] = {"state": "admin"}
            bot.send_message(message.chat.id,
                f"✅ *Kupon Oluşturuldu!*\n\n"
                f"🎟️ Kod: `{d['code']}`\n"
                f"💎 Değer: *{d['value']} Puan*\n"
                f"🔢 Kullanım: *{max_uses}x*",
                parse_mode="Markdown", reply_markup=admin_menu())
            return True

        if state == "add_giveaway_title":
            sessions[uid]["data"]["title"] = text
            sessions[uid]["state"] = "add_giveaway_prize"
            bot.send_message(message.chat.id, "🏆 Ödülü girin (örn: 500 Puan):")
            return True

        if state == "add_giveaway_prize":
            sessions[uid]["data"]["prize"] = text
            sessions[uid]["state"] = "add_giveaway_amount"
            bot.send_message(message.chat.id, "💎 Puan ödülü miktarı (para ödülü yoksa 0):")
            return True

        if state == "add_giveaway_amount":
            sessions[uid]["data"]["prize_amount"] = int(text) if text.isdigit() else 0
            sessions[uid]["state"] = "add_giveaway_hours"
            bot.send_message(message.chat.id, "⏰ Kaç saat sürecek?")
            return True

        if state == "add_giveaway_hours":
            try:
                hours = int(text)
            except:
                bot.send_message(message.chat.id, "❌ Sayı girin:")
                return True
            d = sessions[uid]["data"]
            db.create_giveaway(d["title"], d["prize"], d["prize_amount"], hours)
            sessions[uid] = {"state": "admin"}
            bot.send_message(message.chat.id,
                f"✅ *Çekiliş Başlatıldı!*\n\n"
                f"🎁 Başlık: *{d['title']}*\n"
                f"🏆 Ödül: *{d['prize']}*\n"
                f"⏰ Süre: *{hours} saat*",
                parse_mode="Markdown", reply_markup=admin_menu())
            return True

        if state.startswith("complete_order_"):
            order_id = int(state.replace("complete_order_", ""))
            order = db.get_order(order_id)
            db.complete_order(order_id, text)
            sessions[uid] = {"state": "admin"}
            bot.send_message(message.chat.id, f"✅ Sipariş #{order_id} tamamlandı!", reply_markup=admin_menu())
            if order:
                target = db.get_user_by_id(order["user_id"])
                if target:
                    try:
                        bot.send_message(target["telegram_id"],
                            f"📦 *Siparişiniz Teslim Edildi!*\n\n"
                            f"🛍 Ürün: *{order['product_name']}*\n\n"
                            f"📋 *İçerik:*\n`{text}`",
                            parse_mode="Markdown")
                    except:
                        pass
            return True

        if state.startswith("reply_ticket_"):
            ticket_id = int(state.replace("reply_ticket_", ""))
            conn = db.get_conn()
            c = conn.cursor()
            c.execute("SELECT * FROM support_tickets WHERE id=?", (ticket_id,))
            ticket = c.fetchone()
            conn.close()
            if ticket:
                target = db.get_user_by_id(ticket["user_id"])
                db.close_ticket(ticket_id, text)
                if target:
                    try:
                        bot.send_message(target["telegram_id"],
                            f"📩 *Destek Talebiniz Yanıtlandı!*\n\n"
                            f"📌 Konu: _{ticket['subject']}_\n"
                            f"💬 Yanıt:\n{text}",
                            parse_mode="Markdown")
                    except:
                        pass
            sessions[uid] = {"state": "admin"}
            bot.send_message(message.chat.id, "✅ Yanıt gönderildi ve talep kapatıldı!", reply_markup=admin_menu())
            return True

        return False

    return handle_admin_text, is_admin
