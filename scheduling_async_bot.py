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

import configparser

from utility_file import format_dt, short_dt
import ezgmail

from pprint import pprint

# TODO: prioritize email in presenation
# TODO: inndex removals
# TODO: Interval message redundant? evaluate
# TODO: bdtweentwo tiems tomorow

# Initialization stuff
intents = discord.Intents.default()
intents.members = True
client = discord.Client(intents=intents)
slash = SlashCommand(client, auto_register=True, auto_delete=True)
guild_ids = [687499582459871242, 748887953497129052, 677353989632950273]


# coloredlogs.install()
# serious commands

async def send_message(msg, contact, discord, user_id):
    """
    sends a message
    """
    ezgmail.send(contact, subject='', body=msg)
    if discord:
        await send_discord_message(msg, user_id)


async def send_discord_message(msg, user_id):
    """
    sends a discord dm
    """
    user_obj = client.get_user(user_id)
    await user_obj.send(content=msg)


def basic_init(ctx):
    # initialization of basic values
    user_id = ctx.author.id
    id_ = uuid4().hex + "user" + str(user_id)
    doc = db.user_data.find_one({"user id": user_id})
    user_tz = timezone(doc['timezone'])
    dm = doc['direct_message']
    if doc is None:
        return
    else:
        return user_id, id_, doc, user_tz, dm




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
async def date_message(ctx, message, time_of_day, day_of_month=None, month_of_year=None,
                       year=None):
    try:
        user_id, id_, doc, user_tz, dm = basic_init(ctx)
    except TypeError:
        await ctx.send(content=f"Please register your information with 'define-self'")
        return
    if day_of_month is None:
        day_of_month = datetime.now(user_tz).day
    if month_of_year is None:
        month_of_year = datetime.now(user_tz).month
    if year is None:
        year = datetime.now(user_tz).year

    # check if am or pm are used, set lower and remove spaces: 9:08 pm == 9:08pm
    time_of_day = time_of_day.lower().replace(' ', '')
    if "am" in time_of_day or "pm" in time_of_day:
        time = datetime.strptime(time_of_day, '%I:%M%p')
    else:
        time = datetime.strptime(time_of_day, '%H:%M')

    # define the time of delivery,
    planned_time = user_tz.localize(datetime(year, month_of_year, day_of_month, time.hour, time.minute))

    # check if message is scheduled for the past
    if (x := datetime.now(user_tz)) > planned_time:
        await ctx.send(
            content=f"Chosen time: **{format_dt(planned_time)}** is earlier than current time: **{format_dt(x)}"
                    f"**. Please choose a valid date")
        return

    mainsched.add_job(send_message, 'date', run_date=planned_time,
                      args=(message, doc['contact information'], dm, user_id), id=id_, timezone=user_tz)

    # add to active jobs
    db.bot_usage.find_one_and_update({'user id': user_id},
                                     {'$push': {'active jobs': id_}})

    await ctx.send(content=f"⏰ Message: **{message}** - scheduled for {format_dt(planned_time)}")


@slash.slash(name="time-from-now", description="schedule a message for certain time from now", guild_ids=guild_ids,
             options=[
                 manage_commands.create_option(
                     name="message",
                     description="message to be delivered",
                     option_type=3,
                     required=True
                 ),
                 manage_commands.create_option(
                     name="time",
                     description="time from current time in minutes",
                     option_type=4,
                     required=True
                 )
             ])
async def time_from_now(ctx, message, duration):
    try:
        user_id, id_, doc, user_tz, dm = basic_init(ctx)
    except TypeError:
        await ctx.send(content=f"Please register your information with 'define-self'")
        return

    planned_time = datetime.now(tz=user_tz) + timedelta(seconds=duration)

    mainsched.add_job(send_message, 'date', run_date=planned_time,
                      args=(message, doc['contact information'], dm, user_id),
                      misfire_grace_time=500, replace_existing=True, id=id_,
                      timezone=user_tz)

    # add to  active jobs
    db.bot_usage.find_one_and_update({'user id': user_id},
                                     {'$push': {'active jobs': id_}})

    await ctx.send(content=f"⏰ Message: **{message}** - scheduled for *{format_dt(planned_time)}*  ")



@slash.slash(name="define-self", description="Initialize your details", guild_ids=guild_ids,
             options=[
                 manage_commands.create_option(
                     name="contact_info",
                     description="Your phone number's email address: {your carrier} SMS Gateway",
                     option_type=3,
                     required=True
                 ),
                 manage_commands.create_option(
                     name="direct-message",
                     description="also schedule messages for discord DMs?",
                     option_type=3,
                     required=True,
                     choices=[
                         manage_commands.create_choice(
                             name="Yes",
                             value="Yes"
                         ),
                         manage_commands.create_choice(
                             name="No",
                             value="No"
                         )]),
                 manage_commands.create_option(
                     name="timezone",
                     description="default='America/New_York' tz timezone, continent+city see https://cutt.ly/discord-timezone",
                     option_type=3,
                     required=False
                 ),

             ]
             )
