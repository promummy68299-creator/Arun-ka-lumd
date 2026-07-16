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

admin_wizards = {}

def is_admin(user_id):
    return user_id == config.ADMIN_ID

def build_user_plans_keyboard():
    plans = db.db_get_plans()
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    # Har tareeqe ke auto-generated extra emojis (jaise 🛒 ya 💎) remove kar diye hain.
    # Ab wahi dikhega jo admin ne plan name me khud emoji daala hoga.
    for p in plans:
        btn_plan = types.InlineKeyboardButton(f"{p[1]} — ₹{p[2]} / {p[3]}", callback_data=f"buy_now_{p[0]}")
        markup.add(btn_plan)
        
    # Main dynamic bottom navigation layout 
    btn_demo_hub = types.InlineKeyboardButton("🎬 View Demo", callback_data="user_global_demo")
    btn_report = types.InlineKeyboardButton("🚨 Report Issue", callback_data="user_report_issue")
    markup.row(btn_demo_hub, btn_report)
    return markup

def generate_upi_qr(upi_id, payee_name, price, plan_name):
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
    return byte_arr, upi_url

# --- USER CHATFLOW INTERFACE ---

@bot.message_handler(commands=['start'])
def handle_start(message):
    db.init_db()
    u_id = message.from_user.id
    uname = message.from_user.username or "None"
    fname = message.from_user.first_name or "User"
    
    is_new = db.add_user(u_id, uname, fname)
    
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
        except Exception:
            pass
            
    welcome_img = db.get_setting("welcome_image")
    if welcome_img:
        try:
            bot.send_photo(message.chat.id, welcome_img)
        except Exception:
            pass
            
    welcome_text = db.get_setting("welcome_text") or "Welcome to our Premium VIP Hub! 🔥"
    bot.send_message(message.chat.id, welcome_text)
    bot.send_message(message.chat.id, "👇 Choose a plan below 💎", reply_markup=build_user_plans_keyboard())

@bot.callback_query_handler(func=lambda call: call.data == "user_global_demo")
def handle_global_demo_request(call):
    bot.answer_callback_query(call.id, "🎬 Loading demo catalog library...")
    plans = db.db_get_plans()
    if not plans:
        bot.send_message(call.message.chat.id, "⚠️ No active plans found to show demos.")
        return
        
    has_demo = False
    for p in plans:
        assets = db.db_get_assets(p[0], "demo")
        if assets:
            has_demo = True
            bot.send_message(call.message.chat.id, f"🌟 <b>Demo Reels for: {p[1]}</b>")
            for item in assets:
                try:
                    bot.send_video(call.message.chat.id, item[0])
                except Exception:
                    pass
                    
    if not has_demo:
        bot.send_message(call.message.chat.id, "⚠️ Admin has not uploaded any demo media assets yet.")
    else:
        bot.send_message(call.message.chat.id, "🔥 Grab your premium access slot. Select a plan from the list above!")

@bot.callback_query_handler(func=lambda call: call.data == "user_report_issue")
def handle_user_report(call):
    bot.send_message(call.message.chat.id, "📧 Contact admin directly for account issues or manual transaction support lines.")

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_now_"))
def handle_user_checkout(call):
    plan_id = int(call.data.split("_")[2])
    plan = db.db_get_plan(plan_id)
    if not plan:
        bot.answer_callback_query(call.id, "Plan configuration mismatch.")
        return
        
    upi_id = db.get_setting("upi_id")
    payee_name = db.get_setting("payee_name") or "Merchant"
    
    if not upi_id or upi_id.strip() == "":
        bot.send_message(call.message.chat.id, "❌ UPI system configuration incomplete. Contact Admin to configure UPI ID.")
        return
        
    info_layout = (
        f"💳 <b>Payment Gateway Routing</b>\n\n"
        f"<b>Selected Plan:</b> {plan[1]}\n"
        f"<b>Amount:</b> ₹{plan[2]}\n"
        f"<b>Duration:</b> {plan[3]}\n"
        f"<b>UPI ID:</b> <code>{upi_id}</code>\n\n"
        f"👉 <b>Scan QR or pay using UPI ID above.</b>"
    )
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ I Have Paid", callback_data=f"submit_payment_{plan_id}"),
        types.InlineKeyboardButton("❌ Cancel", callback_data="cancel_payment")
    )
    
    try:
        qr_bytes, upi_url = generate_upi_qr(upi_id, payee_name, plan[2], plan[1])
        qr_bytes.name = "payment_qr.png"
        bot.send_photo(call.message.chat.id, qr_bytes, caption=info_layout, reply_markup=markup)
    except Exception as e:
        logger.error(f"QR system failed, routing text failback wrapper link: {e}")
        # System Failback protection bypass routing logic
        fallback_text = info_layout + f"\n\n🔗 <a href='{upi_url}'>Click here to pay via UPI App directly</a>"
        bot.send_message(call.message.chat.id, fallback_text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "cancel_payment")
