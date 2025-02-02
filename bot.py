import os
import json
import time
import sqlite3
import psycopg2
import telebot
from telebot import types
from datetime import datetime, timedelta
from dotenv import load_dotenv
from psycopg2 import OperationalError
from colorama import init as colorama_init, Fore, Style

# Initialize colorama and load environment variables
colorama_init()
load_dotenv()

# Configuration constants
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID", "-1"))
ENV = os.getenv("ENV", "DEV")
ENABLE_LOGGING = bool(int(os.getenv("ENABLE_LOGGING", "1")))

print(f"{Fore.GREEN}✔ Bot starting at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{Style.RESET_ALL}")

# Database initialization
def init_db():
    """Initialize database connection with retry logic"""
    if ENV == "PROD":
        max_retries = 5
        retry_count = 0
        while retry_count < max_retries:
            try:
                print(f"Attempting PostgreSQL connection ({retry_count + 1}/{max_retries})...")
                conn = psycopg2.connect(
                    host=os.getenv("POSTGRES_HOST"),
                    user=os.getenv("POSTGRES_USER"),
                    password=os.getenv("POSTGRES_PASSWORD"),
                    database=os.getenv("POSTGRES_DATABASE")
                )
                return conn, conn.cursor()
            except OperationalError:
                try:
                    conn = psycopg2.connect(
                        host=os.getenv("POSTGRES_HOST"),
                        user=os.getenv("POSTGRES_USER"),
                        password=os.getenv("POSTGRES_PASSWORD"),
                        database=os.getenv("POSTGRES_DATABASE")
                    )
                    return conn, conn.cursor()
                except OperationalError as e:
                    retry_count += 1
                    if retry_count < max_retries:
                        print(f"{Fore.YELLOW}DB Connection failed: {e}. Retrying...{Style.RESET_ALL}")
                        time.sleep(5)
                    else:
                        raise Exception("Failed to connect to PostgreSQL after multiple attempts")
    else:
        conn = sqlite3.connect('local.db', check_same_thread=False)
        return conn, conn.cursor()

# Initialize database and create tables
db, cursor = init_db()

