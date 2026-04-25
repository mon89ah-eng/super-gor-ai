import os
import telebot
from telebot import types
import requests
from flask import Flask, request
import threading
import time
import sqlite3
from datetime import date, timedelta
import hashlib
import re
import uuid

BOT_TOKEN = "8714413951:AAFVBkBairgC25Kjo9Z-aItHUqRuB9V39uY"
GIGACHAT_KEY = "MDE5ZGJmOGItMmZmYS03ZTQxLWI4ZDYtZjM4NWJiMTJjMzBmOjVkODE4OGEwLWE4YzMtNGJhMC1iZDlmLTU5YTJlMTZhNGZlMw=="

YOUMONEY_ACCOUNT = "4100118733788159"
YOUMONEY_CLIENT_SECRET = "D3F2EEE6CE0E079C7E1E27180E150898E6D2F3B3EE5B25888D3371B393BCF605CFA284BFFDDCEF36DF53148721EE35E356B2FC70CC47A39D9A93E26C7228D680"

PREMIUM_PRICE = 299
PREMIUM_DAYS = 30
FREE_DAILY_LIMIT = 10

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)


# ───────────────────────── БД ─────────────────────────

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
    today = date.today().isoformat()
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''INSERT OR IGNORE INTO users
                 (user_id, username, last_reset, messages_today)
                 VALUES (?, ?, ?, 0)''', (user_id, username, today))
    conn.commit()
    conn.close()

def reset_daily_counter(user_id):
    today = date.today().isoformat()
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('SELECT last_reset FROM users WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    if result and result[0] != today:
        c.execute('''UPDATE users SET messages_today = 0, last_reset = ?
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
    c.execute('''UPDATE users SET is_premium = 1, premium_until = ?
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
            return f"⭐ Premium (до {premium_until})", "♾️ Безлимит", total_msgs
        return "🆓 Free", f"{max(0, FREE_DAILY_LIMIT - msgs_today)} осталось", total_msgs
    return "🆓 Free", f"{FREE_DAILY_LIMIT} осталось", 0

def get_messages_today(user_id):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('SELECT messages_today FROM users WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def increment_message_count(user_id):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''UPDATE users
                 SET messages_today = messages_today + 1,
                     total_messages = total_messages + 1
                 WHERE user_id = ?''', (user_id,))
    conn.commit()
    conn.close()


# ───────────────────────── ЛИМИТ ─────────────────────────

def check_limit(user_id, message):
    if check_premium(user_id):
        return True
    count = get_messages_today(user_id)
    if count >= FREE_DAILY_LIMIT:
        bot.reply_to(message,
            "⚠️ *Лимит исчерпан!*\n\nНажми кнопку для подключения Premium 👇",
            parse_mode='Markdown',
            reply_markup=pay_inline(user_id))
        return False
    increment_message_count(user_id)
    return True


# ───────────────────────── КНОПКИ ─────────────────────────

def main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("🎨 Создать изображение"),
        types.KeyboardButton("💎 Подключить Premium"),
        types.KeyboardButton("📊 Статистика")
    )
    return markup

def pay_inline(user_id):
    link = (
        f"https://yoomoney.ru/quickpay/confirm.xml?"
        f"receiver={YOUMONEY_ACCOUNT}&"
        f"targets=Premium+subscription&"
        f"paymentType=S&"
        f"sum={PREMIUM_PRICE}&"
        f"label=premium_user_{user_id}"
    )
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(f"💳 Оплатить {PREMIUM_PRICE}₽", url=link))
    return markup


# ───────────────────────── GIGACHAT TOKEN ─────────────────────────

def get_gigachat_token():
    try:
        response = requests.post(
            "https://ngw.devices.sberbank.ru:9443/api/v2/oauth",
            headers={
                "Authorization": f"Basic {GIGACHAT_KEY}",
                "RqUID": str(uuid.uuid4()),
                "Content-Type": "application/x-www-form-urlencoded"
            },
            data={"scope": "GIGACHAT_API_PERS"},
            verify=False,
            timeout=15
        )
        if response.status_code == 200:
            return response.json().get("access_token")
    except Exception as e:
        print(f"⚠️ Token error: {e}")
    return None


# ───────────────────────── ГЕНЕРАЦИЯ КАРТИНКИ ─────────────────────────

