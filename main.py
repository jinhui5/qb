import os, asyncio
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from handlers.start import start
from handlers.profile import profile, recharge_records, withdraw_records, transfer_records, redpacket_records, escrow_records, back_to_main
from handlers.exchange import exchange, usdt_to_cny, cny_to_usdt, handle_exchange_input, back_to_main, handle_exchange_input
from handlers.recharge import recharge_menu, recharge_prompt_amount, handle_recharge_amount, handle_recharge_amount

# 后台监听任务
async def periodic_check(context: ContextTypes.DEFAULT_TYPE):
    print("⏳ 后台任务：检查订单和清理过期订单")
    check_pending_orders_with_trongrid()
    expire_old_orders()

def main():
    # 从环境变量中读取 BOT_TOKEN
    bot_token = os.getenv("BOT_TOKEN")
    
    if not bot_token:
        print("错误：没有设置 BOT_TOKEN 环境变量。")
        return

    # 使用读取到的 token 创建 Telegram 应用实例
    app = ApplicationBuilder().token(bot_token).build()
    
    # 注册 /start 命令的处理函数
    app.add_handler(CommandHandler("start", start))
    
    # 注册个人中心菜单回调函数
    app.add_handler(CallbackQueryHandler(profile, pattern="^profile$"))
    app.add_handler(CallbackQueryHandler(recharge_records, pattern="^recharge_records$"))
    app.add_handler(CallbackQueryHandler(withdraw_records, pattern="^withdraw_records$"))
    app.add_handler(CallbackQueryHandler(transfer_records, pattern="^transfer_records$"))
    app.add_handler(CallbackQueryHandler(redpacket_records, pattern="^redpacket_records$"))
    app.add_handler(CallbackQueryHandler(escrow_records, pattern="^escrow_records$"))
    app.add_handler(CallbackQueryHandler(back_to_main, pattern="^back_to_main$"))
    
    # 注册兑换回调函数
    app.add_handler(CallbackQueryHandler(exchange, pattern="^exchange$"))
    app.add_handler(CallbackQueryHandler(usdt_to_cny, pattern="^usdt_to_cny$"))
    app.add_handler(CallbackQueryHandler(cny_to_usdt, pattern="^cny_to_usdt$"))
    
    # 处理用户输入
    # app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_exchange_input))

    # 注册充值回调函数
    app.add_handler(CallbackQueryHandler(recharge_menu, pattern="^recharge$"))
    app.add_handler(CallbackQueryHandler(recharge_prompt_amount, pattern="^recharge_usdt$"))
    app.add_handler(CallbackQueryHandler(back_to_main, pattern="^back_to_main$"))
    async def handle_user_input(update, context):
        action = context.user_data.get("action")
        if action == "usdt_to_cny" or action == "cny_to_usdt":
            await handle_exchange_input(update, context)
        elif action == "usdt_recharge":
            await handle_recharge_amount(update, context)
        else:
            await update.message.reply_text("⚠️ 当前无可处理的操作，请从菜单开始。")

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_input))

    app.job_queue.run_repeating(periodic_check, interval=60, first=10)
    
    app.run_polling()

if __name__ == "__main__":
    main()
