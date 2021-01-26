import discord
from discord_slash import SlashCommand
from discord_slash.utils import manage_commands  

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pymongo import MongoClient
import class_scheduling
import datetime


client = discord.Client()
slash = SlashCommand(client, auto_register=True, auto_delete=True)

mongoclient = MongoClient("mongodb+srv://BotOwner:M26ToshtFDBuT6SY@schedule-bot.c6ats.mongodb.net/discord"
                          "?retryWrites=true&w=majority")
db = mongoclient.discord


guild_ids = [687499582459871242, 748887953497129052, 677353989632950273]

mainsched = AsyncIOScheduler()
mainsched.start()

@slash.slash(name="set-interval-message",
             description="Set a schedule with specific duration and message",
             guild_ids=guild_ids,
             options=[
                 manage_commands.create_option(
                     name="duration",
                     description="Duration of the total interval in minutes. Max value: 360 ",
                     option_type=4,
                     required=True
                 ),
                 manage_commands.create_option(
                     name="increment",
                     description="Increment in minutes. Minimum value: 3",
                     option_type=4,
                     required=True
                 ),
                 manage_commands.create_option(
                     name="message",
                     description="Overwrite your messages in message matrix",
                     option_type=3,
                     required=False,
                 )
             ]
             )
async def set_schedule(ctx, duration, increment, message=None):
    user_id = f"{ctx.author}"

    # Establish the bounds

    if increment < 2:
        increment = 2
    if duration > 360:
        duration = 360
    elif duration < 1:
        await ctx.send(content="Please enter a valid duration.")
        return

    doc = db.user_data.find_one({"user id": user_id})

    # Does their record exist?

    if doc == None:
        await ctx.send(content=f"Please register your information with 'define-self'")
        return

    # Message matrix or defined message
    if message:
        message_check = True
        message = message.split(',')
        logging.info(message)
        individual = class_scheduling.ScheduledPerson(message, doc["contact information"])
    else:
        message_check = None
        logging.info(doc["message matrix"])
        individual = class_scheduling.ScheduledPerson(doc["message matrix"], doc["contact information"])

    individual.operate_scheduler(duration, increment)

    for time, msg in individual.time_dict.items():
        logging.info(f" Message: {msg}, {time}")

        mainsched.add_job(class_scheduling.ScheduledPerson.send_message, 'date', run_date=time, args=(individual, msg),
                          misfire_grace_time=500)

    if message:
        await ctx.send(content=f"Message created: {message}")
    else:
        await ctx.send(content=f"Message created: {doc['message matrix']}")

    # Log data to a database
    info = {
        "initial time": str(individual.fm),
        "end time": str(individual.fm + datetime.timedelta(minutes=duration)),
        "duration": duration,
        "increment": increment,
        "number of messages registered": len(individual.time_dict),
        "message specified?": message_check
    }

    db.bot_usage.insert_one(info)


@slash.slash(name="define-self",
             description="Initialize your details",
             guild_ids=guild_ids,
             options=[
                 manage_commands.create_option(
                     name="contact_info",
                     description="Your phone number's email address: {your carrier} SMS Gateway",
                     option_type=3,
                     required=True
                 ),
                 manage_commands.create_option(
                     name="message_matrix",
                     description="The list of messages you would like to run",
                     option_type=3,
                     required=False
                 )
             ]
             )
async def define_self(ctx, contact_info, message_matrix=None):
    user_id = f"{ctx.author}"

    message_matrix = message_matrix.split(',')

    db.user_data.find_one_and_update({"user id": user_id},
                                   {"$set": {
                                       "contact information": contact_info,
                                       "message matrix": message_matrix}},
                                   upsert=True)

    await ctx.send(content=f"Contact information registered: {contact_info} | {message_matrix}")


client.run("ODAyMzYzNDM1MzM3MjUyODY0.YAuJLg.gC0EWPOtik2ct2jXO5gaNxw66pE")
