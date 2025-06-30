from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from dotenv import load_dotenv
import psycopg2
import os

load_dotenv()

def get_connection():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

def get_user_info(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT username, usdt_balance, cny_balance FROM users WHERE user_id = %s", (user_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row

def get_user_id_by_username(username):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users WHERE username = %s", (username,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row else None

# ✅ 转账菜单
async def transfer_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        user_id = update.callback_query.from_user.id
        username = update.callback_query.from_user.username
    else:
        user_id = update.message.from_user.id
        username = update.message.from_user.username

    user_info = get_user_info(user_id)
    usdt_balance = round(user_info[1], 2) if user_info else 0
    cny_balance = round(user_info[2], 2) if user_info else 0

    text = f"""
🪪用户名：@{username}
🪪用户ID：{user_id}
💵USDT余额：{usdt_balance:.2f}
💴CNY余额：{cny_balance:.2f}

请选择转账类型：
    """
    keyboard = [
        [InlineKeyboardButton("💵USDT转账", callback_data="transfer_usdt")],
        [InlineKeyboardButton("💴CNY转账", callback_data="transfer_cny")],
        [InlineKeyboardButton("⬅️返回上一级", callback_data="back_to_main")]
    ]
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ✅ 用户点击转账类型按钮
async def transfer_usdt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["action"] = "transfer_usdt"
    user_info = get_user_info(update.callback_query.from_user.id)
    context.user_data["usdt_balance"] = float(user_info[1]) if user_info else 0
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("请输入要转账的 💵USDT 金额：")

async def transfer_cny(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["action"] = "transfer_cny"
    user_info = get_user_info(update.callback_query.from_user.id)
    context.user_data["cny_balance"] = float(user_info[2]) if user_info else 0
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("请输入要转账的 💴CNY 金额：")

# ✅ 用户输入金额
async def handle_transfer_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text)
        if amount <= 0:
            await update.message.reply_text("⚠️ 金额必须大于 0，请重新输入。")
            return
    except ValueError:
        await update.message.reply_text("⚠️ 请输入有效的数字金额。")
        return

    context.user_data["transfer_amount"] = amount
    action = context.user_data.get("action")

    insufficient = False
    if action == "transfer_usdt":
        if amount > context.user_data.get("usdt_balance", 0):
            insufficient = True
    elif action == "transfer_cny":
        if amount > context.user_data.get("cny_balance", 0):
            insufficient = True

    if insufficient:
        await update.message.reply_text("🚨操作失败，余额不足！")
        class DummyCallbackQuery:
            def __init__(self, from_user): self.from_user = from_user
            async def answer(self): pass
        update.callback_query = DummyCallbackQuery(update.message.from_user)
        await transfer_menu(update, context)
        return

    await update.message.reply_text("请输入你要转账的目标用户名（格式：@用户名）：")
    context.user_data["awaiting_username"] = True

# ✅ 用户输入 @用户名
async def handle_transfer_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.startswith("@"):
        await update.message.reply_text("请输入有效的用户名（格式为 @用户名）")
        return

    to_username = text[1:]
    to_user_id = get_user_id_by_username(to_username)
    from_user_id = update.message.from_user.id

    if not to_user_id:
        await update.message.reply_text("该用户不存在，请确认对方已使用过钱包。")
        return
    if to_user_id == from_user_id:
        await update.message.reply_text("不能转账给自己。")
        return

    context.user_data["to_user_id"] = to_user_id
    context.user_data["to_username"] = to_username

    from_info = get_user_info(from_user_id)
    usdt_balance = round(from_info[1], 2)
    cny_balance = round(from_info[2], 2)
    amount = context.user_data["transfer_amount"]
    currency = "USDT" if context.user_data["action"] == "transfer_usdt" else "CNY"

    text = f"""
🟢 请确认以下转账信息：

转账给🪪@{to_username}
转账给🪪用户ID：`{to_user_id}`
转账金额：{amount} {currency}
钱包💵USDT余额：{usdt_balance}
钱包💴CNY余额：{cny_balance}
    """
    keyboard = [
        [InlineKeyboardButton("✅确认转账", callback_data="confirm_transfer")],
        [InlineKeyboardButton("⬅️返回上一级", callback_data="transfer_menu")]
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    context.user_data["awaiting_username"] = False

# ✅ 确认转账
async def confirm_transfer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    from_user = update.callback_query.from_user
    from_user_id = from_user.id
    to_user_id = context.user_data.get("to_user_id")
    amount = context.user_data.get("transfer_amount")
    action = context.user_data.get("action")

    if not all([to_user_id, amount, action]):
        await update.callback_query.edit_message_text("❌ 操作失败，数据不完整。")
        return

    conn = get_connection()
    cur = conn.cursor()

    if action == "transfer_usdt":
        cur.execute("UPDATE users SET usdt_balance = usdt_balance - %s WHERE user_id = %s", (amount, from_user_id))
        cur.execute("UPDATE users SET usdt_balance = usdt_balance + %s WHERE user_id = %s", (amount, to_user_id))
    else:
        cur.execute("UPDATE users SET cny_balance = cny_balance - %s WHERE user_id = %s", (amount, from_user_id))
        cur.execute("UPDATE users SET cny_balance = cny_balance + %s WHERE user_id = %s", (amount, to_user_id))

    cur.execute("INSERT INTO transactions (user_id, transaction_type, amount, timestamp) VALUES (%s, 'transfer', %s, NOW())", (from_user_id, amount))
    conn.commit()
    cur.close()
    conn.close()

    await update.callback_query.edit_message_text("✅ 转账成功，已返回转账菜单。")
    await transfer_menu(update, context)

    try:
        await context.bot.send_message(
            chat_id=to_user_id,
            text=f"📥 你收到来自 @{from_user.username} 的转账：{amount} {'USDT' if action == 'transfer_usdt' else 'CNY'}"
        )
    except:
        print(f"无法发送通知给用户 {to_user_id}")

# ✅ 回退按钮处理
async def back_to_transfer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await transfer_menu(update, context)
