import os

# ⚠️ Apna actual Bot Token aur Numeric Admin ID yahan dalein ya Railway Environment Variables me set karein.
BOT_TOKEN = os.getenv("BOT_TOKEN", "8887238154:AAF5BvLiZkMOpjRM0P9luYSSSxTD4qbE0rI")
ADMIN_ID = int(os.getenv("ADMIN_ID", "7709767483"))

# Database configurations
DB_NAME = "permanent_bot_data.db"