def setup_tables():
    """Create all necessary database tables"""
    try:
        # Drop existing tables if in dev mode
        if ENV == "DEV":
            cursor.execute('DROP TABLE IF EXISTS helps')
            cursor.execute('DROP TABLE IF EXISTS language')
            cursor.execute('DROP TABLE IF EXISTS logs')
            db.commit()
        
        # Helps table
        help_table = '''
            CREATE TABLE IF NOT EXISTS helps (
                id {0},
                kitten_id INT,
                thread_id INT DEFAULT 0,
                closed INT DEFAULT 0,
                last_message_time {1}
            )
        '''.format(
            "SERIAL PRIMARY KEY" if ENV == "PROD" else "INTEGER PRIMARY KEY AUTOINCREMENT",
            "TIMESTAMP" if ENV == "PROD" else "DATETIME"
        )
        cursor.execute(help_table)

        # Language table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS language (
                chat_id INTEGER PRIMARY KEY,
                lang TEXT
            )
        ''')

        # Logs table
        logs_table = '''
            CREATE TABLE IF NOT EXISTS logs (
                id {0},
                kitten_id INT,
                supporters_ids TEXT,
                forum_id INT,
                messages TEXT
            )
        '''.format("SERIAL PRIMARY KEY" if ENV == "PROD" else "INTEGER PRIMARY KEY AUTOINCREMENT")
        cursor.execute(logs_table)
        
        db.commit()
        print(f"{Fore.GREEN}✔ Database tables created successfully{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}Error creating tables: {e}{Style.RESET_ALL}")
        raise

setup_tables()

# Load language strings
with open("langs.json", "r", encoding="utf-8") as f:
    LANG_TEXTS = json.load(f)

def get_text(key, chat_id, cursor):
    """Get localized text string"""
    cursor.execute("SELECT lang FROM language WHERE chat_id=?", (chat_id,))
    row = cursor.fetchone()
    user_lang = row[0] if row else "English"
    return LANG_TEXTS.get(key, {}).get(user_lang, LANG_TEXTS[key]["English"])

def log_message(kitten_id, forum_id, message, supporter_id=None):
    """Log messages if logging is enabled"""
    if not ENABLE_LOGGING:
        return
        
    try:
        cursor.execute(
            'SELECT messages, supporters_ids FROM logs WHERE kitten_id=? AND forum_id=?', 
            (kitten_id, forum_id)
        )
        row = cursor.fetchone()
        
        if row:
            messages = json.loads(row[0])
            supporters = json.loads(row[1])
            messages.append(message)
            if supporter_id and supporter_id not in supporters:
                supporters.append(supporter_id)
            cursor.execute(
                'UPDATE logs SET messages=?, supporters_ids=? WHERE kitten_id=? AND forum_id=?',
                (json.dumps(messages), json.dumps(supporters), kitten_id, forum_id)
            )
        else:
            cursor.execute(
                'INSERT INTO logs (kitten_id, forum_id, messages, supporters_ids) VALUES (?, ?, ?, ?)',
                (kitten_id, forum_id, json.dumps([message]), json.dumps([supporter_id] if supporter_id else []))
            )
        db.commit()
    except Exception as e:
        print(f"{Fore.RED}Logging error: {e}{Style.RESET_ALL}")

# Initialize bot
bot = telebot.TeleBot(BOT_TOKEN)

def end_markup(chat_id):
    """Generate keyboard markup with finish button"""
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(get_text("button_finish", chat_id, cursor))
    return kb

# Bot command handlers
@bot.message_handler(commands=['start'])
def start(message):
    """Handle /start command"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.row("Русский", "English", "Қазақша")
    bot.send_message(message.chat.id, "Please select your language / Выберите язык / Тіл таңдаңыз", reply_markup=markup)

@bot.message_handler(commands=['switch_language'])
def switch_language(message):
    """Handle language switch"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.row("Русский", "English", "Қазақша")
    bot.send_message(message.chat.id, get_text("lang_prompt", message.chat.id, cursor), reply_markup=markup)

@bot.message_handler(func=lambda m: m.text in ["Русский", "English", "Қазақша"] and m.chat.type == 'private')
def set_language(message):
    """Set user language preference"""
    cursor.execute('REPLACE INTO language (chat_id, lang) VALUES (?, ?)', (message.chat.id, message.text))
    db.commit()
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.row(
        get_text("button_start", message.chat.id, cursor),
        get_text("button_decline", message.chat.id, cursor)
    )
    bot.send_message(
        message.chat.id,
        get_text("disclaimer_text", message.chat.id, cursor),
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda m: m.text in [get_text("button_start", m.chat.id, cursor), 
                                              get_text("button_decline", m.chat.id, cursor)] 
                                              and m.chat.type == 'private')
def disclaimer_response(message):
    """Process user's response to disclaimer"""
    if message.text == get_text("button_start", message.chat.id, cursor):
        bot.send_message(message.chat.id, 
                        get_text("start_instructions", message.chat.id, cursor), 
                        reply_markup=end_markup(message.chat.id))
    else:
        bot.send_message(message.chat.id, 
                        get_text("session_not_started", message.chat.id, cursor))

@bot.message_handler(commands=['help'])
def help_command(message):
    """Process help requests and create support topics"""
    txt_list = message.text.split(" ")
    if len(txt_list) == 1:
        bot.send_message(message.from_user.id, 
                        get_text("error_no_request", message.from_user.id, cursor),
                        parse_mode="Markdown",
                        reply_markup=end_markup(message.chat.id))
        return

    cursor.execute('SELECT * FROM helps WHERE kitten_id = ?', (message.from_user.id,))
    if cursor.fetchone():
        bot.send_message(message.from_user.id,
                        get_text("error_has_open_session", message.from_user.id, cursor),
                        parse_mode='Markdown',
                        reply_markup=end_markup(message.chat.id))
        return

    cursor.execute('INSERT INTO helps (kitten_id) VALUES (?)', (message.from_user.id,))
    db.commit()

    cursor.execute('SELECT * FROM helps WHERE kitten_id = ?', (message.from_user.id,))
    result = cursor.fetchone()
    
    try:
        forum_topic = bot.create_forum_topic(CHAT_ID, f"Kitten #{result[0]}")
        cursor.execute('UPDATE helps SET thread_id = ? WHERE kitten_id = ?', 
                      (forum_topic.message_thread_id, message.from_user.id))
        db.commit()

        txt_list.remove("/help")
        help_text = ' '.join(txt_list)
        bot.send_message(CHAT_ID, help_text, 
                        reply_to_message_id=forum_topic.message_thread_id,
                        reply_markup=end_markup(message.chat.id))
        log_message(message.from_user.id, forum_topic.message_thread_id, help_text)
        
        bot.send_message(message.from_user.id,
                        get_text("request_sent", message.from_user.id, cursor),
                        parse_mode='Markdown',
                        reply_markup=end_markup(message.chat.id))
    except telebot.apihelper.ApiTelegramException as e:
        print(f"{Fore.RED}Failed to create forum topic: {e}{Style.RESET_ALL}")
        bot.send_message(message.from_user.id,
                        get_text("forum_failed", message.from_user.id, cursor),
                        reply_markup=end_markup(message.chat.id))

@bot.message_handler(commands=['close'])
def close_command(message):
    """Close user's support session"""
    cursor.execute('SELECT * FROM helps WHERE kitten_id = ? AND closed = 0', 
                  (message.from_user.id,))
    result = cursor.fetchone()
    
    if result:
        try:
            bot.close_forum_topic(CHAT_ID, result[2])
            bot.send_message(message.from_user.id,
                           get_text("session_closed", message.from_user.id, cursor),
                           reply_markup=end_markup(message.chat.id))
            cursor.execute('DELETE FROM helps WHERE kitten_id = ?', (message.from_user.id,))
            db.commit()
        except telebot.apihelper.ApiTelegramException as e:
            print(f"{Fore.RED}Failed to close forum topic: {e}{Style.RESET_ALL}")
            bot.send_message(message.from_user.id,
                           get_text("forum_close_failed", message.from_user.id, cursor),
                           reply_markup=end_markup(message.chat.id))

@bot.message_handler(content_types=['text'])
def handle_messages(message):
    """Handle all text messages"""
    print(f"{Fore.CYAN}💬 Message from {message.from_user.id}: {message.text}{Style.RESET_ALL}")

    # Handle finish button
    if message.text == get_text("button_finish", message.chat.id, cursor):
        cursor.execute('SELECT * FROM helps WHERE kitten_id = ? AND closed = 0',
                      (message.from_user.id,))
        result = cursor.fetchone()
        if result:
            try:
                bot.close_forum_topic(CHAT_ID, result[2])
                bot.send_message(message.chat.id,
                               get_text("dialog_ended", message.chat.id, cursor),
                               reply_markup=end_markup(message.chat.id))
                cursor.execute('DELETE FROM helps WHERE kitten_id = ?', (message.from_user.id,))
                db.commit()
            except Exception as e:
                print(f"{Fore.RED}Failed to close session: {e}{Style.RESET_ALL}")
        else:
            bot.send_message(message.chat.id,
                           get_text("dialog_inactive", message.chat.id, cursor),
                           reply_markup=end_markup(message.chat.id))
        return

    # Admin command
    if message.text == "check_chat_id_artchsh_admin_8x7yz25t":
        bot.send_message(message.chat.id, f"Chat ID: {message.chat.id}",
                        reply_markup=end_markup(message.chat.id))
        return

    # Check session timeout
    cursor.execute('SELECT last_message_time FROM helps WHERE kitten_id = ?',
                  (message.from_user.id,))
    row = cursor.fetchone()
    if row and row[0]:
        last_message_time = datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S')
        message_time = datetime.utcfromtimestamp(message.date)
        if message_time - last_message_time > timedelta(hours=3):
            bot.send_message(message.from_user.id,
                           get_text("inactivity_closed", message.from_user.id, cursor),
                           reply_markup=end_markup(message.chat.id))
            cursor.execute('DELETE FROM helps WHERE kitten_id = ?', (message.from_user.id,))
            db.commit()
            return

    # Handle messages from users
    if message.chat.id != CHAT_ID:
        cursor.execute('SELECT * FROM helps WHERE kitten_id = ?', (message.from_user.id,))
        result = cursor.fetchone()
        if not result:
            bot.send_message(message.chat.id,
                           get_text("no_active_ticket", message.chat.id, cursor),
                           parse_mode='Markdown',
                           reply_markup=end_markup(message.chat.id))
            return
        
        bot.send_message(CHAT_ID, message.text,
                        reply_to_message_id=result[2],
                        reply_markup=end_markup(message.chat.id))
        log_message(message.from_user.id, result[2], message.text)

    # Handle messages in support forum
    elif message.chat.id == CHAT_ID and message.message_thread_id:
        cursor.execute('SELECT * FROM helps WHERE thread_id = ?', (message.message_thread_id,))
        result = cursor.fetchone()
        if result:
            bot.send_message(result[1], message.text,
                           parse_mode='Markdown',
                           reply_markup=end_markup(message.chat.id))
            log_message(result[1], message.message_thread_id, message.text,
                       supporter_id=message.from_user.id)

    # Update last message time
    try:
        cursor.execute('UPDATE helps SET last_message_time = datetime("now") WHERE kitten_id = ?',
                      (message.from_user.id,))
        db.commit()
    except Exception as e:
        print(f"{Fore.RED}Failed to update message time: {e}{Style.RESET_ALL}")

if __name__ == '__main__':
    print(f"{Fore.GREEN}🚀 Bot is now running!{Style.RESET_ALL}")
    while True:
        try:
            bot.polling(non_stop=True, interval=2)
        except Exception as e:
            print(f"{Fore.RED}Bot polling error: {e}{Style.RESET_ALL}")
            time.sleep(5)