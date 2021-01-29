import discord
from discord_slash import SlashCommand
from discord_slash.utils import manage_commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.mongodb import MongoDBJobStore
from pymongo import MongoClient
import class_scheduling
import datetime

# TODO: Add cron job
# TODO: display scheduled messages
# TODO: remove scheduled
# TODO: prioritize email in presenation
# TODO: Integrate twiliio send grid in class_scheduling -- wait maybe not lmao
# TODO: figure out how to make gmail work aaaaaaaaaaa Ig it's done 😳

client = discord.Client()
slash = SlashCommand(client, auto_register=True, auto_delete=True)

mongoclient = MongoClient("mongodb+srv://BotOwner:M26ToshtFDBuT6SY@schedule-bot.c6ats.mongodb.net/discord"
                          "?retryWrites=true&w=majority")
db = mongoclient.discord

guild_ids = [687499582459871242, 748887953497129052, 677353989632950273]

jobstores = {
    'default': MongoDBJobStore(client=mongoclient, collection="scheduled-job")
}
mainsched = AsyncIOScheduler(jobstores=jobstores)
mainsched.start()

# fun commands

@slash.slash(name="ping", guild_ids=guild_ids)
async def _ping(ctx):  # Defines a new "context" (ctx) command called "ping."
    await ctx.send(content=f"Pong! ({client.latency * 1000}ms)")

@slash.slash(name="hello", description="say hello!", guild_ids=guild_ids)
async def hello(ctx):
    await ctx.send(content="hello :)")

@slash.slash(name="bye", description="say bye bye :(", guild_ids=guild_ids)
async def bye(ctx):
    await ctx.send(content="bye bye :o")

# serious commands

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
    # Establish the bounds
    if increment < 2:
        increment = 2
    if duration > 360:
        duration = 360
    elif duration < 1:
        await ctx.send(content="Please enter a valid duration.")
        return

    # Does their record exist?
    user_id = ctx.author
    doc = db.user_data.find_one({"user id": user_id})
    # Does their record exist?
    if doc is None:
        await ctx.send(content=f"Please register your information with 'define-self'")
        return

    if message:
        message_check = True
        message = message.split(',')
        individual = class_scheduling.ScheduledPerson(message, doc["contact information"])
    else:
        message_check = None
        individual = class_scheduling.ScheduledPerson(doc["message matrix"], doc["contact information"])

    individual.operate_scheduler(duration, increment)

    for time, msg in individual.time_dict.items():
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
    user_id = ctx.author

    if message_matrix:
        message_matrix = message_matrix.split(',')

    db.user_data.find_one_and_update({"user id": user_id},
                                     {"$set": {
                                         "contact information": contact_info,
                                         "message matrix": message_matrix}},
                                     upsert=True)

    await ctx.send(content=f"Contact information registered: {contact_info} || Message matrix: \n{message_matrix}",
                   complete_hidden=True)


@slash.slash(name="daily-reminder", description="Set a daily reminder", guild_ids=guild_ids,
             options=[
                 manage_commands.create_option(
                     name="hour",
                     description="specify hour, 24h clock",
                     option_type=4,
                     required=True
                 ),
                 manage_commands.create_option(
                     name="minute",
                     description="specify minute",
                     option_type=4,
                     required=True
                 ),
                 manage_commands.create_option(
                     name="message",
                     description="specify message, uses message matrix value if empty",
                     option_type=3,
                     required=False
                 )
             ])
async def daily_reminder(ctx, hour, minute, message):
    user_id = ctx.author
    doc = db.user_data.find_one({"user id": user_id})
    # Does their record exist?
    if doc is None:
        await ctx.send(content=f"Please register your information with 'define-self'")
        return

    await ctx.send(content="Command under maintenance")
    pass


@slash.slash(name="get-schedule", description="acquire your listed schedule", guild_ids=guild_ids)
async def get_schedule(ctx):
    user_id = ctx.author
    doc = db.user_data.find_one({"user id": user_id})
    # Does their record exist?
    if doc is None:
        await ctx.send(content=f"Please register your information with 'define-self'")
        return
    await ctx.send(content="Command under maintenance")
    pass


@slash.slash(name="delete-schedule", description="remove all listed jobs", guild_ids=guild_ids)
async def remove_schedule(ctx):
    user_id = ctx.author
    doc = db.user_data.find_one({"user id": user_id})
    # Does their record exist?
    if doc is None:
        await ctx.send(content=f"Please register your information with 'define-self'")
        return

    await ctx.send(content="Command under maintenance")
    pass


client.run("ODAyMzYzNDM1MzM3MjUyODY0.YAuJLg.gC0EWPOtik2ct2jXO5gaNxw66pE")
