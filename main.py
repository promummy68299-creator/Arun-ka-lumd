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

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

bot = telebot.TeleBot(config.BOT_TOKEN, parse_mode="HTML")

# Volatile state engine tracking active wizard steps for specific users
admin_wizards = {}

def is_admin(user_id):
    return user_id == config.ADMIN_ID

def build_user_plans_keyboard():
    plans = db.db_get_plans()
    markup = types.InlineKeyboardMarkup(row_width=2)
    for p in plans:
        btn_buy = types.InlineKeyboardButton(f"🛒 Buy {p[1]} (₹{p[2]})", callback_data=f"buy_now_{p[0]}")
        btn_demo = types.InlineKeyboardButton(f"🎬 View Demo {p[1]}", callback_data=f"view_demo_{p[0]}")
        markup.add(btn_buy, btn_demo)
    return markup

def generate_upi_qr(upi_id, payee_name, price, plan_name):
    # Dynamic generation mapping schema conforming to strict UPI merchant protocol specs
    encoded_name = urllib.parse.quote(payee_name)
    encoded_ref = urllib.parse.quote(f"Plan Buy {plan_name}")
    upi_url = f"upi://pay?pa={upi_id}&pn={encoded_name}&am={price}&cu=INR&tn={encoded_ref}"
    
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(upi_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    byte_arr = io.BytesIO()
    img.save(byte_arr, format='PNG')
    byte_arr.seek(0)
    return byte_arr

# --- 1. USER FLOW INTEGRATIONS ---

@bot.message_handler(commands=['start'])
def handle_start(message):
    db.init_db()
    u_id = message.from_user.id
    uname = message.from_user.username or "None"
    fname = message.from_user.first_name or "User"
    
    is_new = db.add_user(u_id, uname, fname)
    
    # Broadcast alerts mapping configurations to designated secure core monitoring channel/id
    if is_new:
        now = datetime.datetime.now()
        alert = (
            f"🚀 <b>New User Started</b>\n\n"
            f"<b>Name:</b> {fname}\n"
            f"<b>Username:</b> @{uname}\n"
            f"<b>User ID:</b> <code>{u_id}</code>\n"
            f"<b>Date:</b> {now.strftime('%Y-%m-%d')}\n"
            f"<b>Time:</b> {now.strftime('%H:%M:%S')}"
        )
        try:
            bot.send_message(config.ADMIN_ID, alert)
        except Exception as e:
            logger.error(f"Failed to alert metrics interface: {e}")
            
    # Welcome implementation configurations (Decoupled execution blocks per requirements specs)
    welcome_img = db.get_setting("welcome_image")
    if welcome_img:
        try:
            bot.send_photo(message.chat.id, welcome_img)
        except Exception:
            pass
            
    welcome_text = db.get_setting("welcome_text") or "Welcome to our Premium VIP Hub! 🔥"
    bot.send_message(message.chat.id, welcome_text)
    
    bot.send_message(message.chat.id, "👇 CHOOSE A PLAN BELOW 🤑", reply_markup=build_user_plans_keyboard())

@bot.callback_query_handler(func=lambda call: call.data.startswith("view_demo_"))
def handle_user_view_demo(call):
    plan_id = int(call.data.split("_")[2])
    plan = db.db_get_plan(plan_id)
    if not plan:
        bot.answer_callback_query(call.id, "Plan details expired or missing.", show_alert=True)
        return
        
    bot.answer_callback_query(call.id, "🚀 Streaming demo reels directly into chat window dashboard...")
    assets = db.db_get_assets(plan_id, "demo")
    
    if not assets:
        bot.send_message(call.message.chat.id, "⚠️ No demo assets loaded inside this profile framework.")
        return
        
    for item in assets:
        f_id, f_type = item[0], item[1]
        try:
            if f_type == "video":
                bot.send_video(call.message.chat.id, f_id)
            elif f_type == "photo":
                bot.send_photo(call.message.chat.id, f_id)
        except Exception:
            pass
            
    # Action prompt block anchoring interface loop flow down towards purchase
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(f"🛒 Buy {plan[1]} Now!", callback_data=f"buy_now_{plan_id}"))
    bot.send_message(call.message.chat.id, f"🔥 Enjoyed the preview? Unlock full access premium content packages of <b>{plan[1]}</b> right away!", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_now_"))
def handle_user_checkout(call):
    plan_id = int(call.data.split("_")[2])
    plan = db.db_get_plan(plan_id)
    if not plan:
        bot.answer_callback_query(call.id, "Plan specifications deleted.")
        return
        
    upi_id = db.get_setting("upi_id")
    payee_name = db.get_setting("payee_name") or "Merchant"
    
    if not upi_id:
        bot.send_message(call.message.chat.id, "❌ Payments system under construction. Admin UPI parameters missing.")
        return
        
    # Auto generation via dynamic rendering stack
    try:
        qr_bytes = generate_upi_qr(upi_id, payee_name, plan[2], plan[1])
        qr_bytes.name = "payment_gate_qr.png"
        bot.send_photo(call.message.chat.id, qr_bytes, caption="💳 Scan QR or pay using UPI ID below.")
    except Exception as e:
        logger.error(f"Failed to runtime render payment layout vector structure: {e}")
        bot.send_message(call.message.chat.id, "⚙️ QR Module Processing mismatch. Please copy string identifier explicitly instead.")
        
    bot.send_message(call.message.chat.id, f"<code>{upi_id}</code>")
    
    info_layout = (
        f"💳 <b>Payment System Routing Interface</b>\n\n"
        f"<b>Amount:</b> ₹{plan[2]}\n"
        f"<b>UPI ID:</b> <code>{upi_id}</code>\n\n"
        f"⚠️ Send confirmation receipt snapshot metrics directly after processing wire transmission verification layer."
    )
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ I Have Paid", callback_data=f"submit_payment_{plan_id}"),
        types.InlineKeyboardButton("❌ Cancel", callback_data="cancel_payment")
    )
    bot.send_message(call.message.chat.id, info_layout, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "cancel_payment")
