from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import random
import string
import time
import os
import requests
import psycopg2
from dotenv import load_dotenv

load_dotenv()

RECHARGE_ADDRESS = os.getenv("TRC20_ADDRESS")  # 管理员设置的收款地址

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

# ✅ 显示充值菜单
async def recharge_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        user = update.callback_query.from_user
    else:
        user = update.message.from_user

    user_info = get_user_info(user.id)
    usdt_balance = round(user_info[1], 2) if user_info else 0
    cny_balance = round(user_info[2], 2) if user_info else 0

    text = f"""
🪪用户名：@{user.username}
🪪用户ID：{user.id}
💵USDT余额：{usdt_balance:.2f}
💴CNY余额：{cny_balance:.2f}

请选择充值方式：
    """
    keyboard = [
        [InlineKeyboardButton("💵USDT充值", callback_data="recharge_usdt")],
        [InlineKeyboardButton("⬅️返回上一级", callback_data="back_to_main")]
    ]
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ✅ 点击 USDT 充值按钮，提示输入金额
async def recharge_prompt_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["action"] = "usdt_recharge"
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("请输入要充值的 💵USDT 金额：")

# ✅ 用户输入充值金额
async def handle_recharge_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text)
        if amount <= 0:
            await update.message.reply_text("⚠️ 金额必须大于 0，请重新输入。")
            return
    except ValueError:
        await update.message.reply_text("⚠️ 请输入有效的数字金额。")
        return

    user_id = update.message.from_user.id
    username = update.message.from_user.username

    unique_decimal = round(random.uniform(0.01, 0.99), 2)
    final_amount = round(amount + unique_decimal, 2)

    order_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
    timestamp = int(time.time())

    # 保存订单
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO recharge_orders (order_id, user_id, amount, final_amount, status, created_at)
        VALUES (%s, %s, %s, %s, %s, to_timestamp(%s))
    """, (order_id, user_id, amount, final_amount, "pending", timestamp))
    conn.commit()
    cur.close()
    conn.close()

    photo_url = "https://i.ibb.co/Vxr9cCM/usdt.png"  # 你可替换成你自己的图片链接

    caption = f"""
🆔订单号：`{order_id}`
📥 请向以下地址转账：

地址：`{RECHARGE_ADDRESS}`
金额（含标识）：`{final_amount}` USDT

🕒 请在 30 分钟内完成，否则订单将失效。
    """

    keyboard = [
        [InlineKeyboardButton("⬅️返回上一级", callback_data="recharge")]
    ]

    await update.message.reply_photo(
        photo=photo_url,
        caption=caption,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ✅ 后台定时检查订单状态
def check_pending_orders_with_trongrid():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT order_id, user_id, final_amount FROM recharge_orders
        WHERE status = 'pending' AND created_at > NOW() - INTERVAL '30 minutes'
    """)
    orders = cur.fetchall()

    for order_id, user_id, final_amount in orders:
        # 调用 TronGrid 查询该地址的转账记录
        url = f"https://api.trongrid.io/v1/accounts/{RECHARGE_ADDRESS}/transactions/trc20"
        try:
            response = requests.get(url, timeout=10)
            data = response.json()
            for tx in data.get("data", []):
                if tx["type"] != "Transfer":
                    continue
                if tx["to"].lower() != RECHARGE_ADDRESS.lower():
                    continue
                amount = int(tx["value"]) / (10 ** 6)
                if round(amount, 2) == round(final_amount, 2):
                    # 成功匹配到账
                    cur.execute("UPDATE recharge_orders SET status = 'success' WHERE order_id = %s", (order_id,))
                    cur.execute("UPDATE users SET usdt_balance = usdt_balance + %s WHERE user_id = %s", (amount, user_id))
                    cur.execute("INSERT INTO transactions (user_id, transaction_type, amount, timestamp) VALUES (%s, 'recharge', %s, NOW())", (user_id, amount))
                    conn.commit()

                    # 尝试通知用户
                    try:
                        from telegram import Bot
                        bot = Bot(token=os.getenv("BOT_TOKEN"))
                        bot.send_message(chat_id=user_id, text=f"✅ 充值成功！已到账 {amount} USDT，感谢使用 Ant 钱包。")
                    except Exception as e:
                        print(f"通知用户失败: {e}")
                    break
        except Exception as e:
            print(f"TronGrid 请求失败: {e}")

    cur.close()
    conn.close()

# ✅ 清理超时订单
def expire_old_orders():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        DELETE FROM recharge_orders
        WHERE status = 'pending' AND created_at < NOW() - INTERVAL '30 minutes'
    """)
    conn.commit()
    cur.close()
    conn.close()
