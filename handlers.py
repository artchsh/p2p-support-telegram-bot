import os, json
from dotenv import load_dotenv
load_dotenv()
CHAT_ID = int(os.getenv("CHAT_ID", "-1"))

import telebot
from telebot import types
from datetime import datetime, timedelta
from translations import get_text

ENABLE_LOGGING = int(os.getenv("ENABLE_LOGGING", "0"))

def log_message(cursor, db, kitten_id, forum_id, message, supporter_id=None):
    if ENABLE_LOGGING:
        cursor.execute('SELECT messages, supporters_ids FROM logs WHERE kitten_id=? AND forum_id=?', (kitten_id, forum_id))
        row = cursor.fetchone()
        if row:
            messages = json.loads(row[0])
            supporters_ids = json.loads(row[1])
            messages.append(message)
            if supporter_id and supporter_id not in supporters_ids:
                supporters_ids.append(supporter_id)
            cursor.execute('UPDATE logs SET messages=?, supporters_ids=? WHERE kitten_id=? AND forum_id=?', (json.dumps(messages), json.dumps(supporters_ids), kitten_id, forum_id))
        else:
            messages = [message]
            supporters_ids = [supporter_id] if supporter_id else []
            cursor.execute('INSERT INTO logs (kitten_id, forum_id, messages, supporters_ids) VALUES (?, ?, ?, ?)', (kitten_id, forum_id, json.dumps(messages), json.dumps(supporters_ids)))
        db.commit()

def handle_start(bot, message, cursor):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.row("Русский", "English", "Қазақша")
    bot.send_message(message.chat.id, "Please select your language / Выберите язык / Тіл таңдаңыз", reply_markup=markup)

def handle_switch_language(bot, message, cursor):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.row("Русский", "English", "Қазақша")
    bot.send_message(message.chat.id, get_text("lang_prompt", message.chat.id, cursor), reply_markup=markup)

def handle_set_language(bot, message, cursor, db):
    cursor.execute('REPLACE INTO language (chat_id, lang) VALUES (?, ?)', (message.chat.id, message.text))
    db.commit()
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.row(
        get_text("button_start", message.chat.id, cursor),
        get_text("button_decline", message.chat.id, cursor)
    )
    bot.send_message(message.chat.id, "Some example of disclaimer. Disclaimer! Be careful! Ahtung!", reply_markup=markup)

def handle_disclaimer_response(bot, message, cursor):
    if message.text == get_text("button_start", message.chat.id, cursor):
        bot.send_message(message.chat.id, get_text("start_instructions", message.chat.id, cursor), reply_markup=end_markup(message.chat.id, cursor))
    elif message.text == get_text("button_decline", message.chat.id, cursor):
        bot.send_message(message.chat.id, get_text("session_not_started", message.chat.id, cursor))

def end_markup(chat_id, cursor):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(get_text("button_finish", chat_id, cursor))
    return kb

def handle_help(bot, message, cursor, db):
    txt_list = message.text.split(" ")
    if len(txt_list) == 1:
        bot.send_message(message.from_user.id, get_text("error_no_request", message.from_user.id, cursor), parse_mode="Markdown", reply_markup=end_markup(message.chat.id, cursor))
        return
    
    _SQL = '''SELECT * FROM helps WHERE kitten_id = ?'''
    cursor.execute(_SQL, (message.from_user.id,))
    result = cursor.fetchall()
    if len(result) != 0:
        bot.send_message(message.from_user.id, get_text("error_has_open_session", message.from_user.id, cursor), parse_mode='Markdown', reply_markup=end_markup(message.chat.id, cursor))
        return
    
    _SQL = '''INSERT INTO helps (kitten_id) VALUES (?)'''
    cursor.execute(_SQL, (message.from_user.id,))
    db.commit()
    
    _SQL = '''SELECT * FROM helps WHERE kitten_id = ?'''
    cursor.execute(_SQL, (message.from_user.id,))
    result = cursor.fetchall()
    try:
        forum_topic = bot.create_forum_topic(CHAT_ID, f"Kitten #{result[0][0]}")
        cursor.execute('UPDATE helps SET thread_id = ? WHERE kitten_id = ?', (forum_topic.message_thread_id, message.from_user.id))
        db.commit()
        if "/help" in txt_list:
            txt_list.remove("/help")
        bot.send_message(CHAT_ID, ' '.join(txt_list), reply_to_message_id=forum_topic.message_thread_id, reply_markup=end_markup(message.chat.id, cursor))
        log_message(cursor, db, message.from_user.id, forum_topic.message_thread_id, ' '.join(txt_list))
    except telebot.apihelper.ApiTelegramException:
        bot.send_message(CHAT_ID, get_text("forum_failed", message.from_user.id, cursor), reply_markup=end_markup(message.chat.id, cursor))
    
    bot.send_message(message.from_user.id, get_text("request_sent", message.from_user.id, cursor), parse_mode='Markdown', reply_markup=end_markup(message.chat.id, cursor))

