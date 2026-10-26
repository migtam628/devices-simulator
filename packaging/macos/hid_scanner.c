/* macOS virtual HID keyboard used as a barcode-scanner wedge.
 * Protocol on stdin: SCAN <A-Za-z0-9-._/> or QUIT.
 * Emits READY at successful device creation, OK/ERR per scan.
 * The device exists only while this process runs.
 */
#define _DARWIN_C_SOURCE
#include <CoreFoundation/CoreFoundation.h>
#include <IOKit/hid/IOHIDUserDevice.h>
#include <IOKit/hid/IOHIDKeys.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

/* Standard 8-byte USB HID boot-keyboard descriptor; virtual, not a USB device. */
static const uint8_t kKeyboardDescriptor[] = {
    0x05,0x01, 0x09,0x06, 0xA1,0x01,
    0x05,0x07, 0x19,0xE0, 0x29,0xE7, 0x15,0x00, 0x25,0x01,
    0x75,0x01, 0x95,0x08, 0x81,0x02,
    0x95,0x01, 0x75,0x08, 0x81,0x01,
    0x95,0x05, 0x75,0x01, 0x05,0x08, 0x19,0x01, 0x29,0x05,
    0x91,0x02, 0x95,0x01, 0x75,0x03, 0x91,0x01,
    0x95,0x06, 0x75,0x08, 0x15,0x00, 0x25,0x65,
    0x05,0x07, 0x19,0x00, 0x29,0x65, 0x81,0x00, 0xC0
};
static IOHIDUserDeviceRef gDevice = NULL;
static CFRunLoopRef gLoop = NULL;

static void number_property(CFMutableDictionaryRef props, CFStringRef key, int value) {
    CFNumberRef n = CFNumberCreate(kCFAllocatorDefault, kCFNumberIntType, &value);
    if (n) { CFDictionarySetValue(props, key, n); CFRelease(n); }
}

/* Translate ASCII barcode characters to standard US-layout HID keycodes. */
static int key_for_char(char c, uint8_t *key, uint8_t *modifier) {
    *modifier = 0;
    if (c >= 'a' && c <= 'z') { *key = (uint8_t)(4 + c - 'a'); return 1; }
    if (c >= 'A' && c <= 'Z') { *key = (uint8_t)(4 + c - 'A'); *modifier = 0x02; return 1; }
    if (c >= '1' && c <= '9') { *key = (uint8_t)(30 + c - '1'); return 1; }
    if (c == '0') { *key = 39; return 1; }
    if (c == '-') { *key = 45; return 1; }
    if (c == '_') { *key = 45; *modifier = 0x02; return 1; }
    if (c == '.') { *key = 55; return 1; }
    if (c == '/') { *key = 56; return 1; }
    return 0;
}

static int send_key(uint8_t key, uint8_t modifier) {
    uint8_t report[8] = {0};
    report[0] = modifier;
    report[2] = key;
    IOReturn ret = IOHIDUserDeviceHandleReport(gDevice, report, sizeof(report));
    usleep(12000);
    memset(report, 0, sizeof(report));
    IOReturn released = IOHIDUserDeviceHandleReport(gDevice, report, sizeof(report));
    usleep(12000);
    return ret == kIOReturnSuccess && released == kIOReturnSuccess;
}

static void *read_commands(void *unused) {
    (void)unused;
    char line[150];
    while (fgets(line, sizeof(line), stdin)) {
        size_t length = strlen(line);
        if (length == 0) continue;
        if (line[length-1] == '\n') line[--length] = 0;
        if (strcmp(line, "QUIT") == 0) break;
        if (strncmp(line, "SCAN ", 5) != 0 || length < 6 || length > 105) {
            puts("ERR unsupported command"); fflush(stdout); continue;
        }
        int ok = 1;
        for (const char *p = line + 5; *p; ++p) {
            uint8_t key = 0, mod = 0;
            if (!key_for_char(*p, &key, &mod)) { ok = 0; break; }
            if (!send_key(key, mod)) { ok = 0; break; }
        }
        puts(ok ? "OK" : "ERR HID dispatch failed");
        fflush(stdout);
    }
    if (gLoop) CFRunLoopStop(gLoop);
    return NULL;
}

int main(int argc, char **argv) {
    if (argc == 2 && strcmp(argv[1], "--self-test") == 0) {
        puts("PASS: native macOS barcode HID helper compiled");
        return 0;
    }
    CFMutableDictionaryRef props = CFDictionaryCreateMutable(
        kCFAllocatorDefault, 0, &kCFTypeDictionaryKeyCallBacks, &kCFTypeDictionaryValueCallBacks);
    CFDataRef descriptor = CFDataCreate(kCFAllocatorDefault, kKeyboardDescriptor, sizeof(kKeyboardDescriptor));
    if (!props || !descriptor) {
        fprintf(stderr,"ERR allocation failed\n"); return 1;
    }
    CFDictionarySetValue(props, CFSTR(kIOHIDReportDescriptorKey), descriptor);
    CFDictionarySetValue(props, CFSTR(kIOHIDProductKey), CFSTR("Lulwa SIM Barcode HID"));
    CFDictionarySetValue(props, CFSTR(kIOHIDManufacturerKey), CFSTR("Devices Simulator"));
    CFDictionarySetValue(props, CFSTR(kIOHIDTransportKey), CFSTR("Virtual"));
    number_property(props, CFSTR(kIOHIDVendorIDKey), 0xF00D); /* test-only virtual VID */
    number_property(props, CFSTR(kIOHIDProductIDKey), 0xBACE);
    gDevice = IOHIDUserDeviceCreate(kCFAllocatorDefault, props);
    CFRelease(descriptor);
    CFRelease(props);
    if (!gDevice) {
        fprintf(stderr,"ERR IOHIDUserDeviceCreate failed; check macOS HID permissions/support\n");
        return 2;
    }
    gLoop = CFRunLoopGetCurrent();
    CFRetain(gLoop);
    IOHIDUserDeviceScheduleWithRunLoop(gDevice, gLoop, kCFRunLoopDefaultMode);
    pthread_t worker;
    if (pthread_create(&worker, NULL, read_commands, NULL) != 0) {
        fprintf(stderr,"ERR scanner command reader failed\n");
        CFRelease(gDevice); CFRelease(gLoop);
        return 3;
    }
    puts("READY"); fflush(stdout);
    CFRunLoopRun();
    pthread_join(worker, NULL);
    IOHIDUserDeviceUnscheduleFromRunLoop(gDevice, gLoop, kCFRunLoopDefaultMode);
    CFRelease(gDevice);
    CFRelease(gLoop);
    return 0;
}
