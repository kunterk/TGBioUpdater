#!/usr/bin/env python3
"""
Async Telegram Bio Scrobbler (Hybrid Optimized Edition)

Features:
- Async I/O (aiohttp + Pyrogram) for better performance
- Hybrid Failsafe: Option 3 (Local State) + Option 1 (Invisible Marker) + 24 Hours Manual Override
- Graceful Shutdown handling (SIGINT/SIGTERM)
- Structured Logging
"""

import os
import time
import json
import asyncio
import logging
import signal
import sys
import textwrap
from typing import Optional, Dict, Any

import aiohttp
from pyrogram import Client
from pyrogram.errors import FloodWait

# --- Configuration & Environment Validation ---
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "30"))  # Default 30s untuk elak Rate Limit
TRUNCATE_LEN = int(os.environ.get("BIO_MAX_LEN", "140"))    # Default 140 aksara mengikut Telegram Bio

def get_env(name: str, required: bool = True) -> Optional[str]:
    val = os.environ.get(name)
    if required and (val is None or val == ""):
        print(f"[ERROR] Missing required environment variable: {name}")
        sys.exit(1)
    return val

try:
    API_ID = int(get_env("API_ID"))
    API_HASH = get_env("API_HASH")
    LASTFM_API_KEY = get_env("LASTFM_API_KEY")
    LASTFM_USERNAME = get_env("LASTFM_USERNAME")
    SESSION_STRING = get_env("SESSION_STRING")
except (ValueError, SystemExit) as e:
    print(f"[ERROR] Environment variable validation failed: {e}")
    sys.exit(1)

# --- Logging Setup (Structured) ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("bio-scrobbler")

# --- Constants & State File ---
INVISIBLE_MARKER = "\u200b"  # Zero-width space marker
STATE_FILE = "bot_state.json"
EXPIRATION_SECONDS = 24 * 3600  # 24 Jam

# --- Pyrogram Client Setup ---
app = Client(
    "my_account",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING,
    no_updates=True,
)

LASTFM_URL = "https://ws.audioscrobbler.com/2.0/"

