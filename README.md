# zoom-ms-chocolate-midi

This is just some experimental code that I put together for myself to quickly build different configurations for the M-Vave Chocolate plus and help me figure out what kind of things I might be able to control. The cc 20-24 on the 2nd bank are actually for a totally seperate project and don't have any effect on the ms50g.

This work draws on just a TON of pre-existing research across github reddit and other places on the messages the Zoom pedal accepts.


---------

Control an **original Zoom MS-50G MultiStomp** from an **M-VAVE Chocolate Plus** MIDI footswitch,
with no computer in between: toggle effects, the tuner and CCs, and jump to patches.

It includes:
- `make_fcp.py`, which generates a CubeSuite preset file (`.fcp`) from a simple layout table,
  so you don't have to type SysEx into CubeSuite by hand.
- [`docs/PROTOCOL.md`](docs/PROTOCOL.md), with the MS-50G MIDI/SysEx details and the CubeSuite
  `.fcp` format, as worked out by experiment, and [`docs/TESTPLAN.md`](docs/TESTPLAN.md) with
  what has and hasn't been checked on the hardware.
- `tools/`, two small macOS Swift utilities for talking to the pedal and watching MIDI traffic.

Unofficial; not affiliated with Zoom or M-VAVE. Tested on one MS-50G (firmware 3.10) and one
Chocolate Plus. Use at your own risk.

> **Original MS-50G only.** The MS-50G+ and other MS Plus pedals use a different protocol.
> For those, see [zoom-multistomp-commander](https://github.com/RyoSogawa/zoom-multistomp-commander).

## What works

| | Chocolate alone | Notes |
|---|---|---|
| Effect 1–3 on/off | ✅ | SysEx; each press alternates off/on |
| Effect 4–6 on/off | ❌ | Firmware ignores the on/off message for slots 4–6 |
| Tuner on/off | ✅ | CC 74 |
| Jump to a patch | ✅ | Program Change (editor-off is sent first; see below) |
| Discard unsaved edits | ✅ | SysEx editor-off (`51`) reverts the pedal's edit buffer |
| Next/previous patch | ❌ | No MIDI message for it; needs something that tracks state |
| Tap tempo | ❌ | Tempo is inside each patch; no tap message |

## Hardware setup

1. Set the Chocolate Plus switch to **H** (host).
2. Plug **external 5 V into the Chocolate's USB-C** port. Host mode doesn't work on battery.
3. Connect the Chocolate's **USB-A host port** to the MS-50G's USB port with a data cable.
4. Power the MS-50G separately (adapter or batteries).

To program the Chocolate, switch it to **U** and connect its USB-C to your computer running CubeSuite.

## Usage

```sh
python3 make_fcp.py        # writes chocolate.fcp
```

Then in CubeSuite (Chocolate in U mode): **Import** → `chocolate.fcp`. Switch back to H and connect the pedal.

The default layout:

| Group | A | B | C | D |
|---|---|---|---|---|
| 1 | Tuner on/off | Effect 3 on/off | Effect 2 on/off | Effect 1 on/off |
| 2 | CC 20 (127/0) | CC 21 | CC 22 | CC 23 |

Groups are switched on the Chocolate with E (A+B) and F (C+D). To change the layout, edit
`layout.toml` (or pass another file with `-l`). One `[[switch]]` table per footswitch; unlisted
switches keep CubeSuite's default (PC 0):

```toml
[[switch]]
group = 1
switch = "A"
action = "cc_toggle"      # CC 74, alternating 127 / 0
cc = 74
label = "tuner on/off"    # optional

[[switch]]
group = 1
switch = "D"
action = "effect_toggle"  # effect 1 on/off (effects 1-3 only)
effect = 1

[[switch]]
group = 3
switch = "A"
action = "program"        # jump to patch 12 as shown on the pedal (discards unsaved edits first)
patch = 12

[[switch]]
group = 3
switch = "B"
action = "program"        # plain Program Change; pending edits get saved into the old patch
patch = 13
revert = false

[[switch]]
group = 3
switch = "C"
action = "revert_edits"   # discard unsaved edits, stay on the current patch
```

A switch can send several messages per press, in order, with at most one SysEx message among
them: a `program` switch sends editor-off and then the Program Change.

### Things to know

- **The first press after importing sends the "B" half** of a two-state switch. The generator sets
  things up so the first press turns an effect *off* and turns the tuner *on*.
- **Toggles are blind.** The Chocolate doesn't know the pedal's state. If you change patches or
  step on the pedal itself, a switch can do the opposite of what you expect; press it again.
- **Editor mode:** a freshly powered-on MS-50G ignores effect on/off messages until it gets
  `F0 52 00 58 50 F7`. Each effect switch sends that first automatically.
- **A Program Change saves pending edits.** Verified on this pedal: a Program Change received
  over MIDI stores any unsaved edits into the patch being left, whether it re-selects the same
  patch or jumps to another one. An effect you toggled off with the Chocolate becomes part of
  that patch. A `program` switch therefore sends editor-off (`F0 52 00 58 51 F7`) first, which
  discards the edit buffer (also verified); set `revert = false` to keep the plain Program
  Change. The zoom-explorer source adds that auto-save off makes no difference and that edits
  made on the pedal itself count too.

## Tools (macOS)

Both need the device connected to the Mac over USB.

```sh
swift tools/zoomio.swift backup patches.txt   # save all 50 patches (SysEx) to a file
swift tools/zoomio.swift read                 # current patch, settings block, raw patch data
swift tools/midimon.swift 120                 # watch MIDI from the Chocolate (SINCO) / pedal for 120 s
swift tools/zoomio.swift send F0 52 00 58 29 F7   # send one raw message, print the reply
swift tools/zoomio.swift edits                # re-run the "PC saves edits / 51 reverts" test (restores the patch)
```

`zoomio.swift probe` sends unknown single-byte SysEx commands to the pedal to see what replies.
It skips the known write/store commands, but back up your patches first. `backup`, `read` and
`probe` finish with editor-off, which also discards unsaved edits on the pedal; `send` doesn't.

## Ideas not built yet

- **Cycle list → Chocolate groups:** read the pedal's footswitch cycle list (decoded; see
  PROTOCOL.md) and lay those patches out as `program(n)` switches across groups 3–8.
