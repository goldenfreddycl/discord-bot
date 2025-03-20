import settings
import discord
from datetime import datetime, timedelta # noqa
from classified import GUILD, TopSecretToken
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import sqlite3
import re

# Primary bot initialisation and constants
discord.VoiceClient.warn_nacl = False
logger = settings.logging.getLogger("bot")
intents = discord.Intents.all()
MY_GUILD = discord.Object(id=GUILD)
OWNER_ID = 543450801868243008

# Other constants, just extra
titles_list = ["Knight", "Baron", "Viscount", "Count", "Marquess", "Duke", "Dame", "Baroness", "Viscountess",
               "Countess", "Marchioness", "Duchess"]
SERVER_OWNER_ID = 594800798706434077
ADMIN_IDS = []
RANK_IDS = []
class MyClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def on_ready(self): # noqa
        logger.info(f"User: {client.user} (ID: {client.user.id})")
        logger.info(f"Guild ID: {client.guilds[0].id}")
        sql_conn = sqlite3.connect("roles.sqlite")
        sql_cursor = sql_conn.cursor()
        sql_cursor.execute("SELECT role_id FROM ranks ORDER BY hierarchy")
        for row in sql_cursor.fetchall():
            RANK_IDS.append(int(row[0]))
        logger.info(f"Registered {len(RANK_IDS)} Regimental Ranks")
        sql_cursor.execute("SELECT name FROM ranks WHERE class = 'Officer'")
        results = sql_cursor.fetchall()
        officer_ranks = [r[0] for r in results]
        sql_conn.close()
        sql_conn = sqlite3.connect("users.sqlite")
        sql_cursor = sql_conn.cursor()
        placeholders = ", ".join(f"'{str(rank).replace("'", "''")}'" for rank in officer_ranks)
        sql_cursor.execute(f"SELECT discordid FROM users WHERE rank IN ({placeholders})")
        results = sql_cursor.fetchall()
        admins_registered = 0
        for r in results:
            ADMIN_IDS.append(r)
            admins_registered += 1
        logger.info(f"Registered {admins_registered} admins")

    async def setup_hook(self):
        tree.copy_global_to(guild=MY_GUILD)
        synced = await tree.sync(guild=MY_GUILD)
        logger.info(f"Synced {len(synced)} Commands")


client = MyClient(intents=discord.Intents.all())
tree = app_commands.CommandTree(client)

#async def on_command_error(ctx, error):
#    if isinstance(error, commands.MissingRequiredArgument):
#        await ctx.send("ERROR: Required parameters not filled. Please try again.")
#    if isinstance(error, commands.MissingPermissions):
#        await ctx.send("ERROR: Missing permissions!")
#    else:
#        ctx.send("ERROR: " + str(error))

@tree.command(name="ping", description="Ping test")
async def ping(interaction: discord.Interaction): # noqa
    await interaction.response.defer() # noqa
    await interaction.followup.send("Pong!")

@tree.command(name="register_all", description="Admin Only. Registers all users on to the database.")
async def register_all(interaction: discord.Interaction):
    await interaction.response.defer() # noqa
    if not(interaction.user.id in ADMIN_IDS or interaction.user.id == OWNER_ID or interaction.user.id == SERVER_OWNER_ID):
        embed = discord.Embed(title=f"<:denied:1295098126943916063> Denied!",
                              description="You lack the requisite authority to issue this directive.",
                              color=discord.Colour.dark_red())
        embed.set_author(
            name="Maj. James A. Raney")
        await interaction.followup.send(embed=embed)
        return
    sql_conn = sqlite3.connect("users.sqlite")
    sql_cursor = sql_conn.cursor()
    guild = client.guilds[0]
    members = guild.members

    for member in members:
        if not member.bot:
            roles = member.roles
            role = next((r for r in roles if r.id in RANK_IDS), None)
            if not(role is None):
                role_name = role.name
                sql_cursor.execute("INSERT OR IGNORE INTO users (discordid, username, rank) VALUES (?, ?, ?);",
                                   (member.id, member.name, role_name))
    sql_conn.commit()
    sql_conn.close()
    await interaction.followup.send("Success!")

@tree.command(name="register")
@app_commands.describe(member="Select a member to register")
async def register(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.defer() # noqa
    sql_conn = sqlite3.connect("users.sqlite")
    sql_cursor = sql_conn.cursor()
    sql_cursor.execute(f"SELECT * FROM users WHERE discordid = {str(member.id)}")

    rec = sql_cursor.fetchone()

    if rec is None:
        roles = member.roles
        role = next((r for r in roles if r.id in RANK_IDS), None)
        if not (role is None):
            sql_cursor.execute("INSERT OR IGNORE INTO users (discordid, username, rank) VALUES (?, ?, ?)",
                               (member.id, member.name, role.name))
    else:
        await send_error(interaction, "User is already registered!")

async def change_rank(interaction: discord.Interaction, member: discord.Member, direction: int):
    await interaction.response.defer()  # noqa

    if not (interaction.user.id in ADMIN_IDS or interaction.user.id == OWNER_ID or interaction.user.id == SERVER_OWNER_ID):
        await lack_perms(interaction)

    guild = interaction.guild
    target = await guild.fetch_member(member.id)
    if target is None:
        await interaction.followup.send("ERROR: Member not found!")
        return

    roles = target.roles
    rank = next((r for r in roles if r.id in RANK_IDS), None)
    if not rank:
        await interaction.followup.send("ERROR: Member has no rank!")
        return

    try:
        index = RANK_IDS.index(rank.id)
        new_index = index + direction
        if new_index < 0 or new_index >= len(RANK_IDS):
            await interaction.followup.send("ERROR: Rank change out of bounds!")
            return
    except ValueError:
        await interaction.followup.send("ERROR: Rank not found in list!")
        return

    rank_new_id = RANK_IDS[new_index]
    rank_new = guild.get_role(rank_new_id)

    await target.remove_roles(rank, reason=f"Rank changed by {interaction.user.display_name}")
    await target.add_roles(rank_new, reason=f"Rank changed by {interaction.user.display_name}")

    # Database lookup for rank short name
    sql_conn = sqlite3.connect("roles.sqlite")
    sql_cursor = sql_conn.cursor()
    sql_cursor.execute("SELECT short FROM ranks WHERE role_id = ?", (rank_new_id,))
    row = sql_cursor.fetchone()
    sql_conn.close()

    if row is None:
        await interaction.followup.send("ERROR: Rank not found in the database!")
        return

    rank_short = row[0]

    # Regex to check nickname format
    pattern = r"(\[36thNY\(\w\)\])\s+\S+\.\s+(.+)"
    match = re.match(pattern, target.nick)

    if not match:
        await send_error(interaction,
            '''Target's nickname does not match the regimental format "[36thNY(company)] (rank_short). 
            (nickname)".'''
        )
        return

    prefix = match.group(1)  # [36thNY(X)]
    username = match.group(2)  # The user's name after rank_short

    new_nickname = f"{prefix} {rank_short}. {username}"

    try:
        await target.edit(nick=new_nickname)
    except discord.Forbidden:
        await interaction.followup.send(f"Missing permissions to change {target.display_name}'s nickname.")
        return
    except discord.HTTPException as e:
        await interaction.followup.send(f"Failed to update nickname: {e}")
        return

    await interaction.followup.send(f"Successfully updated <@{target.id}> to {rank_new.name}!")

@tree.command(name="promote", guild=discord.Object(id=GUILD))
@app_commands.describe(member="Member to promote")
async def promote(interaction: discord.Interaction, member: discord.Member):
    await change_rank(interaction, member, direction=+1)

@tree.command(name="demote", guild=discord.Object(id=GUILD))
@app_commands.describe(member="Member to demote")
async def demote(interaction: discord.Interaction, member: discord.Member):
    await change_rank(interaction, member, direction=-1)

@tree.command(name="log_battle", description="Logs the details and attendance of a battle", guild=discord.Object(id=GUILD))
@app_commands.describe(name="Name of Battle", date="dd/mm/yyyy", wins="Amount of wins", losses="Amount of losses",
                       comment="Any extra comments/notes/observations", voice_id="The id of the voice channel")
async def log_battle(interaction: discord.Interaction, name : str, date : str, comment: str, wins: int, losses: int, voice_id: int):
    interaction.response.defer() # noqa

    if not (interaction.user.id in ADMIN_IDS or interaction.user.id == OWNER_ID or interaction.user.id == SERVER_OWNER_ID):
        await lack_perms(interaction)

    if wins < 0 or losses < 0:
        await send_error(interaction, "Wins and losses can't be less than 0")
        return
    elif name.strip() == "":
        await send_error(interaction, "Battle requires a name.")
        return

    try:
        battle_date = datetime.strptime(date, "%d/%m/%Y").date()
    except ValueError:
        await send_error(interaction, "Invalid date format. Use dd/mm/yyyy.")
        return

    guild = interaction.guild
    channel = guild.fetch_channel(voice_id)
    if not(isinstance(channel, discord.VoiceChannel)):
        await send_error(interaction, "Given channel is not a voice channel")
        return

    members = channel.members

    if not members:
        await send_error(interaction, "There are no members in this channel.")
        return

    member_ids = [member.id for member in members]

    sql_conn = sqlite3.connect("regiment.sqlite")
    sql_cursor = sql_conn.cursor()
    sql_cursor.execute(
        "UPDATE stats SET battles = battles + 1, wins = wins + ?, losses = losses + ?",
        (wins, losses))
    sql_conn.commit()
    sql_conn.close()

    sql_conn = sqlite3.connect("regiment.sqlite")
    sql_cursor = sql_conn.cursor()
    sql_cursor.execute(
        "INSERT INTO events (type, wins, losses, date, comment) VALUES (?, ?, ?, ?, ?)",
        ("battle", wins, losses, battle_date, comment))
    sql_conn.commit()
    sql_conn.close()

    sql_conn = sqlite3.connect("users.sqlite")
    sql_cursor = sql_conn.cursor()
    for userid in member_ids:
        sql_cursor.execute(
            "UPDATE users SET battles_attended = battles_attended + 1, last_battle_attended = ? WHERE discordid = ?",
            (battle_date, userid))
    sql_conn.commit()
    sql_conn.close()

    interaction.followup.send("Successfully logged the battle!")

# @tree.command(name="temp_log")
# @app_commands.describe()
# async def temp_log(interaction: discord.Interaction):
#     await interaction.response.defer() # noqa
#     guild = interaction.guild
#     channel = guild.get_channel(1284087521646739477)
#     collected_ids = []
#     sql_conn = sqlite3.connect("users.sqlite")
#     sql_cursor = sql_conn.cursor()
#     updated_users = {}
#     async for message in channel.history():
#         drill_mentioned = False
#         if message.mentions:
#             message_date = message.created_at.strftime("%d/%m/%Y")
#             message_start = message.content.split('@', 1)[0]
#             if "drill" in message_start.lower():
#                 drill_mentioned = True
#             for user in message.mentions:
#                 if not user.bot:
#                     if drill_mentioned:
#                         sql_cursor.execute(
#                             f"UPDATE users SET drills_attended = drills_attended + 1, last_drill_attended = ? WHERE discordid = ?",
#                             (message_date, user.id)
#                         )
#                     else:
#                         sql_cursor.execute(
#                             f"UPDATE users SET battles_attended = battles_attended + 1, last_battle_attended = ? WHERE discordid = ?",
#                             (message_date, user.id)
#                         )
#                 if user.display_name in updated_users:
#                     updated_users[user.display_name] += 1  # Increment the count
#                 else:
#                     updated_users[user.display_name] = 1  # First update for this user
#     sql_conn.commit()
#     sql_conn.close()
#     response = "People updated: " + " - ".join(f"{name}: {count} times" for name, count in updated_users.items())
#     logger.info(response)
#     await interaction.followup.send("debug message success")

async def send_error(interaction: discord.Interaction, message: str):
    await interaction.response.defer() # noqa
    embed = discord.Embed(
        title=f"<:error:1351887847942262784> Error!",
        description=message,
        color=discord.Colour.dark_red()
    )
    await interaction.followup.send(embed=embed)

async def lack_perms(interaction: discord.Interaction):
    embed = discord.Embed(
        title=f"<:error:1351887847942262784> Denied!",
        description="You lack the requisite authority to issue this directive.",
        color=discord.Colour.dark_red()
    )
    embed.set_author(name="Maj. James A. Raney")
    await interaction.followup.send(embed=embed)

@tree.error
async def on_error(interaction: discord.Interaction, error : Exception):
    await interaction.response.defer() # noqa
    embed = discord.Embed(
        title=f"<:error:1351887847942262784> Error!",
        description=error,
        color=discord.Colour.dark_red()
    )
    await interaction.followup.send(embed=embed)

@client.event
async def on_message(message):
    if message.author == client.user:
        return
    if any(word in message.content.lower() for word in ["sigma", "rizz", "gyat", "demure", "skibidi", "mew"]):
        await message.reply("Screw you for saying that")

client.run(TopSecretToken, root_logger=True)