import telebot
from telebot import types
import logging
import io
import qrcode
import urllib.parse
import datetime
import time
import config
import database as db

# --- 1. INITIALIZATION & LOGGING ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
bot = telebot.TeleBot(config.BOT_TOKEN, parse_mode="HTML")
admin_wizards = {}

def is_admin(user_id): return user_id == config.ADMIN_ID

# --- 2. ENHANCED UI: PLAN DISPLAY ---
def build_user_plans_keyboard():
    plans = db.db_get_plans()
    markup = types.InlineKeyboardMarkup(row_width=1)
    for p in plans:
        # Bada size: Plan details saaf aur attractive
        btn_text = f"💎 PLAN: {p[1]} 💎\n💰 PRICE: ₹{p[2]} | ⏳ DURATION: {p[3]}"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"buy_now_{p[0]}"))
    markup.row(types.InlineKeyboardButton("🎬 View Demo Reels", callback_data="user_global_demo"),
               types.InlineKeyboardButton("🚨 Report Issue", callback_data="user_report_issue"))
    return markup

def generate_upi_qr(upi_id, payee_name, price, plan_name):
    encoded_name = urllib.parse.quote(payee_name)
    upi_url = f"upi://pay?pa={upi_id}&pn={encoded_name}&am={price}&cu=INR&tn=Plan_{plan_name}"
    qr = qrcode.QRCode(box_size=10, border=4)
    qr.add_data(upi_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    byte_arr = io.BytesIO()
    img.save(byte_arr, format='PNG')
    byte_arr.seek(0)
    return byte_arr, upi_url

# --- 3. USER INTERFACE FLOW ---
@bot.message_handler(commands=['start'])
def handle_start(message):
    db.init_db()
    u_id = message.from_user.id
    if db.add_user(u_id, message.from_user.username or "None", message.from_user.first_name or "User"):
        try: bot.send_message(config.ADMIN_ID, f"🚀 New User: {message.from_user.first_name}")
        except: pass
    welcome_img = db.get_setting("welcome_image")
    if welcome_img: 
        try: bot.send_photo(message.chat.id, welcome_img)
        except: pass
    bot.send_message(message.chat.id, db.get_setting("welcome_text") or "Welcome to Premium Hub! 🔥", reply_markup=build_user_plans_keyboard())

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_now_"))
def handle_user_checkout(call):
    plan_id = int(call.data.split("_")[2])
    plan = db.db_get_plan(plan_id)
    upi_id = db.get_setting("upi_id")
    qr_bytes, upi_url = generate_upi_qr(upi_id, db.get_setting("payee_name") or "Merchant", plan[2], plan[1])
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ I Have Paid", callback_data=f"submit_payment_{plan_id}"))
    bot.send_photo(call.message.chat.id, qr_bytes, caption=f"Pay ₹{plan[2]} to UPI: <code>{upi_id}</code>", reply_markup=markup)

# --- 4. ADMIN WIZARD & MANAGEMENT (EXTENDED LOGIC) ---
@bot.message_handler(commands=['admin'])
def handle_admin(message):
    if not is_admin(message.from_user.id): return
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("➕ Create Plan", callback_data="adm_create_plan"),
               types.InlineKeyboardButton("📋 Manage Plans", callback_data="adm_manage_plans"),
               types.InlineKeyboardButton("📢 Broadcast", callback_data="adm_broadcast"),
               types.InlineKeyboardButton("📊 Stats", callback_data="adm_stats"))
    bot.send_message(message.chat.id, "⚙️ <b>Admin Dashboard</b>", reply_markup=markup)

def wizard_plan_name(message):
    admin_wizards[message.chat.id] = {"name": message.text}
    msg = bot.send_message(message.chat.id, "2️⃣ Plan Price:")
    bot.register_next_step_handler(msg, wizard_plan_price)

def wizard_plan_price(message):
    admin_wizards[message.chat.id]["price"] = message.text
    msg = bot.send_message(message.chat.id, "3️⃣ Duration (e.g., 30d):")
    bot.register_next_step_handler(msg, wizard_plan_duration)

def wizard_plan_duration(message):
    admin_wizards[message.chat.id]["duration"] = message.text
    msg = bot.send_message(message.chat.id, "4️⃣ Group Link:")
    bot.register_next_step_handler(msg, wizard_plan_link)

def wizard_plan_link(message):
    admin_wizards[message.chat.id]["link"] = message.text
    ctx = admin_wizards[message.chat.id]
    p_id = db.db_add_plan(ctx["name"], ctx["price"], ctx["duration"], ctx["link"])
    ctx["pid"] = p_id
    bot.send_message(message.chat.id, "🎞 Send 5 Premium Videos. Type /done to finish.")
    bot.register_next_step_handler(message, wizard_collect_videos, "premium")

def wizard_collect_videos(message, type):
    if message.text == "/done":
        if type == "premium":
            bot.send_message(message.chat.id, "🎬 Now Send Demo Videos. Type /done to finish.")
            bot.register_next_step_handler(message, wizard_collect_videos, "demo")
        else: bot.send_message(message.chat.id, "✅ Plan Created Successfully.")
        return
    if message.video:
        db.db_add_asset(admin_wizards[message.chat.id]["pid"], message.video.file_id, type, "video")
        msg = bot.reply_to(message, "✅ Saved. Send next or /done.")
        bot.register_next_step_handler(msg, wizard_collect_videos, type)

# --- 5. BROADCAST & POLLING ---
def step_execute_broadcast(message):
    users = db.get_all_users()
    for u_id in users:
        try: bot.send_message(u_id, message.text)
        except: pass
    bot.send_message(config.ADMIN_ID, "📢 Broadcast Completed.")

if __name__ == '__main__':
    db.init_db()
    bot.infinity_polling()
