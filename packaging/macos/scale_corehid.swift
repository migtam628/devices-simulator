// CoreHID POS scale prototype for macOS 15+. Separate opt-in process.
// The unsigned GitHub build lacks Apple's HID virtual-device entitlement.
// This is a GENERIC POS-scale device, never a DYMO USB VID/PID clone.
//
// STDIN: REPORT <six-byte uppercase hex> | QUIT
// STDOUT: READY HID_CREATED_UNVERIFIED | OK REPORT_SENT | ERR <reason>
// --self-test: compiler smoke test without HID registration.
import Foundation
import CoreHID
import Darwin

@available(macOS 15.0, *)
final class ScaleDelegate: HIDVirtualDeviceDelegate {
    func hidVirtualDevice(_ device: HIDVirtualDevice, receivedSetReportRequestOfType type: HIDReportType, id: HIDReportID?, data: Data) async throws {
        throw NSError(domain:"DevicesSimulator.Scale",code:1,
            userInfo:[NSLocalizedDescriptionKey:"Set report unsupported"])
    }
    func hidVirtualDevice(_ device: HIDVirtualDevice, receivedGetReportRequestOfType type: HIDReportType, id: HIDReportID?, maxSize: Int) async throws -> Data {
        throw NSError(domain:"DevicesSimulator.Scale",code:2,
            userInfo:[NSLocalizedDescriptionKey:"Feature report unsupported"])
    }
}

@main
struct ScaleRunner {
    static let descriptor:[UInt8]=[
        0x05,0x8D,0x09,0x20,0xA1,0x01,
        0x09,0x32,0xA1,0x02,0x85,0x03,
        0x09,0x70,0x15,0x01,0x25,0x08,
        0x75,0x08,0x95,0x01,0x81,0x00,
        0x09,0x50,0x15,0x01,0x25,0x0C,
        0x75,0x08,0x95,0x01,0x81,0x00,
        0x09,0x41,0x15,0x81,0x25,0x7F,
        0x75,0x08,0x95,0x01,0x81,0x02,
        0x09,0x40,0x15,0x00,0x26,0xFF,0x7F,
        0x75,0x10,0x95,0x01,0x81,0x02,
        0xC0,0xC0
    ]
    static func say(_ value:String){print(value);fflush(stdout)}
    static func main() async {
        if CommandLine.arguments.contains("--self-test") {
            say("PASS COREDHID_SCALE_COMPILED")
            return
        }
        guard #available(macOS 15.0, *) else {
            say("ERR MACOS_15_REQUIRED")
            return
        }
        let properties=HIDVirtualDevice.Properties(
            descriptor:Data(descriptor),
            vendorID:0, // not a real allocated manufacturer's USB vendor identity
            productID:0xD501,
            product:"Devices Simulator POS Scale",
            manufacturer:"Devices Simulator")
        guard let device=HIDVirtualDevice(properties:properties) else {
            say("ERR HID_CREATION_FAILED_ENTITLEMENT_OR_OS")
            fputs("CoreHID could not create a device. Check approved HID entitlement and code signing.\n",stderr)
            return
        }
        await device.activate(delegate:ScaleDelegate())
        say("READY HID_CREATED_UNVERIFIED")
        while let text=readLine() {
            let line=text.trimmingCharacters(in:.whitespacesAndNewlines)
            if line=="QUIT" {break}
            guard line.hasPrefix("REPORT ") else {say("ERR INVALID_COMMAND");continue}
            let hex=String(line.dropFirst(7))
            guard hex.count==12 else {say("ERR INVALID_LENGTH");continue}
            var data=[UInt8]()
            for index in stride(from:0,to:12,by:2) {
                let begin=hex.index(hex.startIndex,offsetBy:index)
                let end=hex.index(begin,offsetBy:2)
                guard let number=UInt8(hex[begin..<end],radix:16) else {
                    data.removeAll()
                    break
                }
                data.append(number)
            }
            guard data.count==6 && data[0]==3 else {
                say("ERR INVALID_POS_REPORT");continue
            }
            do {
                try await device.dispatchInputReport(
                    data:Data(data),timestamp:SuspendingClock.now)
                say("OK REPORT_SENT")
            } catch {
                say("ERR REPORT_DISPATCH_FAILED")
                fputs("CoreHID report failure: \(error)\n",stderr)
            }
        }
    }
}
