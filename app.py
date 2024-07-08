import os
from dotenv import load_dotenv
from discord import Intents, Client, Message, VoiceChannel, ButtonStyle, Interaction, Embed, app_commands, utils
from discord.ext import commands, tasks
import discord
from groq import Groq
import asyncio
import requests
from random import randint
from random import shuffle
import random
import json
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from io import BytesIO



# LOAD OUR TOKEN FROM SOMEWHERE SAFE
load_dotenv()
dstoken = os.getenv("discord_token")
groqtoken = os.getenv("groq_token")


# BOT SETUP
intents = Intents.default()
intents.message_content = True 
client = commands.Bot(command_prefix="/", help_command=None, intents=intents)


# GROQ SETUP
groq_client = Groq(api_key=groqtoken)


# RESPONSE FUNCTIONALITY
def get_response(user_input: str) -> str:
    chat_completion = groq_client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": "Answer the prompt."
            },
            {
                "role": "user",
                "content": user_input
            }
        ],
        model="llama3-8b-8192",
        temperature=0.5,
        max_tokens=1024,
        top_p=1,
        stop=None,
        stream=False,
    )
    return chat_completion.choices[0].message.content


# MESSAGE FUNCTIONALITY
async def send_message(message: Message, user_message: str) -> None:
    if not user_message:
        print('(Message was empty because intents were not enabled probably)')
        return

    try:
        response: str = get_response(user_message)
        await message.channel.send(response)
    except Exception as e:
        print(e)


# HANDLING THE STARTUP FOR OUR BOT
@client.event
async def on_ready() -> None:
    await client.change_presence(status=discord.Status.online, activity=discord.Game('/help'))
    await load_cogs()
    print(f'{client.user} is now running!')


# LOAD COGS
async def load_cogs():
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py') and filename != '__init__.py':
            await client.load_extension(f'cogs.{filename[:-3]}')


# HANDLING INCOMING MESSAGES
@client.event
async def on_message(message: Message) -> None:
    if message.author == client.user:
        return
    if message.content.startswith("gpt"):
        user_message = message.content[len("gpt"):].strip()
        username = str(message.author)
        channel = str(message.channel)

        print(f'[{channel}] {username}: "{user_message}"')
        await send_message(message, user_message)
    await client.process_commands(message)






# Path to the JSON file for storing data
STATS_FILE = 'russian_roulette_stats.json'

