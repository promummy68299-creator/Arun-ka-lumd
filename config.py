import os

# ⚠️ Apna actual Bot Token aur Numeric Admin ID yahan dalein ya Railway Environment Variables me set karein.
BOT_TOKEN = os.getenv("BOT_TOKEN", "8887238154:AAHhKFjzeDbp2vxY6AH3kWGV9WZkTEq8vIw")
ADMIN_ID = int(os.getenv("ADMIN_ID", "7709767483"))

# Database configurations
DB_NAME = "permanent_bot_data.db"
