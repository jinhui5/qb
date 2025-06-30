from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import psycopg2
import os
from dotenv import load_dotenv
from handlers.start import start

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

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.callback_query.from_user.id
    username = update.callback_query.from_user.username
    
    # 获取用户余额信息
    user_info = get_user_info(user_id)
    if user_info:
        user_name = user_info[0] if user_info[0] else username
        usdt_balance = round(user_info[1], 2)  # 保留两位小数
        cny_balance = round(user_info[2], 2)  # 保留两位小数
    else:
        user_name = username
        usdt_balance = 0.00
        cny_balance = 0.00

    # 格式化个人中心消息
    profile_message = f"""
🪪用户名：@{user_name}
🪪用户ID：`{user_id}`
💵USDT余额：{usdt_balance:.2f}
💴CNY余额：{cny_balance:.2f}
"""
    
    # 创建个人中心菜单按钮
    keyboard = [
        [InlineKeyboardButton("👀查看充值记录", callback_data="recharge_records")],
        [InlineKeyboardButton("👀查看提现记录", callback_data="withdraw_records")],
        [InlineKeyboardButton("👀查看转账记录", callback_data="transfer_records")],
        [InlineKeyboardButton("👀查看红包记录", callback_data="redpacket_records")],
        [InlineKeyboardButton("👀查看担保交易", callback_data="escrow_records")],
        [InlineKeyboardButton("⬅️返回上一级", callback_data="back_to_main")]
    ]
    
    # 创建菜单
    reply_markup = InlineKeyboardMarkup(keyboard)

    # 发送个人中心消息并附上菜单
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(profile_message, reply_markup=reply_markup)

# 查询用户的充值记录（近10条）
async def recharge_records(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.callback_query.from_user.id
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT amount, timestamp FROM transactions 
        WHERE user_id = %s AND transaction_type = 'recharge'
        ORDER BY timestamp DESC LIMIT 10
    """, (user_id,))
    records = cur.fetchall()
    cur.close()
    conn.close()

    if records:
        records_message = "你的近10条充值记录：\n"
        for record in records:
            records_message += f"金额: {record[0]} CNY, 时间: {record[1]}\n"
    else:
        records_message = "没有充值记录。"
    
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(records_message)

# 查询用户的提现记录（近10条）
async def withdraw_records(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.callback_query.from_user.id
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT amount, timestamp FROM transactions 
        WHERE user_id = %s AND transaction_type = 'withdraw'
        ORDER BY timestamp DESC LIMIT 10
    """, (user_id,))
    records = cur.fetchall()
    cur.close()
    conn.close()

    if records:
        records_message = "你的近10条提现记录：\n"
        for record in records:
            records_message += f"金额: {record[0]} CNY, 时间: {record[1]}\n"
    else:
        records_message = "没有提现记录。"
    
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(records_message)

# 查询用户的转账记录（近10条）
async def transfer_records(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.callback_query.from_user.id
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT amount, timestamp FROM transactions 
        WHERE user_id = %s AND transaction_type = 'transfer'
        ORDER BY timestamp DESC LIMIT 10
    """, (user_id,))
    records = cur.fetchall()
    cur.close()
    conn.close()

    if records:
        records_message = "你的近10条转账记录：\n"
        for record in records:
            records_message += f"金额: {record[0]} CNY, 时间: {record[1]}\n"
    else:
        records_message = "没有转账记录。"
    
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(records_message)

# 查询用户的红包记录（近10条）
async def redpacket_records(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.callback_query.from_user.id
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT amount, timestamp FROM red_packets 
        WHERE user_id = %s
        ORDER BY timestamp DESC LIMIT 10
    """, (user_id,))
    records = cur.fetchall()
    cur.close()
    conn.close()

    if records:
        records_message = "你的近10条红包记录：\n"
        for record in records:
            records_message += f"金额: {record[0]} CNY, 时间: {record[1]}\n"
    else:
        records_message = "没有红包记录。"
    
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(records_message)

# 查询用户的担保交易记录（近10条）
async def escrow_records(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.callback_query.from_user.id
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT amount, timestamp FROM transactions 
        WHERE user_id = %s AND transaction_type = 'escrow'
        ORDER BY timestamp DESC LIMIT 10
    """, (user_id,))
    records = cur.fetchall()
    cur.close()
    conn.close()

    if records:
        records_message = "你的近10条担保交易记录：\n"
        for record in records:
            records_message += f"金额: {record[0]} CNY, 时间: {record[1]}\n"
    else:
        records_message = "没有担保交易记录。"
    
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(records_message)

# 返回到主菜单
async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    print("返回到主菜单")
    await start(update, context)
