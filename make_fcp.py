#!/usr/bin/env python3
"""Generate a CubeSuite .fcp preset for an M-VAVE Chocolate Plus that controls an
original Zoom MS-50G through the Chocolate's USB host port.

Usage:
  python3 make_fcp.py                     # writes chocolate.fcp from fcp/template.fcp and layout.toml
  python3 make_fcp.py -o my.fcp           # custom output path
  python3 make_fcp.py -l other.toml       # custom layout file

Then import the file in CubeSuite ("Import", with the Chocolate connected in U mode).
Edit layout.toml to change what each footswitch does. The .fcp format and the MS-50G
messages are documented in docs/PROTOCOL.md.
"""
import argparse
import sys
import tomllib

# --- .fcp layout (see docs/PROTOCOL.md) ---------------------------------------
HEADER = 0x5D              # bytes before the first footswitch record
RECORD = 0x1A1             # 417 bytes per footswitch record; 32 records = 8 groups x 4 switches
BANK_A_LIST, BANK_B_LIST = 0x001, 0x051   # 16 entries x 5 bytes each
BANK_A_DATA, BANK_B_DATA = 0x0A1, 0x121   # SysEx field: length byte + raw bytes
DATA_LEN = 0x80
ENTRY_LEN = 5
MAX_ENTRIES = 16
MODE_SINGLE = 0x00         # same message(s) every press
MODE_TWO_BANKS = 0x01      # alternates bank A / bank B; the first press after import sends bank B
TYPE_PC, TYPE_CC, TYPE_SYSEX = 0x00, 0x01, 0x04
SWITCHES = "ABCD"

# --- MS-50G messages (model id 0x58) -------------------------------------------
EDITOR_ON = bytes([0xF0, 0x52, 0x00, 0x58, 0x50, 0xF7])   # required once after power-up before 0x31 works
EDITOR_OFF = bytes([0xF0, 0x52, 0x00, 0x58, 0x51, 0xF7])  # also discards unsaved edits (reverts the edit buffer)
TUNER_CC = 74


def effect_sysex(slot: int, on: bool) -> bytes:
    """slot 0-2 = effects 1-3; the MS-50G firmware ignores this message for effects 4-6.
    Editor-on is prepended because the Chocolate allows only one SysEx field per bank."""
    assert 0 <= slot <= 2, "MS-50G only accepts 0x31 on/off for effects 1-3"
    return EDITOR_ON + bytes([0xF0, 0x52, 0x00, 0x58, 0x31, slot, 0x00, 0x01 if on else 0x00, 0x00, 0xF7])


# --- Footswitch behaviors -------------------------------------------------------
# A bank is one message or a list of messages, sent in list order on MIDI channel 1.
# A message is ("sysex", bytes), ("cc", number, value) or ("pc", program).
# Only one "sysex" message per bank (the Chocolate has a single SysEx field per bank).

def effect_toggle(effect: int) -> dict:
    """effect = 1-3 as shown on the pedal. First press turns it off."""
    slot = effect - 1
    return {"a": ("sysex", effect_sysex(slot, True)), "b": ("sysex", effect_sysex(slot, False)),
            "label": f"effect {effect} on/off"}


def cc_toggle(number: int, label: str = "") -> dict:
    """Alternates CC value 127 / 0. First press sends 127."""
    return {"a": ("cc", number, 0), "b": ("cc", number, 127), "label": label or f"CC {number} 127/0"}


def program(patch: int, revert: bool = True) -> dict:
    """patch = number shown on the pedal (1-50); sent as Program Change patch-1.

    A Program Change makes the pedal save any unsaved edits (for example an effect switched off
    by another footswitch) into the patch being left, even with auto-save off. With revert=True
    editor-off is sent first so those edits are discarded instead."""
    msgs = ([("sysex", EDITOR_OFF)] if revert else []) + [("pc", patch - 1)]
    return {"single": msgs, "label": f"patch {patch:02d} ({'revert + ' if revert else ''}PC {patch - 1})"}


def revert_edits() -> dict:
    """Discards unsaved edits on the pedal (editor-off), then re-enables editor mode."""
    return {"single": ("sysex", EDITOR_OFF + EDITOR_ON), "label": "discard edits"}


# --- Layout file ------------------------------------------------------------------
# layout.toml holds one [[switch]] table per footswitch. Each maps onto one behavior function above.
# action -> (required keys, optional keys); every entry also has group, switch and action.
ACTIONS = {
    "cc_toggle": (("cc",), ("label",)),
    "effect_toggle": (("effect",), ()),
    "program": (("patch",), ("revert",)),
    "revert_edits": ((), ()),
}


def fail(path: str, entry: int, msg: str) -> None:
    print(f"{path}: [[switch]] entry {entry}: {msg}", file=sys.stderr)
    sys.exit(1)


