import logging
from datetime import timedelta, datetime
from uuid import uuid4

import discord
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_REMOVED
from apscheduler.jobstores.base import JobLookupError
from apscheduler.jobstores.mongodb import MongoDBJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from discord_slash import SlashCommand
from discord_slash.utils import manage_commands
from pymongo import MongoClient
from pytz import timezone, UnknownTimeZoneError

from utility_file import format_dt, short_dt, strhour_to_dt, strweek_to_dt

# coloredlogs.install()
# TODO: hide job
# TODO: send market updates?
# TODO: snooze?
# TODO: optional hidden
# TODO: Natural inputs?

# Initialization stuff
intents = discord.Intents.default()
intents.members = True
client = discord.Client(intents=intents)
slash = SlashCommand(client, sync_commands=True)
guild_ids = [687499582459871242, 748887953497129052, 677353989632950273]

short_delete_time = 5
long_delete_time = 15


# prep commands


async def send_message(msg: str, user_id: int):
    """
    sends a discord dm
    """
    user_obj = client.get_user(user_id)
    await user_obj.send(content=msg)


def create_info(user_id: int):
    """
    creates an entry in the database for a user if it's their first time
    """
    db.user_data.find_one_and_update(
        {"user id": user_id},
        {
            "$set": {
                "timezone": "America/New_York",
            }
        },
        upsert=True,
    )
    db.bot_usage.find_one_and_update(
        {"user id": user_id},
        {"$setOnInsert": {"active jobs": []}},
        upsert=True,
    )


def basic_init(ctx):
    """initialization of basic values
    Returns
    -------

    user_id : :class:`int`
        The id of the user used to place the job in the database.
    id_ : :class:`str`
        The id_ for the specific job. Effectively unique so no jobs are overwritten.
    user_tx : :class:`DstTzInfo`
        The timezone object of the timezone.
    """
    user_id = ctx.author.id
    # access information in define_self
    if db.user_data.find_one({"user id": user_id}) is None:
        create_info(user_id)

    # generate a unique id + the user_id
    id_ = uuid4().hex + "user" + str(user_id)
    # user timezone
    doc = db.user_data.find_one({"user id": user_id})
    user_tz = timezone(doc["timezone"])
    return user_id, id_, user_tz


@slash.slash(
    name="set-timezone",
    description="Initialize your timezone",
    options=[
        manage_commands.create_option(
            # pytz timezone
            name="timezone",
            description="default='America/New_York' tz timezone, continent+city see https://cutt.ly/discord-timezone",
            option_type=3,
            required=False,
        ),
    ],
)
async def set_timezone(
    ctx,
    tz: str = "America/New_York",
):

    # check if the timezone value provided is valid
    try:
        timezone(tz)
    except UnknownTimeZoneError:
        await ctx.send(
            content=f"*{tz}* is not a tz timezone, please pick a valid neighbour",
        )
        return

    user_id, id_, user_tz = basic_init(ctx)

    # Create the entry in the database for the user's preferences
    db.user_data.find_one_and_update(
        {"user id": user_id},
        {
            "$set": {
                "timezone": tz,
            }
        },
        upsert=True,
    )

    # Entry for active jobs, where active jobs will be stored and processed
    db.bot_usage.find_one_and_update(
        {"user id": user_id}, {"$setOnInsert": {"active jobs": []}}, upsert=True
    )

    await ctx.send(
        content=f"**Information registered**: **Timezone**: {tz}",
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
    ctx,
    message: str,
    time_of_day: str,
    day_of_month: int = None,
    month_of_year: int = None,
    year: int = None,
):
    user_id, id_, user_tz = basic_init(ctx)

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
        )
        return

    mainsched.add_job(
        send_message,
        "date",
        run_date=planned_time,
        args=(message, user_id),
        id=id_,
        timezone=user_tz,
    )

    # add to active jobs
    db.bot_usage.find_one_and_update(
        {"user id": user_id}, {"$push": {"active jobs": id_}}
    )
    await ctx.send(
        content=f"⏰ Message: **{message}** - scheduled for {format_dt(planned_time)}",
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
async def time_from_now(ctx, message: str, duration: int):
    user_id, id_, user_tz = basic_init(ctx)

    planned_time = datetime.now(tz=user_tz) + timedelta(minutes=duration)

    mainsched.add_job(
        send_message,
        "date",
        run_date=planned_time,
        args=(message, user_id),
        misfire_grace_time=500,
        id=id_,
        timezone=user_tz,
    )

    # add to  active jobs
    db.bot_usage.find_one_and_update(
        {"user id": user_id}, {"$push": {"active jobs": id_}}
    )
    await ctx.send(
        content=f"⏰ Message: **{message}** - scheduled for *{format_dt(planned_time)}*",
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
        manage_commands.create_option(
            name="days_to_run",
            description="for how many days should the reminder run?",
            option_type=4,
            required=False,
        ),
    ],
)
async def daily_reminder(ctx, message: str, time: str, days_to_run: int = None):
    # init data
    user_id, id_, user_tz = basic_init(ctx)

    time = strhour_to_dt(time)
    if days_to_run:
        end_date = time + timedelta(days=days_to_run)
    else:
        end_date = None

    # create the cron job
    mainsched.add_job(
        send_message,
        "cron",
        (message, user_id),
        hour=time.hour,
        minute=time.minute,
        misfire_grace_time=500,
        id=id_,
        timezone=user_tz,
        end_date=end_date,
    )
    db.bot_usage.find_one_and_update(
        {"user id": user_id}, {"$push": {"active jobs": id_}}
    )

    await ctx.send(
        content=f"⏰ Message: **{message}** - to be sent at *{short_dt(time)}* daily",
    )


