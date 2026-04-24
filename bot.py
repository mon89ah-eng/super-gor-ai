import os
import telebot
import requests
from flask import Flask
import threading
import time

BOT_TOKEN = "8714413951:AAFVBkBairgC25Kjo9Z-aItHUqRuB9V39uY"
GIGACHAT_KEY = "MDE5ZGJmOGItMmZmYS03ZTQxLWI4ZDYtZjM4NWJiMTJjMzBmOjVkODE4OGEwLWE4YzMtNGJhMC1iZDlmLTU5YTJlMTZhNGZlMw=="

bot = telebot.TeleBot(BOT_TOKEN)

try:
    bot.remove_webhook()
    print("✅ Webhook removed")
    time.sleep(1)
except:
    pass

app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Bot is running!"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "👋 Привет! Задай мне вопрос!")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    try:
        # 🔥 Пробуем сначала получить токен
        auth_response = requests.post(
            "https://ngw.devices.sberbank.ru:9443/api/v2/oauth",
            headers={
                "Authorization": f"Basic {GIGACHAT_KEY}",
                "RqUID": "00000000-0000-0000-0000-000000000000",
                "Content-Type": "application/x-www-form-urlencoded"
            },
            data={"scope": "GIGACHAT_API_PERS"},
            verify=False
        )
        
        if auth_response.status_code != 200:
            bot.reply_to(message, f"⚠️ Ошибка авторизации: {auth_response.status_code}")
            return
        
        access_token = auth_response.json()["access_token"]
        
        # Теперь делаем запрос к GigaChat
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(
            "https://gigachat.devices.sberbank.ru/api/v1/chat/completions",
            headers=headers,
            json={
                "model": "GigaChat",
                "messages": [{"role": "user", "content": message.text}]
            },
            verify=False
        )
        
        if response.status_code == 200:
            answer = response.json()["choices"][0]["message"]["content"]
            bot.reply_to(message, answer)
        else:
            bot.reply_to(message, f"⚠️ Ошибка: {response.status_code}")
            
    except Exception as e:
        bot.reply_to(message, f"⚠️ Ошибка: {str(e)}")

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    bot.polling(none_stop=True, timeout=120)
