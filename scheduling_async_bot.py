import discord
from discord_slash import SlashCommand
from discord_slash.utils import manage_commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.mongodb import MongoDBJobStore
from apscheduler.jobstores.base import JobLookupError
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_REMOVED
from pymongo import MongoClient
import class_scheduling
from datetime import timedelta, datetime
from uuid import uuid4
import logging, coloredlogs

# TODO: prioritize email in presenation
# TODO: fix the formatting on Daily-reminder
# Todo: figure out if the class shit is even efficient at all probs not lmfao
# TODO: make the config stuff a function
# TODO: inndex removals
# TODO: if name == 'main' ?
# TODO: Interval message redundant? evaluate
# lots of calls to datetime.now() :/

# Initialization stuff

coloredlogs.install()
client = discord.Client()
slash = SlashCommand(client, auto_register=True, auto_delete=True)
mongoclient = MongoClient("mongodb+srv://BotOwner:M26ToshtFDBuT6SY@schedule-bot.c6ats.mongodb.net/discord"
                          "?retryWrites=true&w=majority")

db = mongoclient.discord

guild_ids = [687499582459871242, 748887953497129052, 677353989632950273]

jobstores = {
    'default': MongoDBJobStore(client=mongoclient, collection="scheduled-job")
}
mainsched = AsyncIOScheduler(jobstores=jobstores, timezone="America/New_York")
mainsched.start()


def jobitem_removed(event):
    splice = event.job_id.split('user')
    job_id = splice[0]
    user_id = int(splice[1])

    db.bot_usage.find_one_and_update({'user id': user_id},
                                     {'$pull': {'active jobs': job_id}})
    logging.info(f"event: {event}, listener activated")


mainsched.add_listener(jobitem_removed, EVENT_JOB_EXECUTED | EVENT_JOB_REMOVED)


# serious commands

# lots of calls to datetime.now :/ maybe a decorator can fix that?
@slash.slash(name="date-message", description="send a message at a specific date and time", guild_ids=guild_ids,
             options=[
                 manage_commands.create_option(
                     name="message",
                     description="message to deliver",
                     option_type=3,
                     required=True
                 ),
                 manage_commands.create_option(
                     name="time_of_day",
                     description="time of day - HH:MM",
                     option_type=3,
                     required=True
                 ),
                 manage_commands.create_option(
                     name="day_of_month",
                     description="day of the month between 1 and 31, defaults current day",
                     option_type=4,
                     required=False
                 ),
                 manage_commands.create_option(
                     name="month_of_year",
                     description="month of the year between 1 and 12, defaults to current month",
                     option_type=4,
                     required=False
                 ),
                 manage_commands.create_option(
                     name="year",
                     description="year format : 2021, defaults to current year",
                     option_type=4,
                     required=False
                 )
             ])
async def date(ctx, message, time_of_day, day_of_month=datetime.now().day, month_of_year=datetime.now().month,
               year=datetime.now().year):
    user_id = ctx.author
    id_ = uuid4().hex + "user" + str(user_id)
    doc = db.user_data.find_one({"user id": user_id})
    if doc is None:
        await ctx.send(content=f"Please register your information with 'define-self'")
        return
    individual = class_scheduling.ScheduledPerson(message, doc["contact information"])

    # check if am or pm are used, set lower and remove spaces: 9:08 pm == 9:08pm
    time_of_day = time_of_day.lower().replace(' ', '')
    if "am" in time_of_day or "pm" in time_of_day:
        time = datetime.strptime(time_of_day, '%I:%M%p')
    else:
        time = datetime.strptime(time_of_day, '%H:%M')

    # define the time of delivery
    propertime = datetime(year, month_of_year, day_of_month, time.hour, time.minute)

    # would use walrus, but heroku doesnt likey

    if (x := datetime.now()) > propertime:
        await ctx.send(
            content=f"Chosen time: **{propertime.strftime('%X')}** is earlier than current time: **{x.strftime('%X')}**. Please choose a valid date")
        return

    mainsched.add_job(class_scheduling.ScheduledPerson.send_message, 'date', run_date=propertime,
                      args=[individual, message], id=id_)

    db.bot_usage.find_one_and_update({'user id': user_id},
                                     {'$push': {'active jobs': id_}})

    await ctx.send(content=f"**{message}** Message sent, due for {propertime}.")