# --- Helper Functions ---
def get_state() -> Dict[str, Any]:
    """Load state from file or return default."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("Gagal membaca %s: %s. Menggunakan state default.", STATE_FILE, e)
    return {"last_song": "", "manual_timestamp": 0}

def save_state(last_song: str, manual_timestamp: float) -> None:
    """Save state to file."""
    try:
        with open(STATE_FILE, "w") as f:
            json.dump({"last_song": last_song, "manual_timestamp": manual_timestamp}, f)
    except Exception as e:
        logger.error("Gagal menyimpan state ke %s: %s", STATE_FILE, e)

def safe_truncate(s: str, max_len: int) -> str:
    """Safely truncate string to max length without breaking word bounds."""
    try:
        return textwrap.shorten(s, width=max_len, placeholder="…")
    except Exception:
        if len(s) <= max_len:
            return s
        return s[:max_len - 1] + "…"

async def fetch_now_playing(session: aiohttp.ClientSession) -> Optional[str]:
    """Fetch now playing track from Last.fm API (async)."""
    params = {
        "method": "user.getrecenttracks",
        "user": LASTFM_USERNAME,
        "api_key": LASTFM_API_KEY,
        "format": "json",
        "limit": "1",
    }
    headers = {
        "User-Agent": "telegram-bio-scrobbler/2.0"
    }
    
    try:
        async with session.get(LASTFM_URL, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                logger.warning("Last.fm returned HTTP status %s", resp.status)
                return None
            
            data = await resp.json()
            tracks = data.get("recenttracks", {}).get("track", [])
            
            if not tracks:
                return None
            
            track = tracks[0]
            artist = track.get("artist", {})
            if isinstance(artist, dict):
                artist = artist.get("#text", "Unknown")
            
            song = track.get("name", "Unknown")
            now_playing = track.get("@attr", {}).get("nowplaying") == "true"
            
            if now_playing:
                return f"🎶 Playing: {song} - {artist}"
            else:
                return f"📻 Last Played: {song} - {artist}"
    
    except asyncio.TimeoutError:
        logger.warning("Timeout semasa panggilan Last.fm API")
    except Exception as e:
        logger.warning("Ralat dari Last.fm API: %s", e)
    
    return None

# --- Main Scrobbler Loop ---
async def poll_and_update(stop_event: asyncio.Event):
    """Main loop: fetch song status and update Telegram bio."""
    async with aiohttp.ClientSession() as http_session:
        while not stop_event.is_set():
            try:
                song_status = await fetch_now_playing(http_session)
                
                if song_status:
                    state = get_state()
                    current_time = time.time()

                    # OPTION 3: Skip Telegram API jika lagu & status bot belum berubah
                    if song_status == state["last_song"] and state["manual_timestamp"] == 0:
                        logger.info("🎵 Lagu masih sama dalam rekod tempatan. Memotong panggilan API Telegram.")
                    else:
                        try:
                            me = await app.get_chat("me")
                            current_telegram_bio = me.bio or ""

                            is_empty = (current_telegram_bio == "")
                            is_updated_by_bot = current_telegram_bio.endswith(INVISIBLE_MARKER)

                            # OPTION 1: Semak jika Bio KOSONG atau DIKEMAS KINI OLEH BOT
                            if is_empty or is_updated_by_bot:
                                # Potong teks dahulu, kemudian pelekat marker tersembunyi di paling hujung
                                truncated_song = safe_truncate(song_status, TRUNCATE_LEN - 1)
                                new_bio = truncated_song + INVISIBLE_MARKER
                                
                                if current_telegram_bio != new_bio:
                                    await app.update_profile(bio=new_bio)
                                    logger.info("🤖 Bio Telegram dikemas kini -> %s", new_bio)
                                
                                save_state(last_song=song_status, manual_timestamp=0)

                            else:
                                # BIO MANUAL DIKESAN (Tiada marker & tidak kosong)
                                if state["manual_timestamp"] == 0:
                                    save_state(last_song=song_status, manual_timestamp=current_time)
                                    logger.info("👤 Bio manual dikesan. Tempoh 24 jam bermula.")
                                else:
                                    time_elapsed = current_time - state["manual_timestamp"]

                                    if time_elapsed > EXPIRATION_SECONDS:
                                        # Had masa 24 jam tamat! Bot ambil alih
                                        truncated_song = safe_truncate(song_status, TRUNCATE_LEN - 1)
                                        new_bio = truncated_song + INVISIBLE_MARKER
                                        await app.update_profile(bio=new_bio)
                                        save_state(last_song=song_status, manual_timestamp=0)
                                        logger.info("⏰ Bio manual melebihi 24 jam. Bot mengambil alih -> %s", new_bio)
                                    else:
                                        hours_left = round((EXPIRATION_SECONDS - time_elapsed) / 3600, 1)
                                        logger.info("👤 Bio manual masih aktif (Baki masa: %s jam). Bot tidak mengganggu.", hours_left)
                        
                        except FloodWait as fw:
                            wait_seconds = int(getattr(fw, "value", fw.x if hasattr(fw, "x") else 10))
                            logger.warning("Telegram FloodWait dikesan! Berehat selama %s saat...", wait_seconds)
                            await asyncio.sleep(wait_seconds)

            except Exception as e:
                logger.exception("Ralat dalam poll loop: %s", e)

            try:
                await asyncio.wait_for(stop_event.wait(), timeout=POLL_INTERVAL)
            except asyncio.TimeoutError:
                continue

# --- Startup & Shutdown ---
async def main():
    """Main entry point with graceful shutdown."""
    stop_event = asyncio.Event()

    def _signal_handler(*_):
        logger.info("Sinyal penutupan diterima (SIGINT/SIGTERM). Menghentikan bot...")
        stop_event.set()

    if sys.platform != "win32":
        try:
            loop = asyncio.get_running_loop()
            loop.add_signal_handler(signal.SIGINT, _signal_handler)
            loop.add_signal_handler(signal.SIGTERM, _signal_handler)
        except NotImplementedError:
            pass

    try:
        await app.start()
        logger.info("Pyrogram client dimulakan.")
        await poll_and_update(stop_event)
    finally:
        logger.info("Menghentikan Pyrogram client...")
        await app.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot dihentikan oleh pengguna (Ctrl+C).")
    except Exception:
        logger.exception("Ralat kritikal, aplikasi ditamatkan.")
        sys.exit(1)
