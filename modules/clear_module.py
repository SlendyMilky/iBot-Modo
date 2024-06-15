import nextcord
from nextcord import SlashOption, Interaction
from nextcord.ext import commands
import os
import logging
from datetime import datetime, timezone, timedelta

# Configuration du logger
logger = logging.getLogger('bot.clear_module')
# logging.basicConfig(level=logging.INFO)

# Variables d'environnement pour la configuration
moderator_role_ids_str = os.getenv('MODERATOR_ROLE_IDS', '')

# Parsing des IDs de rôles modérateurs
if moderator_role_ids_str:
    try:
        moderator_role_ids = list(map(int, moderator_role_ids_str.split(',')))
    except ValueError:
        logger.error("La variable d'environnement 'MODERATOR_ROLE_IDS' contient des valeurs invalides.")
        moderator_role_ids = []
else:
    moderator_role_ids = []
    logger.warning("La variable d'environnement 'MODERATOR_ROLE_IDS' est vide ou non définie.")

class ClearMessages(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def is_moderator(self, member):
        return any(role.id in moderator_role_ids for role in member.roles)

    @nextcord.slash_command(name="clear", description="Supprimer un nombre spécifique de messages.")
    async def clear(self,
                    interaction: Interaction,
                    number: int = SlashOption(name="number", description="Nombre de messages à supprimer", required=True, min_value=1, max_value=100),
                    member: nextcord.Member = SlashOption(name="member", description="Membre visé (facultatif)", required=False)):
        try:
            # Vérifier les permissions
            if not await self.is_moderator(interaction.user):
                await interaction.response.send_message("Vous n'avez pas la permission d'utiliser cette commande.", ephemeral=True)
                return

            await interaction.response.defer()

            # Définir la limite de suppression des messages (14 jours)
            time_limit = datetime.now(timezone.utc) - timedelta(weeks=2)
            recent_time_limit = datetime.now(timezone.utc) - timedelta(seconds=5)
            deleted_messages = 0

            if member:
                # Supprimer les messages d'un utilisateur spécifique
                def check(msg):
                    # Ne pas supprimer les messages du bot envoyés dans les 5 dernières secondes
                    return msg.author.id == member.id and msg.created_at > time_limit

                async for message in interaction.channel.history(limit=200).filter(check):
                    if deleted_messages < number:
                        await message.delete()
                        deleted_messages += 1
                    else:
                        break
            else:
                # Supprimer les derniers messages
                async for message in interaction.channel.history(limit=200):
                    # Ne pas supprimer les messages du bot envoyés dans les 5 dernières secondes
                    if message.created_at > time_limit and not (message.author.bot and message.created_at > recent_time_limit):
                        await message.delete()
                        deleted_messages += 1
                        if deleted_messages >= number:
                            break

            # Utilisation de followup pour garantir l'absence d'erreur 404
            await interaction.followup.send(f"{deleted_messages} messages supprimés.", ephemeral=True)
        except nextcord.errors.NotFound as e:
            logger.error(f"Erreur de message introuvable : {str(e)}")
            await interaction.followup.send("Erreur: Impossible de trouver un message à supprimer. Essayez à nouveau.", ephemeral=True)
        except nextcord.errors.ApplicationInvokeError as e:
            logger.error(f"Erreur d'invocation d'application : {str(e)}")
            await interaction.followup.send("Erreur: Une erreur est survenue lors de l'exécution de la commande.", ephemeral=True)
        except Exception as e:
            logger.exception("Une erreur inattendue est survenue.")
            await interaction.followup.send("Une erreur inattendue est survenue. Merci de réessayer.", ephemeral=True)

def setup(bot):
    bot.add_cog(ClearMessages(bot))
