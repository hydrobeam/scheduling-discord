import discord
from discord_slash import SlashCommand
from discord_slash.utils import manage_commands

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.mongodb import MongoDBJobStore
from apscheduler.jobstores.base import JobLookupError
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_REMOVED
from pymongo import MongoClient

from datetime import timedelta, datetime
from pytz import timezone, UnknownTimeZoneError
from uuid import uuid4

import configparser, logging

from utility_file import format_dt, short_dt, strhour_to_dt
import ezgmail
from googleapiclient.errors import HttpError

# coloredlogs.install()
# TODO: hide job
# TODO: send market updates?
# TODO: snooze?
# TODO: optional hidden
# TODO: Natural inputs?
# TODO: fix get-sched in case of bugging

# Initialization stuff
intents = discord.Intents.default()
intents.members = True
client = discord.Client(intents=intents)
slash = SlashCommand(client, sync_commands=True)
guild_ids = [687499582459871242, 748887953497129052, 677353989632950273]


short_delete_time = 5
long_delete_time = 15

# prep commands
async def send_message(msg, contact, user_id):
    """
    sends a message, called by the scheduler
    """
    try:
        ezgmail.send(contact, subject="", body=msg)
    except HttpError:
        # the email provided is invalid
        logging.exception("Exception on email delivery")

    doc = db.user_data.find_one({"user id": user_id})
    dm = doc["direct_message"]
    if dm:
        await send_discord_message(msg, user_id)


async def send_discord_message(msg, user_id):
    """
    sends a discord dm, called by send_message if DMs are enabled
    """
    user_obj = client.get_user(user_id)
    await user_obj.send(content=msg)


def basic_init(ctx):
    """initialization of basic values"""

    user_id = ctx.author.id
    # generate a unique id + the user_id
    id_ = uuid4().hex + "user" + str(user_id)
    # access information in define_self
    doc = db.user_data.find_one({"user id": user_id})
    # user timezone
    user_tz = timezone(doc["timezone"])
    if doc is None:
        return
    else:
        return user_id, id_, doc, user_tz


@slash.slash(
    name="define-self",
    description="Initialize your details",
    options=[
        manage_commands.create_option(
            name="contact_info",
            description="Your phone number's email address: your carrier's SMS Gateway",
            option_type=3,
            required=True,
        ),
        manage_commands.create_option(
            name="direct-message",
            description="also schedule messages for discord DMs?",
            option_type=3,
            required=True,
            choices=[
                manage_commands.create_choice(name="Yes", value="Yes"),
                manage_commands.create_choice(name="No", value="No"),
            ],
        ),
        manage_commands.create_option(
            # pytz timezone
            name="timezone",
            description="default='America/New_York' tz timezone, continent+city see https://cutt.ly/discord-timezone",
            option_type=3,
            required=False,
        ),
    ],
)
async def define_self(
    ctx,
    contact_info,
    direct_message,
    tz="America/New_York",
):
    # dm has to be Yes/ No because choices dont support True False bools

    user_id = ctx.author.id

    # check if the timezone value provided is valid
    try:
        timezone(tz)
    except UnknownTimeZoneError:
        await ctx.send(
            content=f"*{tz}* is not a tz timezone, please pick a valid neighbour",
            delete_after=short_delete_time,
        )
        return

    # can't use bools as options
    if direct_message == "No":
        direct_message = False
    elif direct_message == "Yes":
        direct_message = True

    # Create the entry in the database for the user's preferences
    db.user_data.find_one_and_update(
        {"user id": user_id},
        {
            "$set": {
                "contact information": contact_info,
                "timezone": tz,
                "direct_message": direct_message,
            }
        },
        upsert=True,
    )

    # Entry for active jobs, where active jobs will be stored and processed
    db.bot_usage.find_one_and_update(
        {"user id": user_id}, {"$setOnInsert": {"active jobs": []}}, upsert=True
    )
    await ctx.send(
        content=f"**Information registered**: {contact_info}, **Timezone**: {tz}, **DM**: {direct_message}",
        delete_after=long_delete_time,
    )


# Actual scheduling commands


