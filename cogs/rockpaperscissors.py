import discord
from discord import ButtonStyle, Interaction, Embed
from discord.ext import commands
from discord.ui import Button, View

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

    @discord.ui.button(label='Rock', style=ButtonStyle.grey, emoji='🧱')
    async def rock(self, interaction: Interaction, button: discord.ui.Button):
        await self.handle_choice(interaction, "rock")

    @discord.ui.button(label='Paper', style=ButtonStyle.grey, emoji='🧻')
    async def paper(self, interaction: Interaction, button: discord.ui.Button):
        await self.handle_choice(interaction, "paper")

    @discord.ui.button(label='Scissors', style=ButtonStyle.grey, emoji='✂️')
    async def scissors(self, interaction: Interaction, button: discord.ui.Button):
        await self.handle_choice(interaction, "scissors")

    @discord.ui.button(label='JOIN', style=ButtonStyle.green, custom_id='join')
    async def join(self, interaction: Interaction, button: discord.ui.Button):
        if len(self.game.players) == 0 or (len(self.game.players) == 1 and interaction.user != self.game.players[0]):
            self.game.add_player(interaction.user)
            button.disabled = True
            await interaction.response.edit_message(view=self)
            await interaction.followup.send(f"{interaction.user.mention} has joined the game!")
        else:
            await interaction.response.send_message("You can't join this game!", ephemeral=True)

    async def handle_choice(self, interaction: Interaction, choice: str):
        player = interaction.user
        if player not in self.game.players:
            await interaction.response.send_message("You are not part of this game!", ephemeral=True)
            return

        self.game.make_choice(player, choice)
        await interaction.response.send_message(f"You chose {choice}!", ephemeral=True)

        if self.game.is_ready():
            winner = self.game.determine_winner()
            p1, p2 = self.game.players
            c1, c2 = self.game.choices[p1], self.game.choices[p2]
            d = {'rock': ':bricks:', 'paper': ':roll_of_paper:', 'scissors': ':scissors:'}
            await interaction.followup.send(f"{p1.mention}{d[c1]} **--** {p2.mention}{d[c2]}")
            if winner:
                await interaction.followup.send(f"{winner.mention} **wins**!")
            else:
                await interaction.followup.send("It's a **tie**!")
            self.stop()

class RPS(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="rps")
    async def start_rps(self, ctx):
        self.game = RPSGame()
        self.view = RPSView(self.game)

        self.game.add_player(ctx.author)
        await ctx.send("Rock-Paper-Scissors game started! Another player must join!", view=self.view)

async def setup(bot):
    await bot.add_cog(RPS(bot))