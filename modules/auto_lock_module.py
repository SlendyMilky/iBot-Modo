import nextcord
from nextcord.ext import commands
import os
import logging
from datetime import datetime, timedelta, timezone
import humanize
import asyncio

# Configuration du logger
logger = logging.getLogger('bot.auto_lock_module')
#logging.basicConfig(level=logging.INFO)

# Variables d'environnement pour la configuration
inactive_days = os.getenv('INACTIVE_DAYS', '15')
auto_lock_forum_ids_str = os.getenv('AUTO_LOCK_FORUM_IDS', '')
info_channel_id_str = os.getenv('INFO_CHANNEL_ID', '')
exempt_thread_ids_str = os.getenv('EXEMPT_THREAD_IDS', '')

# Configuration des IDs de forums et du canal info
try:
    inactive_days = int(inactive_days)
except ValueError:
    logger.error("La variable d'environnement 'INACTIVE_DAYS' contient une valeur invalide.")
    inactive_days = 15

if auto_lock_forum_ids_str:
    try:
        auto_lock_forum_ids = list(map(int, auto_lock_forum_ids_str.split(',')))
    except ValueError:
        logger.error("La variable d'environnement 'AUTO_LOCK_FORUM_IDS' contient des valeurs invalides.")
        auto_lock_forum_ids = []
else:
    auto_lock_forum_ids = []
    logger.warning("La variable d'environnement 'AUTO_LOCK_FORUM_IDS' est vide ou non définie.")

if info_channel_id_str:
    try:
        info_channel_id = int(info_channel_id_str)
    except ValueError:
        logger.error("La variable d'environnement 'INFO_CHANNEL_ID' contient une valeur invalide.")
        info_channel_id = None
else:
    info_channel_id = None
    logger.warning("La variable d'environnement 'INFO_CHANNEL_ID' est vide ou non définie.")

if exempt_thread_ids_str:
    try:
        exempt_thread_ids = list(map(int, exempt_thread_ids_str.split(',')))
    except ValueError:
        logger.error("La variable d'environnement 'EXEMPT_THREAD_IDS' contient des valeurs invalides.")
        exempt_thread_ids = []
else:
    exempt_thread_ids = []
    logger.warning("La variable d'environnement 'EXEMPT_THREAD_IDS' est vide ou non définie.")

class AutoLockThreads(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.loop.create_task(self.lock_inactive_threads())

    @commands.Cog.listener()
    async def on_thread_update(self, before, after):
        # Vérifier si le thread est exempté
        if after.id in exempt_thread_ids:
            return

        # Vérifier les tags modifiés
        before_tags = set(tag.id for tag in before.applied_tags)
        after_tags = set(tag.id for tag in after.applied_tags)

        if before_tags != after_tags:
            resolved_tag = next((tag for tag in after.applied_tags if tag.name == 'Résolu'), None)
            if resolved_tag and not after.name.startswith("✅ - "):
                new_name = f"✅ - {after.name}"
                await after.edit(name=new_name[:100], applied_tags=[resolved_tag])
                logger.info(f"Thread renamed to indicate resolution: {new_name}")

    async def lock_inactive_threads(self):
        while True:
            for forum_id in auto_lock_forum_ids:
                channel = self.bot.get_channel(forum_id)
                if not channel:
                    logger.error(f"Cannot find channel with ID {forum_id}")
                    continue

                info_channel = self.bot.get_channel(info_channel_id) if info_channel_id else None

                for thread in channel.threads:
                    # Vérifier si le thread est exempté
                    if thread.id in exempt_thread_ids:
                        continue

                    if not thread.archived:  # Only checks threads that are not archived
                        last_message_id = thread.last_message_id
                        if last_message_id is not None:
                            try:
                                last_message = await thread.fetch_message(last_message_id)
                            except nextcord.NotFound:
                                continue  # Skip to next iteration if message is not found

                            if datetime.now(timezone.utc) - last_message.created_at > timedelta(days=inactive_days):
                                new_name = f"🔒 - {thread.name}"
                                await thread.edit(locked=True, name=new_name[:100])  # Lock the thread and add "🔒 - " to its name
                                logger.info(f"Thread locked and name changed in {channel.name}")
                                await thread.send(f"Ce thread est fermé automatiquement après {inactive_days} jours d'inactivité.")
                                
                                # Add "Vérou-Auto" tag and archive the thread
                                auto_lock_tag = next((tag for tag in channel.available_tags if tag.name == 'Vérou-Auto'), None)
                                if auto_lock_tag:
                                    current_tags = thread.applied_tags[:]
                                    current_tags.append(auto_lock_tag)
                                    await thread.edit(applied_tags=current_tags)
                                await thread.edit(archived=True)  # Close the thread
                                logger.info(f"Thread closed in {channel.name}")

                                if info_channel:
                                    # Fetch applied tags for the thread
                                    tags = thread.applied_tags
                                    tag_names = ", ".join(tag.name for tag in tags) if tags else "Aucun tag"

                                    # Compile stats and send embed in info channel
                                    user_dict = {}
                                    async for m in thread.history(limit=None):
                                        user_dict[m.author.name] = user_dict.get(m.author.name, 0) + 1

                                    owner_name = thread.owner.name if thread.owner else "Inconnu"
                                    owner_id = thread.owner.id if thread.owner else "Inconnu"

                                    thread_opened = thread.created_at.strftime("%d.%m.%Y - %H:%M")
                                    thread_closed = datetime.now(timezone.utc).strftime("%d.%m.%Y - %H:%M")
                                    duration = humanize.naturaldelta(datetime.now(timezone.utc) - thread.created_at)

                                    data = {
                                        "Ouvert": thread_opened,
                                        "Fermé": thread_closed,
                                        "Durée": duration,
                                        "Créateur": f'{owner_name} (ID: {owner_id})',
                                        "Nombre de participants": len(user_dict.keys()),
                                        "Nombre de messages": sum(user_dict.values()),
                                        "Participants": "\n".join([f"{k} - {v} messages" for k, v in user_dict.items()]),
                                        "Tags": tag_names,
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

                                    await asyncio.sleep(30)  # Petite pause entre chaque thread
            await asyncio.sleep(24*60*60)  # Wait a day before re-executing the loop

def setup(bot):
    bot.add_cog(AutoLockThreads(bot))
