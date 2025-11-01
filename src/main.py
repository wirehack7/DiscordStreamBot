#!/usr/bin/python3
import discord
import logging
import configparser
from func.discordbot import MyClient
from logging.handlers import TimedRotatingFileHandler
import os

log_level_info = {
    "logging.DEBUG": logging.DEBUG,
    "logging.INFO": logging.INFO,
    "logging.WARNING": logging.WARNING,
    "logging.ERROR": logging.ERROR,
}

if __name__ == "__main__":
    config = configparser.ConfigParser()
    # Look for config.ini in project root, then in config/ subdirectory
    project_root = os.path.dirname(os.path.dirname(__file__))
    config_path = os.path.join(project_root, "config.ini")
    if not os.path.exists(config_path):
        config_path = os.path.join(project_root, "config", "config.ini.dist")
    with open(config_path) as fh:
        config.read_file(fh)
    fh.close()

    if "DISCORD" not in config or ("token" not in config["DISCORD"]):
        raise ValueError("Discord config not found, check config.ini!")

    # Check if logging is enabled
    logging_enabled = config.getboolean("DEFAULT", "ENABLE_LOGGING", fallback=True)

    if logging_enabled:
        # Ensure logs directory exists
        project_root = os.path.dirname(os.path.dirname(__file__))
        logs_dir = os.path.join(project_root, "logs")
        os.makedirs(logs_dir, exist_ok=True)

        logging.basicConfig(
            format="%(asctime)s [%(filename)s:%(lineno)s - %(funcName)20s() ] [%(levelname)s] %(message)s",
            level=log_level_info.get(config["DEFAULT"]["LOG_LEVEL"], logging.ERROR),
            encoding="utf-8",
            handlers=[
                logging.StreamHandler(),
                TimedRotatingFileHandler(
                    os.path.join(logs_dir, "output.log"),
                    when="d",
                    interval=1,
                    backupCount=5,
                    encoding="utf-8",
                ),
            ],
        )
    else:
        # Minimal logging - only critical errors to console
        logging.basicConfig(
            format="%(asctime)s [%(levelname)s] %(message)s",
            level=logging.CRITICAL,
            handlers=[logging.StreamHandler()],
        )

    intents = discord.Intents.default()
    intents.message_content = True
    client = MyClient(intents=intents, logging_enabled=logging_enabled)
    client.run(config["DISCORD"]["token"])
