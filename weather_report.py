"""Fetch the weather for Mainz from Open-Meteo (no API key) and print it.

    python weather_report.py          # print on the BTP-2002NP
    python weather_report.py --dry    # only show the text on stdout
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime

import ha_energy
from weather_icons import category, icon

LAT, LON, CITY = 49.9929, 8.2473, "Mainz"
WIDTH = 32  # characters per line; safe for narrow paper
FEED_LINES = 12 # blank space after the report, so the tear/cut lands below the text

WMO = {
    0: "Klar", 1: "Überwiegend klar", 2: "Teils bewölkt", 3: "Bedeckt",
    45: "Nebel", 48: "Reifnebel",
    51: "Leichter Nieselregen", 53: "Nieselregen", 55: "Starker Nieselregen",
    56: "Gefrierender Niesel", 57: "Gefrierender Niesel",
    61: "Leichter Regen", 63: "Regen", 65: "Starker Regen",
    66: "Gefrierender Regen", 67: "Gefrierender Regen",
    71: "Leichter Schneefall", 73: "Schneefall", 75: "Starker Schneefall",
    77: "Schneegriesel", 80: "Leichte Schauer", 81: "Schauer",
    82: "Heftige Schauer", 85: "Schneeschauer", 86: "Starke Schneeschauer",
    95: "Gewitter", 96: "Gewitter mit Hagel", 99: "Starkes Gewitter",
}
DAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


def fetch(days: int = 3) -> dict:
    q = urllib.parse.urlencode({
        "latitude": LAT, "longitude": LON, "timezone": "Europe/Berlin",
        "forecast_days": days,
        "current": "temperature_2m,apparent_temperature,weather_code,"
                   "wind_speed_10m,relative_humidity_2m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
                 "precipitation_sum,precipitation_probability_max",
    })
    with urllib.request.urlopen(f"https://api.open-meteo.com/v1/forecast?{q}", timeout=15) as r:
        return json.load(r)


def describe(code: int) -> str:
    return WMO.get(code, f"Code {code}")


def build_lines(data: dict) -> list[tuple[str, str]]:
    """Return (style, text) lines; style is 'title', 'bold' or 'normal'."""
    cur, daily = data["current"], data["daily"]
    out = [
        ("title", CITY),
        ("normal", datetime.now().strftime("%d.%m.%Y %H:%M")),
        ("normal", "-" * WIDTH),
        ("icon", f"{category(cur['weather_code'])}:112:center"),
        ("bold", f"Jetzt: {cur['temperature_2m']:.0f}°C"),
        ("normal", describe(cur["weather_code"])),
        ("normal", f"Gefühlt {cur['apparent_temperature']:.0f}°C"),
        ("normal", f"Wind {cur['wind_speed_10m']:.0f} km/h, "
                   f"Feuchte {cur['relative_humidity_2m']:.0f}%"),
        ("normal", "-" * WIDTH),
    ]
    for i, day in enumerate(daily["time"]):
        d = datetime.strptime(day, "%Y-%m-%d")
        label = "Heute" if i == 0 else DAYS[d.weekday()] + d.strftime(" %d.%m.")
        out.append(("icon", f"{category(daily['weather_code'][i])}:64:left"))
        out.append(("bold", f"{label}: {daily['temperature_2m_min'][i]:.0f}"
                            f"..{daily['temperature_2m_max'][i]:.0f}°C"))
        out.append(("normal", describe(daily["weather_code"][i])))
        prob = daily["precipitation_probability_max"][i]
        out.append(("normal", f"Regen {daily['precipitation_sum'][i]:.1f} mm"
                              f" ({prob}%)" if prob is not None else
                              f"Regen {daily['precipitation_sum'][i]:.1f} mm"))
    return out


def energy_lines() -> list[tuple[str, str]]:
    """Battery level and yesterday's solar/consumption; skipped if HA is unreachable."""
    try:
        e = ha_energy.fetch()
    except Exception as exc:  # network, auth, missing token ...
        print(f"energy section skipped: {exc!r}", file=sys.stderr)
        return []
    return [
        ("normal", "-" * WIDTH),
        ("bold", "Energie"),
        ("normal", f"Batterie: {e['soc']:.0f}%"),
        ("normal", f"Solar gestern: {e['solar_kwh']:.1f} kWh"),
        ("normal", f"Verbrauch gestern: {e['load_kwh']:.1f} kWh"),
    ]


def room_lines() -> list[tuple[str, str]]:
    try:
        rooms = ha_energy.room_sensors()
    except Exception as exc:
        print(f"room section skipped: {exc!r}", file=sys.stderr)
        return []
    if not rooms:
        return []
    out = [("normal", "-" * WIDTH), ("bold", "Räume")]
    for r in rooms:
        out.append(("normal", f"{r['name'][:15]:<15} {r['temp']:4.1f}°C {r['humidity']:3.0f}%"))
    return out


def print_report(lines: list[tuple[str, str]]) -> None:
    from btp2002 import Printer

    with Printer() as p:
        for style, text in lines:
            if style == "title":
                p.align("center")
                p.style(bold=True, width=2, height=2)
                p.text(text)
                p.style()
            elif style == "icon":
                name, size, where = text.split(":")
                p.align(where)
                p.image(icon(name, int(size)))
            elif style == "bold":
                p.align("left")
                p.style(bold=True)
                p.text(text)
                p.style()
            else:
                p.align("left")
                p.text(text)
        p.feed(FEED_LINES)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="print to stdout only")
    args = ap.parse_args()
    lines = build_lines(fetch()) + energy_lines() + room_lines()
    if args.dry:
        print("\n".join(f"[icon {t}]" if s == "icon" else t for s, t in lines))
    else:
        print_report(lines)
