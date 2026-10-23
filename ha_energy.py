"""Fronius battery / solar / consumption figures from Home Assistant.

Reads HA_TOKEN (and optionally HA_URL) from the environment or a .env file
next to this script.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

HA_URL = "https://homeassistant.mz.arns-lab.net"
TZ = ZoneInfo("Europe/Berlin")

SOC = "sensor.reserva_state_of_charge"                    # battery state of charge, %
PV_TOTAL = "sensor.solarnet_energie_fronius_wechselrichter"  # lifetime PV energy, Wh
LOAD_POWER = "sensor.solarnet_power_load_consumed"        # house consumption, W (no energy counter exists)


def _load_env() -> None:
    env = Path(__file__).with_name(".env")
    if env.exists():
        for line in env.read_text().splitlines():
            k, sep, v = line.partition("=")
            if sep and not line.lstrip().startswith("#"):
                os.environ.setdefault(k.strip(), v.strip().strip("\"'"))


def _get(path: str):
    _load_env()
    base = os.environ.get("HA_URL", HA_URL).rstrip("/")
    req = urllib.request.Request(base + path,
                                 headers={"Authorization": "Bearer " + os.environ["HA_TOKEN"]})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def _history(entity: str, start: datetime, end: datetime) -> list[tuple[datetime, float]]:
    q = (f"/api/history/period/{urllib.parse.quote(start.isoformat())}"
         f"?end_time={urllib.parse.quote(end.isoformat())}"
         f"&filter_entity_id={entity}&minimal_response&no_attributes")
    data = _get(q)
    return [(datetime.fromisoformat(p["last_changed"]), float(p["state"]))
            for p in (data[0] if data else [])
            if p["state"] not in ("unknown", "unavailable")]


def _value_at(pts, t: datetime) -> float | None:
    v = None
    for ts, s in pts:
        if ts <= t:
            v = s
    return v if v is not None else (pts[0][1] if pts else None)


def _integrate_kwh(pts, start: datetime, end: datetime) -> float:
    """Integrate a power series (W, step-wise) over [start, end] into kWh."""
    wh, prev_t, prev_v = 0.0, start, _value_at(pts, start) or 0.0
    for t, v in [p for p in pts if p[0] > start] + [(end, 0.0)]:
        t = min(t, end)
        wh += prev_v * (t - prev_t).total_seconds() / 3600
        prev_t, prev_v = t, v
    return wh / 1000


def room_sensors() -> list[dict]:
    """Zigbee temperature/humidity sensors: any `<x>_temperature` that also has
    `<x>_humidity` and `<x>_battery` entities (Shelly, heat pump etc. have no battery)."""
    states = {s["entity_id"]: s for s in _get("/api/states")}
    rooms = []
    for eid, s in states.items():
        if not (eid.startswith("sensor.") and eid.endswith("_temperature")):
            continue
        base = eid[: -len("_temperature")]
        if f"{base}_humidity" not in states or f"{base}_battery" not in states:
            continue
        name = s["attributes"].get("friendly_name", base)
        for junk in ("Temperatursensor ", " Temperature"):
            name = name.replace(junk, "")
        try:
            temp = float(s["state"])
            hum = float(states[f"{base}_humidity"]["state"])
        except ValueError:  # unavailable / unknown
            continue
        rooms.append({"name": name, "temp": temp, "humidity": hum})
    return sorted(rooms, key=lambda r: r["name"])


def yesterday_bounds() -> tuple[datetime, datetime]:
    today = datetime.combine(datetime.now(TZ).date(), time.min, TZ)
    return today - timedelta(days=1), today


def fetch() -> dict:
    start, end = yesterday_bounds()
    pv = _history(PV_TOTAL, start - timedelta(hours=1), end + timedelta(minutes=5))
    load = _history(LOAD_POWER, start, end)
    return {
        "soc": float(_get(f"/api/states/{SOC}")["state"]),
        "solar_kwh": (_value_at(pv, end) - _value_at(pv, start)) / 1000,
        "load_kwh": _integrate_kwh(load, start, end),
    }