def load_layout(path: str) -> dict:
    """Reads a TOML layout file into {(group, switch letter): behavior}.
    Unlisted switches keep CubeSuite's default (PC 0). Prints a message and exits 1 on any error."""
    try:
        with open(path, "rb") as f:
            doc = tomllib.load(f)
    except FileNotFoundError:
        print(f"{path}: layout file not found", file=sys.stderr)
        sys.exit(1)
    except tomllib.TOMLDecodeError as e:
        print(f"{path}: not valid TOML: {e}", file=sys.stderr)
        sys.exit(1)

    entries = doc.get("switch", [])
    if not isinstance(entries, list):
        print(f"{path}: 'switch' must be an array of tables ([[switch]])", file=sys.stderr)
        sys.exit(1)

    layout = {}
    for n, entry in enumerate(entries, start=1):
        for key in ("group", "switch", "action"):
            if key not in entry:
                fail(path, n, f"missing required key '{key}'")
        group, switch, action = entry["group"], entry["switch"], entry["action"]
        if not isinstance(group, int) or not 1 <= group <= 8:
            fail(path, n, f"group must be an integer 1-8, got {group!r}")
        if not isinstance(switch, str) or switch not in SWITCHES:
            fail(path, n, f"switch must be one of {', '.join(SWITCHES)}, got {switch!r}")
        where = f"group {group} switch {switch}"
        if action not in ACTIONS:
            fail(path, n, f"{where}: unknown action {action!r}; expected one of {', '.join(ACTIONS)}")
        if (group, switch) in layout:
            fail(path, n, f"{where}: listed more than once")
        required, optional = ACTIONS[action]
        for key in required:
            if key not in entry:
                fail(path, n, f"{where}: action '{action}' needs key '{key}'")
        for key in entry:
            if key not in ("group", "switch", "action") + required + optional:
                fail(path, n, f"{where}: unknown key '{key}' for action '{action}'")

        if action == "cc_toggle":
            if not isinstance(entry["cc"], int) or not 0 <= entry["cc"] <= 127:
                fail(path, n, f"{where}: cc must be an integer 0-127, got {entry['cc']!r}")
            layout[(group, switch)] = cc_toggle(entry["cc"], str(entry.get("label", "")))
        elif action == "effect_toggle":
            if not isinstance(entry["effect"], int) or not 1 <= entry["effect"] <= 3:
                fail(path, n, f"{where}: effect must be 1-3 (the MS-50G ignores on/off for 4-6), got {entry['effect']!r}")
            layout[(group, switch)] = effect_toggle(entry["effect"])
        elif action == "program":
            if not isinstance(entry["patch"], int) or not 1 <= entry["patch"] <= 50:
                fail(path, n, f"{where}: patch must be an integer 1-50, got {entry['patch']!r}")
            if not isinstance(entry.get("revert", True), bool):
                fail(path, n, f"{where}: revert must be true or false, got {entry['revert']!r}")
            layout[(group, switch)] = program(entry["patch"], entry.get("revert", True))
        elif action == "revert_edits":
            layout[(group, switch)] = revert_edits()
    return layout


def write_bank(buf: bytearray, base: int, list_off: int, data_off: int, bank) -> None:
    msgs = [bank] if isinstance(bank, tuple) else list(bank)
    assert 0 < len(msgs) <= MAX_ENTRIES, f"a bank holds 1-{MAX_ENTRIES} messages"
    assert sum(m[0] == "sysex" for m in msgs) <= 1, "only one SysEx message per bank"
    for i, msg in enumerate(msgs):
        kind = msg[0]
        if kind == "sysex":
            data = msg[1]
            assert len(data) < DATA_LEN, f"SysEx too long for the field ({len(data)} bytes)"
            entry = [0x01, 0x00, TYPE_SYSEX, 0x00, 0x00]
            buf[base + data_off] = len(data)
            buf[base + data_off + 1:base + data_off + 1 + len(data)] = data
        elif kind == "pc":
            entry = [0x01, 0x00, TYPE_PC, msg[1], 0x00]
        elif kind == "cc":
            entry = [0x01, 0x00, TYPE_CC, msg[1], msg[2]]
        else:
            raise ValueError(msg)
        off = base + list_off + i * ENTRY_LEN
        buf[off:off + ENTRY_LEN] = bytes(entry)


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
    ap.add_argument("-l", "--layout", default="layout.toml")
    ap.add_argument("-o", "--output", default="chocolate.fcp")
    args = ap.parse_args()

    layout = load_layout(args.layout)
    buf = bytearray(open(args.template, "rb").read())
    assert len(buf) == 23646, f"unexpected template size {len(buf)}"
    for (group, switch), behavior in sorted(layout.items()):
        write_record(buf, group, switch, behavior)
    open(args.output, "wb").write(buf)
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
