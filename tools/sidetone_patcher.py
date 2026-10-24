"""Build a custom Maxwell headset firmware that restores v1.0.1.38/46-era DSP
NVDM values on top of a newer stock image (default base: v1.0.1.74).

What it patches: records in the FOTA NVDM partition (P2, flash 0x0832C000)
of the base image, keeping every record the same size and recomputing its
checksum. It then rebuilds the image with the same steps as
firmware_patcher.py (TLV 0x0014 partition hashes, recompress, TLV 0x0011
stream size, outer SHA-256) and re-verifies the result.

NVDM record layout (found by comparing records across v38..v74):
  20-byte header: u8 status(0xFC) u8 page u8 ? u8 0xFF | u16 offset |
                  u8 group_len u8 name_len | u16 value_size | u16 index |
                  u32 sequence | u32 name hash
  group name ("AB15\\0"), item name (e.g. "E600\\0"), value, u16 checksum
Checksum: two 8-bit lane sums (even/odd byte positions), computed
separately over header[1:20] and over (group+name+value), then added
lane-wise. Matches 292/292 (v38, v46, v56) and 299/299 (v74) records.

Sets:
  filter : AB15/E600 -> v38/v46 32-tap filter (replaced in v51)
  v46dsp : filter + AB15/E048 -> 0x0258 and AB15/E400[6] -> 0 (other
           same-size v51 DSP changes)

Usage:
  python sidetone_patcher.py --in Maxwell_v1.0.1.74_XBOX_headset.bin \\
      --ref Maxwell_v1.0.1.46_XBOX_headset.bin --set filter --out custom.bin
"""
import argparse, os, re, struct, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import firmware_patcher as fp  # noqa: E402  (reuses its rebuild/verify helpers)

SETS = {
    "filter": ["E600"],
    "v46dsp": ["E600", "E048", "E400"],
    # v38 mic/audio-IO config (changed in v46: "adjusted mic settings to
    # improve battery life"). Needs a v38 reference: --ref fota.bin,plain.bin
    "v38mic": ["E600", "E0F0"],
}


def lanes(b):
    return [sum(b[0::2]) & 0xFF, sum(b[1::2]) & 0xFF]


def record_checksum(rec_without_ck):
    a, b = lanes(rec_without_ck[1:20]), lanes(rec_without_ck[20:])
    return bytes([(a[0] + b[0]) & 0xFF, (a[1] + b[1]) & 0xFF])


def find_records(P, key):
    """All records for AB15/<key> in partition bytes P: list of (hdr_off, value_off, value_size)."""
    out = []
    for m in re.finditer(rb"AB15\x00" + key.encode() + rb"\x00", P):
        h = m.start() - 20
        if h < 0 or P[h] != 0xFC:
            continue
        vs = struct.unpack("<H", P[h + 8:h + 10])[0]
        v0 = h + 20 + P[h + 6] + P[h + 7]
        if record_checksum(P[h:v0 + vs]) != P[v0 + vs:v0 + vs + 2]:
            raise ValueError(f"{key}: existing checksum at {h:#x} does not verify — format mismatch")
        out.append((h, v0, vs))
    return out


def p2_slice(header, decompressed):
    sizes = fp.parse_partition_sizes(header)
    start = sum(sizes[:2])
    return start, start + sizes[2]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in", dest="input", required=True, help="stock base firmware (e.g. v1.0.1.74)")
    ap.add_argument("--ref", required=True, help="stock v1.0.1.46 firmware of the same platform (source of old values)")
    ap.add_argument("--set", choices=sorted(SETS), default="filter")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    raw = open(args.input, "rb").read()
    header, dec = fp.decompress_firmware(raw)
    # --ref is a stock FOTA file, or "fota.bin,plain.bin" for an encrypted
    # reference (v38) whose decrypted+decompressed image is supplied separately.
    ref_fota, *ref_plain = args.ref.split(",")
    ref_hdr = open(ref_fota, "rb").read()[:0x1000]
    if ref_plain:
        ref_dec = open(ref_plain[0], "rb").read()
    else:
        _, ref_dec = fp.decompress_firmware(open(ref_fota, "rb").read())
    s, e = p2_slice(header, dec)
    rs, re_ = p2_slice(ref_hdr, ref_dec)
    data = bytearray(dec)
    P, R = data[s:e], ref_dec[rs:re_]

    for key in SETS[args.set]:
        recs, refs = find_records(P, key), find_records(R, key)
        if not recs or not refs:
            sys.exit(f"{key}: record missing in base or reference")
        _, rv0, rvs = refs[-1]
        new_val = R[rv0:rv0 + rvs]
        for h, v0, vs in recs:
            if vs != rvs:
                sys.exit(f"{key}: size differs (base {vs}, ref {rvs}) — refusing to resize records")
            old = bytes(P[v0:v0 + vs])
            P[v0:v0 + vs] = new_val
            P[v0 + vs:v0 + vs + 2] = record_checksum(bytes(P[h:v0 + vs]))
            print(f"  {key} @P2+{h:#06x}: {old[:12].hex()}… -> {new_val[:12].hex()}…  (checksum updated)")
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

    hdr = fp.update_partition_hashes(header, bytes(data), fp.parse_partition_sizes(header))
    out_raw = fp.compress_firmware(hdr, bytes(data))
    hdr = fp.update_lzma_stream_size(hdr, len(out_raw) - 0x1000)
    out = bytearray(hdr + out_raw[0x1000:])
    out[0:32] = fp.hashlib.sha256(bytes(out[0x100:])).digest()
    open(args.out, "wb").write(out)

    # Independent re-verification of the written file.
    h2, d2 = fp.decompress_firmware(bytes(out))
    tlv, _, _ = fp.find_tlv_0014(h2)
    off, ok = 0, True
    for i, sz in enumerate(fp.parse_partition_sizes(h2)):
        ok &= fp.hashlib.sha256(d2[off:off + sz]).digest() == bytes(h2[tlv + 8 + 32 * i:tlv + 40 + 32 * i])
        off += sz
    ok &= fp.hashlib.sha256(bytes(out[0x100:])).digest() == bytes(out[:32])
    ok &= d2 == bytes(data)
    print(f"Wrote {args.out} ({len(out)} bytes) — integrity checks: {'PASS' if ok else 'FAIL'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
