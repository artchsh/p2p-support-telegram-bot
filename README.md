# Psychological Help (Telegram Bot) 
## About project
This project was intended for use only in [KIMEP](https://kimep.kz/) university under ["JARQYN.ME"](https://instagram.com/jarqyn_kimep) student organization. However, I have decided that its source code should be public and free to use. I think that we should have more services providing easy and free psychological help for students, especially in Kazakhstan. 

## How this works?
A person, using Telegram, writes to this bot their problem using `/help <message>`, The bot sends this message to a newly created thread in a pre-created supporter's supergroup. One of the available helpers (in my case, they are volunteers from a student organization) will try to help them, and then, when a person feels better, they can close the thread by typing `/close`.

## Anonymity
Supporters do not know any information about the person writing, they have only the text of message *(no profile picture, name, or biography)*
Although, `user_id` is used for database, because it is unique. But, after the thread is closed, the record with the person's `user_id` gets deleted.

### Commands
|Command|Description
|---|---
|/start|Used to start the bot
|/help `message`|Used to send anonymous messages to psychological supporters
|/close|Used to close the current thread