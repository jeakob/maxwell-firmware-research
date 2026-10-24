# Custom v1.0.1.74 headset firmware — v38-era DSP filter

> **Untested on hardware.** These images pass every integrity check the
> bootloader performs, but no one has flashed one yet. Flash at your own risk.

Each image is stock Audeze **v1.0.1.74** headset firmware with DSP NVDM records
restored to their v1.0.1.38 / v1.0.1.46 values. They were built with
[`tools/sidetone_patcher.py`](../tools/sidetone_patcher.py), using stock v1.0.1.46
as the reference.

| File | Changes vs stock v74 | SHA-256 |
|------|----------------------|---------|
| `Maxwell_v1.0.1.74_XBOX_headset_v38filter.bin` | `E600` | `0d5113c4782f9f613d7d71cc98d0a1aacf3afdeeaa5bc2488823fcb356c79200` |
| `Maxwell_v1.0.1.74_PS4_headset_v38filter.bin` | `E600` | `e430dfdb254510a8b096f40608b6a8f84140c0d94fd96b18a1111ac11ef466ef` |
| `Maxwell_v1.0.1.74_XBOX_headset_v38v46dsp.bin` | `E600`, `E048`, `E400[6]` | `a13060cfba9d588953e7f4eb536a13e3afeca626f276e82ddad2617cfed51e3d` |
| `Maxwell_v1.0.1.74_PS4_headset_v38v46dsp.bin` | `E600`, `E048`, `E400[6]` | `82ad297cb3cbc9fb8a57b0e2f1fcafecc73935d3068d4886f2393d729a4b5898` |

Start with a **`v38filter`** image.

## What changed

- **`E600`** is a 32-tap filter. Audeze replaced it in v51, the release whose notes say
  "improved noise levels in some sidetone scenarios". The v38/v46 filter
  rises towards the top of the band, ending about +7 dB at Nyquist. The v51+ filter cuts the
  lowest band about 23 dB and has no top-end boost. It is most likely on the mic/sidetone
  path, but that is inferred, not proven.
- **`E048`** (`0x0258` → `0`) and **`E400[6]`** (`0` → `1`) are the other
  same-size DSP changes made in v51. Their meaning is unknown.

Only those NVDM records and their checksums differ in the decompressed image.
In the header, only the LZMA stream size and the partition-2 hash change.

## How to flash (with kats1123's [maxwell-balance-and-firmware-tool](https://github.com/kats1123/maxwell-balance-and-firmware-tool))

1. Copy the `.bin` for your platform into the tool's `custom\` folder.
2. If the headset is already on v1.0.1.74, flash **stock v1.0.1.63** first (same-version rule).
3. Flash the custom image, then do a **Factory Reset**.
4. Optional: set the balance to about **136/136** to match v38's output level (v74 default is 147).

If the headset reads `E600` from its live NVDM rather than this partition,
the image will behave like stock v74. To undo it, flash stock v63 or v74 again.
