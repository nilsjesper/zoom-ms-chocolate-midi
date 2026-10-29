# zoom-ms-chocolate-midi

## Background 

I'd wanted to see if I could use Claude Code to write sysex-based preset files for my M-Vave Chococlate Plus in order to control a MultiStomp MS-50 to speed up experimentation. I got that working including

* A script to write new CubeSuite compatible import setings based on a toml text file so I could try different things faster.
* Some docs about existing sysex settings
* A Swift based tool for maniuplating the pedal and reading results.

Half way through this, the [MIDISTOMP](https://github.com/matujuice/zoom-ms-midistomp) project came along which meant no more futzing around with sysex and we could now address ALL of the buttons.

I hope some of this might be helpful for other tinkerers!

-Martin

## Overview
My Goal: Control an original Zoom MS-50G MultiStomp from an M-VAVE Chocolate Plus footswitch, with no
computer in between. `make_fcp.py` writes a CubeSuite preset (`.fcp`) that toggles effects and the
tuner and jumps to patches.

It works with Zoom's stock 3.10 firmware. With [MIDISTOMP](https://github.com/matujuice/zoom-ms-midistomp)
firmware it can also switch effects 4-6 and move knobs over MIDI CC.

Tested on one MS-50G and one Chocolate Plus with stock firmware. On MIDISTOMP v1.0 and v1.2 the
preset's messages were checked on the pedal from a Mac, but not yet sent through the Chocolate.
Unofficial and not affiliated with Zoom, M-VAVE or MIDISTOMP. Use at your own risk.

The MS-50G+ and other MS Plus pedals use a different protocol; see
[zoom-multistomp-commander](https://github.com/RyoSogawa/zoom-multistomp-commander) for those.

## Features

| | Stock 3.10 | MIDISTOMP |
|---|---|---|
| Effect 1-3 on/off | yes (SysEx) | yes (CC 14, 24, 34) |
| Effect 4-6 on/off | no | yes (CC 44, 54, 64) |
| Effect knobs | effects 1-3 (SysEx) | yes (CC 15-73) |
| Tuner on/off | yes (CC 74) | yes (CC 74) |
| Jump to a patch | yes (Program Change) | yes (Program Change) |
| Next/previous patch | no | yes (CC 80/81, v1.1 and later) |
| Tap tempo | no | no |

Knobs aren't in the default layout. The full MIDI chart is in [docs/PROTOCOL.md](docs/PROTOCOL.md).

## Hardware setup

1. Set the Chocolate's switch to **H** (host).
2. Plug external 5 V into the Chocolate's USB-C port. Host mode doesn't work on battery.
3. Connect the Chocolate's USB-A port to the MS-50G's USB port with a data cable.
4. Power the MS-50G separately.

To program the Chocolate, set the switch to **U** and connect its USB-C to a computer running CubeSuite.

## Usage

```sh
python3 make_fcp.py                     # MIDISTOMP, MIDI channel 1, layout.toml -> chocolate.fcp
python3 make_fcp.py --channel 2         # pedal's MIDI CHANNEL is 2
python3 make_fcp.py --pc-start 1        # pedal's PROG CH START NO. is 1
python3 make_fcp.py --firmware stock    # stock firmware
python3 make_fcp.py -l other.toml       # another layout file
```

Needs Python 3.11 or newer (for `tomllib`).

On MIDISTOMP, match `--channel` and `--pc-start` to the pedal's MIDI menu (press the left knob,
then MIDI). Any channel works when MIDI CHANNEL is OMNI. A wrong `--pc-start` makes every patch
switch land one patch off.

In CubeSuite, with the Chocolate on U, import `chocolate.fcp`. Then switch back to H and connect the pedal.

Default layout:

| Group | A | B | C | D |
|---|---|---|---|---|
| 1 | Tuner | Effect 3 | Effect 2 | Effect 1 |
| 2 (MIDISTOMP) | Patch 1 | Effect 6 | Effect 5 | Effect 4 |

Switch groups on the Chocolate with E (A+B) and F (C+D). To change the layout, edit
`layout.toml` (or pass another file with `-l`). One `[[switch]]` table per footswitch; unlisted
switches keep CubeSuite's default (PC 0). The file lists every action and has commented-out
examples:

```toml
[[switch]]
group = 3
switch = "A"
action = "program"        # jump to patch 12 as shown on the pedal
patch = 12

[[switch]]
group = 3
switch = "B"
action = "cc_toggle"      # CC 20 on channel 1 for other gear, 127 / 0
cc = 20
channel = 1

[[switch]]
group = 3
switch = "C"
action = "patch_step"     # previous patch (MIDISTOMP v1.1+); step = 1 for next
step = -1
```

[`example-layout.toml`](example-layout.toml) fills groups 1-4 with MIDISTOMP examples: effects
1-6, knobs, patch jumps and up/down, and the tuner. Build it with
`python3 make_fcp.py -l example-layout.toml -o example.fcp`.

An entry with `firmware = "midistomp"` (or `"stock"`) is only used when building for that
firmware; the default group 2 is MIDISTOMP-only this way.

MIDISTOMP builds send only Program Change and CC; SysEx is used only for stock firmware's effect
on/off. A Chocolate switch sends either one SysEx field or a list of PC/CC messages (in list
order), not both: a bank that mixes them comes out garbled, so `make_fcp.py` refuses one.

MIDISTOMP uses CC 14-73 for effects and knobs, so a CC meant for other gear on the same Chocolate
can move a knob. To avoid that, set the pedal's MIDI CHANNEL to 2, build with `--channel 2`, and
send the other gear's CCs on channel 1.

### Notes

- After an import, the first press of a toggle turns the effect off, or the tuner on.
- Toggles don't know the pedal's state. After a patch change or a press on the pedal itself, a
  switch can do the opposite of what you expect; press it again.
- **Leaving a patch saves pending edits.** A Program Change received over MIDI stores unsaved
  edits (an effect you toggled with the Chocolate, for example) into the patch being left. Checked
  on stock 3.10 and on MIDISTOMP v1.2, for edits made by SysEx and by CC. On MIDISTOMP v1.2 with
  AUTO SAVE on, stepping with CC 80/81 stores them too.
- Stock firmware ignores SysEx effect on/off until it gets editor mode (`F0 52 00 58 50 F7`), so
  each stock effect switch sends that first.

## Tools (macOS)

```sh
swift tools/zoomio.swift backup patches.txt   # save all 50 patches to a file
swift tools/zoomio.swift read                 # current program, settings block, current patch
swift tools/zoomio.swift probe                # send unknown SysEx commands, report replies
swift tools/zoomio.swift send F0 52 00 61 29 F7   # send one raw message, print the reply
swift tools/zoomio.swift edits                # rerun the "PC saves edits / 51 reverts" test (restores the patch)
swift tools/midimon.swift 120                 # print MIDI from the Chocolate and pedal for 120 s
```

`backup` and `probe` find the pedal's Program Change channel and numbering on their own. `probe`
skips known write commands, but back up your patches before running it. `backup`, `read` and
`probe` finish with editor-off, which also discards unsaved edits on the pedal; `send` doesn't.
What has and hasn't been checked on the hardware is in [docs/TESTPLAN.md](docs/TESTPLAN.md).

zoomio reads the pedal's model from its identity reply. MIDISTOMP v1.2 is built on Zoom's
MS-70CDR firmware, so it answers SysEx as model `61` instead of `58`.

## Ideas

- Read the pedal's footswitch cycle list (decoded in PROTOCOL.md) and lay those patches out as
  `program` switches in groups 3-8.
- Put a settings write (`2A`, 34 bytes) in a SysEx field to load a prepared cycle list in one
  press. Writing `2A` is untested.
- With MIDISTOMP, sweep a knob CC from the Chocolate's expression input. Untried.
- State-aware toggles and tap tempo need a small USB-host MIDI router that reads the pedal's
  replies. The zoom-explorer source shows the raw material (the **[zx]** items in PROTOCOL.md):
  in editor mode the pedal reports edits made on it as `31` SysEx, and patch changes made with
  its own footswitch aren't announced, so the router has to poll `33`.

## References

- [matujuice/zoom-ms-midistomp](https://github.com/matujuice/zoom-ms-midistomp): MIDISTOMP
  firmware. Its Mac updater was tested with this repo's tools.
- [g200kg/zoom-ms-utility](https://github.com/g200kg/zoom-ms-utility): MS-50G/60B/70CDR patch
  format and [MIDI messages](https://github.com/g200kg/zoom-ms-utility/blob/master/midimessage.md).
- [HamiltonGerlach/MultiStompController](https://github.com/HamiltonGerlach/MultiStompController):
  Arduino foot controller using the same SysEx.
- [PhilDaThrill/MultistompMidi](https://github.com/PhilDaThrill/MultistompMidi): Python MultiStomp
  helpers (MS-70CDR; model byte `0x61`, `0x58` for the MS-50G).
- [thammer/zoom-explorer](https://github.com/thammer/zoom-explorer) and its patch manager
  [sym.bios.is](https://sym.bios.is): the README documents the MS Plus protocol, but the app and
  source (`src/ZoomDevice.ts`, `src/ZoomPatch.ts`) also drive the original MS-50G/60B/70CDR
  (confirmed on this MS-50G). PROTOCOL.md's **[zx]** items come from it. It also has a browser
  MIDI CC mapper for effect parameters and `public/zoom-effect-mappings-msog.json` with names,
  parameter names and ranges for 173 MS-50G effects.
- [RyoSogawa/zoom-multistomp-commander](https://github.com/RyoSogawa/zoom-multistomp-commander):
  SysEx generator for MS Plus pedals; it started this project.
- Reddit: [Chocolate and MS-50G](https://www.reddit.com/r/zoommultistomp/comments/1af8q6p/using_mvave_chocolate_to_change_between_effects/),
  [switcher for effects 1-3](https://www.reddit.com/r/zoommultistomp/comments/a5hcw4/made_a_midiswitcher_for_the_first_3_effects_on_my/),
  [MS Plus SysEx](https://www.reddit.com/r/zoommultistomp/comments/1clsyfn/midi_sysex_for_ms_plus_series/).
- Chocolate host mode needs 5 V: [GP-5 guide](https://rvalladares.com/gp5/gp5-usb-chocolateplus),
  [Neural DSP thread](https://unity.neuraldsp.com/t/mvave-chocolate-plus-usb-host/16825).
- Manuals: [MS-50G](https://zoomcorp.com/media/documents/MS-50G_operationManual_English.pdf)
  (p.11, cycle list), [Chocolate Plus](https://manualf.oss-cn-hongkong.aliyuncs.com/manual/CUBE-TURNER/Chocolate-Plus.pdf),
  [CubeSuite](https://manualf.oss-cn-hongkong.aliyuncs.com/manual/CUBE-TURNER/Chocolate%20Plus-Software%20instructions.pdf)
  (200-byte SysEx limit), [product page](http://www.cuvave.com/product?id=chocolate-plus).

## License

MIT