async def define_self(ctx, contact_info, direct_message, tz='America/New_York', ):
    # dm has to be Yes/ No because choices dont support True False

    user_id = ctx.author.id
    # check if the timezone value provided is valid
    with open('timezones.txt', 'r') as file:
        moxy = file.read().splitlines()
        if tz not in moxy:
            await ctx.send(content=f"*{tz}* is not a tz timezone, please pick a valid neighbour")
            return
    if direct_message == "No":
        direct_message = False
    elif direct_message == "Yes":
        direct_message = True

    db.user_data.find_one_and_update({"user id": user_id},
                                     {"$set": {"contact information": contact_info, "timezone": tz,
                                               "direct_message": direct_message}},
                                     upsert=True)
    db.bot_usage.find_one_and_update(
        {'user id': user_id},
        {"$setOnInsert": {'active jobs': []}},
        upsert=True
    )
    await ctx.send(content=f"**Information registered**: {contact_info}, **Timezone**: {tz}, **DM**: {direct_message}",
                   complete_hidden=True)


@slash.slash(name="daily-reminder", description="Set a daily reminder", guild_ids=guild_ids,
             options=[
                 manage_commands.create_option(
                     name="time",
                     description="time of day - HH:MM",
                     option_type=3,
                     required=True
                 ),
                 manage_commands.create_option(
                     name="message",
                     description="specify message",
                     option_type=3,
                     required=True
                 )
             ])
async def daily_reminder(ctx, time_of_day, message):
    # init data
    try:
        user_id, id_, doc, user_tz, dm = basic_init(ctx)
    except TypeError:
        await ctx.send(content=f"Please register your information with 'define-self'")
        return

    time_of_day = time_of_day.lower().replace(' ', '')
    if "am" in time_of_day or "pm" in time_of_day:
        time = datetime.strptime(time_of_day, '%I:%M%p')
    else:
        time = datetime.strptime(time_of_day, '%H:%M')

    # initialize the class
    mainsched.add_job(send_message, 'cron', (message, doc['contact information'], dm, user_id), hour=time.hour,
                      minute=time.minute, misfire_grace_time=500, replace_existing=True, id=id_, timezone=user_tz)
    db.bot_usage.find_one_and_update({'user id': user_id},
                                     {'$push': {'active jobs': id_}})

    await ctx.send(content=f"⏰ Message: **{message}** - to be sent at *{short_dt(time)}*")


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
                     required=False,
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
async def between_times(ctx, time_1, time_2, interval, message, repeating="false"):
    try:
        user_id, id_, doc, user_tz, dm = basic_init(ctx)
    except TypeError:
        await ctx.send(content=f"Please register your information with 'define-self'")
        return

    if interval < 20:
        interval = 20

    # Format the times
    tomorrow = datetime.now(tz=user_tz) + timedelta(days=1, hours=0, minutes=0)
    time_1 = datetime.strptime(time_1, '%H:%M')
    time_2 = datetime.strptime(time_2, '%H:%M')
    today = datetime.now(tz=user_tz)
    time_1 = today.replace(hour=time_1.hour, minute=time_1.minute)
    time_2 = today.replace(hour=time_2.hour, minute=time_2.minute)

    between_times_interval(message, doc['contact information'], dm, user_id, time_1, time_2, interval, user_tz)

    if repeating == 'True':
        # make sure that the call for repeating starts the next day, not today, not two days from now
        if today > time_1:
            mainsched.add_job(between_times_interval, 'cron', hour=time_1.hour, minute=time_1.minute,
                              args=(message, doc['contact information'], dm, user_id, time_1, time_2, interval, user_tz),
                              misfire_grace_time=500, replace_existing=True, id=id_, timezone=user_tz)
        elif today < time_1:
            mainsched.add_job(between_times_interval, 'cron', start_date=tomorrow, hour=time_1.hour,
                              minute=time_1.minute,
                              args=(message, doc['contact information'], dm, user_id, time_1, time_2, interval, user_tz),
                              misfire_grace_time=500, replace_existing=True, id=id_, timezone=user_tz)

        # add the cron job to active jobs
        db.bot_usage.find_one_and_update({'user id': user_id},
                                         {'$push': {'active jobs': id_}})

    await ctx.send(
        content=f"⏰ Message: {message} \nTime: from **{time_1.strftime('%H:%M')}** to **{time_2.strftime('%H:%M')}** "
                f"\nRepeating: {repeating}")


# error comes up when the function is placed in the above function, so it's here /shrug
def between_times_interval(message, contact, dm, user_id, time_1, time_2, interval, user_tz):
    id_ = uuid4().hex + "user" + str(user_id)
    today = datetime.now(tz=user_tz)
    time_1 = today.replace(hour=time_1.hour, minute=time_1.minute)
    time_2 = today.replace(hour=time_2.hour, minute=time_2.minute)
    if time_1 > time_2:
        time_2 += timedelta(days=1, hours=0, minutes=0)

    mainsched.add_job(send_message, 'interval', minutes=interval,
                      start_date=time_1,
                      end_date=time_2,
                      args=(message, contact, dm, user_id), misfire_grace_time=500, replace_existing=True, id=id_, timezone=user_tz)

    db.bot_usage.find_one_and_update({'user id': user_id},
                                     {'$push': {'active jobs': id_}})


