import os
import logging
import openai
import nextcord
from nextcord.ext import commands

# Set up environment variables
BOT_TOKEN = os.getenv('BOT_TOKEN')
openai.api_key = os.getenv('OPENAI_API_KEY')
DEBUG = os.getenv('DEBUG') == 'true' 

# Add custom logging level
OPENAI_LEVEL_NUM = 25
logging.addLevelName(OPENAI_LEVEL_NUM, "OPENAI")

def openai(self, message, *args, **kws):
    if self.isEnabledFor(OPENAI_LEVEL_NUM):
        self._log(OPENAI_LEVEL_NUM, message, args, **kws) 

logging.Logger.openai = openai

# Configure logging
logging.basicConfig(level=logging.DEBUG if DEBUG else logging.INFO,
                    format='%(asctime)s %(message)s - %(levelname)s',
                    datefmt='%m/%d/%Y %I:%M:%S %p',
                    handlers=[logging.StreamHandler(),
                              logging.FileHandler("modo_log.txt")])

# Instantiate the bot
bot = commands.Bot(command_prefix="§")

if DEBUG:
    @bot.event
    async def on_socket_raw_receive(msg):
        logging.debug(msg)

@bot.event
async def on_ready():
    logging.info(f"We have logged in as {bot.user}")
    await bot.change_presence(activity=nextcord.Game(name=f"t'observer..."))

@bot.event
async def on_message(message):
    logging.info(f"Raw message content: {message.content}")
    logging.info(f"System message content: {message.system_content}")
    for embed in message.embeds:
        logging.info(f"Embed: {embed.to_dict()}")
    for attachment in message.attachments:
        logging.info(f"Attachment: {attachment.url}")
    
    if message.author == bot.user:
        logging.info("Message sent by the bot. Skipping moderation...")
        return
    if message.channel.category is not None and message.channel.category.name[0] in ["🟢", "🔵", "🟡"]:
        if message.content.strip():
            logging.info(f"Sending message for moderation: {message.content}")
            response = openai.Moderation.create(input=message.content) 
            output = response['results'][0]

            flagged_categories = [category for category, flagged in output['categories'].items() if flagged]

            if flagged_categories:
                mod_channel = bot.get_channel(1153256725525315656)
                embed = nextcord.Embed(title="Flagged Message", color=0xff0000)
                embed.add_field(name="Author", value=message.author.name, inline=False)
                embed.add_field(name="Message", value=message.content, inline=False)
                embed.add_field(name="Flagged Categories", value=', '.join(flagged_categories), inline=False)
                logging.warning(f"Flagged message: {message.content}, Flagged categories: {', '.join(flagged_categories)}")
                await mod_channel.send(embed=embed)

        else:
            logging.info("Received an empty message. Skipping moderation...")
    else:
        logging.info("Message doesn't match category. Skipping moderation...")


# Run the bot
bot.run(BOT_TOKEN)
