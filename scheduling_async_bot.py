import discord
from discord_slash import SlashCommand
from discord_slash.utils import manage_commands

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.mongodb import MongoDBJobStore
from apscheduler.jobstores.base import JobLookupError
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_REMOVED
from pymongo import MongoClient

from datetime import timedelta, datetime
from pytz import timezone
from uuid import uuid4
import logging

import utility
from utility import format_dt, short_dt

from pprint import pprint

# TODO: prioritize email in presenation
# TODO: fix the formatting on Daily-reminder, consider creating a datetime object?
# TODO: make the config stuff a function
# TODO: inndex removals
# TODO: if name == 'main' ?
# TODO: Interval message redundant? evaluate
# TODO: bdtweentwo tiems tomorow

# Initialization stuff

# coloredlogs.install()
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
    # the listener checks for when a job is removed, or executed and removes it from 'active jobs'

    user_id = int(event.job_id.split('user')[1])
    job = mainsched.get_job(event.job_id)
    current_time = datetime.now(timezone('America/New_York'))

    try:
        # if end_date exists, check if end_date has already passed, then remove the job if True. if no end_date,
        # or end_date not passed, execute the function
        if x := job.trigger.end_date:
            if current_time >= x:
                # the end_date has passed, remove hte job
                pass
            else:
                # the end_date has note yet passed, do not remove the job
                return
        else:
            # there is no end_date, the job never ends
            return
    except AttributeError:
        # this is a date job, proceed as normal remove the job
        pass
    db.bot_usage.find_one_and_update({'user id': user_id},
                                     {'$pull': {'active jobs': event.job_id}})
    logging.info(f"event: {event}, listener activated")


mainsched.add_listener(jobitem_removed, EVENT_JOB_EXECUTED | EVENT_JOB_REMOVED)


# serious commands

def basic_init(ctx):
    user_id = ctx.author
    id_ = uuid4().hex + "user" + str(user_id)
    doc = db.user_data.find_one({"user id": user_id})
    user_tz = doc['timezone']
    if doc is None:
        await ctx.send(content=f"Please register your information with 'define-self'")
        return
    else:
        return user_id, id_, doc, user_tz


@slash.slash(name="date-mess", description="send a message at a specific date and time", guild_ids=guild_ids,
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
async def date_message(ctx, message, time_of_day, day_of_month=None, month_of_year=None,
                       year=None):
    try:
        user_id, id_, doc, user_tz = basic_init(ctx)
    except TypeError:
        return
    if day_of_month is None:
        day_of_month = datetime.now(timezone('America/New_York')).day
    if month_of_year is None:
        month_of_year = datetime.now(timezone('America/New_York')).month
    if year is None:
        year = datetime.now(timezone('America/New_York')).year


    # check if am or pm are used, set lower and remove spaces: 9:08 pm == 9:08pm
    time_of_day = time_of_day.lower().replace(' ', '')
    if "am" in time_of_day or "pm" in time_of_day:
        time = datetime.strptime(time_of_day, '%I:%M%p')
    else:
        time = datetime.strptime(time_of_day, '%H:%M')

    # define the time of delivery, causews my issue
    active_tz = timezone('America/New_York')
    propertime = active_tz.localize(datetime(year, month_of_year, day_of_month, time.hour, time.minute))

    # check if in the past
    if (x := datetime.now(timezone('America/New_York'))) > propertime:
        await ctx.send(
            content=f"Chosen time: **{format_dt(propertime)}** is earlier than current time: **{format_dt(x)}"
                    f"**. Please choose a valid date")
        return

    mainsched.add_job(utility.send_message, 'date', run_date=propertime,
                      args=(message, doc['contact information']), id=id_)

    # add to active jobs
    db.bot_usage.find_one_and_update({'user id': user_id},
                                     {'$push': {'active jobs': id_}})

    await ctx.send(content=f"**{message}** Message scheduled, due for {format_dt(propertime)}.")


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
    try:
        user_id, id_, doc, user_tz = basic_init(ctx)
    except TypeError:
        return

    end_date = datetime.now(timezone('America/New_York') + timedelta(minutes=duration))
    mainsched.add_job(utility.send_message, 'interval', minutes=increment, end_date=end_date,
                      args=(message, doc['contact information']), misfire_grace_time=500, replace_existing=True, id=id_)

    # add to  active jobs
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
                 ),
                 manage_commands.create_option(
                     name="timezone",
                     description="tz timezone, continent+city|samples: 'America/New_York', 'America/Los_Angeles', 'Asia/Tokyo', see https://bit.ly/3jnoCRE for full list (default = 'America/New_York' or EST)",
                     option_type=3,
                     required=False
                 )
             ])