def handle_cancel_payment(call):
    bot.edit_message_text("❌ Payment process terminated by customer.", call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("submit_payment_"))
def handle_payment_acknowledgement(call):
    plan_id = call.data.split("_")[2]
    msg = bot.send_message(call.message.chat.id, "📸 Please upload your <b>Payment Transaction Screenshot</b> now:")
    bot.register_next_step_handler(msg, step_user_receipt_uploaded, plan_id)

def step_user_receipt_uploaded(message, plan_id):
    if not message.photo:
        bot.reply_to(message, "❌ Attachment mismatch. Process aborted. Re-click plan button to pay.")
        return
        
    plan = db.db_get_plan(int(plan_id))
    f_id = message.photo[-1].file_id
    u_id = message.from_user.id
    uname = message.from_user.username or "None"
    fname = message.from_user.first_name or "User"
    dt_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    bot.send_message(message.chat.id, "⏳ Payment sent to audit queue channels. Waiting for admin approval.")
    
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

# --- ADMIN PANEL MANAGEMENT SYSTEM ---

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
    bot.send_message(chat_id, "⚙️ <b>Premium Control Dashboard</b>", reply_markup=markup)

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
        msg = bot.send_message(call.message.chat.id, "1️⃣ Enter **Plan Name** text:")
        bot.register_next_step_handler(msg, wizard_plan_name)
        
    elif action == "adm_manage_plans":
        plans = db.db_get_plans()
        if not plans:
            bot.send_message(call.message.chat.id, "📋 No plan profiles configured yet.")
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
            bot.send_message(call.message.chat.id, f"📦 <b>Plan Profile</b>\n\n<b>ID:</b> #{p[0]}\n<b>Name:</b> {p[1]}\n<b>Price:</b> ₹{p[2]}\n<b>Duration:</b> {p[3]}\n<b>Private Link:</b> {p[4]}", reply_markup=m)
            
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
        msg = bot.send_message(call.message.chat.id, "📢 Send your target broadcast asset message:")
        bot.register_next_step_handler(msg, step_execute_broadcast)
        
    elif action == "adm_total_users":
        usrs = db.get_all_users()
        bot.send_message(call.message.chat.id, f"👥 <b>Total Registered User Count:</b> {len(usrs)}")
        
    elif action == "adm_stats":
        s = db.get_stats_data()
        msg_stats = (
            f"📊 <b>System Statistics</b>\n\n"
            f"• <b>Total Users:</b> {s['total_users']}\n"
            f"• <b>Today's Users:</b> {s['today_users']}\n"
            f"• <b>This Week Users:</b> {s['week_users']}\n"
            f"• <b>Total Plans:</b> {s['total_plans']}\n"
            f"• <b>Total Starts:</b> {s['total_starts']}\n"
            f"• <b>Last Broadcast Report:</b> {s['last_broadcast']}\n"
            f"• <b>Status:</b> 🟢 Operational"
        )
        bot.send_message(call.message.chat.id, msg_stats)
        
    elif action == "adm_set_wimg":
        msg = bot.send_message(call.message.chat.id, "🖼 Upload the new Welcome Image asset node:")
        bot.register_next_step_handler(msg, step_save_wimg)
        
    elif action == "adm_set_wtxt":
        msg = bot.send_message(call.message.chat.id, "✍ Enter new welcome layout text strings:")
        bot.register_next_step_handler(msg, step_save_wtxt)
        
    elif action == "adm_settings_overview":
        bot.send_message(call.message.chat.id, "⚙️ Dynamic settings running securely on top of Railway node clusters.")
        
    elif action.startswith("ap_pay_"):
        _, _, u_id, p_id = action.split("_")
        plan = db.db_get_plan(int(p_id))
        
        bot.send_message(int(u_id), f"✅ <b>Payment Approved!</b>\n\n🎉 Sending your Premium Media Files Asset packs...")
        
        prem_assets = db.db_get_assets(int(p_id), "premium")
        for asset in prem_assets:
            try:
                bot.send_video(int(u_id), asset[0])
            except Exception:
                pass
                
        bot.send_message(int(u_id), f"🌐 <b>Private Access Channel Link:</b>\n{plan[4]}")
        bot.edit_message_caption("✅ Delivery Vectors Processed & Approved Successfully.", call.message.chat.id, call.message.message_id, reply_markup=None)
        
    elif action.startswith("rj_pay_"):
        _, _, u_id, p_id = action.split("_")
        bot.send_message(int(u_id), "❌ <b>Payment Request Auditing Denied.</b>\n\nVerification screenshot didn't match logs detail parameters.")
        bot.edit_message_caption("❌ Manual Audit Rejection Executed.", call.message.chat.id, call.message.message_id, reply_markup=None)

