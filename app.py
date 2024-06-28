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

ffmpeg_opts = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}
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
                embed = discord.Embed(title = f"PLAYING :   {info['title']}", color = discord.Colour.red())
                await ctx.send(embed=embed, view=MusicControlView(ctx))
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
    if music_queue:
        song = music_queue.pop(0)
        ctx.voice_client.play(song['source'])

    else:
        await ctx.send("Queue is empty, add more songs!")

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

# SEARCH YOUTUBE COMMAND
@client.command(name="search", help="Searches for a song on YouTube")
async def search(ctx, *, query: str):
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'default_search': 'ytsearch1',
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(query, download=False)
        results = info['entries']
        k=[]
        for i in range(5):
            url = i['webpage_url']
            title = i['title']
            k.append(i)

        queue_list = "\n".join([f"{idx + 1}. {song['title']}" for idx, song in enumerate(k)])
        await ctx.send(f"**TOP 5 Youtube Videos:**\n{queue_list}")

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
@client.command(name="jalel")
async def jalel(ctx):
    l=[]
    for i in range(0, len(urls)):
        l.append(urls[i])
    shuffle(l)
    for i in l:
        await play(ctx, i)


##################  GAMES  ######

# DICE COMMAND
@client.command(name="dice")
async def dice(ctx):
    nb = randint(0,5)
    nb_list=[':one:',':two:',':three:' ,':four:', ':five:', ':six']
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
    @discord.ui.button(label='Rock', style=discord.ButtonStyle.grey, emoji='🥔')
    async def rock(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_choice(interaction, "rock")
    @discord.ui.button(label='Paper', style=discord.ButtonStyle.grey, emoji='🧻')
    async def paper(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_choice(interaction, "paper")
    @discord.ui.button(label='Scissors', style=discord.ButtonStyle.grey, emoji='✂️')
    async def scissors(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_choice(interaction, "scissors")
    async def handle_choice(self, interaction: discord.Interaction, choice: str):
        player = interaction.user
        if player not in self.game.players:
            await interaction.response.send_message("Chemda5el rabbak!", ephemeral=True)
            return

        self.game.make_choice(player, choice)
        await interaction.response.send_message(f"You chose {choice}!", ephemeral=True)

        if self.game.is_ready():
            winner = self.game.determine_winner()
            if winner:
                await interaction.followup.send(f"{winner.mention} wins!")
            else:
                await interaction.followup.send("It's a tie!")
            self.stop()

@client.command(name="rps")
async def start_rps(ctx):
    game = RPSGame()
    view = RPSView(game)

    game.add_player(ctx.author)
    await ctx.send("Rock-Paper-Scissors game started! Another player must type **'join'**", view=view)

    def check(message):
        return message.content.lower() == "join" and message.author != ctx.author

    try:
        join_message = await client.wait_for('message', check=check, timeout=60)
        game.add_player(join_message.author)
        await ctx.send(f"{join_message.author.mention} has joined the game!")
    except asyncio.TimeoutError:
        await ctx.send("No one joined the game in time. No friends ?")

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
        ("/loop", "Play the current song in loop forever"),
        ("/queue", "Display the current music queue"),
        ("/help", "Display this message"),
        ("/dice", "Get a number from 1 to 6"),
        ("/rps", "Rock-Paper-Scissors Game Co-op")
    ]
    for name, desc in commands_list:
        embed.add_field(name=name, value=desc, inline=False)
    await ctx.send(embed=embed)

# ON COMMAND ERROR
@client.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send(
            'Invalid Command. Type /help, **nikomok**.')

    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(
            'An Argument is Missing, **nikomok**.')

# MAIN ENTRY POINT
def main() -> None:
    try:
        client.run(dstoken)
    except Exception as e:
        print(f"Error running the bot: {e}")

if __name__ == '__main__':
    main()

