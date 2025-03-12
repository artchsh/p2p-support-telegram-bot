import os, json, time, telebot, traceback
from telebot import types
from datetime import datetime
from dotenv import load_dotenv
from db import Database
from flask import Flask, Response
import threading
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID", "-1"))
ENABLE_LOGGING = bool(int(os.getenv("ENABLE_LOGGING", "1")))
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "-1"))
RETRY_DELAY = float(os.getenv("RETRY_DELAY", "2.0"))
FLASK_PORT = int(os.getenv("FLASK_PORT", "5000"))
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

logger.info(f"Bot starting at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
logger.info(f"Environment: {ENVIRONMENT}")

app = Flask(__name__)

@app.route("/healthcheck")
def healthcheck():
    logger.debug("Healthcheck endpoint called")
    return Response("OK", status=200)

def start_flask():
    logger.info(f"Starting Flask server on port {FLASK_PORT}")
    try:
        app.run(host="0.0.0.0", port=FLASK_PORT, debug=False, use_reloader=False)
    except Exception as e:
        logger.error(f"Error starting Flask server: {e}")

# Create and start Flask thread
flask_thread = threading.Thread(target=start_flask)
flask_thread.daemon = True
logger.info("Starting Flask thread")
flask_thread.start()
logger.info("Flask thread started")

# Give Flask a moment to start up
time.sleep(1)
logger.info("Continuing with bot initialization")

db = Database()

with open("langs.json", "r", encoding="utf-8") as f:
    LANG_TEXTS = json.load(f)

def get_text(key, chat_id):
    user_lang = db.get_language(chat_id)
    return LANG_TEXTS.get(key, {}).get(user_lang, LANG_TEXTS[key]["English"])

def log_message(kitten_id, forum_id, message, supporter_id=None):
    if not ENABLE_LOGGING:
        return
    db.log_message(kitten_id, forum_id, message, supporter_id)

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

def report_error(error_message):
    try:
        # Sanitize error message and traceback to avoid HTML parsing issues
        error_msg_clean = str(error_message).replace('<', '&lt;').replace('>', '&gt;')
        error_traceback = traceback.format_exc()
        error_traceback_clean = error_traceback.replace('<', '&lt;').replace('>', '&gt;')
        
        # Limit traceback length to avoid Telegram message size limits
        if len(error_traceback_clean) > 3000:
            error_traceback_clean = error_traceback_clean[:3000] + '... (truncated)'
        
        error_text = f"<b>Error:</b><code>{error_msg_clean}</code><b>Traceback:</b><pre>{error_traceback_clean}</pre>"
        bot.send_message(ADMIN_CHAT_ID, error_text, parse_mode="HTML")
    except Exception as sendErr:
        print(f"[-] Failed to send error message to admin: {sendErr}")
        # Fallback to plain text if HTML parsing fails
        try:
            plain_text = f"Error: {error_message}\nTraceback: {traceback.format_exc()[:1000]}..."
            bot.send_message(ADMIN_CHAT_ID, plain_text)
        except:
            print("[-] Failed to send even plain text error message")

def create_language_markup():
    markup = types.InlineKeyboardMarkup(row_width=3)
    markup.add(
        types.InlineKeyboardButton("Русский", callback_data="lang_Russian"),
        types.InlineKeyboardButton("English", callback_data="lang_English"),
        types.InlineKeyboardButton("Қазақша", callback_data="lang_Kazakh")
    )
    return markup

def create_disclaimer_markup(chat_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(get_text("button_start", chat_id), callback_data="disclaimer_accept"),
        types.InlineKeyboardButton(get_text("button_decline", chat_id), callback_data="disclaimer_decline")
    )
    return markup

def create_session_markup(chat_id):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(get_text("button_finish", chat_id), callback_data="finish_session"))
    return markup

@bot.message_handler(commands=['start'])
def start(message):
    markup = create_language_markup()
    bot.send_message(
        message.chat.id, 
        "Please select your language / Выберите язык / Тіл таңдаңыз",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('lang_'))
def language_callback(call):
    language = call.data.split('_')[1]
    language_display = {"Russian": "Русский", "English": "English", "Kazakh": "Қазақша"}
    
    db.set_language(call.message.chat.id, language_display[language])
    
    markup = create_disclaimer_markup(call.message.chat.id)
    
    bot.edit_message_text(
        get_text("disclaimer_text", call.message.chat.id),
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
        parse_mode="HTML"
    )
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('disclaimer_'))
def disclaimer_callback(call):
    action = call.data.split('_')[1]
    
    if action == 'accept':
        markup = create_session_markup(call.message.chat.id)
        bot.edit_message_text(
            get_text("anonymity_notice", call.message.chat.id) + "\n\n" + 
            get_text("start_instructions", call.message.chat.id),
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="HTML"
        )
    else:
        bot.edit_message_text(
            get_text("session_not_started", call.message.chat.id),
            call.message.chat.id,
            call.message.message_id
        )
    
    bot.answer_callback_query(call.id)

