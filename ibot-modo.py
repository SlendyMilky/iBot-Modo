import os
import logging
import openai
import nextcord
import unicodedata
import humanize
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






# Auto-Lock old thread in 💸┤offres-des-abonnés ==========================================
async def lock_inactive_threads():
    channel_id = 1019934267406549053
    info_channel_id = 1169746292205944873
    channel = bot.get_channel(channel_id)
    info_channel = bot.get_channel(info_channel_id)

    for thread in channel.threads:
        if not thread.archived:  # Only checks threads that are not archived
            last_message_id = thread.last_message_id
            if last_message_id is not None:
                try:
                    last_message = await thread.fetch_message(last_message_id)
                except NotFound:
                    continue  # Skip to next iteration if message is not found
                
                if datetime.now(timezone.utc) - last_message.created_at > timedelta(days=11):
                    sleep 
                    new_name = f"🔒 - {thread.name}"
                    await thread.edit(locked=True, name=new_name[:100])  # Lock the thread and add "🔒 - " to its name
                    logging.info(f"Thread locked and name changed in 💸┤offres-des-abonnés")
                    await thread.send("Ce thread est fermé automatiquement après 10 jours d'inactivité.")
                    await thread.edit(archived=True)  # Close the thread
                    logging.info(f"Thread closed in 💸┤offres-des-abonnés")
                    
                    # Compile stats and send embed in info channel
                    user_dict = {}
                    for m in await thread.history(limit=None).flatten():
                        if m.author.name in user_dict:
                            user_dict[m.author.name] += 1
                        else:
                            user_dict[m.author.name] = 1

                    thread_opened = thread.created_at.strftime("%d.%m.%Y - %H:%M")
                    thread_closed = datetime.now(timezone.utc).strftime("%d.%m.%Y - %H:%M")
                    duration = humanize.naturaldelta(datetime.now(timezone.utc) - thread.created_at)

                    data = {
                        "Ouvert": thread_opened,
                        "Fermé": thread_closed,
                        "Durée": duration,
                        "Créateur": f'{thread.owner.name} (ID: {thread.owner.id})',
                        "Nombre de participants": len(user_dict.keys()),
                        "Nombre de messages": sum(user_dict.values()),
                        "Participants": "\n".join([f"{k} - {v} messages" for k, v in user_dict.items()]),
                        "Tag": thread.name,
                    }

                    embed = nextcord.Embed(
                        title="🔒 - Statistiques du thread `{}`".format(thread.name), 
                        description="Voici les statistiques pour le thread fermé.", color=0xFFFF00
                    )
                    embed.url = f"https://discord.com/channels/{channel.guild.id}/{thread.id}"
                    
                    for k, v in data.items():
                        embed.add_field(name=k, value=v, inline=True)

                    embed.timestamp = datetime.utcnow()
                    await info_channel.send(embed=embed)

                    await sleep(30)
    await asyncio.sleep(24*60*60)  # Wait a day before re-executing the loop
            
@bot.event
async def on_ready():
    bot.loop.create_task(lock_inactive_threads())
# Auto-Lock old thread in 💸┤offres-des-abonnés ==========================================





# Auto-Lock old thread in 🆘┤aide ==========================================
async def lock_inactive_threads():
    channel_id = 1019928572103770132
    info_channel_id = 1169746176694825022
    channel = bot.get_channel(channel_id)
    info_channel = bot.get_channel(info_channel_id)

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
                    new_name = f"🔒 - {thread.name}"
                    await thread.edit(locked=True, name=new_name[:100])  # Lock the thread and add "🔒 - " to its name
                    logging.info(f"Thread locked and name changed in 🆘┤aide")
                    await thread.send("Ce thread est fermé automatiquement après 14 jours d'inactivité.")
                    await thread.edit(archived=True)  # Close the thread
                    logging.info(f"Thread closed in 🆘┤aide")
                    
                    # Compile stats and send embed in info channel
                    user_dict = {}
                    for m in await thread.history(limit=None).flatten():
                        if m.author.name in user_dict:
                            user_dict[m.author.name] += 1
                        else:
                            user_dict[m.author.name] = 1

                    thread_opened = thread.created_at.strftime("%d.%m.%Y - %H:%M")
                    thread_closed = datetime.now(timezone.utc).strftime("%d.%m.%Y - %H:%M")
                    duration = humanize.naturaldelta(datetime.now(timezone.utc) - thread.created_at)

                    data = {
                        "Ouvert": thread_opened,
                        "Fermé": thread_closed,
                        "Durée": duration,
                        "Créateur": f'{thread.owner.name} (ID: {thread.owner.id})',
                        "Nombre de participants": len(user_dict.keys()),
                        "Nombre de messages": sum(user_dict.values()),
                        "Participants": "\n".join([f"{k} - {v} messages" for k, v in user_dict.items()]),
                        "Tag": thread.name,
                    }

                    embed = nextcord.Embed(
                        title="🔒 - Statistiques du thread `{}`".format(thread.name), 
                        description="Voici les statistiques pour le thread fermé.", color=0xFFFF00
                    )
                    embed.url = f"https://discord.com/channels/{channel.guild.id}/{thread.id}"
                    
                    for k, v in data.items():
                        embed.add_field(name=k, value=v, inline=True)

                    embed.timestamp = datetime.utcnow()
                    await info_channel.send(embed=embed)

                    await sleep(30)
    await asyncio.sleep(24*60*60)  # Wait a day before re-executing the loop
            
@bot.event
async def on_ready():
    bot.loop.create_task(lock_inactive_threads())
# Auto-Lock old thread in 🆘┤aide ==========================================








# Run the bot
bot.run(BOT_TOKEN)