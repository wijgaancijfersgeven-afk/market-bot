import telebot
import database as db
from keyboards import (
    admin_menu, founder_menu, cancel_menu, yes_no_menu,
    pending_action_inline, channel_list_inline,
    manage_products_inline, manage_categories_inline
)

FOUNDER_ID = db.FOUNDER_ID


def register_admin_handlers(bot: telebot.TeleBot, sessions: dict):

    def _is_admin(uid):
        return db.is_admin(uid)

    def _is_founder(uid):
        return db.is_founder(uid)

    def _panel_menu(uid):
        return founder_menu() if _is_founder(uid) else admin_menu()

    def _notify_founder(text, markup=None):
        try:
            bot.send_message(FOUNDER_ID, text, parse_mode="Markdown", reply_markup=markup)
        except Exception:
            pass

    # ── Komutlar ──────────────────────────────────────────

    @bot.message_handler(commands=["admin"])
    def admin_cmd(message):
        uid = message.from_user.id
        if not _is_admin(uid):
            bot.send_message(message.chat.id, "❌ Yetkisiz erişim.")
            return
        sessions[uid] = {"state": "admin"}
        role = "👑 Kurucu" if _is_founder(uid) else "🔧 Admin"
        bot.send_message(message.chat.id,
            f"{role} *Paneli*\n\nHoş geldin!",
            parse_mode="Markdown", reply_markup=_panel_menu(uid))

    @bot.message_handler(commands=["vip"])
    def vip_cmd(message):
        uid = message.from_user.id
        if not _is_admin(uid):
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
            bot.send_message(int(parts[1]), "🎉 *VIP üyeliğiniz aktif edildi!* 👑", parse_mode="Markdown")
        except Exception:
            pass

    @bot.message_handler(commands=["addpoints"])
    def addpoints_cmd(message):
        uid = message.from_user.id
        if not _is_admin(uid):
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
        except Exception:
            pass

    @bot.message_handler(commands=["addadmin"])
    def addadmin_cmd(message):
        uid = message.from_user.id
        if not _is_founder(uid):
            bot.send_message(message.chat.id, "❌ Sadece kurucu admin ekleyebilir.")
            return
        parts = message.text.split()
        if len(parts) < 2:
            bot.send_message(message.chat.id, "Kullanım: `/addadmin <telegram_id>`", parse_mode="Markdown")
            return
        target_id = int(parts[1])
        if target_id == FOUNDER_ID:
            bot.send_message(message.chat.id, "❌ Kendinizi zaten kurucusunuz.")
            return
        success = db.add_admin(target_id, uid)
        if success:
            bot.send_message(message.chat.id, f"✅ *{target_id}* admin olarak eklendi.", parse_mode="Markdown")
            try:
                bot.send_message(target_id, "🔧 *Admin yetkisi verildi!*\n\n/admin yazarak panele girebilirsiniz.", parse_mode="Markdown")
            except Exception:
                pass
        else:
            bot.send_message(message.chat.id, "⚠️ Bu kullanıcı zaten admin.")

    @bot.message_handler(commands=["removeadmin"])
    def removeadmin_cmd(message):
        uid = message.from_user.id
        if not _is_founder(uid):
            bot.send_message(message.chat.id, "❌ Sadece kurucu admin çıkarabilir.")
            return
        parts = message.text.split()
        if len(parts) < 2:
            bot.send_message(message.chat.id, "Kullanım: `/removeadmin <telegram_id>`", parse_mode="Markdown")
            return
        target_id = int(parts[1])
        db.remove_admin(target_id)
        bot.send_message(message.chat.id, f"✅ *{target_id}* admin listesinden çıkarıldı.", parse_mode="Markdown")
        try:
            bot.send_message(target_id, "⚠️ Admin yetkiniz kaldırıldı.")
        except Exception:
            pass

    @bot.message_handler(commands=["broadcast"])
    def broadcast_cmd(message):
        uid = message.from_user.id
        if not _is_admin(uid):
            return
        text = message.text.replace("/broadcast", "", 1).strip()
        if not text:
            bot.send_message(message.chat.id, "Kullanım: `/broadcast <mesaj>`", parse_mode="Markdown")
            return
        users = db.get_all_users()
        bot.send_message(message.chat.id, f"📢 Yayın başlıyor... *{len(users)} kullanıcı*", parse_mode="Markdown")
        sent, failed = 0, 0
        for target_uid in users:
            try:
                bot.send_message(target_uid, f"📢 *Duyuru*\n\n{text}", parse_mode="Markdown")
                sent += 1
            except Exception:
                failed += 1
        bot.send_message(message.chat.id, f"✅ Gönderildi: *{sent}*\n❌ Başarısız: *{failed}*", parse_mode="Markdown")

    # ── Admin metin akışları ───────────────────────────────

    def handle_admin_text(message, sess):
        state = sess.get("state", "")
        text = message.text
        uid = message.from_user.id
        is_fndr = _is_founder(uid)

        if text == "❌ İptal":
            sessions[uid] = {"state": "admin"}
            bot.send_message(message.chat.id, "❌ İptal edildi.", reply_markup=_panel_menu(uid))
            return True

        # ── Ana panel butonları ────────────────────────────

        if text == "📊 İstatistikler":
            s = db.get_stats()
            o = db.get_order_stats()
            channels = db.get_all_channels()
            ch_txt = ", ".join(channels) if channels else "Ayarlanmadı"
            admins = db.get_admins()
            bot.send_message(message.chat.id,
                f"📊 *İstatistikler*\n\n"
                f"┌ 👥 Toplam Kullanıcı: *{s['total_users']}*\n"
                f"├ 👑 VIP: *{s['vip_users']}*\n"
                f"├ 🚫 Banlı: *{s['banned_users']}*\n"
                f"└ 💎 Toplam Puan: *{s['total_balance']}*\n\n"
                f"┌ 📦 Toplam Sipariş: *{o['total']}*\n"
                f"├ ⏳ Bekleyen: *{o['pending']}*\n"
                f"└ 💰 Toplam Ciro: *{o['revenue']} Puan*\n\n"
                f"👥 Adminler: *{len(admins)} kişi*\n"
                f"📢 Zorunlu Kanallar: *{ch_txt}*",
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

        if text == "🗑 Ürün Yönet":
            products = db.get_all_products()
            bot.send_message(message.chat.id,
                f"🗑 *Ürün Yönetimi* ({len(products)} ürün)\n\n"
                f"Düzenlemek istediğin ürüne tıkla:",
                parse_mode="Markdown",
                reply_markup=manage_products_inline(products))
            return True

        if text == "🗑 Kategori Yönet":
            cats = db.get_all_categories()
            bot.send_message(message.chat.id,
                f"🗑 *Kategori Yönetimi* ({len(cats)} kategori)\n\n"
                f"Düzenlemek istediğin kategoriye tıkla:",
                parse_mode="Markdown",
                reply_markup=manage_categories_inline(cats))
            return True

        if text == "🎟️ Kupon Oluştur":
            sessions[uid] = {"state": "add_coupon_code"}
            bot.send_message(message.chat.id, "🎟️ *Yeni Kupon*\n\nKupon kodunu girin (büyük harf):", parse_mode="Markdown", reply_markup=cancel_menu())
            return True

        if text == "🎁 Çekiliş Başlat":
            sessions[uid] = {"state": "add_giveaway_title", "data": {}}
            bot.send_message(message.chat.id, "🎁 *Yeni Çekiliş*\n\nÇekiliş başlığını girin:", parse_mode="Markdown", reply_markup=cancel_menu())
            return True

        # ── Kullanıcı Engelleme (Admin → Kurucu onayına gider) ──

        if text == "🚫 Kullanıcı Engelle":
            sessions[uid] = {"state": "ban_user_id"}
            bot.send_message(message.chat.id,
                "🚫 *Kullanıcı Engelle*\n\nEngellemek istediğiniz kullanıcının Telegram ID'sini girin:",
                parse_mode="Markdown", reply_markup=cancel_menu())
            return True

        if text == "✅ Engel Kaldır":
            sessions[uid] = {"state": "unban_user_id"}
            bot.send_message(message.chat.id,
                "✅ *Engel Kaldır*\n\nEngelini kaldırmak istediğiniz kullanıcının Telegram ID'sini girin:",
                parse_mode="Markdown", reply_markup=cancel_menu())
            return True

        # ── Kanal Yönetimi ──────────────────────────────────

        if text == "📢 Kanal Yönet" and is_fndr:
            channels = db.get_all_channels()
            if not channels:
                msg = "📢 *Zorunlu Kanal Yönetimi*\n\nHenüz kanal eklenmemiş.\n\nEklemek için kanal adını girin (örn: @kanaladi):"
                sessions[uid] = {"state": "founder_add_channel"}
                bot.send_message(message.chat.id, msg, parse_mode="Markdown", reply_markup=cancel_menu())
            else:
                ch_list = "\n".join([f"• {ch}" for ch in channels])
                bot.send_message(message.chat.id,
                    f"📢 *Zorunlu Kanallar*\n\n{ch_list}",
                    parse_mode="Markdown",
                    reply_markup=channel_list_inline(channels))
            return True

        if text == "📢 Kanal Öner" and not is_fndr:
            sessions[uid] = {"state": "admin_suggest_channel"}
            bot.send_message(message.chat.id,
                "📢 *Kanal Öner*\n\nEklemek istediğiniz kanalı girin (örn: @kanaladi):\n\n"
                "_Kurucuya onay için gönderilecektir._",
                parse_mode="Markdown", reply_markup=cancel_menu())
            return True

        # ── Admin Yönetimi (Sadece Kurucu) ──────────────────

        if text == "👥 Admin Yönet" and is_fndr:
            admins = db.get_admins()
            if not admins:
                msg = "👥 *Admin Listesi*\n\nHenüz admin yok.\n\n`/addadmin <telegram_id>` ile ekleyebilirsiniz."
                bot.send_message(message.chat.id, msg, parse_mode="Markdown")
            else:
                lines = []
                for a in admins:
                    lines.append(f"• `{a['telegram_id']}` — {a['added_at'][:10]}")
                bot.send_message(message.chat.id,
                    f"👥 *Admin Listesi* ({len(admins)} kişi)\n\n" + "\n".join(lines) + "\n\n"
                    f"Eklemek: `/addadmin <id>`\nÇıkarmak: `/removeadmin <id>`",
                    parse_mode="Markdown")
            return True

        # ── Onay Bekleyenler (Sadece Kurucu) ─────────────────

        if text == "⏳ Onay Bekleyenler" and is_fndr:
            actions = db.get_pending_actions_list()
            if not actions:
                bot.send_message(message.chat.id, "✅ Onay bekleyen işlem yok!")
                return True
            for a in actions:
                admin_user = db.get_user(a["requested_by"])
                admin_name = admin_user["first_name"] if admin_user else str(a["requested_by"])
                action_labels = {
                    "ban_user": "🚫 Kullanıcı Engelle",
                    "unban_user": "✅ Engel Kaldır",
                    "add_channel": "📢 Kanal Ekle",
                }
                label = action_labels.get(a["action_type"], a["action_type"])
                detail = f"`{a['extra_data']}`" if a["extra_data"] else f"Hedef ID: `{a['target_id']}`"
                bot.send_message(message.chat.id,
                    f"⏳ *Onay Bekleniyor #{a['id']}*\n\n"
                    f"İşlem: *{label}*\n"
                    f"İsteyen Admin: *{admin_name}*\n"
                    f"Detay: {detail}\n"
                    f"Tarih: {a['created_at'][:16]}",
                    parse_mode="Markdown",
                    reply_markup=pending_action_inline(a["id"], label))
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

        if state == "ban_user_id":
            try:
                target_tid = int(text.strip())
            except ValueError:
                bot.send_message(message.chat.id, "❌ Geçersiz ID. Sayı girin:")
                return True
            if target_tid == FOUNDER_ID:
                bot.send_message(message.chat.id, "❌ Kurucuyu engelleyemezsiniz!")
                sessions[uid] = {"state": "admin"}
                bot.send_message(message.chat.id, "↩️", reply_markup=_panel_menu(uid))
                return True
            target = db.get_user(target_tid)
            if not target:
                bot.send_message(message.chat.id, "❌ Kullanıcı bulunamadı!")
                return True

            if is_fndr:
                db.ban_user(target["id"], True)
                sessions[uid] = {"state": "admin"}
                bot.send_message(message.chat.id,
                    f"🚫 *{target['first_name']}* engellendi!",
                    parse_mode="Markdown", reply_markup=_panel_menu(uid))
                try:
                    bot.send_message(target_tid, "🚫 Hesabınız engellenmiştir.")
                except Exception:
                    pass
            else:
                action_id = db.create_pending_action("ban_user", uid, target["id"], f"{target['first_name']} ({target_tid})")
                sessions[uid] = {"state": "admin"}
                bot.send_message(message.chat.id,
                    f"⏳ *Engelleme isteği kurucuya gönderildi.*\n\nKurucu onayladığında işlem gerçekleşecek.",
                    parse_mode="Markdown", reply_markup=_panel_menu(uid))
                admin_user = db.get_user(uid)
                admin_name = admin_user["first_name"] if admin_user else str(uid)
                _notify_founder(
                    f"⚠️ *Onay Gerekiyor #{action_id}*\n\n"
                    f"🔧 Admin *{admin_name}* şu kullanıcıyı engellemek istiyor:\n"
                    f"👤 *{target['first_name']}* (`{target_tid}`)",
                    pending_action_inline(action_id, "🚫 Kullanıcı Engelle")
                )
            return True

        if state == "unban_user_id":
            try:
                target_tid = int(text.strip())
            except ValueError:
                bot.send_message(message.chat.id, "❌ Geçersiz ID. Sayı girin:")
                return True
            target = db.get_user(target_tid)
            if not target:
                bot.send_message(message.chat.id, "❌ Kullanıcı bulunamadı!")
                return True

            if is_fndr:
                db.ban_user(target["id"], False)
                sessions[uid] = {"state": "admin"}
                bot.send_message(message.chat.id,
                    f"✅ *{target['first_name']}* engeli kaldırıldı!",
                    parse_mode="Markdown", reply_markup=_panel_menu(uid))
                try:
                    bot.send_message(target_tid, "✅ Hesabınızın engeli kaldırıldı.")
                except Exception:
                    pass
            else:
                action_id = db.create_pending_action("unban_user", uid, target["id"], f"{target['first_name']} ({target_tid})")
                sessions[uid] = {"state": "admin"}
                bot.send_message(message.chat.id,
                    f"⏳ *Engel kaldırma isteği kurucuya gönderildi.*",
                    parse_mode="Markdown", reply_markup=_panel_menu(uid))
                admin_user = db.get_user(uid)
                admin_name = admin_user["first_name"] if admin_user else str(uid)
                _notify_founder(
                    f"⚠️ *Onay Gerekiyor #{action_id}*\n\n"
                    f"🔧 Admin *{admin_name}* şu kullanıcının engelini kaldırmak istiyor:\n"
                    f"👤 *{target['first_name']}* (`{target_tid}`)",
                    pending_action_inline(action_id, "✅ Engel Kaldır")
                )
            return True

        if state == "admin_suggest_channel":
            channel = text.strip()
            if not channel.startswith("@"):
                channel = "@" + channel
            action_id = db.create_pending_action("add_channel", uid, None, channel)
            sessions[uid] = {"state": "admin"}
            bot.send_message(message.chat.id,
                f"⏳ *Kanal ekleme isteği kurucuya gönderildi.*\n\nKanal: *{channel}*",
                parse_mode="Markdown", reply_markup=_panel_menu(uid))
            admin_user = db.get_user(uid)
            admin_name = admin_user["first_name"] if admin_user else str(uid)
            _notify_founder(
                f"⚠️ *Onay Gerekiyor #{action_id}*\n\n"
                f"🔧 Admin *{admin_name}* şu kanalı eklemek istiyor:\n"
                f"📢 *{channel}*",
                pending_action_inline(action_id, "📢 Kanal Ekle")
            )
            return True

        if state == "founder_add_channel":
            channel = text.strip()
            if not channel.startswith("@"):
                channel = "@" + channel
            db.add_channel(channel)
            sessions[uid] = {"state": "admin"}
            bot.send_message(message.chat.id,
                f"✅ *{channel}* zorunlu kanallara eklendi!",
                parse_mode="Markdown", reply_markup=_panel_menu(uid))
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
                parse_mode="Markdown", reply_markup=_panel_menu(uid))
            return True

        if state == "add_prod_name":
            sessions[uid]["data"]["name"] = text
            sessions[uid]["state"] = "add_prod_price"
            bot.send_message(message.chat.id, "💰 Fiyatı girin (Puan):")
            return True

        if state == "add_prod_price":
            try:
                sessions[uid]["data"]["price"] = int(text)
            except ValueError:
                bot.send_message(message.chat.id, "❌ Geçerli bir sayı girin:")
                return True
            sessions[uid]["state"] = "add_prod_stock"
            bot.send_message(message.chat.id, "📊 Stok girin (-1 = sınırsız):")
            return True

        if state == "add_prod_stock":
            try:
                sessions[uid]["data"]["stock"] = int(text)
            except ValueError:
                bot.send_message(message.chat.id, "❌ Geçerli bir sayı girin:")
                return True
            sessions[uid]["state"] = "add_prod_desc"
            bot.send_message(message.chat.id, "📝 Açıklama girin (yoksa - yaz):")
            return True

        if state == "add_prod_desc":
            sessions[uid]["data"]["desc"] = text if text != "-" else ""
            sessions[uid]["state"] = "add_prod_content"
            bot.send_message(message.chat.id, "📋 Teslim içeriği girin (yoksa - yaz):")
            return True

        if state == "add_prod_content":
            sessions[uid]["data"]["content"] = text if text != "-" else ""
            sessions[uid]["state"] = "add_prod_vip"
            bot.send_message(message.chat.id, "Bu ürün sadece VIP'lere mi özel?", reply_markup=yes_no_menu())
            return True

        if state == "add_prod_vip":
            d = sessions[uid]["data"]
            cats = db.get_categories(is_vip=True)
            sessions[uid]["state"] = "add_prod_cat"
            sessions[uid]["data"]["is_vip"] = (text == "✅ Evet")
            from telebot.types import ReplyKeyboardMarkup, KeyboardButton
            m = ReplyKeyboardMarkup(resize_keyboard=True)
            for cat in cats:
                m.add(KeyboardButton(f"{cat['emoji']} {cat['name']}"))
            m.add(KeyboardButton("❌ İptal"))
            bot.send_message(message.chat.id, "📁 Kategori seçin:", reply_markup=m)
            return True

        if state == "add_prod_cat":
            cats = db.get_categories(is_vip=True)
            cat = next((c for c in cats if f"{c['emoji']} {c['name']}" == text or c["name"] == text), None)
            if not cat:
                bot.send_message(message.chat.id, "❌ Geçerli bir kategori seçin.")
                return True
            d = sessions[uid]["data"]
            db.add_product(d["name"], cat["id"], d["price"], d["stock"], d.get("desc"), d.get("content"), d.get("is_vip", False))
            sessions[uid] = {"state": "admin"}
            bot.send_message(message.chat.id,
                f"✅ *{d['name']}* ürünü eklendi!",
                parse_mode="Markdown", reply_markup=_panel_menu(uid))
            return True

        if state == "add_coupon_code":
            sessions[uid] = {"state": "add_coupon_value", "data": {"code": text.upper()}}
            bot.send_message(message.chat.id, "💎 Kupon değerini girin (Puan):")
            return True

        if state == "add_coupon_value":
            try:
                sessions[uid]["data"]["value"] = int(text)
            except ValueError:
                bot.send_message(message.chat.id, "❌ Geçerli bir sayı girin:")
                return True
            sessions[uid]["state"] = "add_coupon_uses"
            bot.send_message(message.chat.id, "🔢 Maksimum kullanım sayısı:")
            return True

        if state == "add_coupon_uses":
            try:
                max_uses = int(text)
            except ValueError:
                bot.send_message(message.chat.id, "❌ Geçerli bir sayı girin:")
                return True
            d = sessions[uid]["data"]
            db.create_coupon(d["code"], d["value"], max_uses)
            sessions[uid] = {"state": "admin"}
            bot.send_message(message.chat.id,
                f"✅ Kupon *{d['code']}* oluşturuldu!\n💎 Değer: *{d['value']} Puan*\n🔢 Max kullanım: *{max_uses}*",
                parse_mode="Markdown", reply_markup=_panel_menu(uid))
            return True

        if state == "add_giveaway_title":
            sessions[uid]["data"]["title"] = text
            sessions[uid]["state"] = "add_giveaway_prize"
            bot.send_message(message.chat.id, "🏆 Ödülü girin:")
            return True

        if state == "add_giveaway_prize":
            sessions[uid]["data"]["prize"] = text
            sessions[uid]["state"] = "add_giveaway_hours"
            bot.send_message(message.chat.id, "⏰ Kaç saat sürecek?")
            return True

        if state == "add_giveaway_hours":
            try:
                hours = int(text)
            except ValueError:
                bot.send_message(message.chat.id, "❌ Geçerli bir sayı girin:")
                return True
            d = sessions[uid]["data"]
            db.create_giveaway(d["title"], d["prize"], 0, hours)
            sessions[uid] = {"state": "admin"}
            bot.send_message(message.chat.id,
                f"🎉 Çekiliş *{d['title']}* başlatıldı! ({hours} saat)",
                parse_mode="Markdown", reply_markup=_panel_menu(uid))
            return True

        if state.startswith("set_stock_"):
            pid = int(state.replace("set_stock_", ""))
            try:
                stock = int(text.strip())
            except ValueError:
                bot.send_message(message.chat.id, "❌ Geçerli bir sayı girin (-1 = sınırsız):")
                return True
            db.update_product_stock(pid, stock)
            p = db.get_product(pid)
            sessions[uid] = {"state": "admin"}
            stock_txt = "∞ Sınırsız" if stock == -1 else f"{stock} adet"
            bot.send_message(message.chat.id,
                f"✅ *{p['name']}* stoğu güncellendi: *{stock_txt}*",
                parse_mode="Markdown", reply_markup=_panel_menu(uid))
            return True

        if state.startswith("complete_order_"):
            oid = int(state.replace("complete_order_", ""))
            order = db.get_order(oid)
            if order:
                db.complete_order(oid, text)
                user = db.get_user_by_id(order["user_id"])
                sessions[uid] = {"state": "admin"}
                bot.send_message(message.chat.id,
                    f"✅ *Sipariş #{oid}* teslim edildi!",
                    parse_mode="Markdown", reply_markup=_panel_menu(uid))
                if user:
                    try:
                        bot.send_message(user["telegram_id"],
                            f"✅ *Siparişiniz Teslim Edildi!*\n\n"
                            f"📦 Ürün: *{order['product_name']}*\n"
                            f"📋 İçerik:\n`{text}`",
                            parse_mode="Markdown")
                    except Exception:
                        pass
            return True

        if state.startswith("reply_ticket_"):
            tid = int(state.replace("reply_ticket_", ""))
            db.close_ticket(tid, text)
            ticket = db.get_open_tickets()
            conn_t = db.get_conn()
            c_t = conn_t.cursor()
            c_t.execute("SELECT * FROM support_tickets WHERE id=?", (tid,))
            t_row = c_t.fetchone()
            conn_t.close()
            if t_row:
                user = db.get_user_by_id(dict(t_row)["user_id"])
                if user:
                    try:
                        bot.send_message(user["telegram_id"],
                            f"✅ *Destek Talebiniz Yanıtlandı*\n\n"
                            f"📌 Konu: {dict(t_row)['subject']}\n"
                            f"💬 Yanıt: {text}",
                            parse_mode="Markdown")
                    except Exception:
                        pass
            sessions[uid] = {"state": "admin"}
            bot.send_message(message.chat.id, f"✅ Talep #{tid} yanıtlandı ve kapatıldı.",
                reply_markup=_panel_menu(uid))
            return True

        return False

    return handle_admin_text, _is_admin
