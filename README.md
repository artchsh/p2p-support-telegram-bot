# Psychological Help (Telegram Bot) 
## About project
This project was intented for use only in [KIMEP](https://kimep.kz/) university under ["JARQYN.ME"](https://instagram.com/jarqyn_kimep) student organization. But i have decided that it's source code should be public and free to use. I think that we should have more services providing easy and free psychological help for students, especially in Kazakhstan. 

## How this works?
Person, using Telegram, writes to this bot their problem using `/help <message>`, bot sends this message to newly created thread in pre-created supporter's supergroup. One of available helpers (in my case, they are volunteers from student organization) will try to help them, and then, when person will feel better, they can close thread by typing `/close`.

## Anonymity
Supporters do not know any information about the person writing, they have only text of message *(no profile picture, name or biography)*
Although, `user_id` is used for database, because it is unique. But, after the thread is closed, record with person's `user_id` get deleted.

### Commands
|Command|Description
|---|---
|/start|Used to start the bot
|/help `message`|Used to send anonymous message to psychological supporters
|/close|Used to close the current thread