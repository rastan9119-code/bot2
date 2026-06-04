import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

OWNER_ID = 7831930591

DATABASE_NAME = "data/bot.db"
BACKUP_FOLDER = "data/backup"
LOG_FILE = "logs/errors.log"

MAX_MESSAGES_PER_MINUTE = 10

WELCOME_TEXT = """
🌹 به ربات خوش آمدید

از منوی زیر استفاده کنید.
"""

DEFAULT_FEATURES = {
    "music_enabled": True,
    "vpn_enabled": True,
    "wallet_enabled": True,
    "support_enabled": True,
    "owner_panel_enabled": True,
}
