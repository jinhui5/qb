import os
from dotenv import load_dotenv
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

# 导入功能模块
from handlers.start import start
from handlers.profile import (
    profile, recharge_records, withdraw_records,
    transfer_records, redpacket_records, escrow_records,
    back_to_main
)
from handlers.exchange import (
    exchange, usdt_to_cny, cny_to_usdt, handle_exchange_input
)
from handlers.recharge import (
    recharge_menu, recharge_prompt_amount, handle_recharge_amount,
    check_pending_orders_with_trongrid, expire_old_orders
)
from handlers.transfer import (
    transfer_menu, transfer_usdt, transfer_cny,
    handle_transfer_amount, handle_transfer_username,
    confirm_transfer, back_to_transfer
)

load_dotenv()

# ✅ 异步定时任务（每分钟检查充值）
async def periodic_check(context: ContextTypes.DEFAULT_TYPE):
    print("⏳ 后台任务：检查充值订单状态")
    check_pending_orders_with_trongrid()
    expire_old_orders()

# ✅ 统一文本输入处理函数（转账/兑换/充值）
async def handle_user_input(update, context):
    action = context.user_data.get("action")

    if action in ["usdt_to_cny", "cny_to_usdt"]:
        await handle_exchange_input(update, context)

    elif action in ["transfer_usdt", "transfer_cny"]:
        if context.user_data.get("awaiting_username"):
            await handle_transfer_username(update, context)
        else:
            await handle_transfer_amount(update, context)

    elif action == "usdt_recharge":
        await handle_recharge_amount(update, context)

    else:
        await update.message.reply_text("⚠️ 当前无可处理的操作，请从菜单开始。")

# ✅ 主函数入口
def main():
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        print("❌ 错误：BOT_TOKEN 未设置")
        return

    app = ApplicationBuilder().token(bot_token).build()

    # ✅ 命令处理
    app.add_handler(CommandHandler("start", start))

    # ✅ 按钮回调处理
    app.add_handler(CallbackQueryHandler(profile, pattern="^profile$"))
    app.add_handler(CallbackQueryHandler(recharge_records, pattern="^recharge_records$"))
    app.add_handler(CallbackQueryHandler(withdraw_records, pattern="^withdraw_records$"))
    app.add_handler(CallbackQueryHandler(transfer_records, pattern="^transfer_records$"))
    app.add_handler(CallbackQueryHandler(redpacket_records, pattern="^redpacket_records$"))
    app.add_handler(CallbackQueryHandler(escrow_records, pattern="^escrow_records$"))

    app.add_handler(CallbackQueryHandler(exchange, pattern="^exchange$"))
    app.add_handler(CallbackQueryHandler(usdt_to_cny, pattern="^usdt_to_cny$"))
    app.add_handler(CallbackQueryHandler(cny_to_usdt, pattern="^cny_to_usdt$"))

    app.add_handler(CallbackQueryHandler(recharge_menu, pattern="^recharge$"))
    app.add_handler(CallbackQueryHandler(recharge_prompt_amount, pattern="^recharge_usdt$"))

    app.add_handler(CallbackQueryHandler(transfer_menu, pattern="^transfer$"))
    app.add_handler(CallbackQueryHandler(transfer_usdt, pattern="^transfer_usdt$"))
    app.add_handler(CallbackQueryHandler(transfer_cny, pattern="^transfer_cny$"))
    app.add_handler(CallbackQueryHandler(confirm_transfer, pattern="^confirm_transfer$"))
    app.add_handler(CallbackQueryHandler(back_to_transfer, pattern="^transfer_menu$"))
    app.add_handler(CallbackQueryHandler(back_to_main, pattern="^back_to_main$"))

    # ✅ 文本消息处理
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_input))

    # ✅ 后台轮询任务
    app.job_queue.run_repeating(periodic_check, interval=60, first=10)

    print("🤖 Ant 钱包机器人已启动")
    app.run_polling()

if __name__ == "__main__":
    main()
