# coinflipbot.py (Updated with emojis 🌟)
import sqlite3
import random
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

TOKEN = "7644511468:AAHb7jGK-F8f-YyMtRFCJL0O85Z2MG8JIWM"
BOT_USERNAME = "coinflipcryptobot"
ADMIN_CHAT_ID = 6115778445
TON_WALLET_ADDRESS = "UQBdwbnL-66szyr-o11syfLHB48hGjz1Tx9hLNlDxipCz4vr"

GC_TO_TON_RATE = 250
AWAITING_DEPOSIT_CONFIRMATION = {}

def init_db():
    conn = sqlite3.connect("coinflip.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        balance REAL DEFAULT 0,
        referral_code TEXT UNIQUE,
        referred_by TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS deposits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount REAL,
        ton_amount REAL,
        status TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS withdrawals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount REAL,
        address TEXT,
        status TEXT
    )''')
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect("coinflip.db")
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def update_balance(user_id, amount):
    conn = sqlite3.connect("coinflip.db")
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    user_id = user.id
    username = user.username or ""
    args = context.args
    referral = args[0] if args else None

    conn = sqlite3.connect("coinflip.db")
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    if not c.fetchone():
        code = f"REF{user_id}"
        c.execute("INSERT INTO users (user_id, username, balance, referral_code, referred_by) VALUES (?, ?, ?, ?, ?)",
                  (user_id, username, 0, code, referral))
        if referral:
            c.execute("UPDATE users SET balance = balance + 25 WHERE referral_code = ?", (referral,))
        c.execute("UPDATE users SET balance = balance + 3 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

    keyboard = [[KeyboardButton("🎲 Bet"), KeyboardButton("💰 Balance")],
                [KeyboardButton("🎁 Refer & Earn"), KeyboardButton("📥 Deposit")],
                [KeyboardButton("📤 Withdraw")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("👋 Welcome to the Coin Flip Bot! Use the menu below to begin.", reply_markup=reply_markup)

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user = get_user(user_id)
    if user:
        await update.message.reply_text(f"💰 Your balance: {user[2]:.2f} GC")
    else:
        await update.message.reply_text("❌ User not found.")

async def refer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user = get_user(user_id)
    if user:
        ref_link = f"https://t.me/{BOT_USERNAME}?start={user[3]}"
        await update.message.reply_text(f"🔗 Share this referral link and earn 25 GC when someone joins:\n{ref_link}")

async def deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📥 Enter the amount you want to deposit in GC:")
    return 1

async def deposit_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text)
        user_id = update.message.from_user.id
        ton_amount = round(amount / GC_TO_TON_RATE, 4)

        conn = sqlite3.connect("coinflip.db")
        c = conn.cursor()
        c.execute("INSERT INTO deposits (user_id, amount, ton_amount, status) VALUES (?, ?, ?, 'pending')",
                  (user_id, amount, ton_amount))
        conn.commit()
        conn.close()

        AWAITING_DEPOSIT_CONFIRMATION[user_id] = amount

        msg = (f"📨 Please send <b>{ton_amount} TON</b> to this address:\n"
               f"<code>{TON_WALLET_ADDRESS}</code>\n\n"
               f"✅ Click 'Done' once sent or ❌ 'Cancel'.")
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML,
            reply_markup=ReplyKeyboardMarkup([["✅ Done", "❌ Cancel"]], resize_keyboard=True))
        return 2
    except ValueError:
        await update.message.reply_text("⚠️ Please enter a valid number.")
        return 1

async def deposit_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    user_id = user.id
    amount = AWAITING_DEPOSIT_CONFIRMATION.get(user_id)
    if amount:
        await context.bot.send_message(
            ADMIN_CHAT_ID,
            f"📩 {user.username or user_id} requested deposit of {amount} GC"
        )
        await update.message.reply_text("🕐 Deposit request sent to admin. Please wait ~15 minutes.",
            reply_markup=ReplyKeyboardMarkup(
                [["🎲 Bet", "💰 Balance"], ["🎁 Refer & Earn", "📥 Deposit"], ["📤 Withdraw"]], resize_keyboard=True))
    return ConversationHandler.END

async def deposit_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Deposit cancelled.",
        reply_markup=ReplyKeyboardMarkup(
            [["🎲 Bet", "💰 Balance"], ["🎁 Refer & Earn", "📥 Deposit"], ["📤 Withdraw"]], resize_keyboard=True))
    return ConversationHandler.END

async def bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎯 Choose Heads or Tails and amount (e.g., Heads 1.5):")

async def process_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        choice, amount = update.message.text.split()
        amount = float(amount)
        user_id = update.message.from_user.id
        user = get_user(user_id)

        if amount < 0.1:
            return await update.message.reply_text("⚠️ Minimum bet is 0.1 GC")
        if user[2] < amount:
            return await update.message.reply_text("❌ Insufficient balance.")

        outcome = random.choice(["Heads", "Tails"])
        if choice.lower() == outcome.lower():
            win_amount = round(amount * 1.95, 2)
            update_balance(user_id, win_amount)
            result = f"🎉 You WON! Coin was {outcome}. You earned {win_amount} GC."
        else:
            update_balance(user_id, -amount)
            result = f"😢 You LOST! Coin was {outcome}. You lost {amount} GC."
        await update.message.reply_text(result)
    except:
        await update.message.reply_text("⚠️ Invalid input. Use format like: Heads 1.5")

async def withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📤 Enter amount and TON address (e.g., 100 EQabc123...):")
    return 1

async def process_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount, address = update.message.text.split()
        amount = float(amount)
        user_id = update.message.from_user.id
        user = get_user(user_id)

        if user[2] < amount:
            return await update.message.reply_text("❌ Insufficient balance.")

        conn = sqlite3.connect("coinflip.db")
        c = conn.cursor()
        c.execute("INSERT INTO withdrawals (user_id, amount, address, status) VALUES (?, ?, ?, 'pending')",
                  (user_id, amount, address))
        conn.commit()
        conn.close()

        await context.bot.send_message(
            ADMIN_CHAT_ID,
            f"📤 {update.message.from_user.username or user_id} requested withdrawal of {amount} GC to {address}"
        )

        await update.message.reply_text("✅ Withdrawal request sent to admin. Please wait.")
    except:
        await update.message.reply_text("⚠️ Invalid format. Use: 100 EQabc123")
    return ConversationHandler.END

async def pending_deposits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat_id != ADMIN_CHAT_ID:
        return
    conn = sqlite3.connect("coinflip.db")
    c = conn.cursor()
    c.execute("SELECT id, user_id, amount FROM deposits WHERE status = 'pending'")
    rows = c.fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("✅ No pending deposits.")
    else:
        msg = "📥 Pending Deposits:\n"
        for idx, (did, uid, amt) in enumerate(rows, 1):
            msg += f"{idx}. ID {did} | User {uid} | {amt} GC\n"
        await update.message.reply_text(msg)

async def pending_withdrawals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat_id != ADMIN_CHAT_ID:
        return
    conn = sqlite3.connect("coinflip.db")
    c = conn.cursor()
    c.execute("SELECT id, user_id, amount, address FROM withdrawals WHERE status = 'pending'")
    rows = c.fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("✅ No pending withdrawals.")
    else:
        msg = "📤 Pending Withdrawals:\n"
        for idx, (wid, uid, amt, addr) in enumerate(rows, 1):
            msg += f"{idx}. ID {wid} | User {uid} | {amt} GC to {addr}\n"
        await update.message.reply_text(msg)

async def admin_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat_id != ADMIN_CHAT_ID:
        return
    args = context.args
    if not args or len(args) < 2:
        return await update.message.reply_text("⚠️ Usage: /approve deposit|withdraw ID")

    action, target_id = args[0], int(args[1])
    conn = sqlite3.connect("coinflip.db")
    c = conn.cursor()

    if action == "deposit":
        c.execute("SELECT user_id, amount FROM deposits WHERE id = ?", (target_id,))
        row = c.fetchone()
        if row:
            update_balance(row[0], row[1])
            c.execute("UPDATE deposits SET status = 'approved' WHERE id = ?", (target_id,))
    elif action == "withdraw":
        c.execute("UPDATE withdrawals SET status = 'approved' WHERE id = ?", (target_id,))

    conn.commit()
    conn.close()
    await update.message.reply_text(f"✅ {action.title()} {target_id} approved.")

def main():
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("approve", admin_approve))
    app.add_handler(CommandHandler("pendingdeposits", pending_deposits))
    app.add_handler(CommandHandler("pendingwithdrawals", pending_withdrawals))

    deposit_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📥 Deposit$"), deposit)],
        states={
            1: [MessageHandler(filters.TEXT & ~filters.COMMAND, deposit_amount)],
            2: [MessageHandler(filters.Regex("^✅ Done$"), deposit_done),
                MessageHandler(filters.Regex("^❌ Cancel$"), deposit_cancel)]
        },
        fallbacks=[]
    )

    withdraw_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📤 Withdraw$"), withdraw)],
        states={1: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_withdraw)]},
        fallbacks=[]
    )

    app.add_handler(MessageHandler(filters.Regex("^💰 Balance$"), balance))
    app.add_handler(MessageHandler(filters.Regex("^🎁 Refer & Earn$"), refer))
    app.add_handler(MessageHandler(filters.Regex("^🎲 Bet$"), bet))
    app.add_handler(MessageHandler(filters.Regex(r"^(Heads|Tails) \d+(\.\d+)?$"), process_bet))
    app.add_handler(deposit_conv)
    app.add_handler(withdraw_conv)

    app.run_polling()

if __name__ == "__main__":
    main()
