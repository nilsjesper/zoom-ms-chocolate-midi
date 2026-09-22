// midimon: print MIDI from the Chocolate (SINCO) and the Zoom (ZOOM MS Series) on macOS,
// reconnecting when a device is unplugged or power-cycled.
//   swift tools/midimon.swift [seconds]   (default 120)
import CoreMIDI
import Foundation
let t0 = Date()
setvbuf(stdout, nil, _IOLBF, 0)
var client = MIDIClientRef()
var connected = Set<MIDIUniqueID>()
var connectAll: () -> Void = {}
MIDIClientCreateWithBlock("mon" as CFString, &client) { n in if n.pointee.messageID == .msgSetupChanged { print(String(format: "%6.2fs", Date().timeIntervalSince(t0)), "-- MIDI setup changed"); connectAll() } }
var inPort = MIDIPortRef()
MIDIInputPortCreateWithBlock(client, "in" as CFString, &inPort) { list, src in
  let name = Unmanaged<CFString>.fromOpaque(src!).takeUnretainedValue() as String
  var p = list.pointee.packet
  for _ in 0..<list.pointee.numPackets {
    let b = Mirror(reflecting: p.data).children.prefix(Int(p.length)).map { String(format: "%02X", $0.value as! UInt8) }
    print(String(format: "%6.2fs", Date().timeIntervalSince(t0)), name, b.joined(separator: " ")); p = MIDIPacketNext(&p).pointee
  }
}
func name(_ o: MIDIObjectRef) -> String { var n: Unmanaged<CFString>?; MIDIObjectGetStringProperty(o, kMIDIPropertyDisplayName, &n); return (n?.takeRetainedValue() as String?) ?? "" }
connectAll = {
  var live = Set<MIDIUniqueID>()
  for i in 0..<MIDIGetNumberOfSources() { let s = MIDIGetSource(i); let n = name(s); guard n.contains("SINCO") || n.contains("ZOOM") else { continue }
    var uid: MIDIUniqueID = 0; MIDIObjectGetIntegerProperty(s, kMIDIPropertyUniqueID, &uid); live.insert(uid)
    if connected.contains(uid) { continue }
    let tag = Unmanaged.passRetained(n as CFString).toOpaque(); MIDIPortConnectSource(inPort, s, tag); connected.insert(uid)
    print(String(format: "%6.2fs", Date().timeIntervalSince(t0)), "listening:", n) }
  connected = connected.intersection(live)
}
connectAll()
RunLoop.main.run(until: Date().addingTimeInterval(Double(CommandLine.arguments.dropFirst().first ?? "120")!))
print("done")
