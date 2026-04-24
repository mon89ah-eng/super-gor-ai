import os
import telebot
import requests
from flask import Flask, request
import threading
import time
import sqlite3
from datetime import datetime, date, timedelta
import hashlib

BOT_TOKEN = "8714413951:AAFVBkBairgC25Kjo9Z-aItHUqRuB9V39uY"
GIGACHAT_KEY = "MDE5ZGJmOGItMmZmYS03ZTQxLWI4ZDYtZjM4NWJiMTJjMzBmOjVkODE4OGEwLWE4YzMtNGJhMC1iZDlmLTU5YTJlMTZhNGZlMw=="

YOUMONEY_ACCOUNT = "4100118733788159"
YOUMONEY_CLIENT_ID = "12577344FC46155099AB89B76856CF69A450D59BCC7822A817773AAA63BC2CC8"
YOUMONEY_CLIENT_SECRET = "D3F2EEE6CE0E079C7E1E27180E150898E6D2F3B3EE5B25888D3371B393BCF605CFA284BFFDDCEF36DF53148721EE35E356B2FC70CC47A39D9A93E26C7228D680"

PREMIUM_PRICE = 299
PREMIUM_DAYS = 30
FREE_DAILY_LIMIT = 10

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY,
                  username TEXT,
                  messages_today INTEGER DEFAULT 0,
                  is_premium INTEGER DEFAULT 0,
                  premium_until TEXT,
                  last_reset TEXT,
                  total_messages INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()
    print("✅ Database initialized")

def add_user(user_id, username):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    today = date.today().isoformat()
    c.execute('''INSERT OR IGNORE INTO users 
                 (user_id, username, last_reset, messages_today) 
                 VALUES (?, ?, ?, 0)''', (user_id, username, today))
    conn.commit()
    conn.close()

