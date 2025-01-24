import os
from dotenv import load_dotenv
load_dotenv()
import telebot
from db import init_db, checkHelpTable
from handlers import (
    handle_start,
    handle_switch_language,
    handle_set_language,
    handle_disclaimer_response,
    handle_help,
    handle_close,
    handle_text_messages,
    handle_close_topic,
    log_message
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
db, cursor = init_db()
checkHelpTable(cursor, db)
bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start'])
def start(message):
    handle_start(bot, message, cursor)

@bot.message_handler(commands=['switch_language'])
def switch_language(message):
    handle_switch_language(bot, message, cursor)

@bot.message_handler(func=lambda m: m.text in ["Русский", "English", "Қазақша"] and m.chat.type == 'private')
def set_language(message):
    handle_set_language(bot, message, cursor, db)

@bot.message_handler(func=lambda m: m.text in ["Начать", "Не соглашаюсь"] and m.chat.type == 'private')
def disclaimer_response(message):
    handle_disclaimer_response(bot, message, cursor)

@bot.message_handler(commands=['help'])
def help_command(message):
    handle_help(bot, message, cursor, db)

@bot.message_handler(commands=['close'])
def close_command(message):
    handle_close(bot, message, cursor, db)

@bot.message_handler(commands=['close_topic'])
def close_topic_command(message):
    handle_close_topic(bot, message, cursor, db)

@bot.message_handler(content_types=['text'])
def get_text_messages(message):
    handle_text_messages(bot, message, cursor, db)
    log_message(cursor, db, message.from_user.id, message.message_thread_id, message.text, supporter_id=message.from_user.id)

bot.polling(non_stop=True, interval=2)