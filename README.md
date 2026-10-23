# rpi-receipt-printer

Python USB interface for the Orient/SNBC BTP-2002NP (USB id 154f:1001), plus a
morning report printed on it. The device is vendor-specific, so Linux binds no
driver and creates no `/dev/usb/lp0`; `btp2002` talks to it directly with
libusb (pyusb) using ESC/POS.

## Setup (on the Pi, `ssh rpi-printer`)

    sudo cp 99-btp2002.rules /etc/udev/rules.d/
    sudo udevadm control --reload && sudo udevadm trigger
    python3 -m venv ~/printer-venv && ~/printer-venv/bin/pip install -r requirements.txt

Code lives in `~/rpi-receipt-printer`. Test the printer with
`~/printer-venv/bin/python probe.py`, or `from btp2002 import Printer`.

## Morning report

`weather_report.py` prints, in this order: weather for Mainz with icons
(Open-Meteo), today's entries of the iCloud "Family" calendar, Fronius battery
level plus yesterday's solar production and consumption, and temperature /
humidity of all Zigbee room sensors (Home Assistant). A section is skipped if
its source is unreachable. `--dry` prints to stdout instead of the printer.

Secrets go in `~/rpi-receipt-printer/.env` on the Pi (mode 600, not in git):

    HA_TOKEN=...                  # Home Assistant long-lived access token
    ICLOUD_USER=...               # Apple ID
    ICLOUD_APP_PASSWORD=...       # app-specific password from appleid.apple.com

Settings: `FEED_LINES` (blank space before cutting) in `weather_report.py`,
`CALENDAR` / `DAYS_AHEAD` in `calendar_events.py`, entity ids at the top of
`ha_energy.py`.

## Cron job

The report prints every day at 07:45 (the Pi's timezone is Europe/Berlin). The
job is in the `sarns` user's crontab on the Pi; `crontab.example` is a copy:

    crontab crontab.example       # install (replaces the existing crontab)
    crontab -l                    # check
    tail morning.log              # output and errors of the last runs

Run it by hand any time with
`cd ~/rpi-receipt-printer && ~/printer-venv/bin/python weather_report.py`.
For weekdays only, change `* * *` to `* * 1-5` in the crontab.

## Gotchas

- Don't install `niquests` in the venv: it replaces urllib3 with
  urllib3-future, which tries HTTP/3 and fails here with "Message too long".
- Use the Windows OpenSSH (PowerShell) for `ssh rpi-printer`; it reaches the
  1Password agent, Git Bash's ssh doesn't.
