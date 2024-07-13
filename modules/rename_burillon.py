#!/usr/bin/python3

import nextcord
from nextcord.ext import commands
import os
import logging
from datetime import datetime, timedelta, timezone
import humanize
import asyncio
import pytz

from openai import OpenAI
client = OpenAI(api_key=os.getenv('OPENAI_API_TOKEN'))

# Configuration du logger
logger = logging.getLogger('bot.rename_burillon')

# Récupérer l'ID de Burillon
burillon_id_str = os.getenv('BURILLON_ID', '')

class RenameBurillon(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        # Check if the bot is iBot-Modo
        if self.bot.user.id != 1153257783093903442:
            return

        # start the task
        await self.bot.loop.create_task(self.rename_burillon())

    async def ask_gpt(self):
        system_message = {
            "role": "system",
            "content": (
                "Tu es un membre actif de la communauté et tu participes à la recherche de pseudos loufoques pour un utilisateur dont le pseudonyme est Burillon. "
                "Tu dois trouver un nouveau pseudonyme pour cet utilisateur. Il doit être amusant et original. Il peut être un jeu de mots se basant sur son pseudo. "
                "Les pseudonymes types 'Bouillon', 'Brouillon' sont acceptés mais tu dois essayer de trouver quelque chose de plus original. "
                "Tu ne dois jamais répéter un pseudonyme déjà proposé. "
            )
        }

        user_message = {"role":"user", "content": "Trouve moi le pseudonyme parfait pour Burillon."}

        try:
            reponse = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[system_message, user_message],
                max_tokens=1500
            )

            return reponse
        except Exception as e:
            logger.error(f"GPT est PT: {e}", exec_info=True)

    async def rename_burillon(self):
        # Check 8am in France
        now = datetime.now(pytz.timezone('Europe/Paris'))
        if now.hour != 8:
            return
        
        # Get Guild
        guild = self.bot.get_guild(285029536016367616)
        
        # Get member Burillon from ID
        burillon = guild.get_member(int(burillon_id_str))
        if burillon is None:
            logger.error("Impossible de trouver l'utilisateur Burillon.")
            return
        
        # Generate new nickname from ChatGPT
        new_nickname = await self.ask_gpt()
        burillon.edit(nick=new_nickname.choices[0].message.content)

def setup(bot):
    bot.add_cog(RenameBurillon(bot))

