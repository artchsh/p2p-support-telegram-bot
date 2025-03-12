import pytest
import bot


class DummyMessage:
    def __init__(self, chat_id, text):
        self.chat = type('Chat', (), {"id": chat_id})
        self.from_user = type('User', (), {"id": chat_id})
        self.text = text
        self.message_id = 123


class DummyCall:
    def __init__(self, chat_id, data):
        self.message = DummyMessage(chat_id, "")
        self.data = data
        self.id = "call123"


@pytest.fixture(autouse=True)
def setup_db(monkeypatch):
    # Setup a dummy database object in bot.db for testing purposes
    class DummyDB:
        def __init__(self):
            self.lang = {}
            self.helps = {}
            self.help_counter = 1

        def get_language(self, chat_id):
            return self.lang.get(chat_id, "English")

        def set_language(self, chat_id, language):
            self.lang[chat_id] = language

        def get_help(self, kitten_id=None, thread_id=None):
            if kitten_id is not None:
                return self.helps.get(kitten_id)
            return None

        def create_help(self, kitten_id):
            help_obj = {"id": self.help_counter, "kitten_id": kitten_id, "thread_id": 0, "closed": 0, "last_message_time": "2025-03-11 09:00:00.000000"}
            self.helps[kitten_id] = help_obj
            self.help_counter += 1
            return help_obj

        def update_thread_id(self, kitten_id, thread_id):
            if kitten_id in self.helps:
                self.helps[kitten_id]["thread_id"] = thread_id

        def update_last_message_time(self, kitten_id):
            if kitten_id in self.helps:
                self.helps[kitten_id]["last_message_time"] = "2025-03-11 10:00:00.000000"

        def delete_help(self, kitten_id):
            if kitten_id in self.helps:
                del self.helps[kitten_id]

        def log_message(self, kitten_id, forum_id, message, supporter_id=None):
            return True

    dummy_db = DummyDB()
    monkeypatch.setattr(bot, "db", dummy_db)


@pytest.fixture
def capture_messages(monkeypatch):
    messages = []

    def fake_send_message(chat_id, text, reply_markup=None, parse_mode=None, reply_to_message_id=None):
        messages.append({
            "chat_id": chat_id,
            "text": text,
            "reply_markup": reply_markup,
            "parse_mode": parse_mode,
            "reply_to_message_id": reply_to_message_id
        })

    monkeypatch.setattr(bot.bot, "send_message", fake_send_message)
    return messages


def test_start_command(capture_messages):
    msg = DummyMessage(chat_id=1, text="/start")
    bot.start(msg)
    # Check the message sent contains language prompt text.
    assert any("select your language" in m["text"].lower() for m in capture_messages)


def test_language_callback(monkeypatch, capture_messages):
    call = DummyCall(chat_id=2, data="lang_Russian")
    edited_texts = []
    mock_answers = []

    def fake_edit_message_text(text, chat_id, message_id, reply_markup=None, parse_mode=None):
        edited_texts.append((text, chat_id, message_id))

    def fake_answer_cbq(callback_query_id):
        mock_answers.append(callback_query_id)

    monkeypatch.setattr(bot.bot, "edit_message_text", fake_edit_message_text)
    monkeypatch.setattr(bot.bot, "answer_callback_query", fake_answer_cbq)
    
    bot.language_callback(call)
    
    assert mock_answers == [call.id]
    assert len(edited_texts) == 1
    # Check if language was set in dummy db
    assert bot.db.get_language(2) == "Русский"


def test_help_command_no_request(capture_messages):
    msg = DummyMessage(chat_id=3, text="/help")
    bot.help_command(msg)
    # Should send an error about no request.
    assert any("haven't written your support request" in m["text"].lower() for m in capture_messages)


def test_help_command_with_request(monkeypatch, capture_messages):
    # Ensure get_help returns None (no open help)
    monkeypatch.setattr(bot.db, "get_help", lambda kitten_id=None, thread_id=None: None)

    def fake_create_help(kitten_id):
        return {"id": 1, "kitten_id": kitten_id, "thread_id": 111, "closed": 0, "last_message_time": "2025-03-11 09:00:00.000000"}
    monkeypatch.setattr(bot.db, "create_help", fake_create_help)
    
    msg = DummyMessage(chat_id=4, text="/help This is a test help message")
    
    def fake_create_forum_topic(chat_id, name):
        class DummyForum:
            message_thread_id = 555
        return DummyForum()
    monkeypatch.setattr(bot.bot, "create_forum_topic", fake_create_forum_topic)
    
    bot.help_command(msg)
    
    # Expect a confirmation message to the user
    user_msgs = [m for m in capture_messages if m["chat_id"] == msg.from_user.id]
    assert any("anonymous" in m["text"].lower() or "request" in m["text"].lower() for m in user_msgs)


def test_report_error(monkeypatch, capture_messages):
    def fake_send_message(chat_id, text, parse_mode=None, reply_markup=None):
        capture_messages.append({
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "reply_markup": reply_markup
        })
    monkeypatch.setattr(bot.bot, "send_message", fake_send_message)
    monkeypatch.setattr("bot.traceback.format_exc", lambda: "trace_info")
    
    bot.report_error("Test error")
    
    # Check that an error message was sent to the admin (ADMIN_CHAT_ID should be an int)
    assert any(isinstance(m["chat_id"], int) for m in capture_messages)
