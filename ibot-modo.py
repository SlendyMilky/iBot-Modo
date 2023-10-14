import os
import logging
import openai
import nextcord
import unicodedata
from nextcord.ext import commands
from asyncio import sleep
from datetime import datetime, timedelta, timezone
import asyncio
from nextcord.errors import NotFound

# Set up environment variables
BOT_TOKEN = os.getenv('BOT_TOKEN')
openai.api_key = os.getenv('OPENAI_API_KEY')
DEBUG = os.getenv('DEBUG') == 'true'
PSEUDO_CHANNEL_ID = os.getenv('PSEUDO_CHANNEL_ID')


# Add custom logging level
OPENAI_LEVEL_NUM = 25
logging.addLevelName(OPENAI_LEVEL_NUM, "OPENAI")

# Logging ==========================================
logging.basicConfig(level=logging.DEBUG if DEBUG else logging.INFO,
                    format='%(asctime)s %(message)s - %(levelname)s',
                    datefmt='%m/%d/%Y %I:%M:%S %p',
                    handlers=[logging.StreamHandler(),
                              logging.FileHandler("modo_log.txt")])
# Logging ==========================================





# Instantiate the bot ==========================================
bot = commands.Bot(command_prefix="§", intents=nextcord.Intents.all())

if DEBUG:
    @bot.event
    async def on_socket_raw_receive(msg):
        logging.debug(msg)


@bot.event
async def on_ready():
    logging.info(f"We have logged in as {bot.user}")
    await bot.change_presence(activity=nextcord.Game(name=f"t'observer..."))
# Instantiate the bot ==========================================





# Message flag ==========================================
@bot.event
async def on_message(message):
    logging.info(message.content)

    if message.author == bot.user:
        logging.info("Message sent by the bot. Skipping moderation...")
        return
    elif message.content.strip():
        await flag_message(message, is_edited=False)
    else:
        logging.info("Received an empty message. Skipping moderation...")

@bot.event
async def on_message_edit(before, after):
    if after.author == bot.user:
        logging.info("Message edited by the bot. Skipping moderation...")
        return
    elif after.content.strip() != before.content.strip():
        await flag_message(after, is_edited=True, original_content=before.content)

async def flag_message(message, is_edited=False, original_content=""):
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

            embed.add_field(name="✏️ Auteur", value=message.author.name, inline=True)
            embed.add_field(name="🆔", value=message.author.id, inline=True)
            embed.add_field(name="🛡️ Catégories de modération", value=', '.join(flagged_categories), inline=True)

            embed.add_field(name="💬 Message", value=message.content, inline=True)

            if is_edited:
                embed.add_field(name="💬 Message originel", value=original_content, inline=True)
                embed.add_field(name="🔧", value="Message édité", inline=False)

            

            embed.set_thumbnail(url=message.author.avatar.url)

            logging.warning(f"Flagged message: {message.content}, Flagged categories: {', '.join(flagged_categories)}")
            await mod_channel.send(embed=embed)
    else:
        logging.info("Message doesn't match category. Skipping moderation...")
# Message flag ==========================================





# Pseudo flag ==========================================
@bot.event
async def on_member_update(before, after):

    # Check if the member's nickname has changed and if they are not in an exempt role
    pseudo_exempt_roles = [int(id) for id in os.getenv('PSEUDO_NO_MODO').split(',')]

    if before.nick != after.nick and not any(role.id in pseudo_exempt_roles for role in after.roles):

        # If the nickname starts with a non-letter, tries to insert special characters or is not normalized, change it
        if after.nick and not after.nick[0].isalpha() or not after.nick.isalnum() or not unicodedata.is_normalized('NFKC', after.nick):
            async with before.typing():
               # try suggestion with gpt-3.5
                response = openai.ChatCompletion.create(
                   model="gpt-4",
                messages=[
                    {"role": "system", "content": "Ton unique objectif est de proposer un pseudonyme en utilisant uniquement des lettres et des chiffres. Chaque fois que tu reçois un pseudonyme, tu ne dois répondre qu'avec le pseudonyme proposé et absolument rien d'autre."},
                    {"role": "user", "content": f"\'{after.nick}\'"}
                ]
            )
            # generate a normalized pseudonym with gpt-3.5
            new_nick_suggestion = response['choices'][0]['message']['content'].strip()
        
            normalized_nick = unicodedata.normalize('NFKC', new_nick_suggestion)
            allowable_nick = ''.join(ch for ch in normalized_nick if ch.isalnum() or ch.isspace() or ch in ["@", "#", "$", "_", "-", "."])
        
            truncated_nick = allowable_nick[:32] # Makes sure the nickname is not longer than 32 characters
            new_nick = truncated_nick if truncated_nick else None   # If all characters were special, reset nickname to None (the user's username)
        
            await after.edit(nick=new_nick)

            
            # Send edited nickname to moderation channel
            pseudo_mod_channel = bot.get_channel(1162440867513114735)
            embed = nextcord.Embed(title="Modification de pseudo automatique", color=0xff0000)
            embed.timestamp = datetime.now(timezone.utc)

            embed.add_field(name="✏️ Utilisateur", value=after.name, inline=True)
            embed.add_field(name="🆔", value=after.id, inline=True)
            embed.add_field(name="🔧 Pseudo avant modification", value=before.nick, inline=True)
            embed.add_field(name="🔧 Pseudo après modification", value=after.nick, inline=True)
            
            embed.set_thumbnail(url=after.avatar.url)
            await pseudo_mod_channel.send(embed=embed)
        
            logging.info(f'Pseudo de {before.nick} a été modifié en {after.nick}')
# Pseudo flag ==========================================







# Auto-Lock old thread in 💸┤offres-des-abonnés ==========================================
async def lock_inactive_threads():
    channel_id = 1019934267406549053
    channel = bot.get_channel(channel_id)

    for thread in channel.threads:
        if not thread.archived:  # Only checks threads that are not archived
            last_message_id = thread.last_message_id
            if last_message_id is not None:
                try:
                    last_message = await thread.fetch_message(last_message_id)
                except NotFound:
                    continue  # Skip to next iteration if message is not found
                
                if datetime.now(timezone.utc) - last_message.created_at > timedelta(days=15):
                    await thread.edit(locked=True)  # Lock the thread
                    logging.info(f"Thread locked in 💸┤offres-des-abonnés")
    await asyncio.sleep(24*60*60)  # Wait a day before re-executing the loop

@bot.event
async def on_ready():
    bot.loop.create_task(lock_inactive_threads())
# Auto-Lock old thread in 💸┤offres-des-abonnés ==========================================





# Auto-Lock old thread in 🆘┤aide ==========================================
async def lock_inactive_threads():
    channel_id = 1019928572103770132
    channel = bot.get_channel(channel_id)

    for thread in channel.threads:
        if not thread.archived:  # Only checks threads that are not archived
            last_message_id = thread.last_message_id
            if last_message_id is not None:
                try:
                    last_message = await thread.fetch_message(last_message_id)
                except NotFound:
                    continue  # Skip to next iteration if message is not found
                
                if datetime.now(timezone.utc) - last_message.created_at > timedelta(days=15):
                    sleep 
                    await thread.edit(locked=True)  # Lock the thread
                    logging.info(f"Thread locked in 🆘┤aide")
                    await sleep(30)
    await asyncio.sleep(24*60*60)  # Wait a day before re-executing the loop

@bot.event
async def on_ready():
    bot.loop.create_task(lock_inactive_threads())
# Auto-Lock old thread in 🆘┤aide ==========================================






# Run the bot
bot.run(BOT_TOKEN)