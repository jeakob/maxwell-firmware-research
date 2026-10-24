# Custom v1.0.1.74 headset firmware — v38-era DSP filter

> **Partly tested on hardware.** The Xbox `v38filter` and `v38mic` images, and
> `v38mic` builds with a lower `E0F0` gain, have been flashed to one Xbox headset
> (see [Hardware results](#hardware-results)).
> The PS4 images and the `v38v46dsp` images have not been flashed. Flash at your own risk.

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
| `Maxwell_v1.0.1.74_XBOX_headset_v38mic.bin` | `E600`, `E0F0` (from v38) | `c30853ff8ad35fea5c2de336ed7a83c3af5c698c07b551fe3d0ce1a7017c93cc` |
| `Maxwell_v1.0.1.74_PS4_headset_v38mic.bin` | `E600`, `E0F0` (from v38) | `121aa82207f2788e3748f7bd3811b916c4b456f3bda5852a09f2d6fd5fd85d53` |

**For crackly boom-mic sidetone, try a `v38mic` image.** For the filter alone, use `v38filter`.

## What changed

- **`E600`** is a 32-tap filter. Audeze replaced it in v51, the release whose notes say
  "improved noise levels in some sidetone scenarios". The v38/v46 filter
  rises towards the top of the band, ending about +7 dB at Nyquist. The v51+ filter cuts the
  lowest band about 23 dB and has no top-end boost. It is most likely on the mic/sidetone
  path, but that is inferred, not proven.
- **`E0F0`** (164 bytes, most likely the audio I/O / mic configuration). This is the only
  mic-related record that changed from v38 to v46. Several fields go from `0x1f`
  to `0x02`, and one goes from `0xffff` to `0xffe2` (−30). v46's notes say "adjusted mic
  settings to improve battery life" and add the known issue "some users hear low-level noise
  with sidetone enabled". The `v38mic` images restore v38's value.
- **`E048`** (`0x0258` → `0`) and **`E400[6]`** (`0` → `1`) are the other
  same-size DSP changes made in v51. Their meaning is unknown.

Only those NVDM records and their checksums differ in the decompressed image.
In the header, only the LZMA stream size and the partition-2 hash change.

## How to flash (with kats1123's [maxwell-balance-and-firmware-tool](https://github.com/kats1123/maxwell-balance-and-firmware-tool))

1. Copy the `.bin` for your platform into the tool's `custom\` folder.
2. If the headset is already on v1.0.1.74, flash **stock v1.0.1.63** first (same-version rule),
   or relabel the image as `v1.0.1.75` (see [Skipping the v63 downgrade](#skipping-the-v63-downgrade)).
3. Flash the custom image, then do a **Factory Reset**.

If the headset reads `E600` from its live NVDM rather than this partition,
the image will behave like stock v74. To undo it, flash stock v63 or v74 again.

## Hardware results

One Xbox headset on USB-C (PID `0x4B1E`), flashed with MaxwellTool v2.3, October 2026:

| Image | Flash | On-device check | Boom-mic sidetone |
|-------|-------|-----------------|-------------------|
| `XBOX_headset_v38filter` | OK | [`check_e600.py`](../tools/check_e600.py): P2 holds the v38/v46 `E600`; no `E600` in live NVDM | Still crackly |
| `XBOX_headset_v38mic` (stock v63 first, then factory reset) | OK | [`check_v38mic.py`](../tools/check_v38mic.py): P2 `E600` and `E0F0` both match the image; neither key is in live NVDM | Much better |

The filter alone made no audible difference, so on this unit the crackle comes
from the v46 `E0F0` mic change rather than from `E600`. This rests on one
headset and one listener.

### `E0F0[0x90]` gain tests

`v38mic` still left some hiss/crackle, even at the lowest sidetone setting.
Only seven 16-bit values in `E0F0` differ between v38 and v74:

| Byte offset | v74 | v38 |
|-------------|-----|-----|
| `0x4A`, `0x4E`, `0x58`, `0x6D`, `0x82`, `0x99` | `0x02` | `0x1F` |
| `0x90` (signed 16-bit) | **−30** | **−1** |

`0x90` is the only one that looks like a level. Its units are unknown. Keeping
the six `0x1F` bytes from v38 and lowering `0x90` step by step, on the same
headset (each image built with [`tools/e0f0_gain_patcher.py`](../tools/e0f0_gain_patcher.py),
labelled `v1.0.1.75`, flashed directly, then factory reset):

| `E0F0[0x90]` | Sidetone crackle | Mic level on calls | On-device check |
|--------------|------------------|--------------------|-----------------|
| −1 (`v38mic`) | Much better than stock, still there | — | P2 = image |
| −30 | Less noticeable | No change reported | P2 = −30, no live `E0F0` |
| −45 | Better again | — | P2 = −45, no live `E0F0` |
| −60 | Noticeably better | — | — |
| −75 | Built, not flashed | — | — |
| −90 | **Almost completely gone** | — | P2 = −90, no live `E0F0` |

Every step down helped. At −90 the crackle is almost completely gone, and it
is the setting kept. Values below −90 were not tried, and nothing here says
whether `0x90` touches the mic path, the sidetone path, or both. The `0x1F`
bytes appear to be what removes most of the crackle, since −30 with them is
much better than stock −30 without them.

To build the −90 image:

```bash
python tools/e0f0_gain_patcher.py --in custom-firmware/Maxwell_v1.0.1.74_XBOX_headset_v38mic.bin \
    --gain -90 --version v1.0.1.75 --out Maxwell_v1.0.1.75_XBOX_headset_v38micg90.bin
```

The output matches the flashed image byte for byte (SHA-256
`1392d2d21250a7b9b1b5e3c7bdd74121c750c9360ea345c980512b5d5878211f`).

## Skipping the v63 downgrade

The same-version rule appears to compare the image's header version (TLV
`0x0013`) with what the headset reports. The header label is not covered by the
partition hashes, only by the outer SHA-256, so it can be changed freely.

An image relabelled `v1.0.1.75` flashed straight onto a headset running a
custom v1.0.1.74, with no v63 step. Read back over RACE `0x0403` afterwards:

- the FOTA staging header at `0x084A1000` is erased after the update, so the
  `.75` label is gone;
- the running code still holds its built-in `-v1.0.1.74` string (at flash
  `0x0028EA1F` in these builds).

So the headset keeps reporting v1.0.1.74, and every `.75`-labelled build can be
flashed directly. Four `.75` builds (−30, −45, −60, −90) were flashed in a row
this way. The Audeze app was not checked.