@slash.slash(
    name="date-message",
    description="send a message at a specific date and time",
    options=[
        manage_commands.create_option(
            name="message",
            description="message to deliver",
            option_type=3,
            required=True,
        ),
        manage_commands.create_option(
            name="time_of_day",
            description="time of day - HH:MM",
            option_type=3,
            required=True,
        ),
        manage_commands.create_option(
            name="day_of_month",
            description="day of the month between 1 and 31, defaults current day",
            option_type=4,
            required=False,
        ),
        manage_commands.create_option(
            name="month_of_year",
            description="month of the year between 1 and 12, defaults to current month",
            option_type=4,
            required=False,
        ),
        manage_commands.create_option(
            name="year",
            description="year format : 2021, defaults to current year",
            option_type=4,
            required=False,
        ),
    ],
)
async def date_message(
    ctx, message, time_of_day, day_of_month=None, month_of_year=None, year=None
):
    try:
        user_id, id_, doc, user_tz = basic_init(ctx)
    except TypeError:
        await ctx.send(
            content=f"Please register your information with 'define-self'",
            delete_after=short_delete_time,
        )
        return

    present_time = datetime.now(user_tz)
    if day_of_month is None:
        day_of_month = present_time.day
    if month_of_year is None:
        month_of_year = present_time.month
    if year is None:
        year = present_time.year

    # gets datetime object representing hour and minute from user string input
    time = strhour_to_dt(time_of_day)

    # define the time of delivery,
    planned_time = user_tz.localize(
        datetime(year, month_of_year, day_of_month, time.hour, time.minute)
    )

    # check if message is scheduled for the past
    if (x := datetime.now(user_tz)) > planned_time:
        await ctx.send(
            content=f"Chosen time: **{format_dt(planned_time)}** is earlier than current time: **{format_dt(x)}"
            f"**. Please choose a valid date",
            delete_after=short_delete_time,
        )
        return

    mainsched.add_job(
        send_message,
        "date",
        run_date=planned_time,
        args=(message, doc["contact information"], user_id),
        id=id_,
        timezone=user_tz,
    )

    # add to active jobs
    db.bot_usage.find_one_and_update(
        {"user id": user_id}, {"$push": {"active jobs": id_}}
    )
    await ctx.send(
        content=f"⏰ Message: **{message}** - scheduled for {format_dt(planned_time)}",
        delete_after=long_delete_time,
    )


@slash.slash(
    name="time-from-now",
    description="schedule a message for certain time from now",
    options=[
        manage_commands.create_option(
            name="message",
            description="message to be delivered",
            option_type=3,
            required=True,
        ),
        manage_commands.create_option(
            name="duration",
            description="time from current time in minutes",
            option_type=4,
            required=True,
        ),
    ],
)
async def time_from_now(ctx, message, duration):
    try:
        user_id, id_, doc, user_tz = basic_init(ctx)
    except TypeError:
        await ctx.send(
            content=f"Please register your information with 'define-self'",
            delete_after=short_delete_time,
        )
        return

    planned_time = datetime.now(tz=user_tz) + timedelta(minutes=duration)

    mainsched.add_job(
        send_message,
        "date",
        run_date=planned_time,
        args=(message, doc["contact information"], user_id),
        misfire_grace_time=500,
        replace_existing=True,
        id=id_,
        timezone=user_tz,
    )

    # add to  active jobs
    db.bot_usage.find_one_and_update(
        {"user id": user_id}, {"$push": {"active jobs": id_}}
    )
    await ctx.send(
        content=f"⏰ Message: **{message}** - scheduled for *{format_dt(planned_time)}*",
        delete_after=long_delete_time,
    )


@slash.slash(
    name="daily-reminder",
    description="Set a daily reminder",
    options=[
        manage_commands.create_option(
            name="message", description="specify message", option_type=3, required=True
        ),
        manage_commands.create_option(
            name="time", description="time of day", option_type=3, required=True
        ),
    ],
)
async def daily_reminder(ctx, message, time):
    # init data
    try:
        user_id, id_, doc, user_tz = basic_init(ctx)
    except TypeError:
        await ctx.send(
            content=f"Please register your information with 'define-self'",
            delete_after=short_delete_time,
        )
        return

    time = strhour_to_dt(time)

    # create the cron job
    mainsched.add_job(
        send_message,
        "cron",
        (message, doc["contact information"], user_id),
        hour=time.hour,
        minute=time.minute,
        misfire_grace_time=500,
        replace_existing=True,
        id=id_,
        timezone=user_tz,
    )
    db.bot_usage.find_one_and_update(
        {"user id": user_id}, {"$push": {"active jobs": id_}}
    )

    await ctx.send(
        content=f"⏰ Message: **{message}** - to be sent at *{short_dt(time)} daily",
        delete_after=long_delete_time,
    )


