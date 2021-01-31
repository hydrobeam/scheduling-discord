import discord
from discord_slash import SlashCommand
from discord_slash.utils import manage_commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.mongodb import MongoDBJobStore
from pymongo import MongoClient, DESCENDING
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
ap = mongoclient['apscheduler']['scheduled-job']
db = mongoclient.discord
sched = mongoclient.apshceduler

guild_ids = [687499582459871242, 748887953497129052, 677353989632950273]

jobstores = {
    'default':MongoDBJobStore(client=mongoclient, collection="scheduled-job")
}
mainsched = AsyncIOScheduler(jobstores=jobstores)
mainsched.start()



# serious commands

@slash.slash(name="interval-message",
             description="Set a schedule with specific duration and message",
             guild_ids=guild_ids,
             options=[
                 manage_commands.create_option(
                     name="duration",
                     description="duration of the total interval in minutes. Max value: 720 (12 hours) ",
                     option_type=4,
                     required=True
                 ),
                 manage_commands.create_option(
                     name="time_interval",
                     description="time_interval in minutes. Minimum value: 15",
                     option_type=4,
                     required=True
                 ),
                 manage_commands.create_option(
                     name="message",
                     description="message you would like delivered",
                     option_type=3,
                     required=True,
                 )
             ]
             )
async def interval(ctx, duration, increment, message):
    # Establish the bounds
    if increment < 15:
        increment = 15
    if duration > 720:
        duration = 720
    elif duration < 1:
        await ctx.send(content="Please enter a valid duration.")
        return

    # Does their record exist?
    user_id = ctx.author
    doc = db.user_data.find_one({"user id": user_id})
    if doc is None:
        await ctx.send(content=f"Please register your information with 'define-self'")
        return

    """
    message = message.split(',')
    
    individual.operate_scheduler(duration, increment)

    for time, msg in individual.time_dict.items():
        mainsched.add_job(class_scheduling.ScheduledPerson.send_message, 'date', run_date=time, args=(individual, msg),
                          misfire_grace_time=500, replace_existing=True, id=user_id)"""
    str_id = str(user_id) + "interval"

    individual = class_scheduling.ScheduledPerson(message, doc["contact information"])
    mainsched.add_job(class_scheduling.ScheduledPerson.send_message, 'interval', minutes=duration,
                      args=(individual, message), misfire_grace_time=500, replace_existing=True, id=str_id)
    await ctx.send(content=f"Message created: {message}", complete_hidden=True)


"""
    # Log data to a database
    info = {
        "id": job.id,
        "expireAt": str(individual.fm + datetime.timedelta(minutes=duration)),
        "job type": "interval",
    }

    db.bot_usage.insert_one(info)
    db.bot_usage.create_index('expireAt', {'expireAfterSeconds': 0}, background=True)
"""


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
             ]
             )
async def define_self(ctx, contact_info):
    user_id = ctx.author

    db.user_data.find_one_and_update({"user id": user_id},
                                     {"$set": {"contact information": contact_info}},
                                     upsert=True)

    await ctx.send(content=f"Contact information registered: {contact_info}", complete_hidden=True)


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
                     required=True
                 )
             ])
async def daily_reminder(ctx, hour, minute, message):
    # init data
    user_id = ctx.author
    doc = db.user_data.find_one({"user id": user_id})
    if doc is None:
        await ctx.send(content=f"Please register your information with 'define-self'")
        return

    individual = class_scheduling.ScheduledPerson(message, doc["contact information"])
    mainsched.add_job(class_scheduling.ScheduledPerson.send_message, 'cron', args=(individual, message), hour=hour,
                      minute=minute, misfire_grace_time=500, replace_existing=True, id=user_id)

    await ctx.send(content="Command under maintenance")
    pass


@slash.slash(name="get-schedule", description="acquire your listed schedule", guild_ids=guild_ids,
             options=[
                 manage_commands.create_option(
                     name="schedule_type",
                     description="identify the type of job you would like see",
                     required=True,
                     option_type=3,
                     choices=[
                         manage_commands.create_choice(
                             name="interval",
                             value="interval"
                         ),
                         manage_commands.create_choice(
                             name="daily",
                             value="daily"
                         ),
                         manage_commands.create_choice(
                             name="timed",
                             value="timed"
                         ),
                         manage_commands.create_choice(
                             name="all",
                             value="all"
                         )]
                 )
             ])
async def get_schedule(ctx, schedule_type):
    # the verification process
    user_id = ctx.author
    doc = db.user_data.find_one({"user id": user_id})
    if doc is None:
        await ctx.send(content=f"Please register your information with 'define-self'")
        return

    if schedule_type == "all":
        str_out = "No jobs found."
        query_result = ap.find({'_id': {'$regex': '.*' + str(user_id) + '.*'}})

        for item in query_result:
            # find the type of job it is, separating it from the string
            item_type = ''.join(i for i in item['_id'] if not i.isdigit())

            # format the time
            t = datetime.datetime.fromtimestamp((item["next_run_time"]))
            formatted_time = f" Job type: {item_type.title()} ~~ Next due message: {t.hour}:{t.strftime('%M')} {t.strftime('%p')}"
            str_out += formatted_time
    else:
        # get the query

        query_result = ap.find_one({'_id': str(user_id) + schedule_type})

        # format the time
        try:
            t = datetime.datetime.fromtimestamp((query_result['next_run_time']))
        except TypeError:
            await ctx.send(content="No jobs found.")
            return
        str_out = f" Job type: {schedule_type.title()} ~~ Next due message: {t.hour}:{t.strftime('%M')} {t.strftime('%p')}"

    await ctx.send(content=str_out)
    pass


@slash.slash(name="delete-schedule", description="remove all listed jobs", guild_ids=guild_ids,
             options=[
                 manage_commands.create_option(
                     name="schedule_type",
                     description="identify the type of job you would like deleted",
                     required=True,
                     option_type=3,
                     choices=[
                         manage_commands.create_choice(
                             name="interval",
                             value="interval"
                         ),
                         manage_commands.create_choice(
                             name="daily",
                             value="daily"
                         ),
                         manage_commands.create_choice(
                             name="timed",
                             value="timed"
                         ),
                         manage_commands.create_choice(
                             name="all",
                             value="all"
                         )]
                 )
             ])
async def remove_schedule(ctx, schedule_type):
    # verification process
    user_id = ctx.author
    doc = db.user_data.find_one({"user id": user_id})
    if doc is None:
        await ctx.send(content=f"Please register your information with 'define-self'")
        return

    if schedule_type == "all":
        ap.delete_many({'_id': {'$regex': '.*' + str(user_id) + '.*'}})
    else:
        ap.delete_one({'_id': str(user_id) + schedule_type})

    await ctx.send(content="Command executed, listed jobs removed")
    pass

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



client.run("ODAyMzYzNDM1MzM3MjUyODY0.YAuJLg.gC0EWPOtik2ct2jXO5gaNxw66pE")
