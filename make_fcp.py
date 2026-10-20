#!/usr/bin/env python3
"""Generate a CubeSuite .fcp preset for an M-VAVE Chocolate Plus that controls an
original Zoom MS-50G through the Chocolate's USB host port.

Usage:
  python3 make_fcp.py                     # MIDISTOMP firmware, MIDI channel 1, writes chocolate.fcp
  python3 make_fcp.py --channel 2         # match the pedal's MIDI CHANNEL setting (MIDISTOMP)
  python3 make_fcp.py --firmware stock    # Zoom's stock 3.10 firmware (effects 1-3 only)
  python3 make_fcp.py -o my.fcp           # custom output path

Then import the file in CubeSuite ("Import", with the Chocolate connected in U mode).
Edit LAYOUT below to change what each footswitch does. The .fcp format and the MS-50G
messages are documented in docs/PROTOCOL.md.
"""
import argparse
import sys

# --- .fcp layout (see docs/PROTOCOL.md) ---------------------------------------
HEADER = 0x5D              # bytes before the first footswitch record
RECORD = 0x1A1             # 417 bytes per footswitch record; 32 records = 8 groups x 4 switches
BANK_A_LIST, BANK_B_LIST = 0x001, 0x051   # 16 entries x 5 bytes each
BANK_A_DATA, BANK_B_DATA = 0x0A1, 0x121   # SysEx field: length byte + raw bytes
DATA_LEN = 0x80
ENTRY_LEN = 5
MODE_SINGLE = 0x00         # same message(s) every press
MODE_TWO_BANKS = 0x01      # alternates bank A / bank B; the first press after import sends bank B
TYPE_PC, TYPE_CC, TYPE_SYSEX = 0x00, 0x01, 0x04
SWITCHES = "ABCD"

# --- MS-50G messages (model id 0x58) -------------------------------------------
EDITOR_ON = bytes([0xF0, 0x52, 0x00, 0x58, 0x50, 0xF7])  # required once after power-up before 0x31 works
TUNER_CC = 74

# Set from the command line in main(); see --firmware, --channel and --pc-start.
FIRMWARE = "midistomp"     # "midistomp" or "stock"
CHANNEL = 1                # MIDI channel (1-16) for PC and CC sent to the pedal
PC_START = 0               # MIDISTOMP's PROG CH START NO. setting; stock is always 0


def effect_sysex(slot: int, on: bool) -> bytes:
    """slot 0-2 = effects 1-3; the MS-50G firmware ignores this message for effects 4-6.
    Editor-on is prepended because the Chocolate allows only one SysEx field per bank."""
    assert 0 <= slot <= 2, "MS-50G only accepts 0x31 on/off for effects 1-3"
    return EDITOR_ON + bytes([0xF0, 0x52, 0x00, 0x58, 0x31, slot, 0x00, 0x01 if on else 0x00, 0x00, 0xF7])


# --- Footswitch behaviors -------------------------------------------------------
# A bank is ("sysex", bytes), ("cc", number, value[, channel]) or ("pc", program[, channel]).
# Without a channel, PC and CC go out on CHANNEL.

def effect_toggle(effect: int) -> dict:
    """effect = 1-6 as shown on the pedal (1-3 on stock firmware). First press turns it off.
    MIDISTOMP: CC 10n+4 (14, 24 ... 64), 127 = on, 0 = off. Stock: SysEx 0x31."""
    if FIRMWARE == "midistomp":
        assert 1 <= effect <= 6, "effects are 1-6"
        number = 10 * effect + 4
        return {"a": ("cc", number, 127), "b": ("cc", number, 0),
                "label": f"effect {effect} on/off (CC {number})"}
    slot = effect - 1
    return {"a": ("sysex", effect_sysex(slot, True)), "b": ("sysex", effect_sysex(slot, False)),
            "label": f"effect {effect} on/off"}


def cc_toggle(number: int, label: str = "", channel: int | None = None) -> dict:
    """Alternates CC value 127 / 0. First press sends 127. On MIDISTOMP, CC 14-73 move
    effects and knobs (see docs/PROTOCOL.md), so pick another number or channel for other gear."""
    return {"a": ("cc", number, 0, channel), "b": ("cc", number, 127, channel),
            "label": label or f"CC {number} 127/0" + (f" ch {channel}" if channel else "")}


def program(patch: int) -> dict:
    """patch = number shown on the pedal (1-50). Sent as PC patch-1, or PC patch when
    MIDISTOMP's PROG CH START NO. is 1 (--pc-start 1)."""
    pc = patch - 1 + PC_START
    return {"single": ("pc", pc), "label": f"patch {patch:02d} (PC {pc})"}


