#!/usr/bin/env python3
"""Generate a CubeSuite .fcp preset for an M-VAVE Chocolate Plus that controls an
original Zoom MS-50G through the Chocolate's USB host port.

Usage:
  python3 make_fcp.py                     # MIDISTOMP, MIDI channel 1, layout.toml -> chocolate.fcp
  python3 make_fcp.py --channel 2         # match the pedal's MIDI CHANNEL setting (MIDISTOMP)
  python3 make_fcp.py --pc-start 1        # match the pedal's PROG CH START NO. (MIDISTOMP)
  python3 make_fcp.py --firmware stock    # Zoom's stock 3.10 firmware (effects 1-3 only)
  python3 make_fcp.py -l other.toml       # custom layout file
  python3 make_fcp.py -o my.fcp           # custom output path

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

# Set from the command line in main(); see --firmware, --channel and --pc-start.
FIRMWARE = "midistomp"     # "midistomp" or "stock"
CHANNEL = 1                # MIDI channel (1-16) for PC and CC sent to the pedal
PC_START = 0               # MIDISTOMP's PROG CH START NO. setting; stock is always 0


# --- MS-50G messages (stock firmware only; MIDISTOMP builds send only PC and CC) ----
def sysex(*body: int) -> bytes:
    return bytes([0xF0, 0x52, 0x00, 0x58, *body, 0xF7])


def editor_on() -> bytes:
    """Required once after power-up before 0x31 works."""
    return sysex(0x50)


def effect_sysex(slot: int, on: bool) -> bytes:
    """slot 0-2 = effects 1-3; the MS-50G firmware ignores this message for effects 4-6.
    Editor-on is prepended because the Chocolate allows only one SysEx field per bank."""
    assert 0 <= slot <= 2, "MS-50G only accepts 0x31 on/off for effects 1-3"
    return editor_on() + sysex(0x31, slot, 0x00, 0x01 if on else 0x00, 0x00)


# --- Footswitch behaviors -------------------------------------------------------
# A bank is one message or a list of messages, sent in list order.
# A message is ("sysex", bytes), ("cc", number, value[, channel]) or ("pc", program[, channel]).
# Without a channel, PC and CC go out on CHANNEL. A bank is either one "sysex" message or a list
# of PC/CC messages: the Chocolate garbles a bank that mixes them (see docs/PROTOCOL.md).

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


# --- Layout file ------------------------------------------------------------------
# layout.toml holds one [[switch]] table per footswitch. Each maps onto one behavior function above.
# action -> (required keys, optional keys); every entry also has group, switch, action and an
# optional firmware ("midistomp" or "stock": the entry is skipped for the other firmware).
ACTIONS = {
    "cc_toggle": (("cc",), ("label", "channel")),
    "effect_toggle": (("effect",), ()),
    "program": (("patch",), ()),
    "patch_step": (("step",), ()),
}
COMMON = ("group", "switch", "action", "firmware")


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
        required, optional = ACTIONS[action]
        for key in required:
            if key not in entry:
                fail(path, n, f"{where}: action '{action}' needs key '{key}'")
        for key in entry:
            if key not in COMMON + required + optional:
                fail(path, n, f"{where}: unknown key '{key}' for action '{action}'")
        if entry.get("firmware", FIRMWARE) not in ("midistomp", "stock"):
            fail(path, n, f"{where}: firmware must be \"midistomp\" or \"stock\", got {entry['firmware']!r}")
        if entry.get("firmware", FIRMWARE) != FIRMWARE:
            continue
        if (group, switch) in layout:
            fail(path, n, f"{where}: listed more than once")

        if action == "cc_toggle":
            if not isinstance(entry["cc"], int) or not 0 <= entry["cc"] <= 127:
                fail(path, n, f"{where}: cc must be an integer 0-127, got {entry['cc']!r}")
            channel = entry.get("channel")
            if channel is not None and (not isinstance(channel, int) or not 1 <= channel <= 16):
                fail(path, n, f"{where}: channel must be an integer 1-16, got {channel!r}")
            layout[(group, switch)] = cc_toggle(entry["cc"], str(entry.get("label", "")), channel)
        elif action == "effect_toggle":
            top = 6 if FIRMWARE == "midistomp" else 3
            if not isinstance(entry["effect"], int) or not 1 <= entry["effect"] <= top:
                fail(path, n, f"{where}: effect must be 1-{top} on {FIRMWARE} firmware, got {entry['effect']!r}")
            layout[(group, switch)] = effect_toggle(entry["effect"])
        elif action == "program":
            if not isinstance(entry["patch"], int) or not 1 <= entry["patch"] <= 50:
                fail(path, n, f"{where}: patch must be an integer 1-50, got {entry['patch']!r}")
            layout[(group, switch)] = program(entry["patch"])
        elif action == "patch_step":
            if FIRMWARE != "midistomp":
                fail(path, n, f"{where}: patch_step needs MIDISTOMP firmware")
            if entry["step"] not in (1, -1) or isinstance(entry["step"], bool):
                fail(path, n, f"{where}: step must be 1 (next) or -1 (previous), got {entry['step']!r}")
            layout[(group, switch)] = patch_step(entry["step"])
    return layout


def write_bank(buf: bytearray, base: int, list_off: int, data_off: int, bank) -> None:
    msgs = [bank] if isinstance(bank, tuple) else list(bank)
    assert 0 < len(msgs) <= MAX_ENTRIES, f"a bank holds 1-{MAX_ENTRIES} messages"
    assert len(msgs) == 1 or all(m[0] != "sysex" for m in msgs), \
        "a bank is either one SysEx message or a list of PC/CC messages"
    for i, msg in enumerate(msgs):
        kind = msg[0]
        if kind == "sysex":
            data = msg[1]
            assert len(data) < DATA_LEN, f"SysEx too long for the field ({len(data)} bytes)"
            entry = [0x01, 0x00, TYPE_SYSEX, 0x00, 0x00]
            buf[base + data_off] = len(data)
            buf[base + data_off + 1:base + data_off + 1 + len(data)] = data
        elif kind == "pc":
            channel = msg[2] if len(msg) > 2 and msg[2] else CHANNEL
            entry = [0x01, channel - 1, TYPE_PC, msg[1], 0x00]
        elif kind == "cc":
            channel = msg[3] if len(msg) > 3 and msg[3] else CHANNEL
            entry = [0x01, channel - 1, TYPE_CC, msg[1], msg[2]]
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
