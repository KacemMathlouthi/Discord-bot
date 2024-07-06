import os
from dotenv import load_dotenv
from discord import Intents, Client, Message, VoiceChannel, ButtonStyle, Interaction, Embed, app_commands, utils
from discord.ext import commands
import discord
from discord.ui import Button, View
from groq import Groq
import yt_dlp
from yt_dlp import YoutubeDL
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

# MUSIC QUEUE
music_queue = []
is_looping = False
current_song = None

#FFPMEG OPTIONS LOCK
ffmpeg_opts = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}

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
    print(f'{client.user} is now running!')


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

# JOIN VOICE CHANNEL COMMAND
@client.command(name="join")
async def join(ctx):
    if not ctx.message.author.voice:
        await ctx.send("{} is not connected to a voice channel!".format(ctx.message.author.name))
    else:
        channel = ctx.message.author.voice.channel
        if ctx.voice_client is not None:
            await ctx.voice_client.move_to(channel)
        else:
            await channel.connect()

# LEAVE VOICE CHANNEL COMMAND
@client.command(name="leave")
async def leave(ctx):     
    if ctx.voice_client is not None:
        if ctx.message.author.voice.channel != ctx.voice_client.channel :
            await ctx.send("Not in the same channel {} !".format(ctx.message.author.name))
            return
        else:
            await ctx.voice_client.disconnect()
    else:
        await ctx.send("Not in a voice channel.")

# RESUME MUSIC COMMAND
@client.command(name='resume', help='Resumes the song')
async def resume(ctx):
    voice_client = ctx.message.guild.voice_client
    if voice_client.is_paused():
        voice_client.resume()
    else:
        await ctx.send("Not playing anything before this. Use /play command!")

# PAUSE MUSIC COMMAND
@client.command(name='pause', help='This command pauses the song')
async def pause(ctx):
    voice_client = ctx.message.guild.voice_client
    if voice_client.is_playing():
        voice_client.pause()
    else:
        await ctx.send("The bot is not playing anything at the moment.")

# STOP MUSIC COMMAND
@client.command(name='stop', help='This command stops the song')
async def stop(ctx):
    voice_client = ctx.message.guild.voice_client
    if voice_client.is_playing():
        voice_client.stop()
    else:
        await ctx.send("The bot is not playing anything at the moment.")


# VIEW CLASS FOR BUTTONS
class MusicControlView(View):
    def __init__(self, ctx):
        super().__init__(timeout=None)
        self.ctx = ctx

    @discord.ui.button(emoji="⏯", style=ButtonStyle.grey, custom_id="pauseplay_button")
    async def pause_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild.voice_client.is_playing():
            interaction.guild.voice_client.pause()
            await interaction.response.send_message(":pause_button: **Paused**", ephemeral=True)
        elif interaction.guild.voice_client is not None and interaction.guild.voice_client.is_paused():
            interaction.guild.voice_client.resume()
            await interaction.response.send_message(":play_pause: **Resumed**", ephemeral=True)
        else:
            await interaction.response.send_message("Not playing anything at the moment !", ephemeral=True)

    @discord.ui.button(emoji="⏭", style=ButtonStyle.grey, custom_id="skip_button")
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(":fast_forward: **Skipped**", ephemeral=True)
        await skip(self.ctx)

    @discord.ui.button(emoji="<:reacttrash:878915749375246336>", style=ButtonStyle.secondary, custom_id="leave_button")
    async def leave_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild.voice_client is not None:
            if interaction.user.voice is None or interaction.user.voice.channel != interaction.guild.voice_client.channel:
                await interaction.response.send_message("Not in the same channel!", ephemeral=True)
            else:
                await interaction.guild.voice_client.disconnect()
                await interaction.response.send_message("⛔️ **Disconnected**", ephemeral=True)
        else:
            await interaction.response.send_message("Not in a voice channel !", ephemeral=True)

# PLAY MUSIC COMMAND WITH BUTTONS
@client.command(name="play")
async def play(ctx, url: str):
    await join(ctx)
    
    if url.startswith("https://www.youtube.com/"):
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            url2 = info['url']
            source = discord.FFmpegPCMAudio(url2, **ffmpeg_opts)
            music_queue.append({'title': info['title'], 'source': source})
            if not ctx.voice_client.is_playing():
                await play_next(ctx)
            else:
                embed = discord.Embed(title = f"ADDED TO QUEUE :   {info['title']}", color = discord.Colour.red())
                await ctx.send(embed=embed)
    else:
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'default_search': 'ytsearch1',
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            first_result = info['entries'][0]
            url = first_result['webpage_url']
            await play(ctx, url=url)