@slash.slash(
    name="between-two-times",
    description="send messages at an interval between two times throughout the day",
    options=[
        manage_commands.create_option(
            name="time_1",
            description="Initial time. Format in 24h | 9:04",
            option_type=3,
            required=True,
        ),
        manage_commands.create_option(
            name="time_2",
            description="Final time. Format in 24h | 23:30",
            option_type=3,
            required=True,
        ),
        manage_commands.create_option(
            name="interval",
            description="Time between messages in minutes, minimum: 20 minutes",
            option_type=4,
            required=True,
        ),
        manage_commands.create_option(
            name="message",
            description="Message to be sent",
            option_type=3,
            required=True,
        ),
        manage_commands.create_option(
            name="repeating",
            description="Repeat daily?",
            option_type=3,
            required=False,
            choices=[
                manage_commands.create_choice(name="True", value="True"),
                manage_commands.create_choice(name="False", value="False"),
            ],
        ),
    ],
)
async def between_times(ctx, time_1, time_2, interval, message, repeating="false"):
    try:
        user_id, id_, doc, user_tz = basic_init(ctx)
    except TypeError:
        await ctx.send(
            content=f"Please register your information with 'define-self'",
            delete_after=short_delete_time,
        )
        return

    if interval < 20:
        interval = 20

    # Format the times
    tomorrow = datetime.now(tz=user_tz) + timedelta(days=1, hours=0, minutes=0)
    time_1 = strhour_to_dt(time_1)
    time_2 = strhour_to_dt(time_2)
    today = datetime.now(tz=user_tz)
    time_1 = today.replace(hour=time_1.hour, minute=time_1.minute)
    time_2 = today.replace(hour=time_2.hour, minute=time_2.minute)

    # create the interval job for today
    between_times_interval(
        message, doc["contact information"], user_id, time_1, time_2, interval, user_tz
    )

    if repeating == "True":
        # TODO: make sure that the call for repeating starts the next day, not today, not two days from now
        # if current time is after the start date, activate the cron now, else activate it tomorrow
        if today > time_1:
            mainsched.add_job(
                between_times_interval,
                "cron",
                hour=time_1.hour,
                minute=time_1.minute,
                args=(
                    message,
                    doc["contact information"],
                    user_id,
                    time_1,
                    time_2,
                    interval,
                    user_tz,
                ),
                misfire_grace_time=500,
                replace_existing=True,
                id=id_,
                timezone=user_tz,
            )
        elif today < time_1:
            mainsched.add_job(
                between_times_interval,
                "cron",
                start_date=tomorrow,
                hour=time_1.hour,
                minute=time_1.minute,
                args=(
                    message,
                    doc["contact information"],
                    user_id,
                    time_1,
                    time_2,
                    interval,
                    user_tz,
                ),
                misfire_grace_time=500,
                replace_existing=True,
                id=id_,
                timezone=user_tz,
            )

        # add the cron job to active jobs
        db.bot_usage.find_one_and_update(
            {"user id": user_id}, {"$push": {"active jobs": id_}}
        )

    await ctx.send(
        content=f"⏰ Message: {message} \nTime: from **{time_1.strftime('%H:%M')}** to **{time_2.strftime('%H:%M')}** "
        f"\nRepeating: {repeating}",
        delete_after=long_delete_time,
    )


# error comes up when the function is placed in the above function, so it's here /shrug
def between_times_interval(
    message, contact, user_id, time_1, time_2, interval, user_tz
):
    id_ = uuid4().hex + "user" + str(user_id)
    today = datetime.now(tz=user_tz)
    time_1 = today.replace(hour=time_1.hour, minute=time_1.minute)
    time_2 = today.replace(hour=time_2.hour, minute=time_2.minute)
    if time_1 > time_2:
        time_2 += timedelta(days=1, hours=0, minutes=0)

    mainsched.add_job(
        send_message,
        "interval",
        minutes=interval,
        start_date=time_1,
        end_date=time_2,
        args=(message, contact, user_id),
        misfire_grace_time=500,
        replace_existing=True,
        id=id_,
        timezone=user_tz,
    )

    db.bot_usage.find_one_and_update(
        {"user id": user_id}, {"$push": {"active jobs": id_}}
    )


