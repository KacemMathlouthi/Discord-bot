import os
from dotenv import load_dotenv
from discord import Intents, Message, Embed
from discord.ext import commands
import discord
from groq import Groq
import asyncio




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

