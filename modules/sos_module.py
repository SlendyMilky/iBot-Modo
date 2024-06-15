import nextcord
from nextcord import SlashOption, Interaction
from nextcord.ext import commands
from nextcord.ui import View, Button
import os
import logging

# Configuration du logger
logger = logging.getLogger('bot.sos_module')

# Variables d'environnement pour la configuration
moderator_db_channel_id = int(os.getenv('MODERATOR_DB_CHANNEL_ID', 0))
telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
telegram_chat_ids = os.getenv('TELEGRAM_CHAT_IDS', '').split(',')

# Initialise la liste des modérateurs et des utilisateurs Telegram
moderator_db_message_id = None
moderator_db = []
telegram_db = {}

# Classe pour gérer les boutons d'ajout et de suppression de modérateurs
class ModeratorDBView(View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @nextcord.ui.button(label="Ajouter", style=nextcord.ButtonStyle.green)
    async def add_moderator(self, button: Button, interaction: Interaction):
        user_id = interaction.user.id
        if user_id not in [mod['id'] for mod in moderator_db]:
            moderator_db.append({"id": user_id, "name": interaction.user.name})
            await self.cog.update_moderator_db_message(interaction.channel)
            await interaction.response.send_message("Vous avez été ajouté à la liste des modérateurs.", ephemeral=True)
        else:
            await interaction.response.send_message("Vous êtes déjà dans la liste des modérateurs.", ephemeral=True)

    @nextcord.ui.button(label="Retirer", style=nextcord.ButtonStyle.red)
    async def remove_moderator(self, button: Button, interaction: Interaction):
        user_id = interaction.user.id
        if user_id in [mod['id'] for mod in moderator_db]:
            moderator_db[:] = [mod for mod in moderator_db if mod['id'] != user_id]
            await self.cog.update_moderator_db_message(interaction.channel)
            await interaction.response.send_message("Vous avez été retiré de la liste des modérateurs.", ephemeral=True)
        else:
            await interaction.response.send_message("Vous n'êtes pas dans la liste des modérateurs.", ephemeral=True)

class SOSCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def fetch_moderators(self):
        global moderator_db_message_id
        global moderator_db
        if not moderator_db_channel_id:
            logger.error("La variable d'environnement 'MODERATOR_DB_CHANNEL_ID' est vide ou non définie.")
            return
        channel = self.bot.get_channel(moderator_db_channel_id)
        if channel:
            async for message in channel.history(limit=100):
                if message.author.bot and message.embeds:
                    moderator_db_message_id = message.id
                    embed = message.embeds[0]
                    content_lines = embed.description.split('\n')

                    # Parsing Discord Moderators
                    def parse_line(line):
                        if ", ID: " in line:
                            parts = line.split(', ID: ')
                            if len(parts) == 2:
                                try:
                                    return {"id": int(parts[1]), "name": parts[0].split(" ")[0]}
                                except (IndexError, ValueError) as e:
                                    logger.error(f"Erreur de parsing de ligne de modérateur : {line}\n{str(e)}")
                        return None

                    if "Moderators:" in content_lines[0]:
                        moderator_db = [parse_line(line) for line in content_lines[1:content_lines.index("Telegram:")] if parse_line(line)]
                    if "Telegram:" in content_lines:
                        for line in content_lines[content_lines.index("Telegram:") + 1:]:
                            if ", ID: " in line:
                                parts = line.split(', ID: ')
                                if len(parts) == 2:
                                    try:
                                        telegram_db[parts[1]] = parts[0].split(" ")[0]
                                    except (IndexError, ValueError) as e:
                                        logger.error(f"Erreur de parsing de ligne Telegram : {line}\n{str(e)}")

                    return
            # If no database message exists, create one
            moderator_db_message_id = await self.create_moderator_db_message(channel)

    async def create_moderator_db_message(self, channel):
        embed = self.generate_moderator_db_embed()
        view = ModeratorDBView(self)
        db_message = await channel.send(embed=embed, view=view)
        return db_message.id

    def generate_moderator_db_embed(self):
        embed_desc = "Moderators:\n" + '\n'.join([f"{mod['name']}, ID: {mod['id']}" for mod in moderator_db]) + "\n\nTelegram:\n" + '\n'.join([f"{name}, ID: {id}" for id, name in telegram_db.items()])
        return nextcord.Embed(title="Liste des Modérateurs", description=embed_desc)

    async def update_moderator_db_message(self, channel):
        global moderator_db_message_id
        embed = self.generate_moderator_db_embed()
        message = await channel.fetch_message(moderator_db_message_id)
        await message.edit(embed=embed)

    async def sos_notification(self, message, telegram=False):
        if telegram:
            for chat_id in telegram_chat_ids:
                response = requests.post(
                    f'https://api.telegram.org/bot{telegram_bot_token}/sendMessage',
                    data={'chat_id': chat_id, 'text': message}
                )
                if response.status_code != 200:
                    logger.error(f"Erreur lors de l'envoi du message Telegram : {response.text}")
        else:
            for moderator in moderator_db:
                moderator_user = await self.bot.fetch_user(moderator['id'])
                if moderator_user:
                    await moderator_user.send(message)

    @nextcord.slash_command(name="sos", description="Ping les modérateurs en cas d'urgence.")
    async def sos(self,
                  interaction: Interaction,
                  message: str = SlashOption(name="message", description="Message à envoyer aux modérateurs", required=True),
                  moderator: nextcord.Member = SlashOption(name="moderator", description="Modérateur spécifique (facultatif)", required=False)):

        await interaction.response.defer(ephemeral=True)

        if not moderator_db:
            await interaction.followup.send("La base de données des modérateurs est vide.", ephemeral=True)
            return

        if moderator:
            if moderator.id not in [mod['id'] for mod in moderator_db]:
                await interaction.followup.send(f"{moderator.mention} n'est pas un modérateur reconnu.", ephemeral=True)
                return
            # Notify a specific moderator
            await moderator.send(f"🔴 **SOS Notification** 🔴\n\n{message}\n\n_De: {interaction.user.mention}_")
            await interaction.followup.send(f"SOS notification envoyée à {moderator.mention}.", ephemeral=True)
        else:
            # Notify all moderators
            sos_message = f"🔴 **SOS Notification** 🔴\n\n{message}\n\n_De: {interaction.user.mention}_"
            await self.sos_notification(sos_message)
            await interaction.followup.send("SOS notification envoyée à tous les modérateurs.", ephemeral=True)

        # Optionally send to Telegram
        if telegram_bot_token and telegram_chat_ids:
            await self.sos_notification(sos_message, telegram=True)

    @commands.Cog.listener()
    async def on_ready(self):
        await self.fetch_moderators()

def setup(bot):
    bot.add_cog(SOSCommands(bot))
