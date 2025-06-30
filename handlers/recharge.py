from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from uuid import uuid4
import os
import random
import psycopg2
from dotenv import load_dotenv
from datetime import datetime, timedelta
import requests

load_dotenv()

RECHARGE_ADDRESS = os.getenv("USDT_RECHARGE_ADDRESS")
TRON_API_KEY = os.getenv("TRONGRID_API_KEY")

# 数据库连接
def get_connection():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

# 获取用户余额信息
def get_user_info(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT username, usdt_balance, cny_balance FROM users WHERE user_id = %s", (user_id,))
    user_info = cur.fetchone()
    cur.close()
    conn.close()
    return user_info

# 插入充值订单
def create_recharge_order(order_id, user_id, amount_input, amount_real):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO recharge_orders (order_id, user_id, amount_input, amount_real, address, created_at, expires_at, status)
        VALUES (%s, %s, %s, %s, %s, NOW(), NOW() + INTERVAL '30 minutes', 'pending')
    """, (order_id, user_id, amount_input, amount_real, RECHARGE_ADDRESS))
    conn.commit()
    cur.close()
    conn.close()

# 成功到账处理
def complete_recharge(order_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT user_id, amount_input, amount_real FROM recharge_orders WHERE order_id = %s", (order_id,))
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        return False

    user_id, input_amt, real_amt = row

    # 增加余额
    cur.execute("UPDATE users SET usdt_balance = usdt_balance + %s WHERE user_id = %s", (input_amt, user_id))

    # 写入交易记录
    cur.execute("""
        INSERT INTO transactions (user_id, transaction_type, amount, timestamp)
        VALUES (%s, 'recharge', %s, NOW())
    """, (user_id, input_amt))

    # 更新订单状态
    cur.execute("UPDATE recharge_orders SET status = 'success' WHERE order_id = %s", (order_id,))
    conn.commit()
    cur.close()
    conn.close()
    return True

# 过期订单清理
def expire_old_orders():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE recharge_orders
        SET status = 'expired'
        WHERE status = 'pending' AND expires_at < NOW()
    """)
    conn.commit()
    cur.close()
    conn.close()

# TronGrid 实时监听到账
def check_pending_orders_with_trongrid():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT order_id, user_id, amount_real, created_at, expires_at
        FROM recharge_orders
        WHERE status = 'pending'
    """)
    orders = cur.fetchall()

    if not orders:
        cur.close()
        conn.close()
        return

    headers = {"TRON-PRO-API-KEY": TRON_API_KEY}
    url = f"https://api.trongrid.io/v1/accounts/{RECHARGE_ADDRESS}/transactions/trc20?limit=100"

    try:
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json().get("data", [])
    except Exception as e:
        print("TronGrid 请求失败：", e)
        return

    for order_id, user_id, amount_real, created_at, expires_at in orders:
        for tx in data:
            try:
                token_info = tx.get("token_info", {})
                if token_info.get("symbol") != "USDT":
                    continue
                value = int(tx["value"]) / 10**6
                to_addr = tx["to"]
                timestamp = datetime.fromtimestamp(tx["block_timestamp"] / 1000)

                if to_addr.lower() != RECHARGE_ADDRESS.lower():
                    continue

                if abs(value - float(amount_real)) < 0.001 and created_at <= timestamp <= expires_at:
                    print(f"✅ 识别到账 - 订单: {order_id}, 金额: {value}, 时间: {timestamp}")
                    complete_recharge(order_id)
            except Exception as e:
                print("⚠️ 解析交易失败:", e)

    cur.close()
    conn.close()

# 用户点击“📥充值”
async def recharge_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.callback_query.from_user.id
    user_info = get_user_info(user_id)

    if user_info:
        user_name = user_info[0]
        usdt_balance = round(user_info[1], 2)
        cny_balance = round(user_info[2], 2)
    else:
        user_name = update.callback_query.from_user.username
        usdt_balance = 0.00
        cny_balance = 0.00

    text = f"""
🪪用户名：@{user_name}
🪪用户ID：{user_id}
💵USDT余额：{usdt_balance:.2f}
💴CNY余额：{cny_balance:.2f}

请选择充值方式：
    """

    keyboard = [
        [InlineKeyboardButton("💵USDT充值", callback_data="recharge_usdt")],
        [InlineKeyboardButton("⬅️返回上一级", callback_data="back_to_main")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.callback_query.answer()
    await update.callback_query.edit_message_text(text, reply_markup=reply_markup)

# 点击“💵USDT充值” → 提示输入金额
async def recharge_prompt_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("请输入你要充值的 💵USDT 金额：")
    context.user_data["action"] = "usdt_recharge"

# 处理用户输入的金额
async def handle_recharge_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_input = update.message.text

    if context.user_data.get("action") != "usdt_recharge":
        return

    try:
        base_amount = float(user_input)
        if base_amount <= 0:
            await update.message.reply_text("🚫 请输入有效金额。")
            return
    except ValueError:
        await update.message.reply_text("🚫 金额无效，请输入数字。")
        return

    # 生成订单
    suffix = round(random.uniform(0.01, 0.99), 2)
    real_amount = round(base_amount + suffix, 2)
    order_id = str(uuid4())

    create_recharge_order(order_id, user_id, base_amount, real_amount)

    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={RECHARGE_ADDRESS}"
    msg = f"""
请向以下地址转账：

🧾订单编号：`{order_id}`
📬充值地址：`{RECHARGE_ADDRESS}`
💵充值金额：**`{real_amount:.2f}` USDT**

⚠️ 请务必支付 *精确金额*。

⏳ 订单30分钟内有效。

到账后将自动识别并充值成功。
    """

    await update.message.reply_photo(
        photo=qr_url,
        caption=msg,
        parse_mode="Markdown"
    )

    context.user_data.pop("action", None)
