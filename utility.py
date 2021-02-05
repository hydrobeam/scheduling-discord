import ezgmail

def format_dt(dtobject):
    ymd = f"{dtobject.strftime('%b')} {dtobject.day} {dtobject.year}"
    formatted = f"{dtobject.strftime('%A')} {dtobject.hour % 12}:{dtobject.strftime('%M')} {dtobject.strftime('%p')} | {ymd}"
    return formatted


def short_dt(dtobject):
    formatted = f"{dtobject.hour % 12}:{dtobject.strftime('%M')} {dtobject.strftime('%p')}"
    return formatted

def send_message(msg, contact):
    ezgmail.send(contact, subject='', body=msg)