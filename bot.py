import os
import telebot
import requests
from flask import Flask
import threading
import time

BOT_TOKEN = "8714413951:AAFVBkBairgC25Kjo9Z-aItHUqRuB9V39uY"
GIGACHAT_KEY = "MDE5ZGJmOGItMmZmYS03ZTQxLWI4ZDYtZjM4NWJiMTJjMzBmOjVkODE4OGEwLWE4YzMtNGJhMC1iZDlmLTU5YTJlMTZhNGZlMw=="

# Сначала создаём бота
bot = telebot.TeleBot(BOT_TOKEN)

# 🔥 Агрессивно удаляем вебхук ПЕРЕД всем остальным
try:
    bot.remove_webhook()
    print("✅ Webhook removed successfully")
    time.sleep(1)  # Даём Telegram время на обработку
except Exception as e:
    print(f"⚠️ Error removing webhook: {e}")

app = Flask(__name__)

@app.route('/')
def home():
    return "✅ SuperGorAI Bot is running!"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "👋 Привет! Я ИИ-помощник на GigaChat. Задай мне любой вопрос!")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    try:
        headers = {
            "Authorization": f"Bearer {GIGACHAT_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "GigaChat",
            "messages": [{"role": "user", "content": message.text}],
            "temperature": 0.7
        }
        
        response = requests.post(
            "https://gigachat.devices.sberbank.ru/api/v1/chat/completions",
            headers=headers,
            json=data,
            verify=False
        )
        
        if response.status_code == 200:
            answer = response.json()["choices"][0]["message"]["content"]
            bot.reply_to(message, answer)
        else:
            bot.reply_to(message, f"⚠️ Ошибка API: {response.status_code}")
            
    except Exception as e:
        bot.reply_to(message, f"⚠️ Произошла ошибка: {str(e)}")

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    print("🚀 Bot started with polling...")
    bot.polling(none_stop=True, interval=0, timeout=120)