def generate_image(prompt):
    try:
        token = get_gigachat_token()
        if not token:
            return None
        response = requests.post(
            "https://gigachat.devices.sberbank.ru/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json={
                "model": "GigaChat",
                "messages": [
                    {"role": "user", "content": f"Нарисуй: {prompt}"}
                ],
                "function_call": "auto"
            },
            verify=False,
            timeout=60
        )
        if response.status_code == 200:
            content = response.json()["choices"][0]["message"]["content"]
            match = re.search(r'<img[^>]+src="([^"]+)"', content)
            if match:
                file_id = match.group(1)
                img_response = requests.get(
                    f"https://gigachat.devices.sberbank.ru/api/v1/files/{file_id}/content",
                    headers={"Authorization": f"Bearer {token}"},
                    verify=False,
                    timeout=30
                )
                if img_response.status_code == 200:
                    return img_response.content
        print(f"⚠️ Image response: {response.status_code} {response.text[:200]}")
    except Exception as e:
        print(f"⚠️ generate_image error: {e}")
    return None


# ───────────────────────── FLASK ─────────────────────────

try:
    bot.remove_webhook()
    print("✅ Webhook removed")
    time.sleep(1)
except Exception as e:
    print(f"⚠️ Webhook error: {e}")

@app.route('/')
def home():
    return "✅ Bot is running!"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))


# ───────────────────────── YOUMONEY WEBHOOK ─────────────────────────

@app.route('/youmoney-webhook', methods=['POST'])
def youmoney_webhook():
    try:
        data = request.form
        print("🔔 Webhook received")
        if YOUMONEY_CLIENT_SECRET:
            string_to_sign = (
                f"{data.get('notification_type', '')}&"
                f"{data.get('operation_id', '')}&"
                f"{data.get('amount', '')}&"
                f"{data.get('currency', '643')}&"
                f"{data.get('datetime', '')}&"
                f"{data.get('sender', '')}&"
                f"{data.get('codepro', 'false')}&"
                f"{YOUMONEY_CLIENT_SECRET}&"
                f"{data.get('label', '')}"
            )
            signature = hashlib.sha1(string_to_sign.encode('utf-8')).hexdigest()
            received_signature = request.headers.get('X-YooMoney-SHA1', '')
            if received_signature and received_signature.lower() != signature.lower():
                print("❌ Invalid Signature")
                return 'ERROR', 403
        amount = data.get('amount')
        if (
            data.get('notification_type') == 'p2p-incoming'
            and amount is not None
            and round(float(amount), 2) == float(PREMIUM_PRICE)
        ):
            label = data.get('label', '')
            if label.startswith('premium_user_'):
                user_id = int(label.replace('premium_user_', ''))
                premium_until = activate_premium(user_id)
                print(f"✅ Premium activated for {user_id}")
                try:
                    bot.send_message(
                        user_id,
                        f"🎉 *Оплата прошла успешно!*\n\n"
                        f"✅ Premium активирован до {premium_until}\n"
                        f"Спасибо за поддержку! 🚀",
                        parse_mode='Markdown',
                        reply_markup=main_keyboard()
                    )
                except Exception as e:
                    print(f"⚠️ Could not send message: {e}")
        return 'OK', 200
    except Exception as e:
        print(f"❌ Webhook Error: {e}")
        return 'ERROR', 500


# ───────────────────────── КОМАНДЫ ─────────────────────────

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    add_user(user_id, message.from_user.username or "User")
    status, remaining, total = get_user_stats(user_id)
    bot.reply_to(message,
        f"👋 *Привет!*\n\n"
        f"📊 Статус: {status}\n"
        f"📩 Осталось: {remaining}\n"
        f"📈 Всего запросов: {total}\n\n"
        f"Выбери действие 👇",
        parse_mode='Markdown',
        reply_markup=main_keyboard())

@bot.message_handler(commands=['stats'])
def stats_cmd(message):
    user_id = message.from_user.id
    add_user(user_id, message.from_user.username or "User")
    reset_daily_counter(user_id)
    status, remaining, total = get_user_stats(user_id)
    bot.reply_to(message,
        f"📊 *Статистика*\n\n"
        f"Статус: {status}\n"
        f"Осталось сегодня: {remaining}\n"
        f"Всего запросов: {total}",
        parse_mode='Markdown',
        reply_markup=main_keyboard())

