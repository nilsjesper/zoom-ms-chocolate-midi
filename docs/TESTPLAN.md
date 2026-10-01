# Test plan

Checks for the behaviours added on 2026-10-01 (editor-off before a Program Change, multi-message
banks, `layout.toml`). Items marked **done** were run on the project's MS-50G (fw 3.10) from a Mac.
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

## T1: the pedal reports edits made on the pedal

Needs: pedal on the Mac over USB.

1. `swift tools/midimon.swift 90`
2. `swift tools/zoomio.swift send F0 52 00 58 50 F7` in another terminal (editor mode on), or press
   any Chocolate effect switch if the Chocolate is in the chain.
3. On the pedal: stomp to toggle the current effect, then turn one knob a few steps.

Expected from `ZOOM MS Series`: `F0 52 00 58 31 ss 00 vv 00 F7` for the stomp (`vv` 01/00) and
`F0 52 00 58 31 ss pp lo hi F7` per knob step (`pp` ≥ 2).

Result: _not run yet_. If confirmed, change the "Edit report" row in PROTOCOL.md from **[zx]** to
verified. If nothing arrives, the README's router note should drop the "pedal reports edits" claim.

## T4: the Chocolate sends list entries in list order

Needs: Chocolate in U mode on the Mac, CubeSuite.

1. In `layout.toml`, uncomment the group 3 A `program` example (patch 12). `python3 make_fcp.py`.
2. CubeSuite → Import → `chocolate.fcp`.
3. `swift tools/midimon.swift 60`, press group 3 A (switch to group 3 with E/F first).

Expected from `SINCO`: `F0 52 00 58 51 F7` then `C0 0B`, in that order.

Result: _not run yet_. If the PC arrives first, the Chocolate orders entries by type and the
in-bank revert doesn't work: make `program` ignore `revert`, keep `revert_edits` as the way to
discard, and update README "Things to know". If the SysEx never arrives, check the record's
SysEx field in the generated file (offset 0x0A1 of the record).

## Regression

- `python3 make_fcp.py -o /tmp/x.fcp` writes 23,646 bytes; with the shipped `layout.toml` the
  output is byte-identical to the previous generator (checked with `cmp`).
- Group 1 and 2 switches behave as before after import: effect 1–3 toggles, tuner, CC 20–23.
