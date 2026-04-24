import os
import telebot
import requests
from flask import Flask, request
import threading
import time
import sqlite3
from datetime import datetime, date, timedelta
import hashlib

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8714413951:AAFVBkBairgC25Kjo9Z-aItHUqRuB9V39uY")
GIGACHAT_KEY = os.environ.get("GIGACHAT_KEY", "MDE5ZGJmOGItMmZmYS03ZTQxLWI4ZDYtZjM4NWJiMTJjMzBmOjVkODE4OGEwLWE4YzMtNGJhMC1iZDlmLTU5YTJlMTZhNGZlMw==")

YOUMONEY_ACCOUNT = os.environ.get("YOUMONEY_ACCOUNT", "4100118733788159")
YOUMONEY_CLIENT_ID = os.environ.get("YOUMONEY_CLIENT_ID", "12577344FC46155099AB89B76856CF69A450D59BCC7822A817773AAA63BC2CC8")
YOUMONEY_CLIENT_SECRET = os.environ.get("YOUMONEY_CLIENT_SECRET", "D3F2EEE6CE0E079C7E1E27180E150898E6D2F3B3EE5B25888D3371B393BCF605CFA284BFFDDCEF36DF53148721EE35E356B2FC70CC47A39D9A93E26C7228D680")

PREMIUM_PRICE = 299
PREMIUM_DAYS = 30
FREE_DAILY_LIMIT = 10

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

def init_db():
    with sqlite3.connect('users.db') as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY,
                  username TEXT,
                  messages_today INTEGER DEFAULT 0,
                  is_premium INTEGER DEFAULT 0,
                  premium_until TEXT,
                  last_reset TEXT,
                  total_messages INTEGER DEFAULT 0)''')
        conn.commit()
    print("✅ Database initialized")

def add_user(user_id, username):
    today = date.today().isoformat()
    with sqlite3.connect('users.db') as conn:
        conn.execute('''INSERT OR IGNORE INTO users 
                 (user_id, username, last_reset, messages_today) 
                 VALUES (?, ?, ?, 0)''', (user_id, username, today))
        conn.commit()

def reset_daily_counter(user_id):
    today = date.today().isoformat()
    with sqlite3.connect('users.db') as conn:
        c = conn.cursor
