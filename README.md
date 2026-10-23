# rpi-receipt-printer

Python USB interface for the Orient/SNBC BTP-2002NP (USB id 154f:1001).
The device is vendor-specific, so Linux binds no driver and creates no
`/dev/usb/lp0`; `btp2002` talks to it directly with libusb (pyusb) using ESC/POS.

One-time setup on the Pi:

    sudo cp 99-btp2002.rules /etc/udev/rules.d/
    sudo udevadm control --reload && sudo udevadm trigger
    python3 -m venv ~/printer-venv && ~/printer-venv/bin/pip install -r requirements.txt

Then `~/printer-venv/bin/python probe.py`, or `from btp2002 import Printer`.
