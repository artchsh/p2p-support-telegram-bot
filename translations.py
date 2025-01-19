import os
from dotenv import load_dotenv
load_dotenv()
import telebot
from telebot import types
from datetime import datetime, timedelta
import json

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID", "-1"))
ENV = os.getenv("ENV", "DEV")

# Determine environment and use appropriate DB
db, cursor = None, None
if ENV == "PROD":
    exit()
else:
    import sqlite3
    db = sqlite3.connect('local.db', check_same_thread=False)
    cursor = db.cursor()

# Create helper tables for local dev
cursor.execute('''
    CREATE TABLE IF NOT EXISTS language (
        chat_id INTEGER PRIMARY KEY,
        lang TEXT
    )
''')

def checkHelpTable():
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS helps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kitten_id INT,
            thread_id INT DEFAULT 0,
            closed INT DEFAULT 0,
            last_message_time DATETIME
        )
    ''')
    db.commit()

checkHelpTable()
bot = telebot.TeleBot(BOT_TOKEN)

with open("langs.json", "r", encoding="utf-8") as f:
    LANG_TEXTS = json.load(f)

def get_text(key, chat_id, cursor):
    cursor.execute("SELECT lang FROM language WHERE chat_id=?", (chat_id,))
    row = cursor.fetchone()
    user_lang = row[0] if row else "English"
    default_text = LANG_TEXTS[key]["English"]
    return LANG_TEXTS.get(key, {}).get(user_lang, default_text)

@bot.message_handler(commands=['start'])
def start(message):
    # Ask user for preferred language
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.row("Русский", "English", "Қазақша")
    bot.send_message(message.chat.id, "Please select your language / Выберите язык / Тіл таңдаңыз", reply_markup=markup)

@bot.message_handler(commands=['switch_language'])
def switch_language(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.row("Русский", "English", "Қазақша")
    bot.send_message(message.chat.id, get_text("lang_prompt", message.chat.id, cursor), reply_markup=markup)

@bot.message_handler(func=lambda m: m.text in ["Русский", "English", "Қазақша"] and m.chat.type == 'private')
def set_language(message):
    # Save user language
    cursor.execute('REPLACE INTO language (chat_id, lang) VALUES (?, ?)', (message.chat.id, message.text))
    db.commit()
    # Show disclaimer with "Начать" / "Не соглашаюсь"
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.row(get_text("button_start", message.chat.id, cursor), get_text("button_decline", message.chat.id, cursor))
    bot.send_message(
        message.chat.id,
        get_text("disclaimer_text", message.chat.id, cursor),
        reply_markup=markup
    )

@bot.message_handler(func=lambda m: m.text in [get_text("button_start", m.chat.id, cursor), get_text("button_decline", m.chat.id, cursor)] and m.chat.type == 'private')
def disclaimer_response(message):
    if message.text == get_text("button_start", message.chat.id, cursor):
        bot.send_message(message.chat.id, get_text("start_instructions", message.chat.id, cursor), reply_markup=end_markup(message.chat.id, cursor))
    else:
        bot.send_message(message.chat.id, get_text("session_not_started", message.chat.id, cursor))

def end_markup(chat_id, cursor):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(get_text("button_finish", chat_id, cursor))
    return kb

@bot.message_handler(commands=['help'])
def help(message: types.Message):
    # dividing text by space
    txt_list = message.text.split(" ")
    # checking if text contains problem
    if len(txt_list) == 1:
        bot.send_message(message.from_user.id, get_text("error_no_request", message.from_user.id, cursor), parse_mode="Markdown", reply_markup=end_markup(message.chat.id, cursor))
        return
    
    # first check if user has topic opened
    _SQL = '''
        SELECT * FROM helps WHERE kitten_id = ?
    '''
    cursor.execute(_SQL, (message.from_user.id,))
    result = cursor.fetchall()
    # if we found something, respond with error message and stop
    if len(result) != 0:
        bot.send_message(message.from_user.id, get_text("error_has_open_session", message.from_user.id, cursor), parse_mode='Markdown', reply_markup=end_markup(message.chat.id, cursor))
        return
    
    # Create a new record of kitten and their problem
    _SQL = '''
        INSERT INTO helps 
        (kitten_id)
        VALUES
        (?)
    '''
    cursor.execute(_SQL, (message.from_user.id,))
    db.commit()
    
    # create a new forum topic with name that contains id of an existing record
    _SQL = '''
        SELECT * FROM helps WHERE kitten_id = ?
    '''
    cursor.execute(_SQL, (message.from_user.id,))
    result = cursor.fetchall()
    try:
        forum_topic = bot.create_forum_topic(CHAT_ID, f"Kitten #{result[0][0]}")
        cursor.execute('UPDATE helps SET thread_id = ? WHERE kitten_id = ?', (forum_topic.message_thread_id, message.from_user.id))
        db.commit()
        # Remove the /help command from the message text if it exists
        if "/help" in txt_list:
            txt_list.remove("/help")
        bot.send_message(CHAT_ID, ' '.join(txt_list), reply_to_message_id=forum_topic.message_thread_id, reply_markup=end_markup(message.chat.id, cursor))
    except telebot.apihelper.ApiTelegramException:
        bot.send_message(CHAT_ID, get_text("forum_failed", message.from_user.id, cursor), reply_markup=end_markup(message.chat.id, cursor))
    
    bot.send_message(message.from_user.id, get_text("request_sent", message.from_user.id, cursor), parse_mode='Markdown', reply_markup=end_markup(message.chat.id, cursor))
    
@bot.message_handler(commands=['close'])
def close(message: types.Message):
    
    # get user info from records
    _SQL = '''
        SELECT *
        FROM helps
        WHERE kitten_id = ?
    '''
    cursor.execute(_SQL, (message.from_user.id,))
    result = cursor.fetchall()
    
    # check if record exists
    if len(result) != 0:
        # check if topic has not been closed
        if result[0][3] == 0:
            # get thread id from record
            thread_id = result[0][2]
            
            # close forum topic
            try:
                bot.close_forum_topic(CHAT_ID, thread_id)
            except telebot.apihelper.ApiTelegramException:
                bot.send_message(message.from_user.id, get_text("forum_close_failed", message.from_user.id, cursor), reply_markup=end_markup(message.chat.id, cursor))
            
            # send confirmation message
            bot.send_message(message.from_user.id, get_text("session_closed", message.from_user.id, cursor), reply_markup=end_markup(message.chat.id, cursor))
            
            # delete the record
            _SQL = '''
                DELETE FROM helps WHERE kitten_id = ?;
            '''
            cursor.execute(_SQL, (message.from_user.id,))
            db.commit()
            
# this is any text handler
@bot.message_handler(content_types=['text'])
def get_text_messages(message: types.Message):
    # Handle "Закончить" button
    if message.text == get_text("button_finish", message.chat.id, cursor):
        _SQL = '''
            SELECT *
            FROM helps
            WHERE kitten_id = ?
        '''
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

    # Check 3-hour timeout
    cursor.execute('SELECT last_message_time FROM helps WHERE kitten_id=?', (message.from_user.id,))
    row = cursor.fetchone()
    if row and row[0]:

        # Convert last_message_time to datetime object
        last_message_time = datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S')
        # Convert message.date (Telegram epoch) to datetime object
        message_time = datetime.utcfromtimestamp(message.date)

        # Check if more than 3 hours have passed
        if message_time - last_message_time > timedelta(hours=3):
            # Close the help topic if timeout exceeded
            bot.send_message(message.from_user.id, get_text("inactivity_closed", message.from_user.id, cursor), reply_markup=end_markup(message.chat.id, cursor))
            cursor.execute('DELETE FROM helps WHERE kitten_id=?', (message.from_user.id,))
            db.commit()
            return

    # if this was in any personal chat 
    if message.chat.id != CHAT_ID:
        cursor.execute('SELECT * FROM helps WHERE kitten_id = ?', (message.from_user.id,))
        result = cursor.fetchall()
        # If no active ticket, instruct the user to use /help
        if len(result) == 0:
            bot.send_message(
                message.chat.id,
                get_text("no_active_ticket", message.chat.id, cursor),
                parse_mode='Markdown',
                reply_markup=end_markup(message.chat.id, cursor)
            )
            return
        # "forward" message to appropriate channel
        bot.send_message(CHAT_ID, message.text, reply_to_message_id=result[0][2], reply_markup=end_markup(message.chat.id, cursor))
            
    # if this was in CHAT_ID
    if message.chat.id == CHAT_ID:

        # check that thread id exists
        if message.message_thread_id != None:

            _SQL = '''
                SELECT *
                FROM helps
                WHERE thread_id = ?
            '''
            cursor.execute(_SQL, (message.message_thread_id,))
            result = cursor.fetchall()

            # check that records exists
            if len(result) == 0:
                return
            
            bot.send_message(result[0][1], message.text, parse_mode='Markdown', reply_markup=end_markup(message.chat.id, cursor))

    if "chat" in message.text:
        bot.send_message(message.chat.id, f"Chat ID: {message.chat.id} \n Your id: {message.from_user.id}", reply_markup=end_markup(message.chat.id, cursor))

    # update last_message_time
    cursor.execute('UPDATE helps SET last_message_time=datetime("now") WHERE kitten_id=?', (message.from_user.id,))
    db.commit()

bot.polling(non_stop=True, interval=2)