# Tools

Working scripts used during research. Treat as starting points, not
polished products.

## `firmware_patcher.py` — build custom v1.0.1.74 firmware

Decompresses a stock Maxwell v74 firmware, applies byte patches (L/R
balance, concurrent playback), recomputes the per-partition SHA-256 hashes
(TLV `0x0014`), updates the LZMA stream size field (TLV `0x0011`),
recompresses, and recomputes the outer SHA-256. Output is a firmware
that flashes successfully via the Audeze tool or any RACE FOTA path.

```bash
python firmware_patcher.py \
    --in /path/to/Maxwell_v1.0.1.74_XBOX_headset.bin \
    --out /path/to/my_custom_v74.bin \
    --usb-l 141 --usb-r 143 \
    --bt-l  141 --bt-r  154
```

Options:

- `--usb-l N --usb-r N` — USB-C L/R defaults (factory: 141/149)
- `--bt-l N --bt-r N` — BT/dongle L/R defaults (factory: 147/147)
- `--no-concurrent` — skip concurrent playback patches
- `--dry-run` — apply patches but don't write output
- `--verify-only` — just check the input firmware's integrity, don't patch

Then flash the resulting `.bin` via `MaxwellFlasherGUI.exe` from the
[downgrader tool](https://github.com/kats1123/maxwell-firmware-downgrader)
(replace the bundled `Maxwell_v1.0.1.74_XBOX_headset.bin` with your patched
build before launching).

After a successful flash, **do a factory reset on the headset** so the
new NVDM defaults take effect. Without a reset, the old balance values
stay loaded; the patches only execute during NVDM (re-)initialization.

## `dump_bootloader.py` — read 76 KB of bootloader from live device

Uses RACE `0x0403` page reads over USB HID to dump the first-stage
bootloader at flash address `0x08000000`–`0x08013000`. Requires the
headset connected via USB-C cable (PID `0x4B1E` for Xbox, `0x4B1A` for
PS). Saves to `maxwell_bootloader.bin` in the working directory.

Read-only — safe to run.

## `parse_dispatch.py` — print the RACE command dispatch table

Reads a decompressed Maxwell firmware and prints the 30-entry RACE
command dispatch table with known commands annotated. Useful for
finding undocumented command ranges to investigate.

## `find_all_nvdm_defaults.py` — scan factory NVDM writes

Disassembles the firmware to find every `BL nvdm_write_default` call
site, identifying the NVDM key, default value, and length. Shows what
settings are patchable persistently (will be applied after a factory
reset).

## Dependencies

```bash
pip install hidapi capstone
```

Some scripts also require:
- `lzma` (standard library, Python 3.x)
- `pefile` (for DLL analysis scripts, not included here)

## `compare_nvdm_keys.py` — NVDM keys and defaults across versions

Scans each decompressed image for `movw r0,#<key>` sites (keys `0xE000`–`0xF7FF`)
and the immediate loaded just before them, then prints one row per key across
all given firmware files. Used for the v56→v74 comparison in [V38.md](../V38.md).

```bash
KEYS=F665,F668,F66E python compare_nvdm_keys.py Maxwell_v1.0.1.56_XBOX_headset.bin Maxwell_v1.0.1.74_XBOX_headset.bin
```

## `sidetone_patcher.py` — restore the v38/v46 DSP filter on a newer base

Copies NVDM records from a stock v1.0.1.46 image into the FOTA NVDM
partition (P2) of a newer stock image, keeping each record the same size,
recomputing its checksum, then rebuilding and re-verifying the image with
`firmware_patcher.py`'s helpers. `--set filter` restores `E600` (the 32-tap
filter replaced in v51). `--set v46dsp` also restores `E048` and `E400`.
Untested on hardware.

```bash
python sidetone_patcher.py --in Maxwell_v1.0.1.74_XBOX_headset.bin \
    --ref Maxwell_v1.0.1.46_XBOX_headset.bin --set filter --out custom_v74_v38filter.bin
```