- **Set list on a switch:** a Chocolate SysEx field could hold a whole settings write (`2A`,
  34 bytes) to load a prepared cycle list in one tap. Writing `2A` hasn't been tested.
- **Next patch, tap tempo, effects 4–6, state-aware toggles:** these need a small USB-host
  MIDI router that can read the pedal's replies. The zoom-explorer source shows the raw material
  is there: in editor mode the pedal reports every on/off and knob edit made on the pedal as a
  `31` SysEx, it doesn't announce patch changes made with its own footswitch (zoom-explorer polls
  `33` every 500 ms), and effects 4–6 are toggled by writing the whole patch back. Its
  `src/ZoomDevice.ts` is a working reference implementation of all of that.

## References and prior work

**Zoom MultiStomp MIDI/SysEx**
- [g200kg/zoom-ms-utility](https://github.com/g200kg/zoom-ms-utility): the key reference for the
  original MS-50G/60B/70CDR. See its [MIDI message doc](https://github.com/g200kg/zoom-ms-utility/blob/master/midimessage.md)
  (patch format, parameter edit, "effective only for effect1-3") and the
  [browser patch editor](https://g200kg.github.io/zoom-ms-utility/).
- [HamiltonGerlach/MultiStompController](https://github.com/HamiltonGerlach/MultiStompController):
  an Arduino foot controller for the MS-50G/70CDR using the same SysEx set.
- [PhilDaThrill/MultistompMidi](https://github.com/PhilDaThrill/MultistompMidi): Python helpers for
  MultiStomp MIDI (written for the MS-70CDR; model byte `0x61` → `0x58` for the MS-50G).
- [thammer/zoom-explorer](https://github.com/thammer/zoom-explorer) and its patch manager
  [sym.bios.is](https://sym.bios.is): the README documents the **MS Plus** protocol, but the app
  and source (`src/ZoomDevice.ts`, `src/ZoomPatch.ts`) also drive the original MS-50G/60B/70CDR
  (confirmed on this MS-50G). Worth knowing: a browser-based MIDI CC mapper for effect
  parameters (CC 2–14 = effect 1, 17–29 = effect 2, 33–45, 48–60, 63–75, 78–90 = effects 3–6,
  first CC of each block = on/off), and `public/zoom-effect-mappings-msog.json` with names,
  parameter names and ranges for 173 MS-50G effects.
- [RyoSogawa/zoom-multistomp-commander](https://github.com/RyoSogawa/zoom-multistomp-commander):
  a web SysEx generator for MS Plus pedals and MIDI controllers like the Chocolate. It's what
  started this project.

**Discussions**
- [r/zoommultistomp: Using M-Vave Chocolate to change between effects on the MS-50G](https://www.reddit.com/r/zoommultistomp/comments/1af8q6p/using_mvave_chocolate_to_change_between_effects/):
  "MS-50G can only toggle the lower 3 effect slots directly by SysEx… the effect slot toggling is
  done by sending the whole updated patch."
- [r/zoommultistomp: A MIDI switcher for the first 3 effects](https://www.reddit.com/r/zoommultistomp/comments/a5hcw4/made_a_midiswitcher_for_the_first_3_effects_on_my/)
- [r/zoommultistomp: MIDI SysEx for the MS Plus series](https://www.reddit.com/r/zoommultistomp/comments/1clsyfn/midi_sysex_for_ms_plus_series/)
- [Connect GP-5 with Chocolate Plus via USB](https://rvalladares.com/gp5/gp5-usb-chocolateplus) and the
  [Neural DSP forum thread](https://unity.neuraldsp.com/t/mvave-chocolate-plus-usb-host/16825): where
  "host mode needs external 5 V" came from.

**Manuals**
- [Zoom MS-50G operation manual](https://zoomcorp.com/media/documents/MS-50G_operationManual_English.pdf)
  (p.11: footswitch cycle list)
- [Chocolate Plus manual](https://manualf.oss-cn-hongkong.aliyuncs.com/manual/CUBE-TURNER/Chocolate-Plus.pdf)
  (U/H interface modes) and
  [Chocolate Plus software instructions](https://manualf.oss-cn-hongkong.aliyuncs.com/manual/CUBE-TURNER/Chocolate%20Plus-Software%20instructions.pdf)
  (CubeSuite modes, 200-byte SysEx limit)
- [M-VAVE Chocolate Plus product page](http://www.cuvave.com/product?id=chocolate-plus)

## License

MIT
