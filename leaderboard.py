import discord
from discord.ext import commands
import aiosqlite
import asyncio

intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # Ensure this intent is enabled

bot = commands.Bot(command_prefix='=', intents=intents, help_command=None)

DATABASE = 'leaderboard.db'
REQUIRED_ROLE_ID = 1088359970527002624  # Replace with your role ID

async def create_db():
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS leaderboard (
                            user_id INTEGER PRIMARY KEY,
                            points INTEGER NOT NULL,
                            wins INTEGER NOT NULL)''')
        await db.commit()

@bot.event
async def on_ready():
    await create_db()
    print(f'Bot is ready. Logged in as {bot.user}')

def has_role(ctx):
    role = discord.utils.get(ctx.author.roles, id=REQUIRED_ROLE_ID)
    return role is not None

@bot.command(description="Add points to a member and update their position in the leaderboard.")
@commands.check(has_role)
async def add(ctx, member: discord.Member, points: int):
    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute('SELECT points, wins FROM leaderboard WHERE user_id = ?', (member.id,))
        row = await cursor.fetchone()
        if row:
            new_points = row[0] + points
            new_wins = row[1] + 1
            await db.execute('UPDATE leaderboard SET points = ?, wins = ? WHERE user_id = ?', (new_points, new_wins, member.id))
        else:
            new_points = points
            new_wins = 1
            await db.execute('INSERT INTO leaderboard (user_id, points, wins) VALUES (?, ?, ?)', (member.id, new_points, new_wins))
        await db.commit()
    
    # Calculate the user's new position in the leaderboard
    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute('SELECT user_id FROM leaderboard ORDER BY points DESC')
        rows = await cursor.fetchall()
        position = [i for i, row in enumerate(rows, start=1) if row[0] == member.id][0]
    
    # Send a DM to the user
    dm_message = f"Congratulations! {member.mention}, you have been awarded {points} points. Your current position in the leaderboard is #{position}."
    await member.send(dm_message)
    
    await ctx.send(embed=discord.Embed(
        title="Points Awarded",
        description=f'{member.mention} has been awarded {points} points.',
        color=discord.Color.green()
    ))

@bot.command(description="Display the current leaderboard.")
@commands.cooldown(1, 15, commands.BucketType.guild)
async def leaderboard(ctx):
    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute('SELECT user_id, points, wins FROM leaderboard ORDER BY points DESC')
        rows = await cursor.fetchall()
    if not rows:
        await ctx.send(embed=discord.Embed(
            title="Leaderboard",
            description="Leaderboard is empty.",
            color=discord.Color.red()
        ))
    else:
        leaderboard_text = "\n".join([f'#{index + 1} <@{row[0]}>: {row[2]} wins, {row[1]} points' for index, row in enumerate(rows)])
        embed = discord.Embed(
            title="Leaderboard",
            description=leaderboard_text,
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)

@bot.command(description="Reset the leaderboard.")
@commands.check(has_role)
async def reset(ctx):
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute('DELETE FROM leaderboard')
        await db.commit()
    await ctx.send(embed=discord.Embed(
        title="Leaderboard Reset",
        description="The leaderboard has been reset.",
        color=discord.Color.orange()
    ))

@bot.command(name="help", description="Show help information for all commands.")
async def custom_help(ctx):
    embed = discord.Embed(title="Help", description="List of available commands:", color=discord.Color.blue())
    embed.add_field(name="=add @member points", value="Add points to a member and update their position in the leaderboard. (Requires specific role)", inline=False)
    embed.add_field(name="=leaderboard", value="Display the current leaderboard. (15 seconds cooldown)", inline=False)
    embed.add_field(name="=reset", value="Reset the leaderboard. (Requires specific role)", inline=False)
    embed.add_field(name="=help", value="Show this help message.", inline=False)
    await ctx.send(embed=embed)

@add.error
@reset.error
async def role_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send(embed=discord.Embed(
            title="Permission Denied",
            description="You do not have the required role to use this command.",
            color=discord.Color.red()
        ))

@leaderboard.error
async def leaderboard_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        msg = await ctx.send(f"Please wait {error.retry_after:.1f} seconds before using the leaderboard command again.")
        retry_after = int(error.retry_after)
        for i in range(retry_after, 0, -1):
            await asyncio.sleep(1)
            await msg.edit(content=f"Please wait `{i:.1f}` seconds before using the leaderboard command again.")
        await msg.delete()


bot.run(TOKEN)
