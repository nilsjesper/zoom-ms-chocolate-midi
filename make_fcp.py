#!/usr/bin/env python3
"""Generate a CubeSuite .fcp preset for an M-VAVE Chocolate Plus that controls an
original Zoom MS-50G through the Chocolate's USB host port.

Usage:
  python3 make_fcp.py                     # writes chocolate.fcp from fcp/template.fcp
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


def effect_sysex(slot: int, on: bool) -> bytes:
    """slot 0-2 = effects 1-3; the MS-50G firmware ignores this message for effects 4-6.
    Editor-on is prepended because the Chocolate allows only one SysEx field per bank."""
    assert 0 <= slot <= 2, "MS-50G only accepts 0x31 on/off for effects 1-3"
    return EDITOR_ON + bytes([0xF0, 0x52, 0x00, 0x58, 0x31, slot, 0x00, 0x01 if on else 0x00, 0x00, 0xF7])


# --- Footswitch behaviors -------------------------------------------------------
# A bank is ("sysex", bytes), ("cc", number, value) or ("pc", program). MIDI channel 1.

def effect_toggle(effect: int) -> dict:
    """effect = 1-3 as shown on the pedal. First press turns it off."""
    slot = effect - 1
    return {"a": ("sysex", effect_sysex(slot, True)), "b": ("sysex", effect_sysex(slot, False)),
            "label": f"effect {effect} on/off"}


def cc_toggle(number: int, label: str = "") -> dict:
    """Alternates CC value 127 / 0. First press sends 127."""
    return {"a": ("cc", number, 0), "b": ("cc", number, 127), "label": label or f"CC {number} 127/0"}


def program(patch: int) -> dict:
    """patch = number shown on the pedal (1-50); sent as Program Change patch-1."""
    return {"single": ("pc", patch - 1), "label": f"patch {patch:02d} (PC {patch - 1})"}


# (group 1-8, switch letter) -> behavior. Unlisted switches keep CubeSuite's default (PC 0).
LAYOUT = {
    (1, "A"): cc_toggle(TUNER_CC, "tuner on/off"),
    (1, "B"): effect_toggle(3),
    (1, "C"): effect_toggle(2),
    (1, "D"): effect_toggle(1),
    (2, "A"): cc_toggle(20),
    (2, "B"): cc_toggle(21),
    (2, "C"): cc_toggle(22),
    (2, "D"): cc_toggle(23),
}


def write_bank(buf: bytearray, base: int, list_off: int, data_off: int, bank: tuple) -> None:
    kind = bank[0]
    if kind == "sysex":
        msg = bank[1]
        assert len(msg) < DATA_LEN
        entry = [0x01, 0x00, TYPE_SYSEX, 0x00, 0x00]
        buf[base + data_off] = len(msg)
        buf[base + data_off + 1:base + data_off + 1 + len(msg)] = msg
    elif kind == "pc":
        entry = [0x01, 0x00, TYPE_PC, bank[1], 0x00]
    elif kind == "cc":
        entry = [0x01, 0x00, TYPE_CC, bank[1], bank[2]]
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
    args = ap.parse_args()

    buf = bytearray(open(args.template, "rb").read())
    assert len(buf) == 23646, f"unexpected template size {len(buf)}"
    for (group, switch), behavior in sorted(LAYOUT.items()):
        write_record(buf, group, switch, behavior)
    open(args.output, "wb").write(buf)
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
