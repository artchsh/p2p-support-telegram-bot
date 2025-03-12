import os
import json
import time
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, TIMESTAMP, BigInteger, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from contextlib import contextmanager

Base = declarative_base()

class Help(Base):
    __tablename__ = 'helps'
    id = Column(Integer, primary_key=True)
    kitten_id = Column(Integer)
    thread_id = Column(Integer, default=0)
    closed = Column(Integer, default=0)
    last_message_time = Column(TIMESTAMP)

class Language(Base):
    __tablename__ = 'language'
    chat_id = Column(BigInteger, primary_key=True)
    lang = Column(String(255))

class Log(Base):
    __tablename__ = 'logs'
    id = Column(Integer, primary_key=True)
    kitten_id = Column(Integer)
    supporters_ids = Column(Text)
    forum_id = Column(Integer)
    messages = Column(Text)

class Database:
    def __init__(self):
        self._init_db()
    
    def _init_db(self):
        max_retries = 5
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                print(f"[*] Attempting PostgreSQL connection ({retry_count + 1}/{max_retries})...")
                
                db_url = f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}/{os.getenv('POSTGRES_DB')}"
                self.engine = create_engine(db_url)
                
                Base.metadata.create_all(self.engine)
                self.Session = sessionmaker(bind=self.engine)
                
                print("[+] Database connection established successfully")
                break
            except Exception as e:
                retry_count += 1
                if retry_count < max_retries:
                    print(f"[-] DB Connection failed: {e}. Retrying...")
                    time.sleep(5)
                else:
                    raise Exception(f"Failed to connect to PostgreSQL after multiple attempts")
    
    @contextmanager
    def session_scope(self):
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            print(f"[-] Database session error: {e}")
            raise
        finally:
            session.close()
    
    def reconnect_if_needed(self):
        try:
            with self.session_scope() as session:
                session.execute(text("SELECT 1"))
        except (OperationalError, SQLAlchemyError):
            self._init_db()
    
    def get_language(self, chat_id):
        self.reconnect_if_needed()
        with self.session_scope() as session:
            result = session.query(Language).filter(Language.chat_id == chat_id).first()
            return result.lang if result else "English"
    
    def set_language(self, chat_id, language):
        self.reconnect_if_needed()
        with self.session_scope() as session:
            stmt = pg_insert(Language).values(chat_id=chat_id, lang=language)
            stmt = stmt.on_conflict_do_update(
                index_elements=['chat_id'],
                set_=dict(lang=language)
            )
            session.execute(stmt)
    
    def get_help(self, kitten_id=None, thread_id=None) -> Help:
        self.reconnect_if_needed()
        with self.session_scope() as session:
            result = None
            if kitten_id is not None:
                result = session.query(Help).filter(Help.kitten_id == kitten_id).first()
            elif thread_id is not None:
                result = session.query(Help).filter(Help.thread_id == thread_id).first()
            
            if result:
                return {c.name: getattr(result, c.name) for c in result.__table__.columns}
            return None
    
    def get_active_help(self, kitten_id):
        self.reconnect_if_needed()
        with self.session_scope() as session:
            result = session.query(Help).filter(Help.kitten_id == kitten_id, Help.closed == 0).first()
            
            if result:
                return {c.name: getattr(result, c.name) for c in result.__table__.columns}
            return None
    
    def create_help(self, kitten_id):
        self.reconnect_if_needed()
        with self.session_scope() as session:
            new_help = Help(kitten_id=kitten_id, last_message_time=datetime.now())
            session.add(new_help)
            session.commit()
            
            help_obj = session.query(Help).filter(Help.kitten_id == kitten_id).first()
            if help_obj:
                return {c.name: getattr(help_obj, c.name) for c in help_obj.__table__.columns}
            return None
    
    def update_thread_id(self, kitten_id, thread_id):
        self.reconnect_if_needed()
        with self.session_scope() as session:
            session.query(Help).filter(Help.kitten_id == kitten_id).update({"thread_id": thread_id})
    
    def update_last_message_time(self, kitten_id):
        self.reconnect_if_needed()
        with self.session_scope() as session:
            session.query(Help).filter(Help.kitten_id == kitten_id).update({"last_message_time": datetime.now()})
    
    def delete_help(self, kitten_id):
        self.reconnect_if_needed()
        with self.session_scope() as session:
            session.query(Help).filter(Help.kitten_id == kitten_id).delete()
    
    def log_message(self, kitten_id, forum_id, message, supporter_id=None):
        self.reconnect_if_needed()
        
        try:
            with self.session_scope() as session:
                log = session.query(Log).filter(Log.kitten_id == kitten_id, Log.forum_id == forum_id).first()
                
                if log:
                    try:
                        messages = json.loads(log.messages)
                        supporters = json.loads(log.supporters_ids)
                    except json.JSONDecodeError as e:
                        # Handle corrupted JSON data
                        print(f"[-] JSON decode error in log record: {e}")
                        messages = []
                        supporters = []
                        
                    messages.append(message)
                    if supporter_id and supporter_id not in supporters:
                        supporters.append(supporter_id)
                    log.messages = json.dumps(messages)
                    log.supporters_ids = json.dumps(supporters)
                else:
                    new_log = Log(
                        kitten_id=kitten_id,
                        forum_id=forum_id,
                        messages=json.dumps([message]),
                        supporters_ids=json.dumps([supporter_id] if supporter_id else [])
                    )
                    session.add(new_log)
            return True
        except Exception as e:
            print(f"[-] Logging error: {e}")
            return False