async def play_next(ctx):
    global is_looping, current_song

    if is_looping and current_song:
        ctx.voice_client.play(current_song['source'], after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), client.loop))
    elif music_queue:
        song = music_queue.pop(0)
        current_song = song
        ctx.voice_client.play(song['source'], after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), client.loop))
        embed = discord.Embed(title = f"PLAYING :  {song['title']}", color = discord.Colour.red())
        await ctx.send(embed=embed, view=MusicControlView(ctx))
    else:
        await ctx.send("Queue is **empty**, add more songs!")

# SKIP MUSIC COMMAND
@client.command(name='skip', help='This command skips to the next song in the queue')
async def skip(ctx):
    voice_client = ctx.message.guild.voice_client
    if voice_client.is_playing():
        voice_client.stop()
    await play_next(ctx)

# MUSIC QUEUE COMMAND
@client.command(name="queue", help="Displays the current music queue")
async def queue(ctx):
    if music_queue:
        queue_list = "\n".join([f"{idx + 1}. {song['title']}" for idx, song in enumerate(music_queue)])
        await ctx.send(f"**Current queue:**\n{queue_list}")
    else:
        await ctx.send("The queue is currently empty.")

@client.command(name="clear", help="Clears the current music queue")
async def clear(ctx):
    global music_queue
    music_queue = []
    await ctx.send("music queue cleared!")

# SEARCH YOUTUBE COMMAND
@client.command(name="search")
async def search(ctx, *, query: str):
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'default_search': 'ytsearch5',
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(query, download=False)
        results = info['entries']

        if not results:
            await ctx.send("No results found.")
            return

        queue_list = "\n".join([f"{idx + 1}. [{entry['title']}]({entry['webpage_url']})" for idx, entry in enumerate(results[:5])])
        await ctx.send(f"**Top 5 YouTube results for '{query}':**\n{queue_list}")

# LOOP MUSIC COMMAND
@client.command(name='loop')
async def loop(ctx):
    global is_looping, current_song

    if ctx.voice_client is None or not ctx.voice_client.is_playing():
        await ctx.send("No song is currently playing.")
        return

    if not is_looping:
        is_looping = True
        current_song = music_queue[0] if music_queue else None
        await ctx.send("Looping the current song.")
    else:
        is_looping = False
        await ctx.send("Stopped looping the current song.")

# LYRICS COMMAND
@client.command(name="lyrics", help="Fetches the lyrics for the currently playing song")
async def lyrics(ctx):
    if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
        song = music_queue[0] if music_queue else None
        if song:
            song_title = song['title']
            response = requests.get(f"https://api.lyrics.ovh/v1/{song_title}")
            if response.status_code == 200:
                data = response.json()
                lyrics = data.get("lyrics", "No lyrics found")
                await ctx.send(f"Lyrics for {song_title}:\n{lyrics}")
            else:
                await ctx.send("Failed to fetch lyrics.")
        else:
            await ctx.send("No song is currently playing.")
    else:
        await ctx.send("No song is currently playing.")

# JALEL COMMAND
urls=['https://www.youtube.com/watch?v=8y4FtO0J4rU',
      'https://www.youtube.com/watch?v=Yky0ZHBhZxM',
      'https://www.youtube.com/watch?v=Zu_M3VgzUpk',
      'https://www.youtube.com/watch?v=lkeGcH2xZ8Y',
      'https://www.youtube.com/watch?v=4KB7b27_34Q',
      'https://www.youtube.com/watch?v=OnGLU0UpnBc',
      'https://www.youtube.com/watch?v=i2NJd2a5P0M',
      'https://www.youtube.com/watch?v=hyCtOHXcfW0',
      'https://www.youtube.com/watch?v=YJ_a0v4eJU8',
      'https://www.youtube.com/watch?v=VIVzi7rUDBA',
      'https://www.youtube.com/watch?v=Na9jREuExmU',
      'https://www.youtube.com/watch?v=JEWWmx8jKCk',]