# --- AUTOMATED DYNAMIC INPUT FLOW WIZARDS ---

def wizard_plan_name(message):
    if not message.text: return
    admin_wizards[message.chat.id] = {"name": message.text}
    msg = bot.send_message(message.chat.id, "2️⃣ Enter **Plan Price** value (Numbers only, e.g. 49, 99):")
    bot.register_next_step_handler(msg, wizard_plan_price)

def wizard_plan_price(message):
    if not message.text: return
    admin_wizards[message.chat.id]["price"] = message.text
    msg = bot.send_message(message.chat.id, "3️⃣ Enter **Plan Duration / Validity** profile metric (e.g., 30d, 365d):")
    bot.register_next_step_handler(msg, wizard_plan_duration)

def wizard_plan_duration(message):
    if not message.text: return
    admin_wizards[message.chat.id]["duration"] = message.text
    msg = bot.send_message(message.chat.id, "4️⃣ Enter **Private Channel/Group Access Invite Link**:")
    bot.register_next_step_handler(msg, wizard_plan_link)

def wizard_plan_link(message):
    if not message.text: return
    admin_wizards[message.chat.id]["group_link"] = message.text
    
    ctx = admin_wizards[message.chat.id]
    p_id = db.db_add_plan(ctx["name"], ctx["price"], ctx["duration"], ctx["group_link"])
    ctx["inserted_id"] = p_id
    
    msg = bot.send_message(message.chat.id, "🎞 Upload **Premium Videos** for this plan. You can upload as many as you want.\n\n👉 Send `/done` command when you are finished uploading premium videos.")
    bot.register_next_step_handler(msg, wizard_collect_premium_videos)

def wizard_collect_premium_videos(message):
    ctx = admin_wizards.get(message.chat.id)
    if not ctx: return
    
    if message.text and "/done" in message.text.lower():
        msg = bot.send_message(message.chat.id, "🎬 Now upload **Demo Videos** for this specific plan. You can upload as many as you want.\n\n👉 Send `/done` command when you are finished uploading demo videos to complete the plan creation process.")
        bot.register_next_step_handler(msg, wizard_collect_demo_videos)
        return
        
    if not message.video:
        msg = bot.reply_to(message, "❌ Invalid file type. Please upload a Video asset or send `/done`:")
        bot.register_next_step_handler(msg, wizard_collect_premium_videos)
        return
        
    db.db_add_asset(ctx["inserted_id"], message.video.file_id, "premium", "video")
    msg = bot.send_message(message.chat.id, "✅ Premium video registered. Upload another or send `/done`:")
    bot.register_next_step_handler(msg, wizard_collect_premium_videos)

def wizard_collect_demo_videos(message):
    ctx = admin_wizards.get(message.chat.id)
    if not ctx: return
    
    if message.text and "/done" in message.text.lower():
        bot.send_message(message.chat.id, "✅ Plan Created Successfully")
        admin_wizards.pop(message.chat.id, None)
        return
        
    if not message.video:
        msg = bot.reply_to(message, "❌ Invalid file type. Please upload a Video asset or send `/done`:")
        bot.register_next_step_handler(msg, wizard_collect_demo_videos)
        return
        
    db.db_add_asset(ctx["inserted_id"], message.video.file_id, "demo", "video")
    msg = bot.send_message(message.chat.id, "✅ Demo video registered. Upload another or send `/done` to complete configuration:")
    bot.register_next_step_handler(msg, wizard_collect_demo_videos)

# --- PLAN MANAGEMENT ATTRIBUTES DELEGATES ---