def patch_step(step: int) -> dict:
    """MIDISTOMP v1.1 and later: step = 1 loads the next patch (CC 81), -1 the previous one
    (CC 80), wrapping between patch 50 and patch 1. Every press sends 127."""
    assert FIRMWARE == "midistomp", "next/previous patch needs MIDISTOMP"
    assert step in (1, -1), "patch_step takes 1 (next) or -1 (previous)"
    number = 81 if step > 0 else 80
    return {"single": ("cc", number, 127), "label": f"{'next' if step > 0 else 'previous'} patch (CC {number})"}


def layout() -> dict:
    """(group 1-8, switch letter) -> behavior. Unlisted switches keep CubeSuite's default
    (PC 0, which loads patch 1), so give every switch you'll press a behavior."""
    groups = {
        (1, "A"): cc_toggle(TUNER_CC, "tuner on/off"),
        (1, "B"): effect_toggle(3),
        (1, "C"): effect_toggle(2),
        (1, "D"): effect_toggle(1),
    }
    if FIRMWARE == "midistomp":
        groups |= {
            (2, "A"): program(1),          # there is no tap-tempo MIDI message, so a patch jump
            (2, "B"): effect_toggle(6),
            (2, "C"): effect_toggle(5),
            (2, "D"): effect_toggle(4),
        }
    # Next/previous patch (MIDISTOMP v1.1+), e.g.
    #   (3, "A"): patch_step(-1),
    #   (3, "B"): patch_step(1),
    # Other gear on the same USB host port: send it CCs on a channel the pedal ignores
    # (set the pedal's MIDI CHANNEL to something else), e.g.
    #   (3, "A"): cc_toggle(20, channel=1),
    return groups



def write_bank(buf: bytearray, base: int, list_off: int, data_off: int, bank: tuple) -> None:
    kind = bank[0]
    if kind == "sysex":
        msg = bank[1]
        assert len(msg) < DATA_LEN
        entry = [0x01, 0x00, TYPE_SYSEX, 0x00, 0x00]
        buf[base + data_off] = len(msg)
        buf[base + data_off + 1:base + data_off + 1 + len(msg)] = msg
    elif kind == "pc":
        channel = bank[2] if len(bank) > 2 and bank[2] else CHANNEL
        entry = [0x01, channel - 1, TYPE_PC, bank[1], 0x00]
    elif kind == "cc":
        channel = bank[3] if len(bank) > 3 and bank[3] else CHANNEL
        entry = [0x01, channel - 1, TYPE_CC, bank[1], bank[2]]
    else:
        raise ValueError(bank)
    buf[base + list_off:base + list_off + ENTRY_LEN] = bytes(entry)


def write_record(buf: bytearray, group: int, switch: str, behavior: dict) -> None:
    index = (group - 1) * 4 + SWITCHES.index(switch)
    base = HEADER + index * RECORD
    buf[base:base + RECORD] = bytes(RECORD)
    if "single" in behavior:
        buf[base] = MODE_SINGLE
        write_bank(buf, base, BANK_A_LIST, BANK_A_DATA, behavior["single"])
    else:
        buf[base] = MODE_TWO_BANKS
        write_bank(buf, base, BANK_A_LIST, BANK_A_DATA, behavior["a"])
        write_bank(buf, base, BANK_B_LIST, BANK_B_DATA, behavior["b"])
    print(f"group {group} switch {switch}: {behavior['label']}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("-t", "--template", default="fcp/template.fcp")
    ap.add_argument("-o", "--output", default="chocolate.fcp")
    ap.add_argument("--firmware", choices=["midistomp", "stock"], default="midistomp",
                    help="pedal firmware (default midistomp)")
    ap.add_argument("--channel", type=int, choices=range(1, 17), default=1, metavar="1-16",
                    help="MIDI channel for PC/CC; match MIDISTOMP's MIDI CHANNEL (OMNI: any)")
    ap.add_argument("--pc-start", type=int, choices=[0, 1], default=0,
                    help="MIDISTOMP's PROG CH START NO. setting (stock firmware: 0)")
    args = ap.parse_args()
    global FIRMWARE, CHANNEL, PC_START
    FIRMWARE, CHANNEL, PC_START = args.firmware, args.channel, args.pc_start
    if FIRMWARE == "stock" and PC_START:
        ap.error("--pc-start 1 needs MIDISTOMP firmware")

    buf = bytearray(open(args.template, "rb").read())
    assert len(buf) == 23646, f"unexpected template size {len(buf)}"
    for (group, switch), behavior in sorted(layout().items()):
        write_record(buf, group, switch, behavior)
    open(args.output, "wb").write(buf)
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