def add_to_queue(url: str):
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        source = discord.FFmpegPCMAudio(info['url'], **ffmpeg_opts)
        music_queue.append({'title': info['title'], 'source': source})

@client.command(name="jalel")
async def jalel(ctx):
    shuffle(urls)
    await play(ctx, urls[0])
    for url in range(1, 3):
        add_to_queue(urls[url])



##################  GAMES  #####################################

# DICE COMMAND
@client.command(name="dice")
async def dice(ctx):
    nb = randint(0,5)
    nb_list=[':one:',':two:',':three:' ,':four:', ':five:', ':six:']
    await ctx.send(nb_list[nb])

# ROCK PAPER SCISSORS COMMAND

class RPSGame:
    def __init__(self):
        self.players = []
        self.choices = {}

    def add_player(self, player):
        if len(self.players) < 2:
            self.players.append(player)

    def make_choice(self, player, choice):
        self.choices[player] = choice

    def is_ready(self):
        return len(self.players) == 2 and len(self.choices) == 2

    def determine_winner(self):
        p1, p2 = self.players
        c1, c2 = self.choices[p1], self.choices[p2]

        if c1 == c2:
            return None
        elif (c1 == "rock" and c2 == "scissors") or \
             (c1 == "paper" and c2 == "rock") or \
             (c1 == "scissors" and c2 == "paper"):
            return p1
        else:
            return p2

