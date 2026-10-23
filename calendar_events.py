"""Upcoming events from an iCloud calendar via CalDAV.

Needs ICLOUD_USER and ICLOUD_APP_PASSWORD (app-specific password) in the
environment or in the .env file next to this script.
"""
from __future__ import annotations

import os
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import caldav
from icalendar import Calendar

from ha_energy import _load_env

TZ = ZoneInfo("Europe/Berlin")
CALENDAR = "Family"
DAYS_AHEAD = 1  # 1 = today only
DAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


def _calendar() -> caldav.Calendar:
    _load_env()
    client = caldav.DAVClient(url="https://caldav.icloud.com/",
                              username=os.environ["ICLOUD_USER"],
                              password=os.environ["ICLOUD_APP_PASSWORD"], timeout=30)
    for cal in client.principal().calendars():
        # iCloud has a task list with the same name; we want the event calendar
        if cal.get_display_name() == CALENDAR and "VEVENT" in cal.get_supported_components():
            return cal
    raise LookupError(f"calendar {CALENDAR!r} not found")


def fetch(days: int = DAYS_AHEAD) -> list[dict]:
    """Events from the start of today to `days` days ahead, sorted by start.
    Each: {"date": date, "time": time | None (all-day), "title": str}."""
    start = datetime.combine(datetime.now(TZ).date(), time.min, TZ)
    end = start + timedelta(days=days)
    events = []
    for obj in _calendar().search(start=start, end=end, event=True, expand=True):
        for comp in Calendar.from_ical(obj.data).walk("VEVENT"):
            dt = comp.decoded("DTSTART")
            if isinstance(dt, datetime):
                dt = dt.astimezone(TZ) if dt.tzinfo else dt.replace(tzinfo=TZ)
                day, t = dt.date(), dt.time().replace(second=0, microsecond=0)
            else:  # all-day event
                day, t = dt, None
            if day < start.date():  # started on an earlier day, still running today
                t = None
            events.append({"date": max(day, start.date()), "time": t,
                           "title": str(comp.get("SUMMARY", "(ohne Titel)"))})
    return sorted(events, key=lambda e: (e["date"], e["time"] or time.min, e["title"]))


def label(ev: dict) -> str:
    """e.g. 'Sa 24.10. 14:30'; the date is dropped when only today is shown,
    and all-day events read 'ganztägig'."""
    d = ev["date"]
    s = "" if DAYS_AHEAD <= 1 else f"{DAYS[d.weekday()]} {d:%d.%m.} "
    return s + (f"{ev['time']:%H:%M}" if ev["time"] else "ganztägig" if DAYS_AHEAD <= 1
                else "")
