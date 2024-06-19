#!/usr/bin/python3

import os
import logging
from datetime import datetime

import nextcord
from nextcord.ext import commands
import asyncio

# Configuration du logger
logger = logging.getLogger('bot.forum_no_delete_module')

# Variables d'environnement pour la configuration
monitor_forum_ids_str = os.getenv('MONITOR_FORUM_IDS', '')
info_channel_id_str = os.getenv('INFO_CHANNEL_ID', '')

# Configuration des IDs de forums et du canal info
if monitor_forum_ids_str:
    try:
        monitor_forum_ids = list(map(int, monitor_forum_ids_str.split(',')))
    except ValueError:
        logger.error("La variable d'environnement 'MONITOR_FORUM_IDS' contient des valeurs invalides.")
        monitor_forum_ids = []
else:
    monitor_forum_ids = []
    logger.warning("La variable d'environnement 'MONITOR_FORUM_IDS' est vide ou non définie.")

if info_channel_id_str:
    try:
        info_channel_id = int(info_channel_id_str)
    except ValueError:
        logger.error("La variable d'environnement 'INFO_CHANNEL_ID' contient une valeur invalide.")
        info_channel_id = None
else:
    info_channel_id = None
    logger.warning("La variable d'environnement 'INFO_CHANNEL_ID' est vide ou non définie.")

class ForumNoDelete(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.warning_sent = set()
        self.lock = asyncio.Lock()

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info('Module is ready.')

    @commands.Cog.listener()
    async def on_thread_create(self, thread):
        logger.debug(f"Thread créé: {thread.name}")
        if thread.parent_id in monitor_forum_ids:
            try:
                await thread.join()
                logger.info(f"Bot a rejoint le thread {thread.name} dans le forum {thread.parent.name}")
            except Exception as e:
                logger.error(f"Impossible de rejoindre le thread {thread.name}: {e}")

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload):
        async with self.lock:  # Using a lock to avoid race conditions
            try:
                logger.debug(f"Message supprimé: ID {payload.message_id}")
                
                if not (payload.guild_id and payload.channel_id):
                    logger.warning("Informations de guilde ou de canal manquantes dans le payload de suppression de message.")
                    return

                guild = self.bot.get_guild(payload.guild_id)
                if not guild:
                    logger.error(f"Impossible de récupérer la guilde avec ID {payload.guild_id}")
                    return

                channel = None
                try:
                    channel = await self.bot.fetch_channel(payload.channel_id)
                except Exception as e:
                    logger.error(f"Impossible de récupérer le canal avec ID {payload.channel_id} en utilisant fetch_channel : {e}")
                    return
                
                if not isinstance(channel, nextcord.Thread):
                    logger.debug("Le canal n'est pas un thread, ignoré.")
                    return

                if payload.message_id != channel.id:
                    logger.debug("Le message supprimé n'est pas le message initial du thread, ignoré.")
                    return

                if channel.id in self.warning_sent:
                    logger.debug("Avertissement déjà envoyé pour ce thread, ignoré.")
                    return

                info_channel = self.bot.get_channel(info_channel_id) if info_channel_id else None
                if not info_channel:
                    logger.error("Salon d'information introuvable.")
                    return

                try:
                    logger.info(f"Info Channel retrieved: {info_channel.name} (ID: {info_channel.id})")
                    logger.info(f"Channel Type: {type(info_channel)} - Permissions to Send Messages: {info_channel.permissions_for(guild.me).send_messages}, Permissions to Embed Links: {info_channel.permissions_for(guild.me).embed_links}")
                except Exception as e:
                    logger.error(f"Erreur en vérifiant les informations du canal d'info: {e}")
                    return

                if not info_channel.permissions_for(guild.me).send_messages:
                    logger.error("Le bot n'a pas la permission d'envoyer des messages dans ce salon.")
                    return

                if not info_channel.permissions_for(guild.me).embed_links:
                    logger.error("Le bot n'a pas la permission d'envoyer des embeds dans ce salon.")
                    return

                deleter = None
                try:
                    async for entry in guild.audit_logs(limit=5, action=nextcord.AuditLogAction.message_delete, oldest_first=False):
                        if entry.target.id == payload.message_id and (datetime.utcnow() - entry.created_at).total_seconds() < 60:
                            deleter = entry.user
                            break
                except Exception as e:
                    logger.error(f"Erreur lors de la lecture des logs d'audit: {e}")

                deleter_info = f"Message supprimé par : {deleter.mention} (ID: {deleter.id})" if deleter else "Auteur de la suppression introuvable."

                description = f"Le message de base du thread `{channel.name}` a été supprimé par {deleter_info if deleter else 'inconnu'}."
                embed = nextcord.Embed(
                    title=f"🚫 Message de thread supprimé : {channel.name}",
                    description=description,
                    color=0xFF0000,
                    url=f"https://discord.com/channels/{guild.id}/{channel.id}"
                )
                
                if not info_channel.permissions_for(guild.me).send_messages:
                    logger.error("Le bot n'a toujours pas la permission d'envoyer des messages dans ce salon à ce stade.")
                    return

                if not info_channel.permissions_for(guild.me).embed_links:
                    logger.error("Le bot n'a toujours pas la permission d'envoyer des embeds dans ce salon à ce stade.")
                    return
                
                try:
                    await info_channel.send(embed=embed)
                    logger.info(f"Embed envoyé dans le salon d'information pour le thread {channel.name}")
                except Exception as e:
                    logger.error(f"Impossible d'envoyer l'embed dans le salon d'infos: {e}")

                try:
                    warning_message = f"⚠️ Le message de base de ce thread a été supprimé. Cela n'est pas autorisé."
                    await channel.send(warning_message)
                    self.warning_sent.add(channel.id)
                    logger.info(f"Avertissement envoyé au thread {channel.name} concernant la suppression du message de base.")
                except Exception as e:
                    logger.error(f"Impossible d'envoyer l'avertissement dans le thread: {e}")

            except Exception as general_exception:
                logger.error(f"Une erreur inattendue a été rencontrée: {general_exception}")

def setup(bot):
    bot.add_cog(ForumNoDelete(bot))