async def define_self(ctx, contact_info, timezone='America/New_York'):
    user_id = ctx.author
    # log the user's information in a database
    with open('timezones.txt', 'r') as file:
        if timezone not in file:
            await ctx.send(f"*{timezone}* is not a  tz timezone, please pick a valid neighbour")
            return

    db.user_data.find_one_and_update({"user id": user_id},
                                     {"$set": {"contact information": contact_info, "timezone": timezone}},
                                     upsert=True)

    db.bot_usage.find_one_and_update(
        {'user id': user_id},
        {"$setOnInsert": {'active jobs': []}},
        upsert=True
    )

    await ctx.send(content=f"Information registered: {contact_info}, {timezone}", complete_hidden=True)


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
    try:
        user_id, id_, doc, user_tz = basic_init(ctx)
    except TypeError:
        return

    # initialize the class
    mainsched.add_job(utility.send_message, 'cron', args=(message, doc['contact information']), hour=hour,
                      minute=minute, misfire_grace_time=500, replace_existing=True, id=id_)
    db.bot_usage.find_one_and_update({'user id': user_id},
                                     {'$push': {'active jobs': id_}})

    await ctx.send(content=f"Schedule created: for {hour}:{minute} send {message}")


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
    try:
        user_id, id_, doc, user_tz = basic_init(ctx)
    except TypeError:
        return
    # Format the times
    tomorrow = datetime.now(tz=user_tz) + timedelta(days=1, hours=0, minutes=0)
    time_1 = datetime.strptime(time_1, '%H:%M')
    time_2 = datetime.strptime(time_2, '%H:%M')
    today = datetime.now(tz=user_tz)
    time_1 = today.replace(hour=time_1.hour, minute=time_1.minute)
    time_2 = today.replace(hour=time_2.hour, minute=time_2.minute)

    between_times_interval(message, doc['contact information'], time_1, time_2, interval, user_id)

    if repeating == 'True':
        # make sure that the call for repeating starts the next day, not today, not two days from now
        if today > time_1:
            mainsched.add_job(between_times_interval, 'cron', hour=time_1.hour, minute=time_1.minute,
                              args=(message, doc['contact information'], time_1, time_2, interval, user_id, user_tz),
                              misfire_grace_time=500, replace_existing=True, id=id_)
        elif today < time_1:
            mainsched.add_job(between_times_interval, 'cron', start_date=tomorrow, hour=time_1.hour,
                              minute=time_1.minute,
                              args=(message, doc['contact information'], time_1, time_2, interval, user_id, user_tz),
                              misfire_grace_time=500, replace_existing=True, id=id_)

        db.bot_usage.find_one_and_update({'user id': user_id},
                                         {'$push': {'active jobs': id_}})

    await ctx.send(
        content=f"Message: {message} \nTime: from **{time_1.strftime('%H:%M')}** to **{time_2.strftime('%H:%M')}** "
                f"Repeating: {repeating}")


# error comes up when the function is placed in the above function, so it's here /shrug
def between_times_interval(message, contact, time_1, time_2, interval, user_id, user_tz):
    id_ = uuid4().hex + "user" + str(user_id)
    today = datetime.now(tz=user_tz)
    time_1 = today.replace(hour=time_1.hour, minute=time_1.minute)
    time_2 = today.replace(hour=time_2.hour, minute=time_2.minute)
    if time_1 > time_2:
        time_2 += timedelta(days=1, hours=0, minutes=0)

    mainsched.add_job(utility.send_message, 'interval', minutes=interval,
                      start_date=time_1,
                      end_date=time_2,
                      args=(message, contact), misfire_grace_time=500, replace_existing=True, id=id_)

    db.bot_usage.find_one_and_update({'user id': user_id},
                                     {'$push': {'active jobs': id_}})


@slash.slash(name="get-sched", description="acquire your listed schedule", guild_ids=guild_ids)
async def get_schedule(ctx):
    # the verification process
    try:
        user_id, id_, doc, user_tz = basic_init(ctx)
    except TypeError:
        return

    # find the users active jobs
    temp = db.bot_usage.find_one({'user id': user_id})
    str_out = "No jobs found"
    if temp['active jobs']:
        str_out = ""
        job_count = 1
        for value in temp['active jobs']:
            # get the job and extract data from  it
            job = mainsched.get_job(value)
            # message is always the second arg
            jobtime = job.next_run_time
            # details about the trigger
            trig = job.trigger

            # get jobtype
            jobtrig = f" {str(trig).split('[')[0]}"

            # welcome to the ghetto, getting vars from trigger
            try:
                if x := short_dt(trig.start_date):
                    jobtrig += f" | **Start time**: {x} "
                if x := short_dt(trig.end_date):
                    jobtrig += f"**End time**: {x}"
            except AttributeError:
                pass

            next_run_time = format_dt(jobtime)
            str_out += f"*Job: {job_count}* \n" \
                       f"**Next run time**: {next_run_time} \n" \
                       f"**Message**: {job.args[0]} \n" \
                       f"__Trigger__: {jobtrig} \n\n"

            job_count += 1

    await ctx.send(content=str_out)


@slash.slash(name="remove-schedule", description="remove all listed jobs", guild_ids=guild_ids)
async def remove_schedule(ctx):
    # TODO: allow for index deletion
    # verification process
    try:
        user_id, id_, doc, user_tz = basic_init(ctx)
    except TypeError:
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


client.run("ODAyMzYzNDM1MzM3MjUyODY0.YAuJLg.gC0EWPOtik2ct2jXO5gaNxw66pE")