@bot.message_handler(commands=['switch_language'])
def switch_language(message):
    markup = create_language_markup()
    bot.send_message(
        message.chat.id, 
        get_text("lang_prompt", message.chat.id),
        reply_markup=markup
    )

@bot.message_handler(commands=['help'])
def help_command(message):
    txt_list = message.text.split(" ")
    
    # if there is not text after /help then send error
    if len(txt_list) == 1:
        bot.send_message(
            message.from_user.id, 
            get_text("error_no_request", message.from_user.id),
            parse_mode="HTML",
            reply_markup=create_session_markup(message.chat.id)
        )
        return

    # if there is a help request already open send error
    help_request = db.get_help(kitten_id=message.from_user.id)
    if help_request:
        bot.send_message(
            message.from_user.id,
            get_text("error_has_open_session", message.from_user.id),
            parse_mode='HTML',
            reply_markup=create_session_markup(message.chat.id)
        )
        return

    # Creating new help in db
    result = db.create_help(message.from_user.id)
    
    try:
        # Create a forum topic in the support group
        forum_topic = bot.create_forum_topic(CHAT_ID, f"Kitten #{result['id']}")

        # Update thread ID in helps database and send the message
        db.update_thread_id(message.from_user.id, forum_topic.message_thread_id)

        txt_list.remove("/help")
        help_text = ' '.join(txt_list) 
        
        bot.send_message(
            CHAT_ID, 
            help_text,
            reply_to_message_id=forum_topic.message_thread_id
        )
        
        log_message(message.from_user.id, forum_topic.message_thread_id, help_text)
        
        bot.send_message(
            message.from_user.id,
            get_text("anonymous_request_sent", message.from_user.id),
            parse_mode='HTML',
            reply_markup=create_session_markup(message.chat.id)
        )
    except Exception as e:
        print(f"[-] Error in help_command: {e}")
        report_error(e)
        bot.send_message(
            message.from_user.id,
            get_text("forum_failed", message.from_user.id),
            parse_mode="HTML", 
            reply_markup=create_session_markup(message.chat.id)
        )

@bot.message_handler(commands=['close'])
def close_command(message):
    close_session(message.from_user.id, message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data == 'finish_session')
def finish_session_callback(call):
    close_session(call.from_user.id, call.message.chat.id)
    bot.answer_callback_query(call.id, text=get_text("dialog_ended", call.message.chat.id))

def close_session(user_id, chat_id):
    help_request = db.get_active_help(user_id)
    
    if help_request:
        try:
            # Try to send closing message and close forum topic
            try:
                # get thread id from helps by filtering by user
                help_request = db.get_help(kitten_id=user_id)
                if not help_request:
                    bot.send_message(
                        user_id,
                        get_text("no_active_ticket", chat_id),
                        parse_mode="HTML",
                        reply_markup=create_session_markup(chat_id)
                    )
                    return

                # Send closing message to the support group
                try:
                    # First check if we can send a message to the thread
                    bot.send_message(
                        CHAT_ID, 
                        get_text("anonymous_session_closed", chat_id),
                        message_thread_id=help_request['thread_id']
                    )
                    # Then try to close the forum topic
                    bot.close_forum_topic(CHAT_ID, help_request['thread_id'])
                except telebot.apihelper.ApiTelegramException as e:
                    if "chat not found" in str(e).lower():
                        print(f"[-] Chat not found when closing forum topic: {e}")
                        # Continue with deleting the help record even if the forum topic can't be closed
                        pass
                    else:
                        raise
            except telebot.apihelper.ApiTelegramException as te:
                print(f"[-] Telegram API error during forum topic closing: {te}")
                report_error(te)
                bot.send_message(
                    user_id,
                    get_text("forum_close_failed", chat_id),
                    reply_markup=create_session_markup(chat_id)
                )
                return
                
            bot.send_message(
                user_id,
                get_text("session_closed", chat_id),
                parse_mode="HTML"
            )
            db.delete_help(user_id)
        except Exception as e:
            print(f"[-] Error in close_session: {e}")
            report_error(e)
            bot.send_message(
                user_id,
                get_text("forum_close_failed", chat_id),
                reply_markup=create_session_markup(chat_id)
            )
    else:
        bot.send_message(
            user_id,
            get_text("dialog_inactive", chat_id),
            parse_mode="HTML"
        )

