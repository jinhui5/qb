from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ContextTypes
from uuid import uuid4
import os
import random
import psycopg2
from dotenv import load_dotenv
from datetime import datetime, timedelta

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

# 插入订单到数据库
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

# 更新订单状态并充值到账
def complete_recharge(order_id):
    conn = get_connection()
    cur = conn.cursor()

    # 查询订单信息
    cur.execute("SELECT user_id, amount_input, amount_real FROM recharge_orders WHERE order_id = %s", (order_id,))
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        return False
    user_id, input_amt, real_amt = row

    # 更新用户余额
    cur.execute("UPDATE users SET usdt_balance = usdt_balance + %s WHERE user_id = %s", (input_amt, user_id))
    
    # 添加记录
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

# 用户点击“📥充值”按钮
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

# 用户点击“💵USDT充值”
async def recharge_prompt_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("请输入你要充值的 💵USDT 金额：")
    context.user_data["action"] = "usdt_recharge"

# 用户输入充值金额后
async def handle_recharge_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    username = update.message.from_user.username
    user_input = update.message.text

    if context.user_data.get("action") != "usdt_recharge":
        return  # 非充值上下文

    try:
        base_amount = float(user_input)
        if base_amount <= 0:
            await update.message.reply_text("请输入有效金额。")
            return
    except ValueError:
        await update.message.reply_text("请输入数字金额。")
        return

    # 生成订单
    suffix = round(random.uniform(0.01, 0.99), 2)
    real_amount = round(base_amount + suffix, 2)
    order_id = str(uuid4())

    create_recharge_order(order_id, user_id, base_amount, real_amount)

    # 构造返回消息
    qr_image_url = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={RECHARGE_ADDRESS}"
    message_text = f"""
请使用支持 TRC20 的钱包向下方地址转账：

💵充值金额：**{real_amount:.2f} USDT**
📬充值地址：`{RECHARGE_ADDRESS}`
🧾订单编号：`{order_id}`

⚠️请务必转账 *精确金额*，否则将无法自动识别。
⏳订单30分钟内有效，逾期自动取消。
完成充值后稍等几分钟，系统将自动识别到账并完成入账。
    """

    await update.message.reply_photo(
        photo=qr_image_url,
        caption=message_text,
        parse_mode="Markdown"
    )

    # 清除上下文
    context.user_data.pop("action", None)

# TODO: 后台任务示意（示例函数）
def check_pending_orders_with_trongrid():
    """
    可作为独立后台线程或定时任务执行
    - 拉取 recharge_orders where status = 'pending' and expires_at > now()
    - 调用 TronGrid API 获取转账记录
    - 判断是否有匹配金额+时间的交易入账
    - 若匹配成功，调用 complete_recharge(order_id)
    """
    pass  # 实际监听可使用定时任务+TronGrid webhook 或定期轮询