@slash.slash(name="interval-message", description="repeat a message for a specified duration/interval",
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
    id_ = uuid4().hex + "user" + str(user_id)
    doc = db.user_data.find_one({"user id": user_id})
    if doc is None:
        await ctx.send(content=f"Please register your information with 'define-self'")
        return

    individual = class_scheduling.ScheduledPerson(message, doc["contact information"])
    mainsched.add_job(class_scheduling.ScheduledPerson.send_message, 'interval', minutes=duration,
                      args=(individual, message), misfire_grace_time=500, replace_existing=True, id=id_)

    db.bot_usage.find_one_and_update({'user id': user_id},
                                     {'$push': {'active jobs': id_}})

    await ctx.send(content=f"Message created: {message}", complete_hidden=True)


@slash.slash(name="define-self", description="Initialize your details", guild_ids=guild_ids,
             options=[
                 manage_commands.create_option(
                     name="contact_info",
                     description="Your phone number's email address: {your carrier} SMS Gateway",
                     option_type=3,
                     required=True
                 ), ])
async def define_self(ctx, contact_info):
    user_id = ctx.author
    db.user_data.find_one_and_update({"user id": user_id},
                                     {"$set": {"contact information": contact_info}},
                                     upsert=True)

    db.bot_usage.find_one_and_update(
        {'user id': user_id},
        {"$setOnInsert": {'active jobs': []}},
        upsert=True
    )

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
    id_ = uuid4().hex + "user" + str(user_id)
    doc = db.user_data.find_one({"user id": user_id})
    if doc is None:
        await ctx.send(content=f"Please register your information with 'define-self'")
        return

    # initialize the class
    individual = class_scheduling.ScheduledPerson(message, doc["contact information"])
    mainsched.add_job(class_scheduling.ScheduledPerson.send_message, 'cron', args=(individual, message), hour=hour,
                      minute=minute, misfire_grace_time=500, replace_existing=True, id=id_)
    db.bot_usage.find_one_and_update({'user id': user_id},
                                     {'$push': {'active jobs': id_}})

    await ctx.send(content=f"Schedule created: at {hour}:{minute} send {message}")


@slash.slash(name="between-two-times", description='send messages at an interval between two times throughout the day',
             guild_ids=guild_ids,
             options=[
                 manage_commands.create_option(
                     name="time_1",
                     description="Initial time. Format in 24h | 9:04",
                     option_type=3,
                     required=True
                 ),
                 manage_commands.create_option(
                     name="time_2",
                     description="Final time. Format in 24h | 23:30",
                     option_type=3,
                     required=True
                 ),
                 manage_commands.create_option(
                     name="interval",
                     description="Time between messages in minutes, minimum: 20 minutes",
                     option_type=4,
                     required=True
                 ),
                 manage_commands.create_option(
                     name="message",
                     description="Message to be sent",
                     option_type=3,
                     required=True
                 ),
                 manage_commands.create_option(
                     name="repeating",
                     description="Repeat daily?",
                     option_type=3,
                     required=True,
                     choices=[
                         manage_commands.create_choice(
                             name="True",
                             value="True"
                         ),
                         manage_commands.create_choice(
                             name="False",
                             value="False"
                         )
                     ]
                 )
             ])
async def between_times(ctx, time_1, time_2, interval, message, repeating):
    user_id = ctx.author
    id_ = uuid4().hex + "user" + str(user_id)
    doc = db.user_data.find_one({"user id": user_id})
    if doc is None:
        await ctx.send(content=f"Please register your information with 'define-self'")
        return

    individual = class_scheduling.ScheduledPerson(message, doc["contact information"])

    # Format the times
    tomorrow = datetime.now() + timedelta(days=1, hours=0, minutes=0)
    time_1 = datetime.strptime(time_1, '%H:%M')
    time_2 = datetime.strptime(time_2, '%H:%M')
    today = datetime.today()
    time_1 = datetime(today.year, today.month, today.day, time_1.hour, time_1.minute)
    time_2 = datetime(today.year, today.month, today.day, time_2.hour, time_2.minute)

    between_times_interval(individual, message, time_1, time_2, interval, user_id)

    if repeating == 'True':
        # make sure that the call for repeating starts the next day, not today, not two days from now
        if today > time_1:
            mainsched.add_job(between_times_interval, 'cron', hour=time_1.hour, minute=time_1.minute,
                              args=(individual, message, time_1, time_2, interval, user_id),
                              misfire_grace_time=500, replace_existing=True, id=id_)
        elif today < time_1:
            mainsched.add_job(between_times_interval, 'cron', start_date=tomorrow, hour=time_1.hour,
                              minute=time_1.minute,
                              args=(individual, message, time_1, time_2, interval, user_id),
                              misfire_grace_time=500, replace_existing=True, id=id_)

        db.bot_usage.find_one_and_update({'user id': user_id},
                                         {'$push': {'active jobs': id_}})

    await ctx.send(
        content=f"Message: {message} \nTime: from **{time_1.strftime('%H:%M')}** to **{time_2.strftime('%H:%M')}** Repeating: {repeating}")


# error comes up when the function is placed in the above function, so it's here /shrug
def between_times_interval(individual, message, time_1, time_2, interval, user_id):
    id_ = uuid4().hex + "user" + str(user_id)
    today = datetime.today()
    time_1 = datetime(today.year, today.month, today.day, time_1.hour, time_1.minute)
    time_2 = datetime(today.year, today.month, today.day, time_2.hour, time_2.minute)
    if time_1 > time_2:
        time_2 += timedelta(days=1, hours=0, minutes=0)

    mainsched.add_job(class_scheduling.ScheduledPerson.send_message, 'interval', minutes=interval,
                      start_date=time_1,
                      end_date=time_2,
                      args=(individual, message), misfire_grace_time=500, replace_existing=True, id=id_)

    db.bot_usage.find_one_and_update({'user id': user_id},
                                     {'$push': {'active jobs': id_}})


@slash.slash(name="get-schedule", description="acquire your listed schedule", guild_ids=guild_ids)
async def get_schedule(ctx):
    # the verification process
    user_id = ctx.author
    doc = db.user_data.find_one({"user id": user_id})
    if doc is None:
        await ctx.send(content=f"Please register your information with 'define-self'")
        return

    temp = db.bot_usage.find_one({'user id': user_id})
    str_out = "No jobs found"
    if temp['active jobs']:
        str_out = ""
        job_count = 1
        for value in temp['active jobs']:
            job = mainsched.get_job(value)

            # message is always the second arg
            jobtime = job.next_run_time
            ymd = f"{jobtime.strftime('%b')} {jobtime.day} {jobtime.year}"
            str_out += f"*Job: {job_count}* \n" \
                       f"**Next run time**: {jobtime.strftime('%A')} {jobtime.hour % 12}:{jobtime.strftime('%M')} {jobtime.strftime('%p')} | {ymd}\n" \
                       f"**Message**: {job.args[1]} \n" \
                       f"**Trigger**: {job.trigger} \n\n"

            job_count += 1

    await ctx.send(content=str_out)


@slash.slash(name="remove-schedule", description="remove all listed jobs", guild_ids=guild_ids)
async def remove_schedule(ctx):
    # TODO: allow for index deletion
    # verification process
    user_id = ctx.author
    doc = db.user_data.find_one({"user id": user_id})
    if doc is None:
        await ctx.send(content=f"Please register your information with 'define-self'")
        return

    temp = db.bot_usage.find_one({'user id': user_id})
    for value in temp['active jobs']:
        try:
            mainsched.remove_job(value, 'default')
            db.bot_usage.update_one({'user id': user_id},
                                    {'$pull': {'active jobs': value}})
        except JobLookupError:
            db.bot_usage.update_one({'user id': user_id},
                                    {'$pull': {'active jobs': value}})

    await ctx.send(content="Command executed, listed jobs removed")


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
