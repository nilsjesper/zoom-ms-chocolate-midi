# zoom-ms-chocolate-midi

Control an original Zoom MS-50G MultiStomp from an M-VAVE Chocolate Plus footswitch, with no
computer in between. `make_fcp.py` writes a CubeSuite preset (`.fcp`) that toggles effects and the
tuner and jumps to patches.

It works with Zoom's stock 3.10 firmware. With [MIDISTOMP](https://github.com/matujuice/zoom-ms-midistomp)
firmware it can also switch effects 4-6 and move knobs over MIDI CC.

Tested on one MS-50G and one Chocolate Plus with stock firmware. On MIDISTOMP v1.0 and v1.2 the
preset's messages were checked on the pedal from a Mac, but not yet sent through the Chocolate. Unofficial
and not affiliated with Zoom, M-VAVE or MIDISTOMP. Use at your own risk.

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
python3 make_fcp.py                     # MIDISTOMP, MIDI channel 1 -> chocolate.fcp
python3 make_fcp.py --channel 2         # pedal's MIDI CHANNEL is 2
python3 make_fcp.py --pc-start 1        # pedal's PROG CH START NO. is 1
python3 make_fcp.py --firmware stock    # stock firmware
```

On MIDISTOMP, match `--channel` and `--pc-start` to the pedal's MIDI menu (press the left knob,
then MIDI). Any channel works when MIDI CHANNEL is OMNI. A wrong `--pc-start` makes every patch
switch land one patch off.

In CubeSuite, with the Chocolate on U, import `chocolate.fcp`. Then switch back to H and connect the pedal.

Default layout:

| Group | A | B | C | D |
|---|---|---|---|---|
| 1 | Tuner | Effect 3 | Effect 2 | Effect 1 |
| 2 (MIDISTOMP) | Patch 1 | Effect 6 | Effect 5 | Effect 4 |

Switch groups on the Chocolate with E (A+B) and F (C+D). Change the layout in `layout()` in
`make_fcp.py`:

```python
(1, "D"): effect_toggle(1),            # effect 1 on/off
(3, "A"): program(12),                 # patch 12 as numbered on the pedal
(3, "C"): patch_step(-1),              # previous patch (MIDISTOMP v1.1+); patch_step(1) = next
(3, "B"): cc_toggle(20, channel=1),    # CC 20 on channel 1 for other gear, 127 / 0
```

MIDISTOMP uses CC 14-73 for effects and knobs, so a CC meant for other gear on the same Chocolate
can move a knob. To avoid that, set the pedal's MIDI CHANNEL to 2, build with `--channel 2`, and
send the other gear's CCs on channel 1.

### Notes

- After an import, the first press of a toggle turns the effect off, or the tuner on.
- Toggles don't know the pedal's state. After a patch change or a press on the pedal itself, a
  switch can do the opposite of what you expect; press it again.
- With AUTO SAVE on, toggled effects are saved into the patch when you leave it.
- Stock firmware ignores SysEx effect on/off until it gets editor mode (`F0 52 00 58 50 F7`), so
  each stock effect switch sends that first.

## Tools (macOS)

```sh
swift tools/zoomio.swift backup patches.txt   # save all 50 patches to a file
swift tools/zoomio.swift read                 # current program, settings block, current patch
swift tools/zoomio.swift probe                # send unknown SysEx commands, report replies
swift tools/midimon.swift 120                 # print MIDI from the Chocolate and pedal for 120 s
```

`backup` and `probe` find the pedal's Program Change channel and numbering on their own. All
three read the pedal's model from its identity reply: MIDISTOMP v1.2 is built on Zoom's MS-70CDR
firmware, so it answers SysEx as model `61` instead of `58`. `probe`
skips known write commands, but back up your patches before running it.

## Ideas

- Read the pedal's footswitch cycle list (decoded in PROTOCOL.md) and lay those patches out as
  `program(n)` switches in groups 3-8.
- Put a settings write (`2A`, 34 bytes) in a SysEx field to load a prepared cycle list in one
  press. Writing `2A` is untested.
- With MIDISTOMP, sweep a knob CC from the Chocolate's expression input. Untried.

## References

- [matujuice/zoom-ms-midistomp](https://github.com/matujuice/zoom-ms-midistomp): MIDISTOMP
  firmware. Its Mac updater was tested with this repo's tools.
- [g200kg/zoom-ms-utility](https://github.com/g200kg/zoom-ms-utility): MS-50G/60B/70CDR patch
  format and [MIDI messages](https://github.com/g200kg/zoom-ms-utility/blob/master/midimessage.md).
- [HamiltonGerlach/MultiStompController](https://github.com/HamiltonGerlach/MultiStompController):
  Arduino foot controller using the same SysEx.
- [PhilDaThrill/MultistompMidi](https://github.com/PhilDaThrill/MultistompMidi): Python MultiStomp
  helpers (MS-70CDR; model byte `0x61`, `0x58` for the MS-50G).
- [thammer/zoom-explorer](https://github.com/thammer/zoom-explorer): MS Plus protocol work.
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
