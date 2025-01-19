# P2P Support Telegram Bot

This project is a Telegram bot that manages user requests. It creates and manages tickets via Telegram forum topics.

## Features

- Language selection (Russian, English, Kazakh)
- Automated forum topic creation

## Commands

| Command                          | Description                       |
|----------------------------------|-----------------------------------|
| /start                           | Begin a conversation              |
| /switch_language                 | Change language                   |
| /help <your request>             | Create a support request          |
| /close                           | Close the current request         |
| /close_topic                     | Close topic (forum-only command)  |
| /finish (button)                 | Similar to /close                 |
| /check_chat_id_artchsh_admin_8x7yz25t | Debug info                    |

## Prerequisites

1. Python 3.7+
2. pip install -r requirements.txt
3. (Optional) MySQL connector if running in PROD

## Environment Setup

1. Copy .env.example to .env
2. Fill in BOT_TOKEN, CHAT_ID, ENV, and MySQL credentials if needed
3. ENV="DEV" for local development with SQLite

## Running

1. python main.py or python translations.py (depending on your entry point)
2. The bot polls chat messages and processes commands

## FAQs

1. **Where do I set the bot token?**  
   In your .env file under BOT_TOKEN.

2. **How do I switch to a MySQL database?**  
   Set ENV to "PROD" and fill MYSQL_USER, MYSQL_PASSWORD, MYSQL_HOST, and MYSQL_DATABASE. The script will attempt to use MySQL.

3. **Why are forum topics not created?**  
   Make sure the chat is a supergroup with topics enabled, and your bot has administrator permissions for forum topics.

4. **How to close a ticket?**  
   Use /close or press the finish button. The bot will close the forum topic and delete the session record.

5. **Inactivity auto-close?**  
   After 3+ hours of no messages, the request is closed automatically. The user receives a notification.

6. **How to add more languages?**  
   Edit langs.json and add new keys. The bot uses these translations automatically based on stored user language.