def handle_cancel_payment(call):
    bot.edit_message_text("❌ Payment process terminated by customer.", call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("submit_payment_"))
def handle_payment_acknowledgement(call):
    plan_id = call.data.split("_")[2]
    msg = bot.send_message(call.message.chat.id, "📸 Please upload and attach your **Payment Transaction Screenshot** image document directly now:")
    bot.register_next_step_handler(msg, step_user_receipt_uploaded, plan_id)

def step_user_receipt_uploaded(message, plan_id):
    if not message.photo:
        bot.reply_to(message, "❌ Invalid media attachment format type. Process mapping aborted. Re-click 'I Have Paid'.")
        return
        
    plan = db.db_get_plan(int(plan_id))
    f_id = message.photo[-1].file_id
    u_id = message.from_user.id
    uname = message.from_user.username or "None"
    fname = message.from_user.first_name or "User"
    dt_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    bot.send_message(message.chat.id, "⏳ Your verification statement package has reached audit queue channels. Standby.")
    
    admin_markup = types.InlineKeyboardMarkup(row_width=2)
    admin_markup.add(
        types.InlineKeyboardButton("✅ Approve", callback_data=f"ap_pay_{u_id}_{plan_id}"),
        types.InlineKeyboardButton("❌ Reject", callback_data=f"rj_pay_{u_id}_{plan_id}")
    )
    
    audit_card = (
        f"💰 <b>New Payment Request</b>\n\n"
        f"<b>Name:</b> {fname}\n"
        f"<b>Username:</b> @{uname}\n"
        f"<b>User ID:</b> <code>{u_id}</code>\n"
        f"<b>Plan:</b> {plan[1]}\n"
        f"<b>Price:</b> ₹{plan[2]}\n"
        f"<b>Date & Time:</b> {dt_str}"
    )
    bot.send_photo(config.ADMIN_ID, f_id, caption=audit_card, reply_markup=admin_markup)

# --- 2. ADMIN CORE DASHBOARD MANAGEMENT FLOWS ---

