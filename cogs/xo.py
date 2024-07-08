import discord
from discord import Client, ButtonStyle, Interaction, Embed
from discord.ext import commands
from discord.ui import Button, View



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

class XO(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='xo')
    async def tic_tac_toe(self, ctx):
        self.view = TicTacToe(ctx.author)
        await ctx.send('Tic-Tac-Toe: **X** goes first. Click the button below to join as **O**.', view=self.view)



async def setup(bot):
    await bot.add_cog(XO(bot))