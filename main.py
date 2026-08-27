#!/usr/bin/env python3
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

POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "30"))
TRUNCATE_LEN = int(os.environ.get("BIO_MAX_LEN", "140"))

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

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("bio-scrobbler")

INVISIBLE_MARKER = "\u200b"
STATE_FILE = "bot_state.json"
EXPIRATION_SECONDS = 24 * 3600

app = Client("my_account", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING, no_updates=True)
LASTFM_URL = "https://ws.audioscrobbler.com/2.0/"

def get_state() -> Dict[str, Any]:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("Gagal membaca %s: %s", STATE_FILE, e)
    return {"last_song": "", "manual_timestamp": 0}

def save_state(last_song: str, manual_timestamp: float) -> None:
    try:
        with open(STATE_FILE, "w") as f:
            json.dump({"last_song": last_song, "manual_timestamp": manual_timestamp}, f)
    except Exception as e:
        logger.error("Gagal menyimpan state: %s", e)

def safe_truncate(s: str, max_len: int) -> str:
    try:
        return textwrap.shorten(s, width=max_len, placeholder="…")
    except Exception:
        return s if len(s) <= max_len else s[:max_len - 1] + "…"

async def fetch_now_playing(session: aiohttp.ClientSession) -> Optional[str]:
    params = {"method": "user.getrecenttracks", "user": LASTFM_USERNAME, "api_key": LASTFM_API_KEY, "format": "json", "limit": "1"}
    headers = {"User-Agent": "telegram-bio-scrobbler/2.0"}
    try:
        async with session.get(LASTFM_URL, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            tracks = data.get("recenttracks", {}).get("track", [])
            if not tracks:
                return None
            track = tracks[0]
            artist = track.get("artist", {}).get("#text", "Unknown") if isinstance(track.get("artist"), dict) else "Unknown"
            song = track.get("name", "Unknown")
            now_playing = track.get("@attr", {}).get("nowplaying") == "true"
            return f"🎶 Playing: {song} - {artist}" if now_playing else f"📻 Last Played: {song} - {artist}"
    except Exception as e:
        logger.warning("Ralat Last.fm API: %s", e)
    return None

async def poll_and_update(stop_event: asyncio.Event):
    async with aiohttp.ClientSession() as http_session:
        while not stop_event.is_set():
            try:
                song_status = await fetch_now_playing(http_session)
                if song_status:
                    state = get_state()
                    current_time = time.time()
                    if song_status == state["last_song"] and state["manual_timestamp"] == 0:
                        logger.info("🎵 Lagu sama, skip API call.")
                    else:
                        try:
                            me = await app.get_chat("me")
                            current_telegram_bio = me.bio or ""
                            is_empty = (current_telegram_bio == "")
                            is_updated_by_bot = current_telegram_bio.endswith(INVISIBLE_MARKER)

                            if is_empty or is_updated_by_bot:
                                truncated_song = safe_truncate(song_status, TRUNCATE_LEN - 1)
                                new_bio = truncated_song + INVISIBLE_MARKER
                                if current_telegram_bio != new_bio:
                                    await app.update_profile(bio=new_bio)
                                    logger.info("🤖 Bio dikemas kini -> %s", new_bio)
                                save_state(last_song=song_status, manual_timestamp=0)
                            else:
                                if state["manual_timestamp"] == 0:
                                    save_state(last_song=song_status, manual_timestamp=current_time)
                                    logger.info("👤 Bio manual dikesan.")
                                else:
                                    if (current_time - state["manual_timestamp"]) > EXPIRATION_SECONDS:
                                        truncated_song = safe_truncate(song_status, TRUNCATE_LEN - 1)
                                        new_bio = truncated_song + INVISIBLE_MARKER
                                        await app.update_profile(bio=new_bio)
                                        save_state(last_song=song_status, manual_timestamp=0)
                                        logger.info("⏰ 24 jam tamat, bot mengambil alih.")
                        except FloodWait as fw:
                            wait_seconds = int(getattr(fw, "value", fw.x if hasattr(fw, "x") else 10))
                            await asyncio.sleep(wait_seconds)
            except Exception as e:
                logger.exception("Ralat poll loop: %s", e)
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=POLL_INTERVAL)
            except asyncio.TimeoutError:
                continue

async def main():
    stop_event = asyncio.Event()
    def _signal_handler(*_):
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
        logger.info("Pyrogram dimulakan.")
        await poll_and_update(stop_event)
    finally:
        await app.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
