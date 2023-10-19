# TwitchStatusBot

Simple bot to send message to a specific channel in Discord if Streamer get's online at 
Twitch.

## HowTo

Clone the repo and copy over `config.ini.dist` to `config.ini`  
Only sections **[DISCORD]** and **[TWITCH]** are mandatory. If you don't want the other features, delete the whole sections.
Streams is a comma separated list of twitch streamer names. NO TRAILING COMMA!

Edit the file and propagate with API keys from Discord and Twitch.  
To create a Discord bot and get a token go to 
[Discord Applications](https://discord.com/developers/applications) 
and create one.  
For Twitch got to [Twitch Dev Dashboard](https://dev.twitch.tv/console) and create 
an application (not extension). See 
[Client credentials grant flow](https://dev.twitch.tv/docs/authentication/getting-tokens-oauth/#client-credentials-grant-flow) 
on how to get the tokens.

## Prepare Python

Install extensions via `pip install -r requirements.txt` (best practice is using a virtual 
environment for that!)  

## Run

Simply do `python3 main.py`  
**Note**: bot takes local timezone from server for timed data (like D4 worldboss), set it properly!

## Set as systemd service

If you want your bot running as service, do following:
1. copy `bot.service` to `/lib/systemd/system/` 
2. edit the file (set working directory and path to `main.py`)
3. do `sudo systemctl daemon-reload` and `sudo systemctl enable bot`
4. then `sudo service bot start`