@bot.message_handler(content_types=['text', 'photo', 'document'])
def handle_messages(message: telebot.types.Message):
    print(f"[*] Message from {message.from_user.id}: {message.text if message.content_type == 'text' else message.content_type}")

    # Check for inactivity
    help_request = db.get_help(kitten_id=message.from_user.id)
    if help_request and help_request['last_message_time']:
        try:
            # Handle datetime object or string format
            if isinstance(help_request['last_message_time'], datetime):
                last_message_time = help_request['last_message_time']
            else:
                # Try to parse the datetime string with timezone info if present
                try:
                    last_message_time = datetime.fromisoformat(str(help_request['last_message_time']))
                except ValueError:
                    # Fallback to basic format if fromisoformat fails
                    last_message_time = datetime.strptime(str(help_request['last_message_time']), '%Y-%m-%d %H:%M:%S')
            
            # Convert message timestamp to datetime
            message_time = datetime.fromtimestamp(message.date)
            
            # Check if inactive for more than 3 hours
            if (message_time - last_message_time).total_seconds() > 3 * 3600:
                bot.send_message(
                    message.from_user.id,
                    get_text("inactivity_closed", message.from_user.id),
                    reply_markup=create_session_markup(message.chat.id),
                    parse_mode="HTML"
                )
                db.delete_help(message.from_user.id)
                return
        except Exception as e:
            print(f"[-] Error in inactivity check: {e}")
            report_error(e)

    # Handle user messages to forward to support chat
    print("Message Chat ID: ", message.chat.id, "Group chat ID:", CHAT_ID)
    if message.chat.id != CHAT_ID:
        
        help_message = message.text
        user_chat_id = message.chat.id
        help_request = db.get_help(kitten_id=message.from_user.id)
        
        if not help_request:
            bot.send_message(
                user_chat_id,
                get_text("no_active_ticket", user_chat_id),
                parse_mode='HTML',
                reply_markup=create_session_markup(user_chat_id)
            )
            return
            
        forum_thread_id = help_request['thread_id']
        
        # Forward message to support chat based on content type
        if message.content_type == 'text':
            bot.send_message(
                chat_id=CHAT_ID,
                message_thread_id=forum_thread_id, 
                text=help_message
            )
            log_message(message.from_user.id, help_request['thread_id'], message.text)
        else: 
            bot.send_message(
                message.chat.id,
                get_text("unsupported_content", message.chat.id),
                parse_mode="HTML"
            )
            return

    # Handle supporter replies in the forum
    elif message.chat.id == CHAT_ID and message.message_thread_id:
        
        help_request = db.get_help(thread_id=message.message_thread_id)
        answer_message = message.text
        forum_thread_id = help_request['thread_id']
        kitten_id = help_request['kitten_id']
        
        if help_request:
            header = get_text("supporter_message_header", message.chat.id)
            
            # Forward supporter message to user based on content type
            if message.content_type == 'text':
                try:
                    bot.send_message(
                        kitten_id, 
                        f"{header}\n\n{answer_message}",
                        parse_mode='HTML' 
                    )
                    log_message(kitten_id, message.message_thread_id, message.text,
                              supporter_id=message.from_user.id)
                except Exception as e:
                    print(f"[-] Error sending message to user: {e}")
                    report_error(e)
                    bot.send_message(
                        CHAT_ID,
                        f"Error sending your message: {str(e)}",
                        reply_to_message_id=message.message_thread_id
                    )
            else: 
                bot.send_message(
                    message.message_thread_id,
                    "Unsupported content type. Currently, I support only texts.",
                    parse_mode="HTML"
                )
                return

    # Update last message time
    try:
        db.update_last_message_time(message.from_user.id)
    except Exception as e:
        print(f"[-] Failed to update message time: {e}")
        report_error(e)

if __name__ == '__main__':
    logger.info("[+] Bot is now running!")
    
    try:
        logger.info(f"[*] Verifying support group (CHAT_ID: {CHAT_ID})...")
        chat_info = bot.get_chat(CHAT_ID)
        logger.info(f"[+] Support group verified: {chat_info.title}")
        
        if hasattr(chat_info, 'is_forum') and chat_info.is_forum:
            logger.info("[+] Support group has forum capability")
        else:
            logger.warning("[!] Warning: Support group does not support forum topics")
    except Exception as e:
        logger.error(f"[-] Error verifying support group: {e}")
        
    while True:
        try:
            logger.info("Starting bot polling")
            bot.polling(non_stop=True, interval=1, timeout=20)
        except telebot.apihelper.ApiTelegramException as te:
            logger.error(f"[-] Polling Telegram API error: {te}")
            report_error(te)
            time.sleep(RETRY_DELAY)
        except Exception as e:
            logger.error(f"[-] Bot polling error: {e}")
            report_error(e)
            time.sleep(RETRY_DELAY)