@slash.slash(name="get-schedule", description="acquire your listed schedule")
async def get_schedule(ctx):
    ctx.defer()
    # the verification process
    try:
        user_id, id_, doc, user_tz = basic_init(ctx)
    except TypeError:
        await ctx.send(
            content=f"Please register your information with 'define-self'",
            delete_after=short_delete_time,
        )
        return

    # find the users active jobs
    temp = db.bot_usage.find_one({"user id": user_id})

    if temp["active jobs"]:
        str_out = ""
        job_count = 1
        # look through all jobs in 'active jobs'
        for value in temp["active jobs"]:

            # get the job and extract data from  it
            job = mainsched.get_job(value)
            jobtime = job.next_run_time
            # details about the trigger
            trig = job.trigger

            # get jobtype, cron, interval, etc...
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
            # message is always the first arg

            str_out += (
                f"*Job: {job_count}* \n"
                f"**Next run time**: {next_run_time} \n"
                f"**Message**: {job.args[0]} \n"
                f"__Trigger__: {jobtrig} \n\n"
            )

            job_count += 1
    else:
        str_out = "No jobs found"

    await ctx.send(content=str_out)


@slash.slash(
    name="clear-schedule",
    description="clears  all listed jobs",
)
async def remove_schedule(ctx):
    # verification process
    try:
        user_id, id_, doc, user_tz = basic_init(ctx)
    except TypeError:
        await ctx.send(
            content=f"Please register your information with 'define-self'",
            delete_after=short_delete_time,
        )
        return

    # find the user
    user_object = db.bot_usage.find_one({"user id": user_id})
    for job in user_object["active jobs"]:
        try:
            # remove jobs from the scheduler then from 'active jobs'
            mainsched.remove_job(job, "default")

        except JobLookupError:
            # if job doesnt exist, just remove the entry from active jobs
            db.bot_usage.update_one(
                {"user id": user_id}, {"$pull": {"active jobs": job}}
            )

    await ctx.send(
        content="⏰ Command executed, listed jobs removed", delete_after=long_delete_time
    )


@slash.slash(
    name="remove-index",
    description="remove a single job according to its position",
    options=[
        manage_commands.create_option(
            name="index-position",
            description="use get-sched to find the job's position",
            option_type=4,
            required=True,
        )
    ],
)
async def remove_index(ctx, index):
    # verificaiton process
    logging.critical("start of remove_index")
    try:
        user_id, id_, doc, user_tz = basic_init(ctx)
    except TypeError:
        await ctx.send(
            content=f"Please register your information with 'define-self'",
            delete_after=short_delete_time,
        )
        return

    index -= 1

    try:
        job_id = db.bot_usage.find_one({"user id": user_id})[f"active jobs"][index]
    except IndexError:
        await ctx.send(content=f"**Index not found**", delete_after=short_delete_time)
        return

    mainsched.remove_job(job_id)

    await ctx.send(
        content=f"⏰ Command executed, **Index**: {index + 1} job removed",
        delete_after=short_delete_time,
    )


# the listener, listens for a job being removed, or a job being executed
def jobitem_removed(event):
    """
    the listener checks for when a job is removed or executed and removes it from 'active jobs'
    """

    logging.warning("listener activated")

    user_id = int(event.job_id.split("user")[1])
    job = mainsched.get_job(event.job_id)
    try:
        time_z = job.trigger.timezone
    except AttributeError:
        #    doesn't matter what the timezone is, just needs to be valid. date_jobs always get removed
        time_z = timezone("America/New_York")
    current_time = datetime.now(tz=time_z)

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
    db.bot_usage.find_one_and_update(
        {"user id": user_id}, {"$pull": {"active jobs": event.job_id}}
    )


if __name__ == "__main__":
    # parse the config file
    config = configparser.ConfigParser()
    config.read("config.ini")
    # connect to the mongodb database
    mongoclient = MongoClient(config["MONGO"]["mongo_value"])
    db = mongoclient.discord

    # apscheduler setup, connecting to mongodb + initializing
    jobstores = {
        "default": MongoDBJobStore(client=mongoclient, collection="scheduled-job")
    }
    mainsched = AsyncIOScheduler(jobstores=jobstores)
    mainsched.start()

    mainsched.add_listener(jobitem_removed, EVENT_JOB_EXECUTED | EVENT_JOB_REMOVED)
    client.run(config["DISCORD"]["bot_token"])
