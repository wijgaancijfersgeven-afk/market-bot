╔══════════════════════════════════════╗
║     MARKET BOT — KURULUM REHBERİ    ║
╚══════════════════════════════════════╝

▌GEREKSINIMLER
  Python 3.10 veya üstü

▌KURULUM

  1. Kütüphaneleri yükle:
     pip install -r requirements.txt

  2. .env dosyası oluştur:
     cp .env.example .env
     nano .env   ← token, admin id ve bot adını yaz

  3. Botu başlat:
     python bot.py

▌.env DOSYASI İÇERİĞİ

  TELEGRAM_BOT_TOKEN=BotFather'dan aldığın token
  ADMIN_IDS=Telegram ID'in (virgülle birden fazla eklenebilir)
  BOT_NAME=İstediğin bot adı   ← "Dextroo" yerine ne istersen

▌7/24 VDS'DE ÇALIŞTIRMA

  ── Yöntem A: screen (hızlı) ──────────────
  screen -S market-bot
  python bot.py
  Ctrl+A, D   ← arka plana al

  Geri dönmek için: screen -r market-bot

  ── Yöntem B: systemd (önerilen) ──────────
  sudo nano /etc/systemd/system/marketbot.service

  içine yapıştır:
  ───────────────────────────────────────────
  [Unit]
  Description=Market Telegram Bot
  After=network.target

  [Service]
  WorkingDirectory=/root/market-bot
  ExecStart=/usr/bin/python3 /root/market-bot/bot.py
  Restart=always
  RestartSec=5
  EnvironmentFile=/root/market-bot/.env

  [Install]
  WantedBy=multi-user.target
  ───────────────────────────────────────────

  Kaydet, sonra çalıştır:
  sudo systemctl daemon-reload
  sudo systemctl enable marketbot
  sudo systemctl start marketbot
  sudo systemctl status marketbot   ← aktif mi kontrol et

▌ADMIN KOMUTLARI

  /admin                       → Admin panelini aç
  /vip <telegram_id>           → Kullanıcıyı VIP yap
  /addpoints <id> <miktar>     → Puan ekle
  /ban <telegram_id>           → Kullanıcıyı banla
  /unban <telegram_id>         → Banı kaldır
  /broadcast <mesaj>           → Herkese duyuru gönder

  Admin panelinden yapabileceklerin:
  ├ 📊 İstatistik görüntüle
  ├ 📦 Bekleyen siparişleri teslim et
  ├ ➕ Kategori & ürün ekle
  ├ 🎟️ Kupon kodu oluştur
  ├ 🎁 Çekiliş başlat
  ├ 📢 Zorunlu kanal ayarla / kaldır
  └ 🆘 Destek taleplerini yanıtla

▌ZORUNLU KANAL ÖZELLİĞİ

  Admin panelinde "📢 Kanal Ayarla" butonuna bas.
  Kanal kullanıcı adını gir: @kanaladi
  Artık kullanıcılar kanala üye olmadan botu kullanamaz.
  Kanalı kaldırmak için aynı menüden "🗑 Kanalı Kaldır" seç.

▌DOSYA YAPISI

  bot.py           → Ana bot (giriş noktası)
  database.py      → SQLite veritabanı işlemleri
  keyboards.py     → Tüm klavye şablonları
  handlers/
    admin.py       → Admin panel akışları
  requirements.txt
  .env             → Gizli ayarlar (kendin oluştur)
  bot.db           → Veritabanı (ilk çalıştırmada otomatik oluşur)
