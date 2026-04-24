import os
import telebot
from gigachat import GigaChat
from flask import Flask
import threading

# Твои ключи (уже вставлены)
BOT_TOKEN = "8714413951:AAFVBkBairgC25Kjo9Z-aItHUqRuB9V39uY"
GIGACHAT_AUTH = "MDE5ZGJmOGItMmZmYS03ZTQxLWI4ZDYtZjM4NWJiMTJjMzBmOjkwZDFlZWMxLTNhMzUtNDNlMC1iYjgzLTlkM2E2ZThmN2JiNg"

bot = telebot.TeleBot(BOT_TOKEN)
giga = GigaChat(credentials=GIGACHAT_AUTH, verify_ssl_certs=False, scope="GIGACHAT_API_PERS")

app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Bot is alive!"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "👋 Привет! Я ИИ-помощник. Задай мне вопрос!")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    try:
        response = giga.chat(messages=[{"role": "user", "content": message.text}])
        answer = response.choices[0].message.content
        bot.reply_to(message, answer)
    except Exception as e:
        bot.reply_to(message, f"⚠️ Ошибка: {str(e)}")

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    print("🚀 Бот запущен...")
    bot.polling()
