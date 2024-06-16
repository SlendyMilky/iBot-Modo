import nextcord
from nextcord import SlashOption, Interaction
from nextcord.ext import commands
from nextcord.ui import View, Button
import os
import json
import logging
import requests

# Configuration du logger
logger = logging.getLogger('bot.sos_module')

# Variables d'environnement pour la configuration
moderator_db_channel_id = int(os.getenv('MODERATOR_DB_CHANNEL_ID', 0))
telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
telegram_chat_ids = os.getenv('TELEGRAM_CHAT_IDS', '').split(',')

# Chemin vers le fichier JSON pour la base de données locale
db_file_path = os.path.join('database', 'moderator_db.json')

# Assurez-vous que le dossier 'database' existe
os.makedirs('database', exist_ok=True)

# Initialise la liste des modérateurs et des utilisateurs Telegram
moderator_db = []
telegram_db = {}


class ModeratorDBView(View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @nextcord.ui.button(label="Ajouter", style=nextcord.ButtonStyle.green)
    async def add_moderator(self, button: Button, interaction: Interaction):
        user_id = interaction.user.id
        if user_id not in [mod['id'] for mod in moderator_db]:
            moderator_db.append({"id": user_id, "name": interaction.user.name})
            self.cog.save_data()
            await self.cog.update_moderator_db_message(interaction.channel)
            # Supprime le message de confirmation
            # await interaction.response.send_message("Vous avez été ajouté à la liste des modérateurs.")
        else:
            # Supprime le message de confirmation
            # await interaction.response.send_message("Vous êtes déjà dans la liste des modérateurs.")
            pass

    @nextcord.ui.button(label="Retirer", style=nextcord.ButtonStyle.red)
    async def remove_moderator(self, button: Button, interaction: Interaction):
        user_id = interaction.user.id
        if user_id in [mod['id'] for mod in moderator_db]:
            moderator_db[:] = [mod for mod in moderator_db if mod['id'] != user_id]
            self.cog.save_data()
            await self.cog.update_moderator_db_message(interaction.channel)
            # Supprime le message de confirmation
            # await interaction.response.send_message("Vous avez été retiré de la liste des modérateurs.")
        else:
            # Supprime le message de confirmation
            # await interaction.response.send_message("Vous n'êtes pas dans la liste des modérateurs.")
            pass


class SOSCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.moderator_db_message_id = None  # Initialize the attribute
        self.load_data()

    def load_data(self):
        global moderator_db
        global telegram_db
        if os.path.exists(db_file_path):
            try:
                with open(db_file_path, 'r') as file:
                    if os.stat(db_file_path).st_size == 0:
                        data = {}
                    else:
                        data = json.load(file)
                    moderator_db = data.get('moderators', [])
                    telegram_db = data.get('telegram', {})
                    self.moderator_db_message_id = data.get('moderator_db_message_id', None)
            except json.JSONDecodeError:
                data = {}
                moderator_db = []
                telegram_db = {}
                self.moderator_db_message_id = None
                self.save_data()
        else:
            self.save_data()

    def save_data(self):
        with open(db_file_path, 'w') as file:
            json.dump({
                'moderators': moderator_db, 
                'telegram': telegram_db, 
                'moderator_db_message_id': self.moderator_db_message_id
            }, file)

    async def fetch_moderators(self):
        global moderator_db
        global telegram_db
        if not moderator_db_channel_id:
            logger.error("La variable d'environnement 'MODERATOR_DB_CHANNEL_ID' est vide ou non définie.")
            return
        channel = self.bot.get_channel(moderator_db_channel_id)
        if not channel:
            logger.warning(f"Le canal avec l'ID {moderator_db_channel_id} est introuvable.")
            return

        try:
            if self.moderator_db_message_id:
                message = await channel.fetch_message(self.moderator_db_message_id)
                await self.update_moderator_db_message(channel)
            else:
                self.moderator_db_message_id = await self.create_moderator_db_message(channel)
                self.save_data()

        except nextcord.errors.NotFound:
            self.moderator_db_message_id = await self.create_moderator_db_message(channel)
            self.save_data()
            logger.info(f"Nouveau message de base de données des modérateurs créé avec l'ID: {self.moderator_db_message_id}")

    async def create_moderator_db_message(self, channel):
        embed = self.generate_moderator_db_embed()
        view = ModeratorDBView(self)
        db_message = await channel.send(embed=embed, view=view)
        return db_message.id

    def generate_moderator_db_embed(self):
        embed_desc = ("Moderators:\n" + 
                      '\n'.join([f"{mod['name']}, ID: {mod['id']}" for mod in moderator_db]) + 
                      "\n\nTelegram:\n" + 
                      '\n'.join([f"{name}, ID: {id}" for id, name in telegram_db.items()]))
        return nextcord.Embed(title="Liste des Modérateurs", description=embed_desc)

    async def update_moderator_db_message(self, channel):
        embed = self.generate_moderator_db_embed()
        message = await channel.fetch_message(self.moderator_db_message_id)
        await message.edit(embed=embed)

    async def fetch_telegram_usernames(self):
        global telegram_db
        for chat_id in telegram_chat_ids:
            response = requests.get(
                f'https://api.telegram.org/bot{telegram_bot_token}/getChat',
                params={'chat_id': chat_id}
            )
            if response.status_code == 200:
                chat_info = response.json()
                if chat_info and chat_info['ok']:
                    username = chat_info['result'].get('username') or chat_info['result'].get('title')
                    if username:
                        telegram_db[chat_id] = username
        self.save_data()

    async def sos_notification(self, discord_message=None, telegram_message=None, telegram=False):
        if telegram and telegram_message:
            for chat_id in telegram_chat_ids:
                response = requests.post(
                    f'https://api.telegram.org/bot{telegram_bot_token}/sendMessage',
                    data={
                        'chat_id': chat_id, 
                        'text': telegram_message, 
                        'parse_mode': 'HTML', 
                        'disable_web_page_preview': True
                    }
                )
                if response.status_code != 200:
                    logger.error(f"Erreur lors de l'envoi du message Telegram : {response.text}")
        else:
            for moderator in moderator_db:
                moderator_user = await self.bot.fetch_user(moderator['id'])
                if moderator_user:
                    await moderator_user.send(embed=discord_message)

    @nextcord.slash_command(name="sos", description="Ping les modérateurs en cas d'extrême urgence. ⚠️ Abus sévèrement punis ! ⚠️")
    async def sos(self,
                  interaction: Interaction,
                  message: str = SlashOption(name="message", description="Message à envoyer aux modérateurs", required=True)):

        await interaction.response.defer(ephemeral=True)

        if not moderator_db:
            await interaction.followup.send("La base de données des modérateurs est vide.", ephemeral=True)
            return

        sos_embed = nextcord.Embed(
            title="🔴 **SOS Notification** 🔴",
            description=(
                f"**Serveur**: {interaction.guild.name}\n"
                f"**Salon**: {interaction.channel.mention}\n"
                f"**Message**: {message}\n\n"
                f"_De: {interaction.user.mention}_\n"
                f"[Aller au salon](<https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}>)"  # désactive la prévisualisation
            )
        )

        telegram_message = (
            f"🔴 <b>SOS Notification</b> 🔴\n\n"
            f"<b>Serveur</b>: {interaction.guild.name}\n"
            f"<b>Salon</b>: <a href=\"https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}\">{interaction.channel.name}</a>\n"
            f"<b>Message</b>: {message}\n\n"
            f"<i>De: {interaction.user}</i>"
        )

        # Notify all moderators
        await self.sos_notification(discord_message=sos_embed)
        await interaction.followup.send("SOS notification envoyée à tous les modérateurs.", ephemeral=True)

        # Optionally send to Telegram
        if telegram_bot_token and telegram_chat_ids:
            await self.sos_notification(telegram_message=telegram_message, telegram=True)

    async def sync_commands(self):
        await self.bot.sync_all_application_commands()
        logger.info("Commandes slash synchronisées avec le serveur.")

    @commands.Cog.listener()
    async def on_ready(self):
        await self.sync_commands()
        await self.fetch_moderators()
        await self.fetch_telegram_usernames()
        if self.moderator_db_message_id:
            channel = self.bot.get_channel(moderator_db_channel_id)
            if channel:
                try:
                    view = ModeratorDBView(self)
                    message = await channel.fetch_message(self.moderator_db_message_id)
                    await message.edit(view=view)
                except nextcord.errors.NotFound:
                    self.moderator_db_message_id = await self.create_moderator_db_message(channel)
                    self.save_data()
                    logger.info(f"Nouveau message de base de données des modérateurs créé avec l'ID: {self.moderator_db_message_id}")


def setup(bot):
    bot.add_cog(SOSCommands(bot))