@bot.message_handler(commands=['pay'])
def pay_cmd(message):
    user_id = message.from_user.id
    if check_premium(user_id):
        bot.reply_to(message, "⭐ У тебя уже есть Premium!", reply_markup=main_keyboard())
        return
    bot.reply_to(message,
        f"💎 *Premium — {PREMIUM_PRICE}₽ / {PREMIUM_DAYS} дней*\n\n"
        f"✅ Безлимитные сообщения\n"
        f"✅ Генерация картинок\n"
        f"✅ Приоритетная поддержка\n\n"
        f"Нажми кнопку для оплаты 👇",
        parse_mode='Markdown',
        reply_markup=pay_inline(user_id))


# ───────────────────────── КНОПКИ КЛАВИАТУРЫ ─────────────────────────

@bot.message_handler(func=lambda m: m.text == "💎 Подключить Premium")
def button_premium(message):
    user_id = message.from_user.id
    if check_premium(user_id):
        bot.reply_to(message, "⭐ У тебя уже есть Premium!", reply_markup=main_keyboard())
        return
    bot.reply_to(message,
        f"💎 *Premium — {PREMIUM_PRICE}₽ / {PREMIUM_DAYS} дней*\n\n"
        f"✅ Безлимитные сообщения\n"
        f"✅ Генерация картинок\n"
        f"✅ Приоритетная поддержка\n\n"
        f"Нажми кнопку для оплаты 👇",
        parse_mode='Markdown',
        reply_markup=pay_inline(user_id))

@bot.message_handler(func=lambda m: m.text == "📊 Статистика")
def button_stats(message):
    stats_cmd(message)

@bot.message_handler(func=lambda m: m.text == "🎨 Создать изображение")
def button_image(message):
    bot.reply_to(message,
        "🎨 Напиши что нарисовать:\n\n"
        "Пример: *нарисуй котика в космосе*\n"
        "или используй команду */image описание*",
        parse_mode='Markdown',
        reply_markup=main_keyboard())

@bot.message_handler(commands=['image'])
def image_cmd(message):
    user_id = message.from_user.id
    add_user(user_id, message.from_user.username or "User")
    reset_daily_counter(user_id)
    if not check_limit(user_id, message):
        return
    prompt = message.text.replace('/image', '', 1).strip()
    if not prompt:
        bot.reply_to(message, "✏️ Напиши описание после команды.\nПример: /image котик в космосе")
        return
    _do_generate_image(message, prompt)


# ───────────────────────── ОБРАБОТКА СООБЩЕНИЙ ─────────────────────────

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    add_user(user_id, message.from_user.username or "User")
    reset_daily_counter(user_id)
    text = message.text or ""

    if text.lower().startswith("нарисуй"):
        if not check_limit(user_id, message):
            return
        prompt = text[7:].strip()
        if not prompt:
            bot.reply_to(message, "✏️ Напиши что нарисовать после слова «нарисуй»")
            return
        _do_generate_image(message, prompt)
        return

    if not check_limit(user_id, message):
        return

    try:
        token = get_gigachat_token()
        if not token:
            bot.reply_to(message, "⚠️ Ошибка подключения к нейросети.")
            return
        resp = requests.post(
            "https://gigachat.devices.sberbank.ru/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json={
                "model": "GigaChat",
                "messages": [{"role": "user", "content": text}]
            },
            verify=False,
            timeout=30
        )
        if resp.status_code == 200:
            bot.reply_to(message, resp.json()["choices"][0]["message"]["content"])
        else:
            print(f"⚠️ GigaChat error: {resp.status_code} {resp.text[:200]}")
            bot.reply_to(message, "⚠️ Ошибка нейросети.")
    except Exception as e:
        print(f"⚠️ handle_message error: {e}")
        bot.reply_to(message, "⚠️ Произошла ошибка.")


# ───────────────────────── КАРТИНКА ─────────────────────────

def _do_generate_image(message, prompt):
    msg = bot.reply_to(message, "🎨 Генерирую картинку, подожди...")
    image_data = generate_image(prompt)
    if image_data:
        bot.send_photo(message.chat.id, image_data, reply_to_message_id=message.message_id)
        bot.delete_message(message.chat.id, msg.message_id)
    else:
        bot.edit_message_text(
            "⚠️ Не удалось сгенерировать картинку. Попробуй другой запрос.",
            message.chat.id, msg.message_id)


# ───────────────────────── ЗАПУСК ─────────────────────────

if __name__ == '__main__':
    init_db()
    threading.Thread(target=run_flask, daemon=True).start()
    print("🚀 Bot started...")
    bot.polling(none_stop=True, timeout=30, long_polling_timeout=30)
