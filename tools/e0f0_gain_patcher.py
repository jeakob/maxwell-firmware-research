"""Set the E0F0 value at +0x90 (signed 16-bit) in a Maxwell headset image, and
optionally relabel the header version, so the image can be flashed without a
stock v1.0.1.63 downgrade first.

E0F0[0x90] is -30 in stock v46+ and -1 in v38. On one Xbox headset running the
v38mic image, lowering it to -30, -45, -60 and -90 reduced sidetone crackle at
every step with no change in mic level on calls (see custom-firmware/README.md).

The version label lives only in header TLV 0x0013. The running firmware keeps
reporting its own built-in version string, so a "v1.0.1.75" label always counts
as a version change against a v1.0.1.74 headset.

Usage:
  python e0f0_gain_patcher.py --in Maxwell_v1.0.1.74_XBOX_headset_v38mic.bin \\
      --gain -90 --version v1.0.1.75 --out Maxwell_v1.0.1.75_XBOX_headset_v38micg90.bin
"""
import argparse, hashlib, os, re, struct, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import firmware_patcher as fp  # noqa: E402
from sidetone_patcher import find_records, record_checksum, p2_slice  # noqa: E402

FIELD = 0x90


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in", dest="input", required=True, help="headset firmware image (e.g. a v38mic build)")
    ap.add_argument("--gain", type=int, required=True, help="new E0F0[0x90] value, -32768..32767")
    ap.add_argument("--version", help='header version label, e.g. "v1.0.1.75" (default: keep)')
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    raw = open(args.input, "rb").read()
    header, dec = fp.decompress_firmware(raw)
    s, e = p2_slice(header, dec)
    data = bytearray(dec)
    P = data[s:e]
    new = struct.pack("<h", args.gain)

    recs = find_records(P, "E0F0")
    if not recs:
        sys.exit("E0F0: record missing")
    for h, v0, vs in recs:
        old = struct.unpack("<h", P[v0 + FIELD:v0 + FIELD + 2])[0]
        P[v0 + FIELD:v0 + FIELD + 2] = new
        P[v0 + vs:v0 + vs + 2] = record_checksum(bytes(P[h:v0 + vs]))
        print(f"  E0F0 @P2+{h:#06x}: [{FIELD:#x}] {old} -> {args.gain}  (checksum updated)")
    data[s:e] = P

    # Re-verify every record checksum in the patched partition.
    bad = 0
    for m in re.finditer(rb"AB15\x00", P):
        h = m.start() - 20
        if h < 0 or P[h] != 0xFC:
            continue
        vs = struct.unpack("<H", P[h + 8:h + 10])[0]
        v0 = h + 20 + P[h + 6] + P[h + 7]
        bad += record_checksum(P[h:v0 + vs]) != P[v0 + vs:v0 + vs + 2]
    print(f"  NVDM record checksums after patch: {'all OK' if not bad else f'{bad} BAD'}")
    if bad:
        sys.exit(1)

    hdr = bytearray(fp.update_partition_hashes(header, bytes(data), fp.parse_partition_sizes(header)))
    if args.version:
        tag, ln = struct.unpack("<HH", hdr[0x10E:0x112])
        label = args.version.encode() + b"\x00"
        if tag != 0x0013 or len(label) > ln:
            sys.exit(f"version TLV not at 0x10E or label longer than {ln - 1} bytes")
        hdr[0x112:0x112 + ln] = label + b"\xff" * (ln - len(label))
        print(f"  version TLV -> {args.version}")
    out_raw = fp.compress_firmware(bytes(hdr), bytes(data))
    hdr = fp.update_lzma_stream_size(bytes(hdr), len(out_raw) - 0x1000)
    out = bytearray(hdr + out_raw[0x1000:])
    out[0:32] = hashlib.sha256(bytes(out[0x100:])).digest()
    open(args.out, "wb").write(out)

    # Independent re-verification of the written file.
    h2, d2 = fp.decompress_firmware(bytes(out))
    tlv, _, _ = fp.find_tlv_0014(h2)
    off, ok = 0, True
    for i, sz in enumerate(fp.parse_partition_sizes(h2)):
        ok &= hashlib.sha256(d2[off:off + sz]).digest() == bytes(h2[tlv + 8 + 32 * i:tlv + 40 + 32 * i])
        off += sz
    ok &= hashlib.sha256(bytes(out[0x100:])).digest() == bytes(out[:32])
    ok &= struct.unpack("<I", h2[0x10A:0x10E])[0] == len(out) - 0x1000
    ok &= d2 == bytes(data)
    print(f"Wrote {args.out} ({len(out)} bytes) — integrity checks: {'PASS' if ok else 'FAIL'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