class RPSView(View):
    def __init__(self, game):
        super().__init__(timeout=None)
        self.game = game
    @discord.ui.button(label='Rock', style=discord.ButtonStyle.grey, emoji='🧱')
    async def rock(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_choice(interaction, "rock")
    @discord.ui.button(label='Paper', style=discord.ButtonStyle.grey, emoji='🧻')
    async def paper(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_choice(interaction, "paper")
    @discord.ui.button(label='Scissors', style=discord.ButtonStyle.grey, emoji='✂️')
    async def scissors(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_choice(interaction, "scissors")
    @discord.ui.button(label='JOIN', style=discord.ButtonStyle.green, custom_id='join')
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        if len(self.game.players) == 0 or (len(self.game.players) == 1 and interaction.user != self.game.players[0]):
            self.game.add_player(interaction.user)
            button.disabled = True
            await interaction.response.edit_message(view=self)
            await interaction.followup.send(f"{interaction.user.mention} has joined the game!")
        else:
            await interaction.response.send_message("You can't join this game!", ephemeral=True)

    async def handle_choice(self, interaction: discord.Interaction, choice: str):
        player = interaction.user
        if player not in self.game.players:
            await interaction.response.send_message("Chemda5el rabbak!", ephemeral=True)
            return

        self.game.make_choice(player, choice)
        await interaction.response.send_message(f"You chose {choice}!", ephemeral=True)

        if self.game.is_ready():
            winner = self.game.determine_winner()
            p1, p2 = self.game.players
            c1, c2 = self.game.choices[p1], self.game.choices[p2]
            d={'rock':':bricks:', 'paper':':roll_of_paper:', 'scissors':':scissors:' }
            await interaction.followup.send(f"{p1.mention}{d[c1]}  **--**  {p2.mention}{d[c2]}")
            if winner:
                await interaction.followup.send(f"{winner.mention} **wins** !")
            else:
                await interaction.followup.send("It's a **tie** !")
            self.stop()

@client.command(name="rps")
async def start_rps(ctx):
    game = RPSGame()
    view = RPSView(game)

    game.add_player(ctx.author)
    await ctx.send("Rock-Paper-Scissors game started! Another player must join !", view=view)



# XOXO GAME
class TicTacToeButton(Button):
    def __init__(self, x, y):
        super().__init__(style=discord.ButtonStyle.secondary, label='\u200b', row=y)
        self.x = x
        self.y = y

    async def callback(self, interaction: discord.Interaction):
        view: TicTacToe = self.view
        if interaction.user != view.players[view.current_player]:
            await interaction.response.send_message("It's not your turn !", ephemeral=True)
            return

        state = view.board[self.y][self.x]
        if state in ('X', 'O'):
            return

        if view.current_player == 0:
            self.style = discord.ButtonStyle.danger
            self.label = 'X'
            self.disabled = True
            view.board[self.y][self.x] = 'X'
            view.current_player = 1
        else:
            self.style = discord.ButtonStyle.success
            self.label = 'O'
            self.disabled = True
            view.board[self.y][self.x] = 'O'
            view.current_player = 0

        winner = view.check_winner()
        if winner is not None:
            for child in view.children:
                child.disabled = True
            await interaction.response.edit_message(content=f'{view.players[winner].mention} **wins** !', view=view)
        elif view.is_full():
            for child in view.children:
                child.disabled = True
            await interaction.response.edit_message(content='It\'s a **tie** !', view=view)
        else:
            await interaction.response.edit_message(view=view)


class TicTacToe(View):
    def __init__(self, player1):
        super().__init__()
        self.current_player = 0
        self.board = [[None] * 3 for _ in range(3)]
        self.players = [player1, None]
        for y in range(3):
            for x in range(3):
                self.add_item(TicTacToeButton(x, y))
        self.join_button = Button(label="JOIN", style=discord.ButtonStyle.primary)
        self.join_button.callback = self.join_game
        self.add_item(self.join_button)

    async def join_game(self, interaction: discord.Interaction):
        if self.players[1] is None and interaction.user != self.players[0]:
            self.players[1] = interaction.user
            self.join_button.disabled = True
            await interaction.response.edit_message(content=f'{self.players[0].mention}:regional_indicator_x: **VS** {self.players[1].mention}:regional_indicator_o: : Game starts now!', view=self)
        else:
            await interaction.response.send_message("You can't join this game !", ephemeral=True)

    def check_winner(self):
        for line in self.board:
            if line[0] == line[1] == line[2] and line[0] is not None:
                return 0 if line[0] == 'X' else 1

        for col in range(3):
            if self.board[0][col] == self.board[1][col] == self.board[2][col] and self.board[0][col] is not None:
                return 0 if self.board[0][col] == 'X' else 1

        if self.board[0][0] == self.board[1][1] == self.board[2][2] and self.board[0][0] is not None:
            return 0 if self.board[0][0] == 'X' else 1

        if self.board[0][2] == self.board[1][1] == self.board[2][0] and self.board[0][2] is not None:
            return 0 if self.board[0][2] == 'X' else 1

        return None

    def is_full(self):
        return all(all(cell is not None for cell in row) for row in self.board)


@client.command(name='xo')
async def tic_tac_toe(ctx):
    view = TicTacToe(ctx.author)
    await ctx.send('Tic-Tac-Toe: **X** goes first. Click the button below to join as **O**.', view=view)

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

    for _ in range(5):  # Number of cycles through names for dramatic effect
        for member in members:
            embed.description = f"Selecting... {member.display_name}"
            await countdown_message.edit(embed=embed)
            await asyncio.sleep(0.5)  # Adjust timing for effect

    # Final selection display
    embed = discord.Embed(title="⚡️ Selected for Disconnection", description=f"{chosen_member.mention} has been selected!", color=discord.Color.gold())
    await countdown_message.edit(embed=embed)
    await asyncio.sleep(2)  # Dramatic pause

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

# HELP COMMAND
@client.command(name="help", help="Displays this message")
async def help_command(ctx):
    embed = Embed(title="Music Bot Help", description="List of commands", color=0x00ff00)
    commands_list = [
        ("/join", "Join the voice channel"),
        ("/leave", "Leave the voice channel"),
        ("/play <url/name>", "Play a song from YouTube"),
        ("/pause", "Pause the current song"),
        ("/resume", "Resume the paused song"),
        ("/skip", "Skip to the next song in the queue"),
        ("/loop", "Play the current song in loop until /loop again"),
        ("/queue", "Display the current music queue"),
        ("/clear", "Clear the current music queue"),
        ("/help", "Display this message"),
        ("/dice", "Get a number from 1 to 6"),
        ("/rps", "Rock-Paper-Scissors Game Co-op"),
        ("/xo", "Tic-Tac-Toe Game Co-op")
    ]
    for name, desc in commands_list:
        embed.add_field(name=name, value=desc, inline=False)
    await ctx.send(embed=embed)

# ON COMMAND ERROR
@client.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send(
            'Invalid Command. Type /help, Retry.')

    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(
            'An Argument is Missing, Retry.')

# MAIN ENTRY POINT
def main() -> None:
    try:
        client.run(dstoken)
    except Exception as e:
        print(f"Error running the bot: {e}")

if __name__ == '__main__':
    main()

