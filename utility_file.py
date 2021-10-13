from datetime import datetime


def format_dt(dtobject):
    """
    format: Saturday 8:00 PM | Feb 6 2021 ;datetime-->string
    """
    ymd = f"{dtobject.strftime('%b')} {dtobject.day} {dtobject.year}"
    formatted = f"{dtobject.strftime('%A')} {dtobject.strftime('%I')}:{dtobject.strftime('%M')} {dtobject.strftime('%p')} | {ymd}"
    return formatted


def short_dt(dtobject):
    """
    format: 5:03 PM ; datetime--> string
    """
    formatted = (
        f"{dtobject.strftime('%I')}:{dtobject.strftime('%M')} {dtobject.strftime('%p')}"
    )
    return formatted


def strhour_to_dt(time_of_day):
    """
    turns a string under several time formats into a datetime object:
    7:09pm
    7pm
    23:01
    """
    time_of_day = time_of_day.lower().replace(" ", "")
    if "am" in time_of_day or "pm" in time_of_day:
        if ":" in time_of_day:
            # 7:09pm
            time = datetime.strptime(time_of_day, "%I:%M%p")
        else:
            # 7pm
            time = datetime.strptime(time_of_day, "%I%p")

    else:
        # 23:01
        time = datetime.strptime(time_of_day, "%H:%M")

    return time


def strweek_to_dt(week):
    week = week.lower().replace(" ", "")
    if len(week) > 3:
        # Sunday, Monday, Tuesday
        time = datetime.strptime(week, "%A")
    else:
        # Sun, Mon, Sat
        time = datetime.strptime(week, "%a")

    return time
