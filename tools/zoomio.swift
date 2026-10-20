// zoomio: talk to an original Zoom MS-50G over USB MIDI on macOS (model 0x58, or 0x61 on MIDISTOMP v1.2+).
//   swift tools/zoomio.swift backup <file>   save all 50 patches (changes patch, then restores it)
//   swift tools/zoomio.swift read            current program, settings block (2B), current patch
//   swift tools/zoomio.swift probe           send unknown single-byte SysEx commands, report replies
//   swift tools/zoomio.swift send <hex...>   send one raw message as-is (no editor on/off), print the reply
//   swift tools/zoomio.swift edits           test whether 51 reverts unsaved edits and whether a PC stores them
//                                            (flips effect 1 of the current patch; restores it at the end)
// Note: backup/read/probe end with editor-off (51), which also discards unsaved edits on the pedal.
// See docs/PROTOCOL.md for what the messages mean.
import CoreMIDI
import Foundation
setvbuf(stdout, nil, _IOLBF, 0)
let lock = NSLock()
var rx: [UInt8] = []
var client = MIDIClientRef(); MIDIClientCreate("zoomio" as CFString, nil, nil, &client)
var inPort = MIDIPortRef()
MIDIInputPortCreateWithBlock(client, "in" as CFString, &inPort) { list, _ in
  var p = list.pointee.packet
  for _ in 0..<list.pointee.numPackets {
    let b = Mirror(reflecting: p.data).children.prefix(Int(p.length)).map { $0.value as! UInt8 }
    lock.lock(); rx += b; lock.unlock(); p = MIDIPacketNext(&p).pointee
  }
}
func name(_ o: MIDIObjectRef) -> String { var n: Unmanaged<CFString>?; MIDIObjectGetStringProperty(o, kMIDIPropertyDisplayName, &n); return (n?.takeRetainedValue() as String?) ?? "" }
for i in 0..<MIDIGetNumberOfSources() { let s = MIDIGetSource(i); if name(s).contains("ZOOM") { MIDIPortConnectSource(inPort, s, nil) } }
var outPort = MIDIPortRef(); MIDIOutputPortCreate(client, "out" as CFString, &outPort)
var dst = MIDIEndpointRef()
for i in 0..<MIDIGetNumberOfDestinations() { let d = MIDIGetDestination(i); if name(d).contains("ZOOM") { dst = d } }
func send(_ bytes: [UInt8]) { var pl = MIDIPacketList(); let pk = MIDIPacketListInit(&pl); MIDIPacketListAdd(&pl, 1024, pk, 0, bytes.count, bytes); MIDISend(outPort, dst, &pl) }
func wait(_ s: Double) { RunLoop.main.run(until: Date().addingTimeInterval(s)) }
func take() -> [UInt8] { lock.lock(); let r = rx; rx = []; lock.unlock(); return r }
func xfer(_ b: [UInt8], _ t: Double = 0.4) -> [UInt8] { _ = take(); send(b); wait(t); return take() }
func hex(_ b: [UInt8]) -> String { b.map { String(format: "%02X", $0) }.joined(separator: " ") }
var Z: [UInt8] = [0xF0, 0x52, 0x00, 0x58]  // model byte set from the identity reply below
func prog() -> Int { let r = xfer(Z + [0x33, 0xF7], 0.3); if let i = r.firstIndex(of: 0xC0), i + 1 < r.count { return Int(r[i+1]) }; return -1 }
func patch() -> [UInt8] { xfer(Z + [0x29, 0xF7], 0.8) }
// Program Change channel and numbering. Stock: channel 1, PC 0 = patch 1. MIDISTOMP firmware
// can filter to one MIDI CHANNEL and start at PC 1 (PROG CH START NO. 1); findPC() finds out.
var pcCh: UInt8 = 0, pcOff = 0
func pc(_ n: Int) { send([0xC0 | pcCh, UInt8(n + pcOff)]); wait(0.4) }  // n = 0-based patch index
func findPC() -> Bool {
  let start = prog()
  for ch in UInt8(0)..<16 {
    send([0xC0 | ch, 1]); wait(0.4); let p1 = prog()
    send([0xC0 | ch, 2]); wait(0.4); let p2 = prog()
    if p1 >= 0 && p2 == p1 + 1 {
      pcCh = ch; pcOff = 1 - p1; pc(start)
      print("program change: channel \(ch + 1), PC \(pcOff) = patch 1")
      return true
    }
  }
  return false
}