def load_stats():
    """Load the game statistics from a JSON file."""
    try:
        with open(STATS_FILE, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {}

def save_stats(stats):
    """Save the game statistics to a JSON file."""
    with open(STATS_FILE, 'w') as file:
        json.dump(stats, file, indent=4)

def update_stats(member, stats, disconnected=False):
    """Update statistics for a member."""
    user_id = str(member.id)
    if user_id not in stats:
        stats[user_id] = {'games_played': 0, 'times_disconnected': 0, 'name': member.display_name}
    stats[user_id]['games_played'] += 1
    if disconnected:
        stats[user_id]['times_disconnected'] += 1
    return stats

@client.command(name="rr_stats", help="Display Russian Roulette game statistics for all users.")
async def show_stats(ctx):
    """Show the statistics of the Russian Roulette game for all users."""
    stats = load_stats()
    if not stats:
        await ctx.send("No game statistics available yet.")
        return

    embed = discord.Embed(title="Game Statistics for All Users", description="Overview of all participation in Russian Roulette:", color=discord.Color.blue())
    # Sorting users by games played for better overview
    sorted_stats = sorted(stats.items(), key=lambda x: x[1]['games_played'], reverse=True)

    for user_id, user_stats in sorted_stats:
        embed.add_field(name=user_stats['name'], value=f"Games Played: {user_stats['games_played']}\nTimes Disconnected: {user_stats['times_disconnected']}", inline=False)

    await ctx.send(embed=embed)

@client.command(name="rr", help="Russian Roulette: Disconnects a random user from the voice channel with enhanced visual effects.")
async def russian_roulette(ctx):
    if not ctx.author.voice:
        await ctx.send(embed=discord.Embed(title="Russian Roulette", description="You are not connected to a voice channel!", color=discord.Color.red()))
        return

    voice_channel = ctx.author.voice.channel
    members = [member for member in voice_channel.members if member != client.user]  # Exclude the bot itself
    if len(members) <= 1:
        await ctx.send(embed=discord.Embed(title="Russian Roulette", description="Not enough players in the voice channel!", color=discord.Color.orange()))
        return

    stats = load_stats()

    # Enhanced countdown using embeds
    embed = discord.Embed(title="🎲 Russian Roulette", description="Starting Russian Roulette in 3...", color=discord.Color.blue())
    countdown_message = await ctx.send(embed=embed)
    for second in range(2, 0, -1):
        await asyncio.sleep(1)
        embed.description = f"Starting Russian Roulette in {second}..."
        await countdown_message.edit(embed=embed)
    await asyncio.sleep(1)
    embed.description = "🎯 **FIRE!**"
    await countdown_message.edit(embed=embed)

    await asyncio.sleep(1)
    chosen_member = random.choice(members)  # Random selection
    for member in members:
        update_stats(member, stats, disconnected=(member == chosen_member))
    save_stats(stats)

    for _ in range(3):  # Number of cycles through names for dramatic effect
        for member in members:
            embed.description = f"Selecting... {member.display_name}"
            await countdown_message.edit(embed=embed)
            await asyncio.sleep(0.5)  # Adjust timing for effect

    # Final selection display
    embed = discord.Embed(title="⚡️ Selected for Disconnection", description=f"{chosen_member.mention} has been selected!", color=discord.Color.gold())
    await countdown_message.edit(embed=embed)
    await asyncio.sleep(1)  # Dramatic pause

    # Disconnect the selected member
    await chosen_member.move_to(None)
    embed = discord.Embed(title="🚪 Disconnected", description=f"{chosen_member.display_name} has been disconnected from the voice channel!", color=discord.Color.green())
    await countdown_message.edit(embed=embed)

@client.command(name="rr_graph", help="Displays a graphical view of Russian Roulette statistics.")
async def show_graph(ctx):
    stats = load_stats()
    if not stats:
        await ctx.send("No game statistics available yet.")
        return

 # Convert the dictionary to a DataFrame
    data = pd.DataFrame.from_dict(stats, orient='index')
    data.reset_index(drop=True, inplace=True)
    data.columns = ['Games Played', 'Times Disconnected', 'Name']

    # Setting up the plotting
    sns.set(style="whitegrid")
    fig, ax = plt.subplots(figsize=(10, 5))

    # Create bars for "Games Played"
    bar1 = sns.barplot(x='Name', y='Games Played', data=data, color='deepskyblue', label='Games Played')

    # Create bars for "Times Disconnected"
    bar2 = sns.barplot(x='Name', y='Times Disconnected', data=data, color='tomato', label='Times Disconnected')

    # Adding labels
    for bar in bar1.containers:
        bar1.bar_label(bar, label_type='edge', fontsize=9, color='black', fontweight='bold')
        
    for bar in bar2.containers:
        bar2.bar_label(bar, label_type='edge', fontsize=9, color='black', fontweight='bold')

    # Adding final touches to the plot
    plt.xlabel('Player Names')
    plt.ylabel('Count')
    plt.title('Games Played and Disconnections per Player in Russian Roulette')
    plt.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    # Save plot to a bytes buffer
    buffer = BytesIO()
    plt.savefig(buffer, format='png')
    buffer.seek(0)
    plt.close(fig)

    # Send plot in discord
    file = discord.File(fp=buffer, filename='russian_roulette_stats.png')
    await ctx.send("Here's the latest version of the Russian Roulette statistics:", file=file)


# ON COMMAND ERROR
@client.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        embed = discord.Embed(
            title='Invalid Command. Type /help, Retry.',
            color=0xff0000
            )
        await ctx.send(embed=embed)


    if isinstance(error, commands.MissingRequiredArgument):
        embed = discord.Embed(
            title='An Argument is Missing, Retry.',
            color=0xff0000
            )
        await ctx.send(embed=embed)

# MAIN ENTRY POINT
def main() -> None:
    try:
        client.run(dstoken)
    except Exception as e:
        print(f"Error running the bot: {e}")

if __name__ == '__main__':
    main()

