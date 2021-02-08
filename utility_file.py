import ezgmail


def format_dt(dtobject):
    """
    format: Saturday 8:00 PM | Feb 6 2021 ;datetime-->string
    """
    ymd = f"{dtobject.strftime('%b')} {dtobject.day} {dtobject.year}"
    formatted = f"{dtobject.strftime('%A')} {dtobject.strftime('%I')}:{dtobject.strftime('%M')} {dtobject.strftime('%p')} | {ymd}"
    return formatted


def short_dt(dtobject):
    """
    format: 5:03pm ; datetime--> string
    """
    formatted = f"{dtobject.strftime('%I')}:{dtobject.strftime('%M')} {dtobject.strftime('%p')}"
    return formatted


