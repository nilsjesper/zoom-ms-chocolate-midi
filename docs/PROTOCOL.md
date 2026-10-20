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
| Edit report (pedal → host) | `F0 52 00 58 31 ss pp lo hi F7` | Sent by the pedal, in editor mode, for every edit made on the pedal: `pp` = 0 is on/off, 2… knobs (verified on MIDISTOMP v1.2: a stomp sent `31 00 00 00 00`, a knob sent `31 00 04 vv 00` per step). |
| Auto-save report (pedal → host) | `F0 52 00 58 32 01 00 00 pp 00 00 00 00 00 F7` | With AUTO SAVE on, about 5 s after the last edit made on the pedal, it stores the patch and sends this (the same bytes as Store patch). Seen on MIDISTOMP v1.2 in editor mode. |
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
  nothing. Sending `51` before the PC discards the edits instead: verified that `31`, `51`, PC
  leaves the patch untouched.
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

## MS-50G with MIDISTOMP firmware

[MIDISTOMP](https://github.com/matujuice/zoom-ms-midistomp) v1.0 is a patched MS-50G 3.10 OS. It
reports the same identity (model `58`, firmware `3.10`), and all the SysEx above works unchanged,
including `31` ignoring effects 4–6. Verified on one MS-50G, from a Mac over USB:

| Message | Bytes | Notes |
|---|---|---|
| Effect n on/off | `B0 cc vv` | `cc` = 10n+4 (14, 24, 34, 44, 54, 64); `vv` 0–63 off, 64–127 on. All six effects, no editor mode needed. |
| Effect n, knob k | `B0 cc vv` | `cc` = 10n+4+k (k = 1–9, so CC 15–73); `vv` 0–127 spans the knob's whole range. A knob the effect lacks does nothing. |
| Tuner | `B0 4A vv` | CC 74, as stock. |
| Previous / next patch | `B0 50 vv` / `B0 51 vv` | CC 80 / 81, MIDISTOMP v1.1+. `vv` 64–127 steps once, wrapping between patch 50 and 1; 0–63 does nothing. Follows CC RECEIVE and MIDI CHANNEL. |
| Program Change | `C0 pp` | PROG CH START NO. 0: `pp` 0–49 = patch 1–50 (stock numbering). START NO. 1: `pp` 1–50 = patch 1–50, PC 0 ignored. |
| MIDI clock | `F8` | 24 per beat; sets the patch tempo after about 2 beats, held to 40–250 BPM. |
| Start / Stop | `FA` / `FC` | For MIDISTOMP's custom effects; no visible change on stock effects. |

Other CCs (e.g. CC 7) do nothing. The MIDI menu (left knob → MIDI) can turn each message type off
and set MIDI CHANNEL (OMNI or 1–16). With a channel set, CC and PC on other channels are ignored.
Clock, Start and Stop have no channel.

**MIDISTOMP v1.2** is built on Zoom's MS-70CDR 2.10 OS for every pedal. On an MS-50G it reports
model `61` and firmware `2.10`, and it only answers SysEx addressed to model `61`
(`F0 52 00 61 …`); its replies carry `61` too. With that byte, editor mode (`50`/`51`), current
program (`33`), read patch (`29`, the same 146 bytes; all 50 patches survived the update
unchanged), write + store (`28` + `32`), the settings read (`2B` → `2A`) and effect on/off
(`31`, slot 0) work as above. The gotchas above hold on v1.2 too, for edits made with `31` and
with the effect CCs: `51` discards them, a Program Change stores them, and `51` before the PC
keeps the patch clean (`zoomio edits`, plus the same steps by CC). With AUTO SAVE on, stepping
with CC 81 and back with CC 80 also stored a CC edit. Rechecked on v1.2, with editor mode on: effect on/off and knobs, CC 80/81,
Program Change with START NO. 0, clock, and the MIDI CHANNEL filter. Start/Stop were accepted.
The tuner CC and START NO. 1 weren't retried.

**Replies stay on channel 1.** The current-program reply to `33` is `B0 00 00 B0 20 00 C0 pp` on
channel 1 whatever MIDI CHANNEL is set to. It only came back after editor mode on (`50`).

**Patch tempo** (patch bytes counted from `F0` = 0): byte 125 is the 7-bit group's MSB byte, and
tempo = `(b[131] << 3) | (b130 >> 5)`, where b130 = `b[130]`, plus 128 if bit 2 of byte 125 is set.
Checked against clock at 73, 100, 160 and 250 BPM and stored tempos from 42 to 250.

**AUTO SAVE** (pedal SETTINGS): when it's on, edits made over MIDI (CC toggles, knob CCs, clock
tempo) are saved into the patch when the pedal leaves it. To undo a test, write the original patch
back (`28`) and store it (`32`); that restored a patch byte for byte.

**TEMPO LOCK** (MIDISTOMP setting): per MIDISTOMP's source, bit 5 of byte 23 of the unpacked
settings block (`2B` → `2A`). It read 0 with TEMPO LOCK off; reading it while on is untested.

## M-VAVE Chocolate Plus

- Shows up over USB MIDI as **`SINCO`**. No reply to the universal identity request.
- **Host mode** (switch on **H**): the USB-A port drives a USB MIDI device such as the MS-50G.
  It **needs external 5 V into the USB-C port**; on battery the host port does nothing.
- **U mode**: USB-C is a normal USB MIDI device (use this for CubeSuite). The host port is off.
- SysEx passes through the host port unchanged.
- One SysEx field per bank (manual: max 200 bytes); several PC/CC/Note entries per bank are allowed.
- **A bank is SysEx or PC/CC, not both** (CubeSuite's editor enforces this too). Checked with
  midimon in Advanced custom mode 1 (test T4 in [`TESTPLAN.md`](TESTPLAN.md)):
  - PC and CC entries are sent in list order: PC + CC gave `C0 0D B0 51 7F`, CC + PC gave
    `B0 50 7F C0 0E`. A lone SysEx entry sends the field once.
  - SysEx entry, then PC or CC: the SysEx field went out twice and the PC/CC never did.
  - PC, then SysEx entry: `C0 0B C0 00 C0 00`, so the SysEx was lost and two stray PC 0s (patch
    1) were sent.
- Header byte 0 `04` (Advanced custom mode 2, as CubeSuite exports it) left the Chocolate showing
  **`cub`**, even after a power cycle, and the switches ignored the preset: A–D sent CC 20–23
  (127 on press, 0 on release). Importing a mode 1 file (`03`) fixed it. A mode 2 export differs
  from mode 1 only in that byte and a shorter tail.
- In two-bank ("switch between two banks") mode, the **first press after an import sends bank B**.
- Two-bank toggles are blind: they don't know the pedal's state, so changing patches or stepping
  on the pedal itself can put them out of step.

### CubeSuite `.fcp` export format

23,646 bytes: a 0x5D-byte header, then 32 footswitch records of 0x1A1 (417) bytes, then a tail.
Record index = `(group − 1) × 4 + switch` (A = 0 … D = 3), verified for groups 1–3.

**Header**

| Offset | Meaning |
|---|---|
| 0 | Device mode (`03` = Advanced custom mode 1, `04` = Advanced custom mode 2) |
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
