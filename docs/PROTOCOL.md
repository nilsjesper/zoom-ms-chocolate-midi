# Protocol notes

Everything here was worked out by experiment on one setup: an **original Zoom MS-50G**
(firmware 3.10, identity model byte `0x58`) and an **M-VAVE Chocolate Plus** programmed with
CubeSuite on macOS. "Verified" means observed on that hardware; anything else is marked.

Not affiliated with Zoom or M-VAVE.

## Zoom MS-50G (original, not the MS-50G+)

The MS Plus series (MS-50G+, MS-70CDR+, …) uses a different protocol (model byte `0x6E`).
Tools written only for the Plus series do not work on the original MS-50G. Original-series
family codes are `58` (MS-50G), `5F` (MS-60B) and `61` (MS-70CDR).

Rows and notes marked **[zx]** come from reading the
[thammer/zoom-explorer](https://github.com/thammer/zoom-explorer) source (`src/ZoomDevice.ts`,
`src/ZoomPatch.ts`), which drives the original MS series as well. They have not been verified on
this pedal yet; the remaining checks are in [`TESTPLAN.md`](TESTPLAN.md).

All SysEx below starts with `F0 52 00 58` (Zoom manufacturer id `52`, device `00`, model `58`).

| Message | Bytes | Notes |
|---|---|---|
| Identity request | `F0 7E 00 06 01 F7` | Reply includes model `58` and firmware as ASCII (`3.10`). |
| Program Change | `C0 pp` | Selects patch; `pp` = 0–49 = pedal patch 1–50. |
| Tuner | `B0 4A vv` | CC 74; `vv` ≥ 64 on, < 64 off. |
| Editor mode on | `F0 52 00 58 50 F7` | **Required once after power-up** before parameter edits work. |
| Editor mode off | `F0 52 00 58 51 F7` | Without it the pedal stays unlocked until power-cycled. Also **reverts the edit buffer**, discarding unsaved edits (verified: effect toggled by `31`, then `51`, reads back as stored). |
| Effect on/off | `F0 52 00 58 31 ss 00 vv 00 F7` | `ss` = slot 0–2, `vv` = 01 on / 00 off. **Effects 4–6 are ignored.** |
| Parameter edit | `F0 52 00 58 31 ss pp lo hi F7` | `pp` = 2… for knobs (from the g200kg doc; effects 1–3 only). |
| Edit report (pedal → host) | `F0 52 00 58 31 ss pp lo hi F7` | **[zx]** Sent by the pedal, in editor mode, for every edit made on the pedal: `pp` = 0 is on/off, 2… knobs. |
| Current program | `F0 52 00 58 33 F7` | Reply: `B0 00 00 B0 20 00 C0 pp`. **[zx]** The pedal never sends a PC on its own when the user changes patch; zoom-explorer polls this every 500 ms. |
| Read patch | `F0 52 00 58 29 F7` | Reply: 146-byte patch starting `F0 52 00 58 28`. **[zx]** Right after an effect is added or deleted on the pedal the effect-count field can be stale; read again. |
| Read stored patch | `F0 52 00 58 09 00 00 pp F7` | **[zx]** Reply `F0 52 00 58 08 00 00 pp <len lo> <len hi> <patch>`; byte 7 echoes `pp`. Reads a slot without changing program (`backup` currently uses PC + `29`). |
| Write patch | `F0 52 00 58 28 <patch> F7` | Writes the current patch (in memory). |
| Store patch | `F0 52 00 58 32 01 00 00 pp 00 00 00 00 00 F7` | Saves to memory slot `pp`. Destructive. |
| Read settings | `F0 52 00 58 2B F7` | Reply: `2A` + 28 bytes; see below. |

