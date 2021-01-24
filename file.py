import discord
import logging

client = discord.Client()

@client.event
async def on_ready():
    logging.info(f"LOGGED IN THIS BITCH AS {client}")

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith('!hello'):
        await message.channel.send('Hello!')

@client.event
async def on_message(message):
    logging.info(f"author: {str(message.author)[0:-5]}, message: {message.content} ")

client.run('ODAyMzYzNDM1MzM3MjUyODY0.YAuJLg.cpNJWwAbavt8psSJaitRgwte4is')
