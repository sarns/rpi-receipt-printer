"""Quick hardware probe: status bytes, printer ID, and a test print."""
from btp2002 import Printer

with Printer() as p:
    for k in (1, 2, 3, 4):
        print("status", k, p.status(k))
    for name, cmd in [("model", b"\x1d\x49\x01"), ("type", b"\x1d\x49\x02"),
                      ("name", b"\x1d\x49\x43"), ("fw", b"\x1d\x49\x41")]:
        print(name, p.raw_probe(cmd))
    p.align("center")
    p.style(bold=True, width=2, height=2)
    p.text("BTP-2002NP")
    p.style()
    p.text("python test print")
    p.align("left")
    p.barcode("123456789")
    p.qr("https://example.com")
    p.feed(3)
