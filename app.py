import os
from dotenv import load_dotenv
from discord import Intents, Client, Message, VoiceChannel, ButtonStyle, Interaction, Embed
from discord.ext import commands
import discord
from discord.ui import Button, View
from groq import Groq
import yt_dlp
from yt_dlp import YoutubeDL
import asyncio
import requests

# LOAD OUR TOKEN FROM SOMEWHERE SAFE
load_dotenv()
dstoken = os.getenv("discord_token")
groqtoken = os.getenv("groq_token")

# BOT SETUP
intents = Intents.default()
intents.message_content = True 
client = commands.Bot(command_prefix="/", intents=intents)

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
                "content": "Start each conversation by saying 'asba lomar' then proceed to answer the prompt."
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
        return
    else:
        channel = ctx.message.author.voice.channel
        if ctx.voice_client is not None:
            if ctx.message.author.voice.channel == ctx.voice_client.channel:
                await ctx.send("I'm already in {} !".format(ctx.message.author.name))
            else:
                await ctx.voice_client.move_to(channel)
                await ctx.send(f"Joined {channel.name} voice channel!") 
        else:
            await channel.connect()
            await ctx.send(f"Joined {channel.name} voice channel!")    

# LEAVE VOICE CHANNEL COMMAND
@client.command(name="leave")
async def leave(ctx):     
    if ctx.voice_client is not None:
        if ctx.message.author.voice.channel != ctx.voice_client.channel:
            await ctx.send("We are not in the same channel {} !".format(ctx.message.author.name))
            return
        else:
            await ctx.voice_client.disconnect()
            await ctx.send("Disconnected from the voice channel.")
    else:
        await ctx.send("I am not in a voice channel.")

# RESUME MUSIC COMMAND
@client.command(name='resume', help='Resumes the song')
async def resume(ctx):
    voice_client = ctx.message.guild.voice_client
    if voice_client.is_paused():
        voice_client.resume()
    else:
        await ctx.send("The bot was not playing anything before this. Use /play command!")

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

# SKIP MUSIC COMMAND
@client.command(name='skip', help='This command skips to the next song in the queue')
async def skip(ctx):
    voice_client = ctx.message.guild.voice_client
    if voice_client.is_playing():
        voice_client.stop()
    await play_next(ctx)

# VIEW CLASS FOR BUTTONS
class MusicControlView(View):
    def __init__(self, ctx):
        super().__init__(timeout=None)
        self.ctx = ctx

    @discord.ui.button(label="Pause", style=ButtonStyle.primary)
    async def pause_button(self, button: Button, interaction: Interaction):
        await pause(self.ctx)

    @discord.ui.button(label="Resume", style=ButtonStyle.primary)
    async def resume_button(self, button: Button, interaction: Interaction):
        await resume(self.ctx)

    @discord.ui.button(label="Skip", style=ButtonStyle.secondary)
    async def skip_button(self, button: Button, interaction: Interaction):
        await skip(self.ctx)

    @discord.ui.button(label="Leave", style=ButtonStyle.danger)
    async def leave_button(self, button: Button, interaction: Interaction):
        await leave(self.ctx)

# PLAY MUSIC COMMAND WITH BUTTONS
@client.command(name="play")
async def play(ctx, *, url: str):
    if ctx.voice_client is None:
        if not ctx.message.author.voice:
            await ctx.send("{} is not connected to a voice channel!".format(ctx.message.author.name))
            return
        else:
            channel = ctx.message.author.voice.channel
            if ctx.voice_client is not None:
                if ctx.message.author.voice.channel == ctx.voice_client.channel:
                    await ctx.send("I'm already in {} !".format(ctx.message.author.name))
                else:
                    await ctx.voice_client.move_to(channel)
                    await ctx.send(f"Joined {channel.name} voice channel!") 
            else:
                await channel.connect()
                await ctx.send(f"Joined {channel.name} voice channel!")  
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        url2 = info['url']

    ffmpeg_opts = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn',
    }

    source = discord.FFmpegPCMAudio(url2, **ffmpeg_opts)
    music_queue.append({'title': info['title'], 'source': source})
    if not ctx.voice_client.is_playing():
        await play_next(ctx)
    else:
        await ctx.send(f"Added to queue: {info['title']}")

    await ctx.send(f"Now playing: {info['title']}", view=MusicControlView(ctx))

async def play_next(ctx):
    if music_queue:
        song = music_queue.pop(0)
        ctx.voice_client.play(song['source'], after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), client.loop))
        await ctx.send(f"Now playing: {song['title']}")
    else:
        await ctx.send("Queue is empty, add more songs!")

# MUSIC QUEUE COMMAND
@client.command(name="queue", help="Displays the current music queue")
async def queue(ctx):
    if music_queue:
        queue_list = "\n".join([f"{idx + 1}. {song['title']}" for idx, song in enumerate(music_queue)])
        await ctx.send(f"Current queue:\n{queue_list}")
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
        first_result = info['entries'][0]
        url = first_result['webpage_url']
        await play(ctx, url=url)

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

# HELP COMMAND
@client.command(name="helpme", help="Displays this message")
async def help_command(ctx):
    embed = Embed(title="Music Bot Help", description="List of commands", color=0x00ff00)
    commands_list = [
        ("/join", "Join the voice channel"),
        ("/leave", "Leave the voice channel"),
        ("/play <url>", "Play a song from YouTube"),
        ("/pause", "Pause the current song"),
        ("/resume", "Resume the paused song"),
        ("/stop", "Stop the current song"),
        ("/skip", "Skip to the next song in the queue"),
        ("/queue", "Display the current music queue"),
        ("/search <query>", "Search for a song on YouTube and play the first result"),
        ("/lyrics", "Fetch the lyrics for the currently playing song"),
        ("/helpme", "Display this message")
    ]
    for name, desc in commands_list:
        embed.add_field(name=name, value=desc, inline=False)
    await ctx.send(embed=embed)

# MAIN ENTRY POINT
def main() -> None:
    client.run(dstoken)

if __name__ == '__main__':
    main()