def reset_daily_counter(user_id):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    today = date.today().isoformat()
    c.execute('SELECT last_reset FROM users WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    if result and result[0] != today:
        c.execute('''UPDATE users 
                     SET messages_today = 0, last_reset = ? 
                     WHERE user_id = ?''', (today, user_id))
        conn.commit()
    conn.close()

def check_premium(user_id):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('SELECT is_premium, premium_until FROM users WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    conn.close()
    if not result:
        return False
    is_premium, premium_until = result
    if is_premium and premium_until and date.fromisoformat(premium_until) >= date.today():
        return True
    return False

def activate_premium(user_id, days=PREMIUM_DAYS):
    premium_until = (date.today() + timedelta(days=days)).isoformat()
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''UPDATE users 
                 SET is_premium = 1, premium_until = ? 
                 WHERE user_id = ?''', (premium_until, user_id))
    conn.commit()
    conn.close()
    return premium_until

def get_user_stats(user_id):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''SELECT messages_today, is_premium, premium_until, total_messages 
                 FROM users WHERE user_id = ?''', (user_id,))
    result = c.fetchone()
    conn.close()
    if result:
        msgs_today, is_premium, premium_until, total_msgs = result
        if check_premium(user_id):
            status = f"⭐ **Premium** (до {premium_until})"
            remaining = "♾️ Безлимит"
        else:
            status = "🆓 **Free**"
            remaining = f"{max(0, FREE_DAILY_LIMIT - msgs_today)} осталось"
        return status, remaining, total_msgs
    return "🆓 **Free**", f"{FREE_DAILY_LIMIT} осталось", 0

def increment_message_count(user_id):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''UPDATE users 
                 SET messages_today = messages_today + 1,
                     total_messages = total_messages + 1
                 WHERE user_id = ?''', (user_id,))
    conn.commit()
    conn.close()

try:
    bot.remove_webhook()
    print("✅ Telegram Webhook removed")
    time.sleep(1)
except Exception as e:
    print(f"⚠️ Webhook error: {e}")

@app.route('/')
def home():
    return "✅ SuperGorAI Bot is running!"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

@app.route('/youmoney-webhook', methods=['POST'])
def youmoney_webhook():
    try:
        data = request.form
        print("🔔 Webhook received")
        if YOUMONEY_CLIENT_SECRET:
            params_to_sign = {
                'amount': data.get('amount', ''),
                'codepro': data.get('codepro', 'false'),
                'currency': data.get('currency', '643'),
                'datetime': data.get('datetime', ''),
                'label': data.get('label', ''),
                'notification_type': data.get('notification_type', ''),
                'operation_id': data.get('operation_id', ''),
                'sender': data.get('sender', ''),
                'unaccepted': data.get('unaccepted', 'false')
            }
            sorted_params = sorted(params_to_sign.items())
            params_str = '&'.join([f"{k}={v}" for k, v in sorted_params])
            string_to_sign = params_str + YOUMONEY_CLIENT_SECRET
            signature = hashlib.sha1(string_to_sign.encode('utf-8')).hexdigest()
            received_signature = request.headers.get('X-YooMoney-SHA1')
            if received_signature and received_signature.lower() != signature.lower():
                print("❌ Invalid Signature")
                return 'ERROR', 403
        amount = data.get('amount')
        if (
            data.get('notification_type') == 'p2p-incoming'
            and amount is not None
            and float(amount) == PREMIUM_PRICE
        ):
            label = data.get('label')
            if label and label.startswith('premium_user_'):
                user_id = int(label.replace('premium_user_', ''))
                premium_until = activate_premium(user_id)
                print(f"✅ Premium activated for {user_id}")
                try:
                    bot.send_message(
                        user_id,
                        f"🎉 **Оплата прошла успешно!**\n\n"
                        f"✅ **Premium активирован до {premium_until}**\n"
                        f"Спасибо за поддержку! 🚀",
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    print(f"⚠️ Could not send message: {e}")
        return 'OK', 200
    except Exception as e:
        print(f"❌ Webhook Error: {e}")
        return 'ERROR', 500

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    add_user(user_id, message.from_user.username or "User")
    status, remaining, total = get_user_stats(user_id)
    bot.reply_to(message,
        f"👋 **Привет!**\n\n"
        f"📊 **Твой статус:**\n{status}\n"
        f"📩 Осталось: {remaining}\n"
        f"📈 Всего: {total}\n\n"
        f"💎 **Premium:** {PREMIUM_PRICE}₽/{PREMIUM_DAYS} дней\n"
        f"/premium - Подробнее\n"
        f"/pay - Оплатить",
        parse_mode='Markdown')

@bot.message_handler(commands=['premium'])
def premium_info(message):
    if check_premium(message.from_user.id):
        bot.reply_to(message, "⭐ У тебя уже есть Premium!")
        return
    bot.reply_to(message,
        f"⭐ **PREMIUM**\n\n"
        f"✅ Безлимитные сообщения\n"
        f"✅ Приоритетная поддержка\n\n"
        f"**Цена:** {PREMIUM_PRICE}₽\n\n"
        f"Нажми /pay для оплаты!",
        parse_mode='Markdown')

@bot.message_handler(commands=['pay'])
def pay_premium(message):
    user_id = message.from_user.id
    if check_premium(user_id):
        bot.reply_to(message, "⭐ У тебя уже есть Premium!")
        return
    link = (
        f"https://yoomoney.ru/quickpay/confirm.xml?"
        f"receiver={YOUMONEY_ACCOUNT}&"
        f"targets=Premium+subscription&"
        f"paymentType=S&"
        f"sum={PREMIUM_PRICE}&"
        f"label=premium_user_{user_id}"
    )
    bot.reply_to(message,
        f"💳 **Оплата Premium**\n\n"
        f"Сумма: **{PREMIUM_PRICE}₽**\n\n"
        f"1. Перейди по ссылке\n"
        f"2. Оплати картой\n"
        f"3. Premium активируется автоматически!\n\n"
        f"🔗 [**ОПЛАТИТЬ**]({link})",
        parse_mode='Markdown',
        disable_web_page_preview=True)

@bot.message_handler(commands=['stats'])
def user_stats_cmd(message):
    user_id = message.from_user.id
    add_user(user_id, message.from_user.username or "User")
    reset_daily_counter(user_id)
    status, remaining, total = get_user_stats(user_id)
    bot.reply_to(message,
        f"📊 **Статистика:**\n"
        f"{status}\n"
        f"Осталось: {remaining}\n"
        f"Всего: {total}",
        parse_mode='Markdown')

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    add_user(user_id, message.from_user.username or "User")
    reset_daily_counter(user_id)
    if not check_premium(user_id):
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute('SELECT messages_today FROM users WHERE user_id = ?', (user_id,))
        row = c.fetchone()
        conn.close()
        count = row[0] if row else 0
        if count >= FREE_DAILY_LIMIT:
            bot.reply_to(message,
                f"⚠️ **Лимит исчерпан!**\n\n"
                f"Жми /pay для безлимита",
                parse_mode='Markdown')
            return
        increment_message_count(user_id)
    try:
        auth = requests.post(
            "https://ngw.devices.sberbank.ru:9443/api/v2/oauth",
            headers={
                "Authorization": f"Basic {GIGACHAT_KEY}",
                "RqUID": "00000000-0000-0000-0000-000000000000",
                "Content-Type": "application/x-www-form-urlencoded"
            },
            data={"scope": "GIGACHAT_API_PERS"},
            verify=False
        )
        if auth.status_code == 200:
            token = auth.json()["access_token"]
            resp = requests.post(
                "https://gigachat.devices.sberbank.ru/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "GigaChat",
                    "messages": [{"role": "user", "content": message.text}]
                },
                verify=False
            )
            if resp.status_code == 200:
                bot.reply_to(message, resp.json()["choices"][0]["message"]["content"])
            else:
                bot.reply_to(message, "⚠️ Ошибка нейросети.")
        else:
            bot.reply_to(message, "⚠️ Ошибка подключения.")
    except Exception as e:
        print(f"⚠️ GigaChat error: {e}")
        bot.reply_to(message, "⚠️ Произошла ошибка.")

if __name__ == '__main__':
    init_db()
    threading.Thread(target=run_flask, daemon=True).start()
    print("🚀 Bot started...")
    bot.polling(none_stop=True)
