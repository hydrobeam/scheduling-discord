import discord
from discord_slash import SlashCommand
import random
from discord_slash.utils import manage_commands  # Allows us to manage the command settings.

client = discord.Client()
slash = SlashCommand(client, auto_register=True, auto_delete=True)

guild_ids = [687499582459871242, 748887953497129052, 677353989632950273]  # Put your server ID in this array.


@slash.slash(name="ping", guild_ids=guild_ids)
async def _ping(ctx):  # Defines a new "context" (ctx) command called "ping."
    await ctx.send(content=f"Pong! ({client.latency * 1000}ms)")


@slash.slash(name="ding", guild_ids=guild_ids)
async def _dong(ctx):
    await ctx.send(content=f"your dog?")


@slash.slash(name="roll", guild_ids=guild_ids)
async def roll(ctx):
    await ctx.send(content=f"your roll: {random.randint(1, 6)}")


@slash.slash(name="flip",
             description="flips a coin",
             guild_ids=guild_ids
             )
async def flip(ctx):
    roll = random.randint(1, 2)
    if roll == 1:
        await ctx.send(content="heads")
    elif roll == 2:
        await ctx.send(content="tails")


@slash.slash(name="sum-between-numbers",
             description="python in the flesh",
             guild_ids=guild_ids,
             options=[
                 manage_commands.create_option(
                     name="num_1",
                     description="minimum range value",
                     option_type=4,
                     required=True
                 ),
                 manage_commands.create_option(
                     name="num_2",
                     description="maximum range value",
                     option_type=4,
                     required=True
                 ),

             ])
async def sum_numbers(ctx, num_1, num_2):
    if num_1 > num_2:
        op1 = num_2
        op2 = num_1
    else:
        op1 = num_1
        op2 = num_2

    sloppy = round((op2 - op1 + 1)*(op1 + op2) / 2)
    await ctx.send(content=f"sum of numbers between {op1} and {op2}: {sloppy}")


client.run("ODAyMzYzNDM1MzM3MjUyODY0.YAuJLg.cpNJWwAbavt8psSJaitRgwte4is")