let mode = CommandLine.arguments.dropFirst().first ?? ""
if dst == 0 { print("ZOOM MS Series not connected"); exit(1) }
// Identity reply F0 7E 00 06 02 52 mm ...: mm = 58 for the MS-50G OS (stock, MIDISTOMP v1.0/v1.1),
// 61 for MIDISTOMP v1.2+, which is built on the MS-70CDR OS. SysEx only answers to that byte.
let id = xfer([0xF0, 0x7E, 0x00, 0x06, 0x01, 0xF7], 0.5)
if let i = id.firstIndex(of: 0x52), i + 1 < id.count { Z[3] = id[i + 1] }
print(String(format: "model %02X", Z[3]))
if mode != "send" && prog() < 0 { send(Z + [0x50, 0xF7]); wait(0.3); if prog() < 0 { print("pedal not responding"); exit(1) } }
if mode == "backup" {
  send(Z + [0x50, 0xF7]); wait(0.3)
  let start = prog(); print("current program:", start)
  if !findPC() { print("pedal ignores Program Change on every channel (PROG CH RECEIVE off?)"); exit(1) }
  var out = ""
  for n in 0..<50 { pc(n); if prog() != n { print("patch \(n + 1) did not load"); exit(1) }; let p = patch(); out += "\(n) \(hex(p))\n"; print(n, p.count, "bytes", String(bytes: p.count > 141 ? Array(p[132..<145]).filter { $0 >= 0x20 && $0 < 0x7F } : [], encoding: .ascii) ?? "") }
  try! out.write(toFile: CommandLine.arguments[2], atomically: true, encoding: .utf8)
  pc(start); print("restored program:", prog())
  send(Z + [0x51, 0xF7]); wait(0.2)
} else if mode == "read" {
  send(Z + [0x50, 0xF7]); wait(0.3)
  print("program:", prog())
  for c: UInt8 in [0x07, 0x16, 0x2B, 0x60] { print(String(format: "cmd %02X:", c), hex(xfer(Z + [c, 0xF7], 0.4))) }
  print("patch:", hex(patch()))
  send(Z + [0x51, 0xF7]); wait(0.2)
} else if mode == "probe" {
  let skip: Set<UInt8> = [0x28, 0x29, 0x31, 0x32, 0x33, 0x50, 0x51]
  send(Z + [0x50, 0xF7]); wait(0.3)
  let start = prog(); let base = patch(); print("start program:", start, "patch bytes:", base.count)
  if !findPC() { print("pedal ignores Program Change on every channel (PROG CH RECEIVE off?)"); exit(1) }
  for c in UInt8(0)..<0x80 where !skip.contains(c) {
    let r = xfer(Z + [c, 0xF7], 0.35)
    let p = prog(); let pd = patch()
    var note = ""
    if !r.isEmpty { note += " reply: \(hex(r))" }
    if p != start { note += " PROGRAM \(start)->\(p)" }
    if pd != base && pd.count == base.count { note += " PATCH CHANGED (\(zip(pd, base).filter { $0 != $1 }.count) bytes)" }
    if pd.count != base.count { note += " patch read \(pd.count) bytes" }
    if !note.isEmpty { print(String(format: "cmd %02X:", c) + note) }
    if p != start && p >= 0 { pc(start) }
  }
  print("end program:", prog())
  send(Z + [0x51, 0xF7]); wait(0.2)
} else if mode == "send" {
  let bytes = CommandLine.arguments.dropFirst(2).compactMap { UInt8($0, radix: 16) }
  if bytes.isEmpty { print("usage: send <hex bytes>, e.g. send F0 52 00 58 29 F7 (61 on MIDISTOMP v1.2)"); exit(1) }
  print("sent: ", hex(bytes))
  let r = xfer(bytes, 0.8)
  print("reply:", r.isEmpty ? "(none)" : hex(r))
} else if mode == "edits" {
  // T2/T3 in docs/TESTPLAN.md. Uses effect 1 of the current patch and a PC round trip
  // (other patch, then back) instead of a power cycle to see what is in memory.
  _ = take(); wait(2.0); let noise = take()
  if !noise.isEmpty { print("warning: \(noise.count) unsolicited bytes in 2 s (another editor polling?):", hex(noise)); print("close sym.bios.is / other Zoom editors and retry"); exit(1) }
  send(Z + [0x50, 0xF7]); wait(0.3)
  if !findPC() { print("pedal ignores Program Change on every channel (PROG CH RECEIVE off?)"); exit(1) }
  let start = prog(); let orig = patch()
  guard start >= 0, orig.count == 146 else { print("could not read program/patch:", start, orig.count); exit(1) }
  let want = Int(orig[6] & 1); let flipped = 1 - want
  print("program \(start) (pedal patch \(start + 1)), effect 1 is \(want == 1 ? "on" : "off"); original patch saved in memory for restore")
  func bit() -> Int { let p = patch(); return p.count == 146 ? Int(p[6] & 1) : -1 }
  func flip(_ to: Int) { send(Z + [0x31, 0x00, 0x00, UInt8(to), 0x00, 0xF7]); wait(0.5) }
  func roundTrip() { pc((start + 1) % 50); wait(0.2); pc(start); wait(0.2) }

  flip(flipped); let b1 = bit(); print("after 31 flip: bit =", b1, b1 == flipped ? "(flipped)" : "(NOT flipped; aborting)"); if b1 != flipped { exit(1) }
  send(Z + [0x51, 0xF7]); wait(0.5); send(Z + [0x50, 0xF7]); wait(0.3)
  let t3 = bit()
  print("T3 after 51 then 50: bit =", t3, t3 == want ? "=> 51 REVERTS unsaved edits" : t3 == flipped ? "=> 51 does NOT revert" : "(read failed)")

  if t3 != flipped { flip(flipped); print("re-flipped for T2: bit =", bit()) }
  pc(start); wait(0.2)
  let t2a = bit(); wait(2.0); let t2b = bit()
  print("after PC to same patch: bit =", t2a, "at 0.6 s,", t2b, "at ~3.5 s")
  roundTrip()
  let t2 = bit()
  print("T2 after PC away and back: bit =", t2, t2 == flipped ? "=> PC STORES unsaved edits" : t2 == want ? "=> PC does NOT store (memory unchanged)" : "(read failed)")

  // T3b: with a clean revert before the PC, nothing should be stored. Needs memory back at `want` first.
  if t3 == want {
    if bit() != want { flip(want); pc(start); wait(0.2); roundTrip() }
    let pre = bit(); print("T3b precondition: memory bit =", pre, pre == want ? "(ok)" : "(could not reset; skipping T3b)")
    if pre == want {
      flip(flipped); print("  flipped: bit =", bit())
      send(Z + [0x51, 0xF7]); wait(0.5); pc(start); wait(0.2); send(Z + [0x50, 0xF7]); wait(0.3); roundTrip()
      let t3b = bit(); print("T3b flip, 51, PC, round trip: bit =", t3b, t3b == want ? "=> revert-before-PC keeps the patch clean" : "=> STORED despite 51")
    }
  }

  // Restore: put the original bit back and store it the same way, then verify all 146 bytes.
  if bit() != want { flip(want); pc(start); wait(0.2); roundTrip() }
  var fin = patch()
  if fin != orig { print("restore via 31+PC left differences; writing original patch with 28"); send(orig); wait(0.8); pc(start); wait(0.2); roundTrip(); fin = patch() }
  print(fin == orig ? "restored: patch identical to original" : "RESTORE FAILED: patch differs (\(zip(fin, orig).filter { $0 != $1 }.count) bytes); restore it from your backup")
  print("end program:", prog())
} else {
  print("usage: zoomio backup <file> | read | probe | send <hex bytes> | edits"); exit(1)
}
