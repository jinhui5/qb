from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import psycopg2
import os
from dotenv import load_dotenv
from handlers.start import start  # 导入 start 函数

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

# 汇率
USDT_TO_CNY_RATE = 7  # 1 USDT = 7 CNY
CNY_TO_USDT_RATE = 1 / USDT_TO_CNY_RATE  # 1 CNY = 1 / 7 USDT

# 兑换菜单
async def exchange(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        user_id = update.callback_query.from_user.id
        user_name = update.callback_query.from_user.username
    elif update.message:
        user_id = update.message.from_user.id
        user_name = update.message.from_user.username
    else:
        return  # 如果既不是 callback_query 也不是 message，则直接返回

    user_info = get_user_info(user_id)

    if user_info:
        user_name = user_info[0]  # 用户名
        usdt_balance = round(user_info[1], 2)  # USDT余额
        cny_balance = round(user_info[2], 2)  # CNY余额
    else:
        user_name = update.callback_query.from_user.username
        usdt_balance = 0.00
        cny_balance = 0.00
    
    # 汇率保留两位小数
    usdt_to_cny_rate = round(USDT_TO_CNY_RATE, 2)
    cny_to_usdt_rate = round(CNY_TO_USDT_RATE, 2)

    keyboard = [
        [InlineKeyboardButton("💵USDT → 💴CNY", callback_data="usdt_to_cny")],
        [InlineKeyboardButton("💴CNY → 💵USDT", callback_data="cny_to_usdt")],
        [InlineKeyboardButton("⬅️返回上一级", callback_data="back_to_main")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.callback_query:
        await update.callback_query.answer()
    
    # 格式化消息，包含用户信息和汇率
    message_text = f"""

🪪用户名：@{user_name}
🪪用户ID：{user_id}
💵USDT余额：{usdt_balance:.2f}
💴CNY余额：{cny_balance:.2f}

当前汇率：
1 USDT = {usdt_to_cny_rate} CNY
1 CNY = {cny_to_usdt_rate:.2f} USDT

请选择兑换方向：
"""

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text=message_text,
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            text=message_text,
            reply_markup=reply_markup
        )
        
# 兑换 USDT → CNY
async def usdt_to_cny(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.callback_query.from_user.id
    user_info = get_user_info(user_id)
    
    if user_info:
        usdt_balance = user_info[1]
    else:
        await update.callback_query.answer("无法获取您的信息，请稍后再试。")
        return

    # 确保 callback_query 存在
    if update.callback_query:
        await update.callback_query.answer()
    
    await update.callback_query.edit_message_text("请输入您要兑换的💵 USDT 数量：")
    context.user_data["action"] = "usdt_to_cny"  # 保存用户当前兑换操作
    context.user_data["usdt_balance"] = usdt_balance

# 兑换 CNY → USDT
async def cny_to_usdt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.callback_query.from_user.id
    user_info = get_user_info(user_id)
    
    if user_info:
        cny_balance = user_info[2]
    else:
        await update.callback_query.answer("无法获取您的信息，请稍后再试。")
        return

    # 确保 callback_query 存在
    if update.callback_query:
        await update.callback_query.answer()
    
    await update.callback_query.edit_message_text("请输入您要兑换的💴 CNY 数量：")
    context.user_data["action"] = "cny_to_usdt"  # 保存用户当前兑换操作
    context.user_data["cny_balance"] = cny_balance

# 用户输入兑换金额
async def handle_exchange_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id  # 直接使用来自消息的 user_id
    user_info = get_user_info(user_id)
    
    # 获取用户余额
    usdt_balance = 0.00
    cny_balance = 0.00

    if user_info:
        usdt_balance = round(user_info[1], 2)  # USDT余额
        cny_balance = round(user_info[2], 2)  # CNY余额

    if context.user_data.get("action") == "usdt_to_cny":
        try:
            amount = float(update.message.text)

            if amount > usdt_balance:
                # 提示余额不足，并自动返回兑换菜单
                await update.message.reply_text("🚨操作失败，余额不足！")
                # 自动返回兑换菜单，且只调用一次
                await exchange(update, context)
            else:
                cny_amount = round(amount * USDT_TO_CNY_RATE, 2)  # 保留两位小数
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("UPDATE users SET usdt_balance = usdt_balance - %s, cny_balance = cny_balance + %s WHERE user_id = %s", 
                            (amount, cny_amount, user_id))
                conn.commit()
                cur.close()
                conn.close()

                # 兑换成功后，自动返回兑换菜单，且只调用一次
                await update.message.reply_text(f"成功兑换 {amount}💵 USDT 为 {cny_amount:.2f}💴 CNY！")
                await exchange(update, context)
        except ValueError:
            await update.message.reply_text("请输入有效的数字。")
        
    elif context.user_data.get("action") == "cny_to_usdt":
        try:
            amount = float(update.message.text)

            if amount > cny_balance:
                # 提示余额不足，并自动返回兑换菜单
                await update.message.reply_text("🚨操作失败，余额不足！")
                # 自动返回兑换菜单，且只调用一次
                await exchange(update, context)
            else:
                usdt_amount = round(amount * CNY_TO_USDT_RATE, 2)  # 保留两位小数
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("UPDATE users SET cny_balance = cny_balance - %s, usdt_balance = usdt_balance + %s WHERE user_id = %s", 
                            (amount, usdt_amount, user_id))
                conn.commit()
                cur.close()
                conn.close()

                # 兑换成功后，自动返回兑换菜单，且只调用一次
                await update.message.reply_text(f"成功兑换 {amount}💴 CNY 为 {usdt_amount:.2f}💵 USDT！")
                await exchange(update, context)
        except ValueError:
            await update.message.reply_text("请输入有效的数字。")
   
# 返回主菜单
async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await start(update, context)
