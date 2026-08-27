import os
import logging
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = os.environ.get("GUIDE_BOT_TOKEN")
API_ID = os.environ.get("API_ID")
API_HASH = os.environ.get("API_HASH")

COLAB_LINK = "https://colab.research.google.com/drive/1b2hjzn6XlN1fYLPHS8lD-vwn6esrP3d3?usp=sharing"
RENDER_DEPLOY_LINK = "https://render.com/deploy?repo=https://github.com/kunterk/TGBioUpdater"

TEXTS = {
    "MY": {
        "welcome": "👋 **Selamat Datang ke TGBioUpdater!**\n\nSila pilih bahasa anda / Please choose your language:",
        "menu": "🎵 **TGBioUpdater Guide Bot**\n\nBot ini membantu anda mengemas kini Bio Telegram secara automatik mengikut lagu Last.fm anda!\n\nSila pilih **Opsyen Deployment** anda:",
        "opt_a": "🖥️ **Opsyen A: Local PC (Percuma)**\n\n1. Install Python di PC anda.\n2. Git clone repo ini.\n3. Bina fail `.env` menggunakan `.env.example`.\n4. Dapatkan String Session guna Colab:\n👉 [Buka Google Colab Generator]({colab})\n5. Jalankan `python runner.py`.",
        "opt_b": "☁️ **Opsyen B: Render One-Click (Mudah)**\n\n1. Dapatkan Session String anda di Colab:\n👉 [Buka Google Colab Generator]({colab})\n2. Tekan butang di bawah untuk Deploy ke Render secara automatik!",
        "opt_c": "🛠️ **Opsyen C: Manual Render Setup**\n\n1. Fork Repo ini di GitHub.\n2. Dapatkan Session String di Colab:\n👉 [Buka Google Colab Generator]({colab})\n3. Buka Render.com -> New Worker -> Sambungkan Repo Fork anda.\n4. Masukkan Environment Variables secara manual."
    },
    "ID": {
        "welcome": "👋 **Selamat Datang di TGBioUpdater!**\n\nPilih bahasa kamu / Please choose your language:",
        "menu": "🎵 **TGBioUpdater Guide Bot**\n\nBot ini membantu memperbarui Bio Telegram kamu secara otomatis dari Last.fm!\n\nPilih **Opsi Deployment** kamu:",
        "opt_a": "🖥️ **Opsi A: Local PC (Gratis)**\n\n1. Install Python di PC.\n2. Git clone repo ini.\n3. Buat file `.env` dari `.env.example`.\n4. Dapatkan Session String via Colab:\n👉 [Buka Google Colab Generator]({colab})\n5. Jalankan `python runner.py`.",
        "opt_b": "☁️ **Opsi B: Render One-Click (Praktis)**\n\n1. Dapatkan Session String di Colab:\n👉 [Buka Google Colab Generator]({colab})\n2. Klik tombol di bawah untuk Deploy ke Render!",
        "opt_c": "🛠️ **Opsi C: Manual Render Setup**\n\n1. Fork Repo ini di GitHub.\n2. Dapatkan Session String di Colab:\n👉 [Buka Google Colab Generator]({colab})\n3. Buka Render.com -> New Worker -> Sambungkan Repo Fork.\n4. Isi Environment Variables secara manual."
    },
    "ENG": {
        "welcome": "👋 **Welcome to TGBioUpdater!**\n\nPlease select your preferred language:",
        "menu": "🎵 **TGBioUpdater Guide Bot**\n\nThis bot helps you automatically sync your Telegram Bio with Last.fm now playing tracks!\n\nSelect your **Deployment Option**:",
        "opt_a": "🖥️ **Option A: Local PC (Free)**\n\n1. Install Python on your PC.\n2. Git clone this repo.\n3. Create a `.env` file from `.env.example`.\n4. Get Session String via Colab:\n👉 [Open Google Colab Generator]({colab})\n5. Run `python runner.py`.",
        "opt_b": "☁️ **Option B: Render One-Click (Easy)**\n\n1. Get your Session String on Colab:\n👉 [Open Google Colab Generator]({colab})\n2. Click the button below to Deploy to Render!",
        "opt_c": "🛠️ **Option C: Manual Render Setup**\n\n1. Fork this Repo on GitHub.\n2. Get Session String on Colab:\n👉 [Open Google Colab Generator]({colab})\n3. Open Render.com -> New Worker -> Connect your Forked Repo.\n4. Fill in Environment Variables manually."
    }
}

if not BOT_TOKEN:
    logging.info("GUIDE_BOT_TOKEN tidak dijumpai. Skipping Guide Bot execution.")
else:
    app = Client(
        "guide_bot",
        api_id=int(API_ID) if API_ID else None,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN
    )

    @app.on_message(filters.command("start"))
    async def start_cmd(client, message):
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("🇲🇾 Bahasa Melayu", callback_data="lang_MY")],
            [InlineKeyboardButton("🇮🇩 Bahasa Indonesia", callback_data="lang_ID")],
            [InlineKeyboardButton("🇬🇧 English", callback_data="lang_ENG")]
        ])
        await message.reply_text(TEXTS["MY"]["welcome"], reply_markup=buttons)

    @app.on_callback_query(filters.regex("^lang_"))
    async def lang_choice(client, callback):
        lang = callback.data.split("_")[1]
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("🖥️ Option A (Local PC)", callback_data=f"opt_A_{lang}")],
            [InlineKeyboardButton("☁️ Option B (One-Click Render)", callback_data=f"opt_B_{lang}")],
            [InlineKeyboardButton("🛠️ Option C (Manual Render)", callback_data=f"opt_C_{lang}")]
        ])
        await callback.message.edit_text(TEXTS[lang]["menu"], reply_markup=buttons)

    @app.on_callback_query(filters.regex("^opt_"))
    async def opt_choice(client, callback):
        _, opt, lang = callback.data.split("_")
        msg_key = f"opt_{opt.lower()}"
        text = TEXTS[lang][msg_key].format(colab=COLAB_LINK)
        
        buttons = []
        if opt == "B":
            buttons.append([InlineKeyboardButton("🚀 Deploy to Render", url=RENDER_DEPLOY_LINK)])
        buttons.append([InlineKeyboardButton("🔙 Back", callback_data=f"lang_{lang}")])
        
        await callback.message.edit_text(text, reply_markup=buttons, disable_web_page_preview=True)

    if __name__ == "__main__":
        app.run()
