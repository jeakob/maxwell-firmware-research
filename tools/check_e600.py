"""READ-ONLY check: is the restored v38/v46 E600 filter on the headset, and is
a live-NVDM copy overriding it?

Reads flash over RACE 0x0403 (the same page read dump_bootloader.py uses;
nothing is written):
  1. the FOTA NVDM partition at 0x0832C000 (80 KB) -> E600 record(s)
  2. the live NVDM partition at 0x087F6000 (40 KB)  -> any E600 record(s)

Usage (Windows, headset on USB-C, Audeze app and MaxwellTool closed):
  pip install hidapi
  python check_e600.py
"""
import struct, sys, time, re, hid

VID, PIDS = 0x3329, [0x4B1A, 0x4B1E]
REGIONS = {"FOTA NVDM (P2)": (0x0832C000, 0x14000), "live NVDM": (0x087F6000, 0xA000)}
V46 = bytes.fromhex("01010100fdff0600f6ff0f00ebff1e00d7ff3700b7ff5e0088ff970045ffe600"
                    "e9fe51016dfee101c4fda702dafcc00382fb71054ef97708d2f4f70f0ae56c51")
V51 = bytes.fromhex("0101e7ffe6ffe3ffdeffd8ffcdffc4ffb2ffa6ff8cff80ff5eff55ff2aff27ff"
                    "f3fefbfeb9fed3fe7ffeb3fe43fea0fefdfda7fe99fd13ffa4fc300209eedf4a")


def find_race_path():
    for d in hid.enumerate():
        if d["vendor_id"] == VID and d["product_id"] in PIDS and d["usage_page"] == 0xFF13:
            return d["path"]
    return None


class R:
    def __init__(self):
        path = find_race_path()
        if not path:
            sys.exit("Headset not found on USB-C. Close the Audeze app / MaxwellTool and reconnect.")
        self.dev = hid.device(); self.dev.open_path(path)
        for _ in range(8):
            r = bytes(self.dev.get_input_report(7, 62))
            if struct.unpack("<H", r[1:3])[0] == 0:
                break

    def read_page(self, addr):
        body = struct.pack("<BBHH", 0x05, 0x5A, 0x0008, 0x0403) + bytes([0, 1]) + struct.pack("<I", addr)
        self.dev.write(b"\x06" + struct.pack("<H", len(body)) + body)
        deadline, acc = time.time() + 1.0, b""
        while time.time() < deadline:
            r = bytes(self.dev.get_input_report(7, 62))
            n = struct.unpack("<H", r[1:3])[0]
            if n == 0:
                if acc:
                    break
                time.sleep(0.005); continue
            acc += r[3:3 + n]
        if len(acc) < 14 or struct.unpack("<H", acc[4:6])[0] != 0x0403:
            return None
        return acc[14:14 + 256]


def read_region(r, base, size):
    out = bytearray()
    for a in range(base, base + size, 0x100):
        for _ in range(3):
            p = r.read_page(a)
            if p and len(p) == 256:
                break
        else:
            sys.exit(f"read failed at {a:#x}")
        out += p
    return bytes(out)


def e600_records(P):
    found = []
    for m in re.finditer(rb"E600\x00", P):
        h = m.start() - 25          # 20-byte header + "AB15\0"
        if h < 0 or P[h] != 0xFC:
            continue
        vs = struct.unpack("<H", P[h + 8:h + 10])[0]
        seq = struct.unpack("<I", P[h + 12:h + 16])[0]
        v0 = h + 20 + P[h + 6] + P[h + 7]
        found.append((h, seq, P[v0:v0 + vs]))
    return found


def label(v):
    return "v38/v46 filter (restored)" if v == V46 else "v51+ filter (stock)" if v == V51 else "other: " + v[:16].hex()


r = R()
for name, (base, size) in REGIONS.items():
    print(f"Reading {name} {base:#x} (+{size:#x}) ...")
    recs = e600_records(read_region(r, base, size))
    if not recs:
        print("   no E600 record")
    for h, seq, v in recs:
        print(f"   E600 @+{h:#06x} seq={seq}: {label(v)}")
