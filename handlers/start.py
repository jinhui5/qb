from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import psycopg2
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 连接数据库
def get_connection():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

# 获取用户信息
def get_user_info(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT username, usdt_balance, cny_balance FROM users WHERE user_id = %s", (user_id,))
    user_info = cur.fetchone()
    cur.close()
    conn.close()
    return user_info

# 插入用户信息（首次启动时）
def add_user_to_db(user_id, username):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO users (user_id, username, usdt_balance, cny_balance) 
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (user_id) DO NOTHING;
    """, (user_id, username, 0.00, 0.00))  # 初始余额为 0
    conn.commit()
    cur.close()
    conn.close()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 判断 update 是来自 message 还是 callback_query
    if update.message:
        user_id = update.message.from_user.id
        username = update.message.from_user.username
    elif update.callback_query:
        user_id = update.callback_query.from_user.id
        username = update.callback_query.from_user.username
    else:
        return  # 如果没有 message 或 callback_query，直接返回

    # 获取用户余额信息
    user_info = get_user_info(user_id)
    if not user_info:
        add_user_to_db(user_id, username)  # 新用户插入数据库

    # 获取最新的用户余额信息
    user_info = get_user_info(user_id)
    if user_info:
        user_name = user_info[0] if user_info[0] else username  # 使用数据库存储的用户名或 Telegram 的用户名
        usdt_balance = round(user_info[1], 2)  # 保留两位小数
        cny_balance = round(user_info[2], 2)  # 保留两位小数
    else:
        user_name = username
        usdt_balance = 0.00
        cny_balance = 0.00

    # 格式化欢迎消息
    welcome_message = f"""
欢迎使用 Ant 钱包 - 让支付更简单

🪪用户名：@{user_name}
🪪用户ID：{user_id}
💵USDT余额：{usdt_balance:.2f}
💴CNY余额：{cny_balance:.2f}

请选择以下功能：
"""

    # 创建底部菜单按钮
    keyboard = [
        [
            InlineKeyboardButton("👤个人中心", callback_data="profile"),
            InlineKeyboardButton("🔄兑换", callback_data="exchange"),
        ],
        [
            InlineKeyboardButton("📥充值", callback_data="recharge"),
            InlineKeyboardButton("📤提现", callback_data="withdraw"),
        ],
        [
            InlineKeyboardButton("💳转账", callback_data="transfer"),
            InlineKeyboardButton("🧧红包", callback_data="redpacket"),
        ],
        [
            InlineKeyboardButton("⚖️担保交易", callback_data="escrow"),
            InlineKeyboardButton("🤵‍♂️联系客服", callback_data="contact"),
        ],
    ]
    
    # 创建菜单
    reply_markup = InlineKeyboardMarkup(keyboard)

    # 发送欢迎消息并附上底部菜单按钮
    if update.message:
        await update.message.reply_text(welcome_message, reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.edit_message_text(welcome_message, reply_markup=reply_markup)