def handle_close(bot, message, cursor, db):
    _SQL = '''SELECT * FROM helps WHERE kitten_id = ?'''
    cursor.execute(_SQL, (message.from_user.id,))
    result = cursor.fetchall()
    if len(result) != 0:
        if result[0][3] == 0:
            thread_id = result[0][2]
            try:
                bot.close_forum_topic(CHAT_ID, thread_id)
            except telebot.apihelper.ApiTelegramException:
                bot.send_message(message.from_user.id, get_text("forum_close_failed", message.from_user.id, cursor), reply_markup=end_markup(message.chat.id, cursor))
            bot.send_message(message.from_user.id, get_text("session_closed", message.from_user.id, cursor), reply_markup=end_markup(message.chat.id, cursor))
            _SQL = '''DELETE FROM helps WHERE kitten_id = ?;'''
            cursor.execute(_SQL, (message.from_user.id,))
            db.commit()

def handle_close_topic(bot, message, cursor, db):
    # Only allow this command in forum topics
    if message.chat.id != CHAT_ID or message.message_thread_id is None:
        return
        
    # Check if topic exists and is not closed
    _SQL = '''SELECT * FROM helps WHERE thread_id = ?'''
    cursor.execute(_SQL, (message.message_thread_id,))
    result = cursor.fetchall()
    
    if len(result) == 0 or result[0][3] == 1:
        return
        
    try:
        bot.close_forum_topic(CHAT_ID, message.message_thread_id)
        bot.send_message(result[0][1], get_text("session_closed", result[0][1], cursor))
        cursor.execute('DELETE FROM helps WHERE thread_id = ?', (message.message_thread_id,))
        db.commit()
    except telebot.apihelper.ApiTelegramException:
        bot.send_message(CHAT_ID, get_text("forum_close_failed", result[0][1], cursor), 
                        reply_to_message_id=message.message_thread_id)

def handle_text_messages(bot, message, cursor, db):
    if message.text == get_text("button_finish", message.chat.id, cursor):
        _SQL = '''SELECT * FROM helps WHERE kitten_id = ?'''
        cursor.execute(_SQL, (message.from_user.id,))
        result = cursor.fetchall()
        if len(result) != 0 and result[0][3] == 0:
            thread_id = result[0][2]
            bot.close_forum_topic(CHAT_ID, thread_id)
            bot.send_message(message.chat.id, get_text("dialog_ended", message.chat.id, cursor), reply_markup=end_markup(message.chat.id, cursor))
            cursor.execute('DELETE FROM helps WHERE kitten_id=?', (message.from_user.id,))
            db.commit()
        else:
            bot.send_message(message.chat.id, get_text("dialog_inactive", message.chat.id, cursor), reply_markup=end_markup(message.chat.id, cursor))
        return

    if message.text == "check_chat_id_artchsh_admin_8x7yz25t":
        bot.send_message(message.chat.id, f" Chat ID: {message.chat.id}", reply_markup=end_markup(message.chat.id, cursor))
        return

    cursor.execute('SELECT last_message_time FROM helps WHERE kitten_id=?', (message.from_user.id,))
    row = cursor.fetchone()
    if row and row[0]:
        last_message_time = datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S')
        message_time = datetime.utcfromtimestamp(message.date)
        if message_time - last_message_time > timedelta(hours=3):
            bot.send_message(message.from_user.id, get_text("inactivity_closed", message.from_user.id, cursor), reply_markup=end_markup(message.chat.id, cursor))
            cursor.execute('DELETE FROM helps WHERE kitten_id=?', (message.from_user.id,))
            db.commit()
            return

    if message.chat.id != CHAT_ID:
        cursor.execute('SELECT * FROM helps WHERE kitten_id = ?', (message.from_user.id,))
        result = cursor.fetchall()
        if len(result) == 0:
            bot.send_message(
                message.chat.id,
                get_text("no_active_ticket", message.chat.id, cursor),
                parse_mode='Markdown',
                reply_markup=end_markup(message.chat.id, cursor)
            )
            return
        bot.send_message(CHAT_ID, message.text, reply_to_message_id=result[0][2], reply_markup=end_markup(message.chat.id, cursor))
        log_message(cursor, db, message.from_user.id, result[0][2], message.text)
            
    if message.chat.id == CHAT_ID:
        if message.message_thread_id != None:
            _SQL = '''SELECT * FROM helps WHERE thread_id = ?'''
            cursor.execute(_SQL, (message.message_thread_id,))
            result = cursor.fetchall()
            if len(result) == 0:
                return
            bot.send_message(result[0][1], message.text, parse_mode='Markdown', reply_markup=end_markup(message.chat.id, cursor))
            log_message(cursor, db, result[0][1], message.message_thread_id, message.text, supporter_id=message.from_user.id)

    if "chat" in message.text:
        bot.send_message(message.chat.id, f"Chat ID: {message.chat.id} \n Your id: {message.from_user.id}", reply_markup=end_markup(message.chat.id, cursor))

    cursor.execute('UPDATE helps SET last_message_time=datetime("now") WHERE kitten_id=?', (message.from_user.id,))
    db.commit()