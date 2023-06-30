# TwitchStatusBot

Simple bot to send message to a specific channel in Discord if Streamer get's online at 
Twitch.

## HowTo

Clone the repo and copy over `dist.env` to `.env`

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

