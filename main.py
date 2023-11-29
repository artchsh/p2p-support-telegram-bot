import telebot, mysql.connector
from telebot import types
from config import BOT_TOKEN, CHAT_ID, MYSQL_CREDENTIALS

db = mysql.connector.connect(
    host=MYSQL_CREDENTIALS["host"],
    user=MYSQL_CREDENTIALS["user"],
    password=MYSQL_CREDENTIALS["password"],
    database=MYSQL_CREDENTIALS["database"]
)
cursor = db.cursor()

def checkHelpTable():
    _SQL = '''
        CREATE TABLE IF NOT EXISTS helps (
            id INT AUTO_INCREMENT PRIMARY KEY,
            kitten_id INT,
            thread_id INT DEFAULT 0,
            closed INT DEFAULT 0
        )
    '''
    cursor.execute(_SQL)
    db.commit()

checkHelpTable()
bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.from_user.id, "Привет, чтобы получить помощь напиши `/help <Ваша проблема>`", parse_mode="Markdown")

@bot.message_handler(commands=['help'])
def help(message: types.Message):
    # dividing text by space
    txt_list = message.text.split(" ")
    # checking if text contains problem
    if len(txt_list) == 1:
        # if not, send an error then stop
        bot.send_message(message.from_user.id, "Вы не написали вашу проблему. `/help <Ваша проблема>`", parse_mode="Markdown")
        return
    
    # first check if user has topic opened
    _SQL = '''
        SELECT * FROM helps WHERE kitten_id = %s
    '''
    cursor.execute(_SQL, (message.from_user.id,))
    result = cursor.fetchall()
    # if we found something, respond with error message and stop
    if len(result) != 0:
        bot.send_message(message.from_user.id, "Вы еще не завершили свою предыдущую проблему. Чтобы это сделать, напишите `/close`", parse_mode='Markdown')
        return
    
    # Create a new record of kitten and their problem
    _SQL = '''
        INSERT INTO helps 
        (kitten_id)
        VALUES
        (%s)
    '''
    cursor.execute(_SQL, (message.from_user.id,))
    db.commit()
    
    # create a new forum topic with name that contains id of an existing record
    _SQL = '''
        SELECT * FROM helps WHERE kitten_id = %s
    '''
    cursor.execute(_SQL, (message.from_user.id,))
    result = cursor.fetchall()
    forum_topic = bot.create_forum_topic(CHAT_ID, f"Kitten #{result[0][0]}")
    
    # update the record to set the thread_id
    _SQL = '''
        UPDATE helps
        SET thread_id = %s
        WHERE kitten_id = %s
    '''
    cursor.execute(_SQL, (forum_topic.message_thread_id, message.from_user.id,))
    db.commit()
    
    # remove command from text
    txt_list.remove('/help')
    # send problem to created thread 
    bot.send_message(CHAT_ID, ' '.join(txt_list), reply_to_message_id=forum_topic.message_thread_id)
    
    bot.send_message(message.from_user.id, "Ваша проблема была отправлена. Если вы хотите добавить что-то еще, не стесняйтесь, пишите дальше, но уже без `/help` :)", parse_mode='Markdown')
    
@bot.message_handler(commands=['close'])
def close(message: types.Message):
    
    # get user info from records
    _SQL = '''
        SELECT *
        FROM helps
        WHERE kitten_id = %s
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
            bot.close_forum_topic(CHAT_ID, thread_id)
            
            # send confirmation message
            bot.send_message(message.from_user.id, "Вы успешно завершили свою проблему!")
            
            # delete the record
            _SQL = '''
                DELETE FROM helps WHERE kitten_id = %s;
            '''
            cursor.execute(_SQL, (message.from_user.id,))
            db.commit()
            
# this is any text handler
@bot.message_handler(content_types=['text'])
def get_text_messages(message: types.Message):
    # if this was in any personal chat 
    if message.chat.id != CHAT_ID:
        # get user info
        _SQL = '''
            SELECT *
            FROM helps
            WHERE kitten_id = %s
        '''
        cursor.execute(_SQL, (message.from_user.id,))
        result = cursor.fetchall()

        # check if record not exists
        if len(result) == 0:
            bot.send_message(message.from_user.id, "Вы либо ошиблись, либо ваша проблема была закрыта. Чтобы задать новую проблему, напишите `/help <Ваша проблема>`", parse_mode='Markdown')
            return

        # "forward" message to appropriate channel
        bot.send_message(CHAT_ID, message.text, reply_to_message_id=result[0][2])
            
    # if this was in CHAT_ID
    if message.chat.id == CHAT_ID:

        # check that thread id exists
        if message.message_thread_id != None:

            _SQL = '''
                SELECT *
                FROM helps
                WHERE thread_id = %s
            '''
            cursor.execute(_SQL, (message.message_thread_id,))
            result = cursor.fetchall()

            # check that records exists
            if len(result) == 0:
                return
            
            bot.send_message(result[0][1], message.text, parse_mode='Markdown')

    if "chat" in message.text:
        bot.send_message(message.chat.id, f"Chat ID: {message.chat.id} \n Your id: {message.from_user.id}")

bot.polling(non_stop=True, interval=2) #обязательная для работы бота часть