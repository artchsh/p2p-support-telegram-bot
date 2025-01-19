import os
from dotenv import load_dotenv
load_dotenv()
import sqlite3

def init_db():
    env = os.getenv("ENV", "DEV")
    if env == "PROD" and os.getenv("MYSQL_USER") != "":
        exit()
        import mysql.connector
        db = mysql.connector.connect(
            host=os.getenv("MYSQL_HOST"),
            user=os.getenv("MYSQL_USER"),
            password=os.getenv("MYSQL_PASSWORD"),
            database=os.getenv("MYSQL_DATABASE")
        )
        cursor = db.cursor()
    else:
        db = sqlite3.connect('local.db', check_same_thread=False)
        cursor = db.cursor()
    return db, cursor

def checkHelpTable(cursor, db):
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

def create_language_table(cursor):
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS language (
            chat_id INTEGER PRIMARY KEY,
            lang TEXT
        )
    ''')
    db.commit()

db, cursor = init_db()
checkHelpTable(cursor, db)
create_language_table(cursor)