@slash.slash(
    name="weekly-message",
    description="send message at a weekly interval",
    options=[
        manage_commands.create_option(
            name="message",
            description="the message.",
            option_type=3,
            required=True,
        ),
        manage_commands.create_option(
            name="day_of_week",
            description="Day of the week in text: Sunday or Sun",
            option_type=3,
            required=True,
        ),
        manage_commands.create_option(
            name="time",
            description="time",
            option_type=3,
            required=True,
        ),
        manage_commands.create_option(
            name="weeks_to_run",
            description="For how many weeks should the reminder run?",
            option_type=4,
            required=False,
        ),
    ],
)
async def weekly_message(
    ctx, message: str, day_of_week: str, time: str, weeks_to_run: int = None
):
    user_id, id_, user_tz = basic_init(ctx)

    day_of_week = strweek_to_dt(day_of_week)
    time = strhour_to_dt(time)

    if weeks_to_run:
        end_date = day_of_week + timedelta(weeks=weeks_to_run)
    else:
        end_date = None
    mainsched.add_job(
        send_message,
        trigger="cron",
        args=(message, user_id),
        day_of_week=day_of_week.day,
        hour=time.hour,
        minute=time.minute,
        misfire_grace_time=500,
        id=id_,
        timezone=user_tz,
        end_date=end_date,
    )

    db.bot_usage.find_one_and_update(
        {"user id": user_id}, {"$push": {"active jobs": id_}}
    )

    await ctx.send(
        content=f"⏰ Message: **{message}** - to be sent at {short_dt(time)} on **day of week:{day_of_week}** weekly",
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
async def between_times(
    ctx, time_1: str, time_2: str, interval: int, message: str, repeating: str = "False"
):
    user_id, id_, user_tz = basic_init(ctx)

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
    between_times_interval(message, user_id, time_1, time_2, interval, user_tz)

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
                    user_id,
                    time_1,
                    time_2,
                    interval,
                    user_tz,
                ),
                misfire_grace_time=500,
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
                    user_id,
                    time_1,
                    time_2,
                    interval,
                    user_tz,
                ),
                misfire_grace_time=500,
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
    )


# error comes up when the function is placed in the above function, so it's here /shrug
def between_times_interval(message, user_id, time_1, time_2, interval, user_tz):
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
        args=(message, user_id),
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
    # the verification process
    user_id, id_, user_tz = basic_init(ctx)

    # find the users active jobs
    temp = db.bot_usage.find_one({"user id": user_id})

    if temp["active jobs"]:
        author = ctx.author
        pfp = author.avatar_url
        embed = discord.Embed(title="Your schedule", color=0xA0CA9B)
        embed.set_author(name=author.display_name, icon_url=pfp)

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

            str_out = (
                f"**Next run time**: {next_run_time} \n"
                f"**Message**: {job.args[0]} \n"
                f"__Trigger__: {jobtrig} \n\n"
            )
            embed.add_field(name=f"Job: {job_count} ", value=str_out)
            job_count += 1
    else:
        embed = "No jobs found"

    await ctx.send(embed=embed)


@slash.slash(
    name="clear-schedule",
    description="clears  all listed jobs",
)
async def remove_schedule(ctx):
    # verification process
    user_id, id_, user_tz = basic_init(ctx)

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
            name="index",
            description="use get-sched to find the job's position",
            option_type=4,
            required=True,
        ),
        manage_commands.create_option(
            name="until",
            description="from the index chosen, until the this one",
            option_type=4,
            required=False,
        ),
    ],
)
async def remove_index(ctx, index: int, until: int = None):
    # verificaiton process
    user_id, id_, user_tz = basic_init(ctx)

    index -= 1
    if until:
        until -= 1

    if not until:
        try:
            job_hold = [
                db.bot_usage.find_one({"user id": user_id})[f"active jobs"][index]
            ]
        except IndexError:
            await ctx.send(
                content=f"**Index not found**", delete_after=short_delete_time
            )
            return
    else:
        moving_index = index
        job_hold = []
        while moving_index < until:
            try:
                job_id = db.bot_usage.find_one({"user id": user_id})[f"active jobs"][
                    moving_index
                ]
            except IndexError:
                await ctx.send(
                    content=f"**Index not found**", delete_after=short_delete_time
                )
                return
            job_hold.append(job_id)
            moving_index += 1

    for job_id in job_hold:
        mainsched.remove_job(job_id)

    content = f"⏰ Command executed. "
    if until:
        content += f"**{len(job_hold)}** jobs removed. From **{index}** to **{until}**."
    else:
        content += f" **Index**: {index} job removed."
    await ctx.send(
        content=content,
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
    # connect to the mongodb database

    from decouple import config

    mongoclient = MongoClient(config("MONGO"))
    db = mongoclient.discord

    # apscheduler setup, connecting to mongodb + initializing
    jobstores = {
        "default": MongoDBJobStore(client=mongoclient, collection="scheduled-job")
    }
    mainsched = AsyncIOScheduler(jobstores=jobstores)
    mainsched.start()

    mainsched.add_listener(jobitem_removed, EVENT_JOB_EXECUTED | EVENT_JOB_REMOVED)
    client.run(config("TOKEN"))
