import pathlib
import os
import logging

import discord

import classified
from logging.config import dictConfig

Token = classified.TopSecretToken
BASE_DIR = pathlib.Path(__file__).parent
CMDS_DIR = BASE_DIR / "cmds"
COGS_DIR = BASE_DIR / "cogs"
GUILDS_ID = discord.Object(id=int(classified.GUILD))

LOGGING_CONFIG = {
    "version": 1,
    "disabled_existing_loggers": False,
    "formatters":{
        "verbose":{
            "format": "%(levelname)-10s - %(asctime)s - %(module)-15s : %(message)s"
        },
        "standard":{
            "format": "%(levelname)-10s - %(name)-15s : %(message)s"
        }
    },
    "handlers":{
        "console": {
            'level': "DEBUG",
            'class': "logging.StreamHandler",
            'formatter': "standard"
        },
        "console2": {
            'level': "WARNING",
            'class': "logging.StreamHandler",
            'formatter': "standard"
        },
        "file": {
            'level': "INFO",
            'class': "logging.FileHandler",
            'filename': "logs/infos.log",
            'mode': "w",
            'formatter': 'verbose'
        }

    },
    "loggers":{
        "bot": {
            'handlers':['console'],
            "level": "INFO",
            "propagate": False
        },
        "discord": {
            'handlers':['console2', "file"],
            "level": "INFO",
            "propagate": False
        },
    }
}

dictConfig(LOGGING_CONFIG)
