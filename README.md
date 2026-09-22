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
  `.fcp` format, as worked out by experiment.
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
| Jump to a patch | ✅ | Program Change |
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

Groups are switched on the Chocolate with E (A+B) and F (C+D). To change the layout, edit `LAYOUT`
in `make_fcp.py`:

```python
LAYOUT = {
    (1, "A"): cc_toggle(TUNER_CC, "tuner on/off"),
    (1, "D"): effect_toggle(1),      # effect 1 on/off (effects 1-3 only)
    (2, "A"): cc_toggle(20),         # CC 20, alternating 127 / 0
    (3, "A"): program(12),           # jump to patch 12 as shown on the pedal
}
```

### Things to know

- **The first press after importing sends the "B" half** of a two-state switch. The generator sets
  things up so the first press turns an effect *off* and turns the tuner *on*.
- **Toggles are blind.** The Chocolate doesn't know the pedal's state. If you change patches or
  step on the pedal itself, a switch can do the opposite of what you expect; press it again.
- **Editor mode:** a freshly powered-on MS-50G ignores effect on/off messages until it gets
  `F0 52 00 58 50 F7`. Each effect switch sends that first automatically.

## Tools (macOS)

Both need the device connected to the Mac over USB.

```sh
swift tools/zoomio.swift backup patches.txt   # save all 50 patches (SysEx) to a file
swift tools/zoomio.swift read                 # current patch, settings block, raw patch data
swift tools/midimon.swift 120                 # watch MIDI from the Chocolate (SINCO) / pedal for 120 s
```

`zoomio.swift probe` sends unknown single-byte SysEx commands to the pedal to see what replies.
It skips the known write/store commands, but back up your patches first.

## Ideas not built yet

- **Cycle list → Chocolate groups:** read the pedal's footswitch cycle list (decoded; see
  PROTOCOL.md) and lay those patches out as `program(n)` switches across groups 3–8.
- **Set list on a switch:** a Chocolate SysEx field could hold a whole settings write (`2A`,
  34 bytes) to load a prepared cycle list in one tap. Writing `2A` hasn't been tested.
- **Next patch, tap tempo, effects 4–6, state-aware toggles:** these need a small USB-host
  MIDI router that can read the pedal's replies.

## License

MIT
