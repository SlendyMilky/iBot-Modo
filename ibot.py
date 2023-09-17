import os
import re
import logging
import datetime
import openai
import nextcord
from nextcord.ext import commands

FORUM_CHANNEL_NAME = os.getenv('FORUM_CHANNEL_NAME')
BOT_TOKEN = os.getenv('BOT_TOKEN')
ASK_GPT_ROLES_ALLOWED = os.getenv('ASK_GPT_ROLES_ALLOWED')
ASK_GPT4_ROLES_ALLOWED = os.getenv('ASK_GPT4_ROLES_ALLOWED')

openai.api_key = os.getenv('OPENAI_API_KEY')

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(message)s',
                    datefmt='%m/%d/%Y %I:%M:%S %p',
                    handlers=[logging.StreamHandler(),
                              logging.FileHandler("thread_log.txt")])

bot = commands.Bot(command_prefix="§")

@bot.event
async def on_ready():
    print(f"We have logged in as {bot.user}")
    await bot.change_presence(activity=nextcord.Game(name=f"t'observer..."))



bot.run(BOT_TOKEN)