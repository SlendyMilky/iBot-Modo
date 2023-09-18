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

# Configure logging
logging.basicConfig(level=logging.DEBUG if DEBUG else logging.INFO,
                    format='%(asctime)s %(message)s - %(levelname)s',
                    datefmt='%m/%d/%Y %I:%M:%S %p',
                    handlers=[logging.StreamHandler(),
                              logging.FileHandler("modo_log.txt")])

# Instantiate the bot
bot = commands.Bot(command_prefix="§", intents=nextcord.Intents.all())

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
    logging.info(message.content)

    if message.author == bot.user:
        logging.info("Message sent by the bot. Skipping moderation...")
        return
    elif message.content.strip():
        if message.channel.category is not None and message.channel.category.name.startswith(("🟢", "🔵", "🟡")):
            logging.info(f"Sending message for moderation: {message.content}")
            response = openai.Moderation.create(input=message.content) 
            output = response['results'][0]
        
            flagged_categories = [category for category, flagged in output['categories'].items() if flagged]

            if flagged_categories:
                # Create a link to the message
                message_link = f"https://discord.com/channels/{message.guild.id}/{message.channel.id}/{message.id}"

                mod_channel = bot.get_channel(1153256725525315656)
                embed = nextcord.Embed(title="Message problématique", url=message_link, color=0xff0000)
                embed.timestamp = message.created_at

                embed.add_field(name="Auteur", value=message.author.name, inline=True)
                embed.add_field(name="ID", value=message.author.id, inline=True)
                embed.add_field(name="Catégories de modération", value=', '.join(flagged_categories), inline=True)
                embed.add_field(name="Message", value=message.content, inline=False)

                embed.set_footer(icon_url=message.author.avatar.url, text=message.author.name)

                logging.warning(f"Flagged message: {message.content}, Flagged categories: {', '.join(flagged_categories)}")
                await mod_channel.send(embed=embed)
                
        else:
            logging.info("Received an empty message. Skipping moderation...")
    else:
        logging.info("Message doesn't match category. Skipping moderation...")

# Run the bot
bot.run(BOT_TOKEN)