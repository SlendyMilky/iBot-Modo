'''
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
'''