@slash.slash(name="get-sched", description="acquire your listed schedule", guild_ids=guild_ids)
async def get_schedule(ctx):
    # the verification process
    try:
        user_id, id_, doc, user_tz, dm = basic_init(ctx)
    except TypeError:
        await ctx.send(content=f"Please register your information with 'define-self'")
        return

    # find the users active jobs
    temp = db.bot_usage.find_one({'user id': user_id})

    if temp['active jobs']:
        str_out = ""
        job_count = 1
        # look through all jobs in 'active jobs'
        for value in temp['active jobs']:

            # get the job and extract data from  it
            job = mainsched.get_job(value)
            # message is always the second arg
            jobtime = job.next_run_time
            # details about the trigger
            trig = job.trigger

            # get jobtype
            jobtrig = f" {str(trig).split('[')[0]}"

            #  getting vars from trigger game
            try:
                if x := short_dt(trig.start_date):
                    jobtrig += f" | **Start time**: {x} "
                if x := short_dt(trig.end_date):
                    jobtrig += f"**End time**: {x}"
                jobtrig += f" **Timezone**: {trig.timezone}"
            except AttributeError:
                # this is a date job, no relevant attributes
                pass

            next_run_time = format_dt(jobtime)
            str_out += f"*Job: {job_count}* \n" \
                       f"**Next run time**: {next_run_time} \n" \
                       f"**Message**: {job.args[0]} \n" \
                       f"__Trigger__: {jobtrig} \n\n"

            job_count += 1
    else:
        str_out = "No jobs found"

    await ctx.send(content=str_out)


@slash.slash(name="remove-schedule", description="remove all listed jobs", guild_ids=guild_ids)
async def remove_schedule(ctx):
    # verification process
    try:
        user_id, id_, doc, user_tz, dm = basic_init(ctx)
    except TypeError:
        await ctx.send(content=f"Please register your information with 'define-self'")
        return

    # find the user
    user_object = db.bot_usage.find_one({'user id': user_id})
    for value in user_object['active jobs']:
        try:
            # remove jobs from the scheduler then from 'active jobs'
            mainsched.remove_job(value, 'default')
            db.bot_usage.update_one({'user id': user_id},
                                    {'$pull': {'active jobs': value}})
        except JobLookupError:
            # if job doesnt exist, just remove the entry from active jobs
            db.bot_usage.update_one({'user id': user_id},
                                    {'$pull': {'active jobs': value}})

    await ctx.send(content="⏰ Command executed, listed jobs removed")


@slash.slash(name="remove-index", description="remove a single job according to its position", guild_ids=guild_ids,
             options=[
                 manage_commands.create_option(
                     name="index-position",
                     description="do get-sched to find the job's position",
                     option_type=4,
                     required=True
                 )
             ])
async def remove_index(ctx, index):
    # verificaiton process
    try:
        user_id, id_, doc, user_tz, dm = basic_init(ctx)
    except TypeError:
        await ctx.send(content=f"Please register your information with 'define-self'")
        return

    index -= 1

    try:
        job_id = db.bot_usage.find_one({'user id': user_id})[f'active jobs'][index]
    except IndexError:
        await ctx.send(content=f"**Index not found**")
        return

    # mongodb doesnt support index removals, set job to null, then remove null
    mainsched.remove_job(job_id)
    db.bot_usage.find_one_and_update({'user id': user_id},
                                     {'$set': {f'active jobs.{index}': None}})
    db.bot_usage.find_one_and_update({'user id': user_id},
                                     {'$pull': {'active jobs': None}})

    await ctx.send(content=f"⏰ Command executed, **Index**: {index} job removed")


# the listener
def jobitem_removed(event):
    """
        the listener checks for when a job is removed or executed and removes it from 'active jobs'
        """

    user_id = int(event.job_id.split('user')[1])
    job = mainsched.get_job(event.job_id)
    try:
        tz = job.trigger.timezone
    except AttributeError:
        # doesn't matter what the timezone is, just needs to be valid. date_jobs always get removed
        tz = "America/New_York"
    current_time = datetime.now(tz=timezone(tz))

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


if __name__ == '__main__':
    # parse the config file
    config = configparser.ConfigParser()
    config.read('config.ini')
    # connect to the mongodb database
    mongoclient = MongoClient(config['MONGO']['mongo_value'])
    db = mongoclient.discord

    # apscheduler setup, connecting to mongodb + initializing
    jobstores = {
        'default': MongoDBJobStore(client=mongoclient, collection="scheduled-job")
    }
    mainsched = AsyncIOScheduler(jobstores=jobstores)
    mainsched.start()

    mainsched.add_listener(jobitem_removed, EVENT_JOB_EXECUTED | EVENT_JOB_REMOVED)
    client.run(config["DISCORD"]["bot_token"])
