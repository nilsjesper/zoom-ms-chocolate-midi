# Test plan

Checks for the behaviors added on 2026-10-01 (Program Change and editor-off findings,
multi-message banks, `layout.toml`). Sending editor-off before a `program` switch's PC was
dropped on 2026-10-20: the Chocolate can't send SysEx and a PC from one switch (T4), and
discarding edits wasn't needed. Items marked **done** were run on the project's MS-50G (fw 3.10) from a Mac.
The remaining two need the Chocolate and a foot on the pedal.

## Done: Program Change stores edits, editor-off reverts them

`swift tools/zoomio.swift edits` (pedal on the Mac over USB, no other Zoom editor open). It flips
effect 1 of the current patch and restores the patch at the end. Expected output:

```
T3 after 51 then 50: bit = <original> => 51 REVERTS unsaved edits
T2 after PC away and back: bit = <flipped> => PC STORES unsaved edits
T3b flip, 51, PC, round trip: bit = <original> => revert-before-PC keeps the patch clean
restored: patch identical to original
```

Observed exactly that, twice, on patch 22. A variant without the same-patch PC (flip, PC away,
PC back) also stored the edit.

**MIDISTOMP v1.2 (2026-10-20):** same result from `zoomio edits` on patch 3 (model `61` detected,
patch restored identical). The same three steps with the effect toggled by CC 14 instead of `31`
gave the same results. With AUTO SAVE on, CC 81 then CC 80 also stored a CC edit. All 50
patches matched the backup afterwards.

## T1: the pedal reports edits made on the pedal

Needs: pedal on the Mac over USB.

1. `swift tools/midimon.swift 90`
2. `swift tools/zoomio.swift send F0 52 00 58 50 F7` (`61` on MIDISTOMP v1.2) in another
   terminal (editor mode on), or press any Chocolate effect switch if the Chocolate is in the
   chain.
3. On the pedal: stomp to toggle the current effect, then turn one knob a few steps.

Expected from `ZOOM MS Series`: `F0 52 00 58 31 ss 00 vv 00 F7` for the stomp (`vv` 01/00) and
`F0 52 00 58 31 ss pp lo hi F7` per knob step (`pp` ≥ 2).

**Done 2026-10-20** on MIDISTOMP v1.2 (model `61`), patch 26, editor mode on, AUTO SAVE on:

```
17.23s ZOOM MS Series F0 52 00 61 31 00 00 00 00 F7          stomp: effect 1 off
21.65s ZOOM MS Series F0 52 00 61 31 00 04 39 00 F7          knob, then one line per step
  ...  (17 steps, value 39 -> 49)
27.80s ZOOM MS Series F0 52 00 61 32 01 00 00 19 00 00 00 00 00 F7   AUTO SAVE stored patch 26
```

The "Edit report" row in PROTOCOL.md is now verified. New: AUTO SAVE stores about 5 s after the
last edit and announces it with `32`. Patch 26 was written back from a copy taken just before.

## T4: the Chocolate sends list entries in list order

**Done 2026-10-20** (Chocolate in U mode on the Mac, CubeSuite import, `midimon`, Advanced custom
mode 1). Probe presets with one combination per switch:

| Bank | Sent |
|---|---|
| PC alone | `C0 0C` |
| PC, CC | `C0 0D B0 51 7F` |
| CC, PC | `B0 50 7F C0 0E` |
| SysEx alone | `F0 52 00 61 51 F7` |
| SysEx, PC (the old `program` switch) | `F0 52 00 61 51 F7` twice, no PC |
| SysEx, CC | `F0 52 00 61 51 F7` twice, no CC |
| PC, SysEx | `C0 0B C0 00 C0 00` |

So PC/CC lists are sent in order, and SysEx can't share a bank with them. CubeSuite's editor
allows only one or the other as well. `program` now sends the PC alone, and `make_fcp.py`
refuses a mixed bank.

A probe built as Advanced custom mode 2 (header byte `04`) left the display on `cub`, and the
switches sent CC 20–23 (127 on press, 0 on release) instead of the preset; importing a mode 1 file
brought it back.

## Regression

- `python3 make_fcp.py -o /tmp/x.fcp` writes 23,646 bytes. With the shipped `layout.toml`, the
  default, `--firmware stock`, `--channel 2` and `--pc-start 1` builds are byte-identical
  (`cmp`) to the generator before `layout.toml`.
- After import: group 1 A sent `B0 4A 7F` (tuner), group 2 A sent `C0 00` (patch 1) alone.
