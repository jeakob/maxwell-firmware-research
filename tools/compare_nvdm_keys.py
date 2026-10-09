"""Cross-version table of NVDM keys and the immediate value loaded next to them.

For every `movw r0,#key` (key in 0xE000-0xF7FF) in each decompressed image,
reports the nearest preceding `movw r2/r3,#imm` within 20 bytes -- which, at
nvdm_set_default call sites, is the factory default. `?` means the site has
no nearby immediate (a read, or a value loaded some other way); `-` means the
key is not referenced at all in that version.

Usage: KEYS=F665,F668,F66E python compare_nvdm_keys.py <fw1.bin> [fw2.bin ...]
       (omit KEYS to print every key)
"""
import lzma, os, struct, sys

def decompress(path):
    raw = open(path, "rb").read()
    payload = raw[0x1000:]
    fixed = payload[:5] + struct.pack("<Q", 0xFFFFFFFFFFFFFFFF) + payload[13:]
    return lzma.decompress(fixed, format=lzma.FORMAT_ALONE)

def decode_movw(b):
    """Decode a 4-byte buffer as Thumb-2 movw; return (rd, imm16) or None."""
    if len(b) < 4:
        return None
    hw1, hw2 = struct.unpack("<HH", b[:4])
    if (hw1 & 0xFBF0) != 0xF240 or hw2 & 0x8000:
        return None
    imm4 = hw1 & 0xF; i = (hw1 >> 10) & 1
    imm3 = (hw2 >> 12) & 7; rd = (hw2 >> 8) & 0xF; imm8 = hw2 & 0xFF
    return rd, (imm4 << 12) | (i << 11) | (imm3 << 8) | imm8

def scan(fw):
    sites = {}
    for o in range(0, len(fw) - 4, 2):
        m = decode_movw(fw[o:o + 4])
        if not m or m[0] != 0 or not (0xE000 <= m[1] <= 0xF7FF):
            continue
        val = None
        for back in range(4, 22, 2):
            v = decode_movw(fw[o - back:o - back + 4])
            if v and v[0] in (2, 3):
                val = v; break
        sites.setdefault(m[1], []).append(val)
    return sites

names = [p.replace("\\", "/").split("/")[-1] for p in sys.argv[1:]]
results = [scan(decompress(p)) for p in sys.argv[1:]]
want = {int(k, 16) for k in os.environ.get("KEYS", "").split(",") if k}
print(" | ".join(["key"] + names))
for key in sorted(set().union(*results)):
    if want and key not in want:
        continue
    row = [f"{key:#06x}"]
    for sites in results:
        vals = sites.get(key)
        row.append("-" if vals is None else ",".join(
            "?" if v is None else f"r{v[0]}={v[1]:#06x}" for v in vals[:3]))
    print(" | ".join(row))