**Patch data:** in the raw 146-byte message, effect on/off is bit 0 of bytes 6, 26, 47, 67, 88,
108 (effects 1–6) and tempo is in bytes 130–131. Details in the
[g200kg MIDI message doc](https://github.com/g200kg/zoom-ms-utility/blob/master/midimessage.md).

The raw message is a 5-byte header plus 7-bit groups (1 MSB byte + 7 data bytes), so unpacked
offset `u` sits at raw byte `6 + 8·(u div 7) + (u mod 7)`. **[zx]** Unpacked layout, from
`ZoomPatch.readMSPatch`:

| Unpacked | Size | Meaning |
|---|---|---|
| 0 | 6 × 18 | One 18-byte block per effect slot. Bits LSB-first from byte 0: bit 0 on/off, bits 1–28 effect id, then three 13-bit parameters, five 8-bit parameters, 20 unknown bits, one more 8-bit parameter. |
| 108 | 3 | Status: byte 0 bits 0–5 "DSP full", bits 6–7 + byte 1 bit 0 current slot (counted from the right), byte 1 bits 2–4 effect count, tempo = byte 1 bits 5–7 (low) + byte 2 bits 0–4 (high). |
| 111 | 10 | Patch name (ASCII). |
| 121 | 1 | Unknown. |

The effect-id → name/parameter table for 226 original-series effects (173 on the MS-50G) is
`public/zoom-effect-mappings-msog.json` in the zoom-explorer repo.

**What doesn't exist (verified):**
- No CC changes the patch: all 128 CCs were sent with values 127/64/1/0.
- No "next patch" message, no tap-tempo message. Tempo changes need a full patch write.
- `0x31` on/off does nothing for effects 4–6. The workaround is a full patch write, which is a
  snapshot of one specific patch. **[zx]** zoom-explorer does exactly this for slots 4–6 and
  warns of a brief audio mute.

**Gotchas:**
- A **Program Change received over MIDI stores unsaved edits** into the current patch slot
  (verified here with `zoomio edits`: toggle effect 1 with `31`, send a PC, move away and back,
  the toggle is in memory). Any PC with a dirty edit buffer does it, whether it re-selects the
  same patch or leaves it. zoom-explorer adds **[zx]**: auto-save off makes no difference, edits
  made on the pedal count too, they survive a power cycle, and the pedal's own footswitch stores
  nothing. `make_fcp.py`'s `program()` sends `51` before the PC for this reason; verified that
  `31`, `51`, PC leaves the patch untouched.
- Oddity: after a PC to the *same* patch, `29` keeps returning the old stored values for several
  seconds, yet after moving to another patch and back the edits are there. Don't use a same-patch
  PC plus `29` to check what was stored.
- `51` discards the edit buffer, so `zoomio backup`/`read`/`probe`, which end with `51`, throw
  away unsaved edits on the pedal.

**Other commands that reply** (none changed the patch or program; meaning unknown):
`01`, `0E` → `00 0B` · `04`, `05` → `00 00` · `07` → `06 32 00 7A 00` · `16` → `17 xx 00 00 00 00` ·
`60` → `60 05 00`.

### Settings block (`2B` → `2A`) and the footswitch cycle list

The `2A` reply holds global settings, including the **footswitch cycle list** (manual p.11:
patches tagged A, B, C… that the pedal's own footswitch steps through).

Decoding (verified against a 9-entry list):
1. Take the 28 bytes after `F0 52 00 58 2A`.
2. Unpack Zoom 7-bit groups: each group is 1 MSB byte + 7 data bytes. MSB-byte **bit 6** is the
   high bit of data byte 0, bit 0 is the high bit of data byte 6.
3. List entries are **6-bit, LSB-first patch numbers (0-based)** starting at bit 24 of the
   unpacked stream, in letter order A, B, C…

One more bit (raw byte 31) changes when an entry is added or removed; probably a count or end
marker. Writing `2A` back is untested.

## M-VAVE Chocolate Plus

- Shows up over USB MIDI as **`SINCO`**. No reply to the universal identity request.
- **Host mode** (switch on **H**): the USB-A port drives a USB MIDI device such as the MS-50G.
  It **needs external 5 V into the USB-C port**; on battery the host port does nothing.
- **U mode**: USB-C is a normal USB MIDI device (use this for CubeSuite). The host port is off.
- SysEx passes through the host port unchanged.
- One SysEx field per bank (manual: max 200 bytes); several PC/CC/Note entries per bank are allowed.
  `make_fcp.py` assumes entries are sent in list order (SysEx entry first, then PC); not yet
  checked with midimon (test T4 in [`TESTPLAN.md`](TESTPLAN.md)).
- In two-bank ("switch between two banks") mode, the **first press after an import sends bank B**.
- Two-bank toggles are blind: they don't know the pedal's state, so changing patches or stepping
  on the pedal itself can put them out of step.

### CubeSuite `.fcp` export format

23,646 bytes: a 0x5D-byte header, then 32 footswitch records of 0x1A1 (417) bytes, then a tail.
Record index = `(group − 1) × 4 + switch` (A = 0 … D = 3), verified for groups 1–3.

**Header**

| Offset | Meaning |
|---|---|
| 0 | Device mode (`03` = Advanced custom mode) |
| 4, 6, 8, 10 | Custom-mode CC numbers for switches A–D |
| 12 | Custom-mode CC for "I" (the expression/pedal jack; default 7) |
| 13… | "Interface" list: 5-byte entries `01, channel−1, CC, loosen value, step-on value` |

The "Interface" list is the mapping for the pedal jack: an expression pedal sweeps each listed
CC from the "loosen" (up) value to the "step on" (down) value. It's one list for the whole device.
(Inferred from the CubeSuite UI and file contents; not tested with a pedal attached.)

**Footswitch record**

| Offset | Size | Meaning |
|---|---|---|
| 0x000 | 1 | Mode: `00` single step, `01` switch between two banks |
| 0x001 | 80 | Bank A message list: 16 entries × 5 bytes |
| 0x051 | 80 | Bank B message list |
| 0x0A1 | 128 | Bank A SysEx field: length byte + raw bytes |
| 0x121 | 128 | Bank B SysEx field |

List entry: `01, channel−1, type, data1, data2`, where type `00` = Program Change
(data1 = program), `01` = CC (data1 = number, data2 = value), `04` = SysEx (bytes live in that
bank's SysEx field). Note On/Off exist in the UI; their type codes weren't checked.

The tail (after the 32 records) wasn't decoded; one byte changes with the selected group.

## References

- [g200kg/zoom-ms-utility — MIDI messages](https://github.com/g200kg/zoom-ms-utility/blob/master/midimessage.md)
- [thammer/zoom-explorer](https://github.com/thammer/zoom-explorer) (`src/ZoomDevice.ts`,
  `src/ZoomPatch.ts`) and [sym.bios.is](https://sym.bios.is): source of the **[zx]** items
- [r/zoommultistomp: Chocolate + MS-50G thread](https://www.reddit.com/r/zoommultistomp/comments/1af8q6p/using_mvave_chocolate_to_change_between_effects/)
  ("MS-50G can only toggle the lower 3 effect slots directly by SysEx")
- [Chocolate Plus software instructions (PDF)](https://manualf.oss-cn-hongkong.aliyuncs.com/manual/CUBE-TURNER/Chocolate%20Plus-Software%20instructions.pdf)
- [GP-5 + Chocolate Plus host setup](https://rvalladares.com/gp5/gp5-usb-chocolateplus) (host mode needs external power)
- [Zoom MS-50G operation manual](https://zoomcorp.com/media/documents/MS-50G_operationManual_English.pdf)
