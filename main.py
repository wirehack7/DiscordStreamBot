#!/usr/bin/python3
import os
import discord
import logging
import configparser
from func.discordbot import MyClient
import colorlog
from logging.handlers import TimedRotatingFileHandler
import time

log_level_info = {
    'logging.DEBUG': logging.DEBUG,
    'logging.INFO': logging.INFO,
    'logging.WARNING': logging.WARNING,
    'logging.ERROR': logging.ERROR,
}

if __name__ == "__main__":
    config = configparser.ConfigParser()
    with open('config.ini') as fh:
        config.read_file(fh)
    fh.close()

    if 'DISCORD' not in config or ('token' not in config['DISCORD']):
        raise ValueError('Discord config not found, check config.ini!')

    logging.basicConfig(
        format="%(asctime)s [%(filename)s:%(lineno)s - %(funcName)20s() ] [%(levelname)s] %(message)s",
        level=log_level_info.get(config['DEFAULT']['LOG_LEVEL'], logging.ERROR),
        handlers=[
            colorlog.StreamHandler(),
            TimedRotatingFileHandler("logs/output.log",
                                     when="d",
                                     interval=1,
                                     backupCount=5
                                     )
        ]
    )

    intents = discord.Intents.default()
    intents.message_content = True
    client = MyClient(intents=intents)
    client.run(config['DISCORD']['token'])