@bot.callback_query_handler(func=lambda call: call.data.startswith("mp_"))
def handle_management_logic_actions(call):
    if not is_admin(call.from_user.id): return
    tokens = call.data.split("_")
    action_type = tokens[1]
    plan_id = int(tokens[3])
    
    if action_type == "del":
        db.db_delete_plan(plan_id)
        bot.edit_message_text("🗑 Subscription plan removed from database records.", call.message.chat.id, call.message.message_id)
        
    elif action_type == "edit":
        sub_target = tokens[2]
        if sub_target == "price":
            msg = bot.send_message(call.message.chat.id, "💰 Enter new price profile value:")
            bot.register_next_step_handler(msg, lambda m: update_field_step(m, plan_id, "price"))
        elif sub_target == "dur":
            msg = bot.send_message(call.message.chat.id, "⏳ Enter new plan validation duration parameter:")
            bot.register_next_step_handler(msg, lambda m: update_field_step(m, plan_id, "duration"))
        elif sub_target == "link":
            msg = bot.send_message(call.message.chat.id, "🔗 Enter new replacement target invite link gateway:")
            bot.register_next_step_handler(msg, lambda m: update_field_step(m, plan_id, "group_link"))
            
    elif action_type == "rep":
        sub_target = tokens[2]
        db.db_clear_assets(plan_id, sub_target)
        if sub_target == "prem":
            msg = bot.send_message(call.message.chat.id, "🎞 Upload replacement **Premium Videos**. Send `/done` when complete:")
            admin_wizards[call.message.chat.id] = {"inserted_id": plan_id}
            bot.register_next_step_handler(msg, wizard_collect_premium_videos)
        elif sub_target == "demo":
            msg = bot.send_message(call.message.chat.id, "🎬 Upload replacement **Demo Videos**. Send `/done` when complete:")
            admin_wizards[call.message.chat.id] = {"inserted_id": plan_id}
            bot.register_next_step_handler(msg, wizard_collect_demo_videos)

def update_field_step(message, plan_id, field):
    if not message.text: return
    db.db_update_plan_field(plan_id, field, message.text)
    bot.reply_to(message, f"✅ Parameter configuration database mapping for [{field}] updated successfully.")

# --- UTILITIES LAYERS AND BROADCAST MODULES ---

@bot.callback_query_handler(func=lambda call: call.data.startswith("payset_"))
def handle_payment_settings_actions(call):
    if not is_admin(call.from_user.id): return
    target = call.data.split("_")[1]
    
    if target == "upi":
        msg = bot.send_message(call.message.chat.id, "💳 Enter your destination Payment UPI ID:")
        bot.register_next_step_handler(msg, lambda m: save_setting_step(m, "upi_id"))
    elif target == "name":
        msg = bot.send_message(call.message.chat.id, "👤 Enter target custom Merchant Payee Name identity strings:")
        bot.register_next_step_handler(msg, lambda m: save_setting_step(m, "payee_name"))
    elif target == "preview":
        upi = db.get_setting("upi_id") or "test@upi"
        pn = db.get_setting("payee_name") or "Merchant Test"
        try:
            q_b, u_url = generate_upi_qr(upi, pn, "99", "Preview Setup Package")
            q_b.name = "test_preview.png"
            bot.send_photo(call.message.chat.id, q_b, caption=f"🔍 <b>Mockup Routing Gateway URI Preview Screen:</b>\n\n<code>{u_url}</code>")
        except Exception as e:
            bot.send_message(call.message.chat.id, f"❌ QR Core exception layer processing mismatch log details: {e}")

def save_setting_step(message, key):
    if not message.text: return
    db.set_setting(key, message.text.strip())
    bot.reply_to(message, f"✅ Global core settings preference parameter updated: [{key}]")

def step_save_wimg(message):
    if not message.photo:
        bot.reply_to(message, "❌ Invalid content format layout blueprint.")
        return
    db.set_setting("welcome_image", message.photo[-1].file_id)
    bot.reply_to(message, "✅ Welcome landing banner graphic pinned into local engine configuration keys successfully.")

def step_save_wtxt(message):
    if not message.text: return
    db.set_setting("welcome_text", message.text)
    bot.reply_to(message, "✅ System welcome text configuration updated.")

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
    bot.send_message(config.ADMIN_ID, f"📢 <b>Broadcast Summary Report Engine Logs:</b>\n\n<code>{summary_report}</code>")

if __name__ == '__main__':
    db.init_db()
    logger.info("🤖 Bot Core Engine initialized successfully.")
    while True:
        try:
            bot.infinity_polling(timeout=30, long_polling_timeout=30)
        except Exception as err:
            logger.error(f"⚠️ Polling connection issue resolved: {err}")
            time.sleep(5)
