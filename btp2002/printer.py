"""Userspace USB driver for the SNBC / Orient BTP-2002NP thermal printer.

The printer exposes a vendor-specific USB interface (bulk OUT 0x01, bulk IN
0x82/0x83), so the kernel's ``usblp`` driver never binds and no /dev/usb/lp0
appears. This talks to it directly through libusb (pyusb) using ESC/POS
commands, which SNBC printers of this family emulate.
"""
from __future__ import annotations

import time

import usb.core
import usb.util

VID, PID = 0x154F, 0x1001
EP_OUT, EP_IN = 0x01, 0x82

ESC, GS, LF, DLE = b"\x1b", b"\x1d", b"\n", b"\x10"


class PrinterError(Exception):
    pass


class Printer:
    def __init__(self, vid: int = VID, pid: int = PID, timeout_ms: int = 5000):
        self.timeout = timeout_ms
        self.dev = usb.core.find(idVendor=vid, idProduct=pid)
        if self.dev is None:
            raise PrinterError("printer not found (check USB cable / power)")
        try:
            if self.dev.is_kernel_driver_active(0):
                self.dev.detach_kernel_driver(0)
        except (NotImplementedError, usb.core.USBError):
            pass
        try:
            self.dev.set_configuration()
        except usb.core.USBError as e:
            if e.errno == 13:
                raise PrinterError(
                    "permission denied: install 99-btp2002.rules (see README)"
                ) from e
            raise
        self.encoding = "cp437"
        self.initialize()

    # -- low level -------------------------------------------------------
    def write(self, data: bytes, chunk: int = 4096) -> None:
        for i in range(0, len(data), chunk):
            self.dev.write(EP_OUT, data[i : i + chunk], self.timeout)

    def read(self, n: int = 64, timeout_ms: int = 1000) -> bytes:
        try:
            return bytes(self.dev.read(EP_IN, n, timeout_ms))
        except usb.core.USBTimeoutError:
            return b""

    def close(self) -> None:
        usb.util.dispose_resources(self.dev)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # -- status ----------------------------------------------------------
    def status(self, kind: int = 1) -> int | None:
        """Real-time status (DLE EOT n). kind: 1 printer, 2 offline, 3 error, 4 paper."""
        self.write(DLE + b"\x04" + bytes([kind]))
        time.sleep(0.2)
        r = self.read(8, 500)
        return r[0] if r else None

    def paper_ok(self) -> bool | None:
        s = self.status(4)
        return None if s is None else not (s & 0x60)

    # -- text ------------------------------------------------------------
    def initialize(self) -> None:
        self.write(ESC + b"@")

    def text(self, s: str = "", end: str = "\n") -> None:
        self.write((s + end).encode(self.encoding, errors="replace"))

    def set_codepage(self, n: int, encoding: str) -> None:
        self.write(ESC + b"t" + bytes([n]))
        self.encoding = encoding

    def align(self, where: str = "left") -> None:
        self.write(ESC + b"a" + bytes([{"left": 0, "center": 1, "right": 2}[where]]))

    def style(self, bold=False, underline=False, invert=False,
              width: int = 1, height: int = 1) -> None:
        if not (1 <= width <= 8 and 1 <= height <= 8):
            raise ValueError("width/height must be 1..8")
        self.write(ESC + b"E" + bytes([bold]))
        self.write(ESC + b"-" + bytes([2 if underline else 0]))
        self.write(GS + b"B" + bytes([invert]))
        self.write(GS + b"!" + bytes([((width - 1) << 4) | (height - 1)]))

    def feed(self, lines: int = 1) -> None:
        self.write(ESC + b"d" + bytes([lines]))

    def cut(self, partial: bool = True) -> None:
        self.write(GS + b"V" + bytes([66 if partial else 65, 0]))

    # -- labels / gap sensor --------------------------------------------
    def feed_to_label(self) -> None:
        """Advance to the next label gap/black mark (FF in label mode)."""
        self.write(b"\x0c")

    # -- barcodes / QR ---------------------------------------------------
    def barcode(self, data: str, kind: int = 73, height: int = 80,
                width: int = 2, hri: int = 2) -> None:
        """kind 73 = CODE128, 67 = EAN13, 69 = CODE39 (GS k m n d1..dn)."""
        d = data.encode("ascii")
        if kind == 73:
            d = b"{B" + d
        self.write(GS + b"h" + bytes([height]) + GS + b"w" + bytes([width])
                   + GS + b"H" + bytes([hri]))
        self.write(GS + b"k" + bytes([kind, len(d)]) + d + LF)

    def qr(self, data: str, size: int = 6, ec: int = 49) -> None:
        d = data.encode("utf-8")
        n = len(d) + 3
        self.write(GS + b"(k\x04\x00\x31\x41\x32\x00")
        self.write(GS + b"(k\x03\x00\x31\x43" + bytes([size]))
        self.write(GS + b"(k\x03\x00\x31\x45" + bytes([ec]))
        self.write(GS + b"(k" + bytes([n & 255, n >> 8]) + b"\x31\x50\x30" + d)
        self.write(GS + b"(k\x03\x00\x31\x51\x30")

    # -- images ----------------------------------------------------------
    def image(self, img, max_width: int = 384) -> None:
        """Print a PIL image (or path) as a raster bitmap (GS v 0)."""
        from PIL import Image

        if isinstance(img, str):
            img = Image.open(img)
        if img.width > max_width:
            img = img.resize((max_width, int(img.height * max_width / img.width)))
        img = img.convert("L").convert("1")  # dithered 1-bit
        w = (img.width + 7) // 8
        px = img.load()
        rows = bytearray()
        for y in range(img.height):
            for bx in range(w):
                b = 0
                for bit in range(8):
                    x = bx * 8 + bit
                    if x < img.width and px[x, y] == 0:
                        b |= 0x80 >> bit
                rows.append(b)
        self.write(GS + b"v0\x00" + bytes([w & 255, w >> 8, img.height & 255,
                                           img.height >> 8]) + bytes(rows))

    def raw_probe(self, cmd: bytes, wait: float = 0.3) -> bytes:
        """Send raw bytes and return whatever the printer answers."""
        self.read(64, 20)
        self.write(cmd)
        time.sleep(wait)
        return self.read(256, 500)