def show_admin_dashboard(chat_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("➕ Create Plan", callback_data="adm_create_plan"),
        types.InlineKeyboardButton("📋 Manage Plans", callback_data="adm_manage_plans"),
        types.InlineKeyboardButton("💳 Payment Settings", callback_data="adm_payment_settings"),
        types.InlineKeyboardButton("📢 Broadcast", callback_data="adm_broadcast"),
        types.InlineKeyboardButton("👥 Total Users", callback_data="adm_total_users"),
        types.InlineKeyboardButton("📊 Statistics", callback_data="adm_stats"),
        types.InlineKeyboardButton("🖼 Welcome Image", callback_data="adm_set_wimg"),
        types.InlineKeyboardButton("✍ Welcome Text", callback_data="adm_set_wtxt"),
        types.InlineKeyboardButton("⚙ Settings", callback_data="adm_settings_overview")
    )
    bot.send_message(chat_id, "⚙️ <b>Premium Inline Control Architecture Engine Dashboard Panel</b>", reply_markup=markup)

@bot.message_handler(commands=['admin'])
def handle_admin_command(message):
    if not is_admin(message.from_user.id):
        return
    show_admin_dashboard(message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_") or call.data.startswith("ap_pay_") or call.data.startswith("rj_pay_"))
def handle_admin_callbacks(call):
    if not is_admin(call.from_user.id):
        return
        
    action = call.data
    
    if action == "adm_create_plan":
        msg = bot.send_message(call.message.chat.id, "1️⃣ Enter **Plan Name** text value:")
        bot.register_next_step_handler(msg, wizard_plan_name)
        
    elif action == "adm_manage_plans":
        plans = db.db_get_plans()
        if not plans:
            bot.send_message(call.message.chat.id, "📋 No plan metrics deployed yet inside backend infrastructure mapping.")
            return
        for p in plans:
            m = types.InlineKeyboardMarkup(row_width=2)
            m.add(
                types.InlineKeyboardButton("✏️ Change Price", callback_data=f"mp_edit_price_{p[0]}"),
                types.InlineKeyboardButton("⏳ Change Duration", callback_data=f"mp_edit_dur_{p[0]}"),
                types.InlineKeyboardButton("🔗 Change Group Link", callback_data=f"mp_edit_link_{p[0]}"),
                types.InlineKeyboardButton("🎞 Replace Premium Videos", callback_data=f"mp_rep_prem_{p[0]}"),
                types.InlineKeyboardButton("🎬 Replace Demo Videos", callback_data=f"mp_rep_demo_{p[0]}"),
                types.InlineKeyboardButton("🗑 Delete Plan", callback_data=f"mp_del_{p[0]}")
            )
            bot.send_message(call.message.chat.id, f"📦 <b>Plan Profile Details</b>\n\n<b>ID:</b> #{p[0]}\n<b>Name:</b> {p[1]}\n<b>Price:</b> ₹{p[2]}\n<b>Duration:</b> {p[3]}\n<b>Private Link:</b> {p[4]}", reply_markup=m)
            
    elif action == "adm_payment_settings":
        upi = db.get_setting("upi_id") or "Unset"
        name = db.get_setting("payee_name") or "Unset"
        m = types.InlineKeyboardMarkup(row_width=2)
        m.add(
            types.InlineKeyboardButton("✏️ Set/Edit UPI ID", callback_data="payset_edit_upi"),
            types.InlineKeyboardButton("✏️ Set Payee Name", callback_data="payset_edit_name"),
            types.InlineKeyboardButton("🔍 Preview Payment Screen", callback_data="payset_preview")
        )
        bot.send_message(call.message.chat.id, f"💳 <b>Payment Configurations Interface</b>\n\n<b>Current UPI ID:</b> <code>{upi}</code>\n<b>Payee Name:</b> {name}", reply_markup=m)
        
    elif action == "adm_broadcast":
        msg = bot.send_message(call.message.chat.id, "📢 Send your target broadcast asset message framework (Supports plaintext, document, photo, or video format layouts):")
        bot.register_next_step_handler(msg, step_execute_broadcast)
        
    elif action == "adm_total_users":
        usrs = db.get_all_users()
        bot.send_message(call.message.chat.id, f"👥 <b>Total Static Userbase Registered Payload Counts:</b> {len(usrs)} accounts.")
        
    elif action == "adm_stats":
        s = db.get_stats_data()
        msg_stats = (
            f"📊 <b>System Statistics & Metrics Dashboard</b>\n\n"
            f"• <b>Total Users:</b> {s['total_users']}\n"
            f"• <b>Today Users joined:</b> {s['today_users']}\n"
            f"• <b>This Week Users:</b> {s['week_users']}\n"
            f"• <b>Total Plans Configured:</b> {s['total_plans']}\n"
            f"• <b>Total System /start Sequences:</b> {s['total_starts']}\n"
            f"• <b>Last Broadcast Report Metadata:</b> {s['last_broadcast']}\n"
            f"• <b>Bot Node Status:</b> 🟢 Operational / Healthy"
        )
        bot.send_message(call.message.chat.id, msg_stats)
        
    elif action == "adm_set_wimg":
        msg = bot.send_message(call.message.chat.id, "🖼 Upload the new Welcome Image graphic asset node:")
        bot.register_next_step_handler(msg, step_save_wimg)
        
    elif action == "adm_set_wtxt":
        msg = bot.send_message(call.message.chat.id, "✍ Enter new welcome greeting plaintext layout configurations:")
        bot.register_next_step_handler(msg, step_save_wtxt)
        
    elif action == "adm_settings_overview":
        bot.send_message(call.message.chat.id, "⚙️ System variables executing inside automated core context layers smoothly on Railway platforms.")
        
    elif action.startswith("ap_pay_"):
        _, _, u_id, p_id = action.split("_")
        plan = db.db_get_plan(int(p_id))
        
        # User notification sequence injection execution routing metrics
        bot.send_message(int(u_id), f"✅ <b>Payment Approved!</b>\n\n🎉 Your premium access pipeline context has been provisioned configuration arrays.")
        
        prem_assets = db.db_get_assets(int(p_id), "premium")
        for asset in prem_assets:
            try:
                bot.send_video(int(u_id), asset[0])
            except Exception:
                pass
                
        bot.send_message(int(u_id), f"🌐 <b>Private Access Channel Link:</b>\n{plan[4]}")
        bot.edit_message_caption("✅ Automated Delivery Vectors Processed & Approved Successfully.", call.message.chat.id, call.message.message_id, reply_markup=None)
        
    elif action.startswith("rj_pay_"):
        _, _, u_id, p_id = action.split("_")
        bot.send_message(int(u_id), "❌ <b>Payment Request Auditing Denied.</b>\n\nVerification screenshot matched mismatched logs details. Contact support.")
        bot.edit_message_caption("❌ Manual Audit Rejection Executed Successfully.", call.message.chat.id, call.message.message_id, reply_markup=None)

# --- 3. WIZARD INTERFACES & INPUT ROUTINES PARSING STACK ---

def wizard_plan_name(message):
    if not message.text: return
    admin_wizards[message.chat.id] = {"name": message.text, "premium_count": 0, "demo_count": 0}
    msg = bot.send_message(message.chat.id, "2️⃣ Enter **Plan Price** value string:")
    bot.register_next_step_handler(msg, wizard_plan_price)

def wizard_plan_price(message):
    if not message.text: return
    admin_wizards[message.chat.id]["price"] = message.text
    msg = bot.send_message(message.chat.id, "3️⃣ Enter **Plan Duration / Validity** profile metric:")
    bot.register_next_step_handler(msg, wizard_plan_duration)

def wizard_plan_duration(message):
    if not message.text: return
    admin_wizards[message.chat.id]["duration"] = message.text
    msg = bot.send_message(message.chat.id, "4️⃣ Enter **Private Channel/Group URL Access Link** matching parameter specs:")
    bot.register_next_step_handler(msg, wizard_plan_link)

def wizard_plan_link(message):
    if not message.text: return
    admin_wizards[message.chat.id]["group_link"] = message.text
    
    # Core internal indexing structure deployment phase mapping allocation
    ctx = admin_wizards[message.chat.id]
    p_id = db.db_add_plan(ctx["name"], ctx["price"], ctx["duration"], ctx["group_link"])
    ctx["inserted_id"] = p_id
    
    msg = bot.send_message(message.chat.id, f"5️⃣ Upload **Premium Video 1** asset details attachment now:")
    bot.register_next_step_handler(msg, wizard_collect_premium_videos, 1)

def wizard_collect_premium_videos(message, index):
    if not message.video:
        msg = bot.reply_to(message, "❌ File type mismatch. Re-upload a video file node for validation matching:")
        bot.register_next_step_handler(msg, wizard_collect_premium_videos, index)
        return
        
    ctx = admin_wizards[message.chat.id]
    db.db_add_asset(ctx["inserted_id"], message.video.file_id, "premium", "video")
    
    if index < 5:
        msg = bot.send_message(message.chat.id, f"Upload **Premium Video {index + 1}** structure metadata profile:")
        bot.register_next_step_handler(msg, wizard_collect_premium_videos, index + 1)
    else:
        msg = bot.send_message(message.chat.id, "🔟 Upload **Demo Video 1** asset context file attachment (Upload 10 to 15 assets total. Send /done anytime to conclude array creation inputs):")
        bot.register_next_step_handler(msg, wizard_collect_demo_videos, 1)

def wizard_collect_demo_videos(message, index):
    ctx = admin_wizards.get(message.chat.id)
    if not ctx: return
    
    if message.text and "/done" in message.text.lower():
        if index < 10:
            msg = bot.reply_to(message, "⚠️ Requirements state at minimum 10 Demo reels needed. Please keep uploading:")
            bot.register_next_step_handler(msg, wizard_collect_demo_videos, index)
            return
        bot.send_message(message.chat.id, "✅ Plan Created Successfully")
        admin_wizards.pop(message.chat.id, None)
        return
        
    if not message.video:
        msg = bot.reply_to(message, "❌ Video wrapper asset validation failed. Attach raw video file node:")
        bot.register_next_step_handler(msg, wizard_collect_demo_videos, index)
        return
        
    db.db_add_asset(ctx["inserted_id"], message.video.file_id, "demo", "video")
    
    if index >= 15:
        bot.send_message(message.chat.id, "✅ Plan Created Successfully")
        admin_wizards.pop(message.chat.id, None)
    else:
        msg = bot.send_message(message.chat.id, f"Upload **Demo Video {index + 1}** attachment structure (Or type /done if index count is between 10-15 total modules):")
        bot.register_next_step_handler(msg, wizard_collect_demo_videos, index + 1)

# --- 4. MANAGE INTERNAL TARGET FILE ATTRIBUTES MODULAR CALLS ---

@bot.callback_query_handler(func=lambda call: call.data.startswith("mp_"))
def handle_management_logic_actions(call):
    if not is_admin(call.from_user.id): return
    tokens = call.data.split("_")
    action_type = tokens[1]
    plan_id = int(tokens[3])
    
    if action_type == "del":
        db.db_delete_plan(plan_id)
        bot.edit_message_text("🗑 Subscription plan entry wiped entirely out of local system registers.", call.message.chat.id, call.message.message_id)
        
    elif action_type == "edit":
        sub_target = tokens[2]
        if sub_target == "price":
            msg = bot.send_message(call.message.chat.id, "💰 Enter new Price target number sequence configurations:")
            bot.register_next_step_handler(msg, lambda m: update_field_step(m, plan_id, "price"))
        elif sub_target == "dur":
            msg = bot.send_message(call.message.chat.id, "⏳ Write new plan validation duration window parameters text:")
            bot.register_next_step_handler(msg, lambda m: update_field_step(m, plan_id, "duration"))
        elif sub_target == "link":
            msg = bot.send_message(call.message.chat.id, "🔗 Write new replacement target secure delivery gateway link:")
            bot.register_next_step_handler(msg, lambda m: update_field_step(m, plan_id, "group_link"))
            
    elif action_type == "rep":
        sub_target = tokens[2]
        db.db_clear_assets(plan_id, sub_target)
        if sub_target == "prem":
            msg = bot.send_message(call.message.chat.id, "🎞 Re-upload **Premium Video 1** package setup chain index:")
            admin_wizards[call.message.chat.id] = {"inserted_id": plan_id}
            bot.register_next_step_handler(msg, wizard_collect_premium_videos, 1)
        elif sub_target == "demo":
            msg = bot.send_message(call.message.chat.id, "🎬 Re-upload **Demo Video 1** layout package setup chain index:")
            admin_wizards[call.message.chat.id] = {"inserted_id": plan_id}
            bot.register_next_step_handler(msg, wizard_collect_demo_videos, 1)

def update_field_step(message, plan_id, field):
    if not message.text: return
    db.db_update_plan_field(plan_id, field, message.text)
    bot.reply_to(message, f"✅ Parameter value array mapping for [{field}] shifted to storage configurations.")

# --- 5. GLOBAL PREFERENCES CORE CONTROLS AND BROADCAST MODULE RENDERERS ---

@bot.callback_query_handler(func=lambda call: call.data.startswith("payset_"))
def handle_payment_settings_actions(call):
    if not is_admin(call.from_user.id): return
    target = call.data.split("_")[1]
    
    if target == "upi":
        msg = bot.send_message(call.message.chat.id, "💳 Write down the merchant targeted destination UPI addressing sequence:")
        bot.register_next_step_handler(msg, lambda m: save_setting_step(m, "upi_id"))
    elif target == "name":
        msg = bot.send_message(call.message.chat.id, "👤 Enter target corporate name identity strings configuration context:")
        bot.register_next_step_handler(msg, lambda m: save_setting_step(m, "payee_name"))
    elif target == "preview":
        upi = db.get_setting("upi_id") or "test@upi"
        pn = db.get_setting("payee_name") or "Merchant Test"
        try:
            q_b = generate_upi_qr(upi, pn, "99", "Demo Preview Configuration Package Mapping")
            q_b.name = "test_preview.png"
            bot.send_photo(call.message.chat.id, q_b, caption=f"🔍 <b>Checkout Dynamic Rendering Engine Matrix Mockup View</b>\n\nRouting URI: upi://pay?pa={upi}...")
        except Exception as e:
            bot.send_message(call.message.chat.id, f"❌ Dynamic mapping pipeline error details: {e}")

def save_setting_step(message, key):
    if not message.text: return
    db.set_setting(key, message.text)
    bot.reply_to(message, f"✅ System system routing global preference entry updated mapping variable: [{key}]")

def step_save_wimg(message):
    if not message.photo:
        bot.reply_to(message, "❌ Content structure rejected. Not a file attachment image node blueprint.")
        return
    db.set_setting("welcome_image", message.photo[-1].file_id)
    bot.reply_to(message, "✅ Welcome landing screen graphic banner profile pinned into system engine blocks.")

def step_save_wtxt(message):
    if not message.text: return
    db.set_setting("welcome_text", message.text)
    bot.reply_to(message, "✅ System welcome landing plain strings text data configured explicitly.")

def step_execute_broadcast(message):
    users = db.get_all_users()
    success, failed = 0, 0
    
    for u_id in users:
        try:
            if message.content_type == 'text':
                bot.send_message(u_id, message.text)
            elif message.content_type == 'photo':
                bot.send_photo(u_id, message.photo[-1].file_id, caption=message.caption)
            elif message.content_type == 'video':
                bot.send_video(u_id, message.video.file_id, caption=message.caption)
            elif message.content_type == 'document':
                bot.send_document(u_id, message.document.file_id, caption=message.caption)
            success += 1
        except Exception:
            failed += 1
            
    summary_report = f"Total Users: {len(users)}\nSuccess: {success}\nFailed: {failed}"
    db.set_setting("last_broadcast", f"Ran on {datetime.datetime.now().strftime('%Y-%m-%d')} | Success: {success} / Failed: {failed}")
    bot.send_message(config.ADMIN_ID, f"📢 <b>Broadcast Execution Routine Summary:</b>\n\n<code>{summary_report}</code>")

# --- 6. INITIALIZATION EXECUTION MATRIX LAYER ---

if __name__ == '__main__':
    db.init_db()
    logger.info("🤖 Premium Upgraded Bot Core Pipeline deployed into operational state architecture hooks.")
    while True:
        try:
            bot.infinity_polling(timeout=30, long_polling_timeout=30)
        except Exception as err:
            logger.error(f"⚠️ Re-establishing connectivity framework wrapper abstraction nodes on event rupture: {err}")
            time.sleep(5)
