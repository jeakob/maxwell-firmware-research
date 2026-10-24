"""READ-ONLY check: is the headset on the v38mic image?

Takes the expected E600/E0F0 values from the custom-firmware v38mic and
v38filter images for the connected platform, then reads the FOTA NVDM (P2)
and live NVDM partitions over RACE 0x0403 (same page read as check_e600.py;
nothing is written) and compares.

Usage (Windows, headset on USB-C, Audeze app and MaxwellTool closed):
  pip install hidapi
  python check_v38mic.py
"""
import os, re, struct, sys, time
import hid

HERE = os.path.dirname(os.path.abspath(__file__))
IMGS = os.path.join(HERE, "..", "custom-firmware")
sys.path.insert(0, HERE)
import firmware_patcher as fp  # noqa: E402

VID, PLATFORM = 0x3329, {0x4B1A: "PS4", 0x4B1E: "XBOX"}
P2_BASE, P2_SIZE = 0x0832C000, 0x14000
LIVE_BASE, LIVE_SIZE = 0x087F6000, 0xA000
KEYS = ["E600", "E0F0"]


def records(P, key):
    """Latest-first list of (hdr_off, seq, value) for AB15/<key>."""
    out = []
    for m in re.finditer(rb"AB15\x00" + key.encode() + rb"\x00", P):
        h = m.start() - 20
        if h < 0 or P[h] != 0xFC:
            continue
        vs = struct.unpack("<H", P[h + 8:h + 10])[0]
        seq = struct.unpack("<I", P[h + 12:h + 16])[0]
        v0 = h + 20 + P[h + 6] + P[h + 7]
        out.append((h, seq, bytes(P[v0:v0 + vs])))
    return sorted(out, key=lambda r: -r[1])


def image_p2(name):
    with open(os.path.join(IMGS, name), "rb") as f:
        header, dec = fp.decompress_firmware(f.read())
    sizes = fp.parse_partition_sizes(header)
    start = sum(sizes[:2])
    return dec[start:start + sizes[2]]


class R:
    def __init__(self):
        d = next((d for d in hid.enumerate()
                  if d["vendor_id"] == VID and d["product_id"] in PLATFORM and d["usage_page"] == 0xFF13), None)
        if not d:
            sys.exit("Headset not found on USB-C. Close the Audeze app / MaxwellTool and reconnect.")
        self.platform = PLATFORM[d["product_id"]]
        self.dev = hid.device(); self.dev.open_path(d["path"])
        for _ in range(8):
            if struct.unpack("<H", bytes(self.dev.get_input_report(7, 62))[1:3])[0] == 0:
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

    def read_region(self, base, size):
        out = bytearray()
        for a in range(base, base + size, 0x100):
            for _ in range(3):
                p = self.read_page(a)
                if p and len(p) == 256:
                    break
            else:
                sys.exit(f"read failed at {a:#x}")
            out += p
        return bytes(out)


r = R()
mic = image_p2(f"Maxwell_v1.0.1.74_{r.platform}_headset_v38mic.bin")
flt = image_p2(f"Maxwell_v1.0.1.74_{r.platform}_headset_v38filter.bin")
want = {k: records(mic, k)[0][2] for k in KEYS}
old = {k: records(flt, k)[0][2] for k in KEYS}   # v38filter keeps stock v74 E0F0


def label(k, v):
    if v == want[k]:
        return "matches v38mic image"
    if v == old[k]:
        return "matches v38filter image (stock v74 E0F0)"
    return "other: " + v[:16].hex()


print(f"{r.platform} headset")
print(f"Reading FOTA NVDM (P2) {P2_BASE:#x} (+{P2_SIZE:#x}) ...")
P2 = r.read_region(P2_BASE, P2_SIZE)
for k in KEYS:
    for h, seq, v in records(P2, k):
        print(f"   {k} @+{h:#06x} seq={seq}: {label(k, v)}")
print(f"Reading live NVDM {LIVE_BASE:#x} (+{LIVE_SIZE:#x}) ...")
L = r.read_region(LIVE_BASE, LIVE_SIZE)
for k in KEYS:
    recs = records(L, k)
    if not recs:
        print(f"   no {k} record")
    for h, seq, v in recs:
        print(f"   {k} @+{h:#06x} seq={seq}: {label(k, v)}")
