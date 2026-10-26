/* macOS barcode input simulator using public Quartz keyboard events.
 * This IS NOT a virtual HID device, OS scanner or USB keyboard.
 * Protocol: input "SCAN <allowed ASCII>" or "QUIT". stdout READY / OK / ERR ...
 * Requires Accessibility permission for the helper binary.
 */
#include <ApplicationServices/ApplicationServices.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static bool valid_code(const char *code) {
    size_t n = strlen(code);
    if (n < 1 || n > 100) return false;
    for (size_t i = 0; i < n; ++i) {
        char c = code[i];
        if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
              (c >= '0' && c <= '9') || c == '.' || c == '-' ||
              c == '_' || c == '/')) return false;
    }
    return true;
}

static bool post_character(UniChar c) {
    CGEventRef down = CGEventCreateKeyboardEvent(NULL, 0, true);
    CGEventRef up = CGEventCreateKeyboardEvent(NULL, 0, false);
    if (!down || !up) {
        if (down) CFRelease(down);
        if (up) CFRelease(up);
        return false;
    }
    CGEventKeyboardSetUnicodeString(down, 1, &c);
    CGEventKeyboardSetUnicodeString(up, 1, &c);
    CGEventPost(kCGHIDEventTap, down);
    CGEventPost(kCGHIDEventTap, up);
    CFRelease(down);
    CFRelease(up);
    usleep(22000);
    return true;
}

int main(int argc, char **argv) {
    if (argc == 2 && strcmp(argv[1], "--self-test") == 0) {
        puts("PASS: Quartz barcode keyboard helper compiled");
        return 0;
    }
    /* macOS may display a system prompt, but permission is not granted
       immediately. Never report READY until Accessibility is actually trusted. */
    const void *keys[] = { kAXTrustedCheckOptionPrompt };
    const void *values[] = { kCFBooleanTrue };
    CFDictionaryRef options = CFDictionaryCreate(
        kCFAllocatorDefault, keys, values, 1,
        &kCFTypeDictionaryKeyCallBacks, &kCFTypeDictionaryValueCallBacks);
    Boolean allowed = AXIsProcessTrustedWithOptions(options);
    if (options) CFRelease(options);
    if (!allowed) {
        puts("ERR ACCESSIBILITY_PERMISSION_REQUIRED");
        fflush(stdout);
        fprintf(stderr, "Open macOS System Settings > Privacy & Security > Accessibility, allow DevicesSimulator (or this helper), then relaunch.\n");
        return 3;
    }
    puts("READY KEYBOARD_SIMULATION");
    fflush(stdout);
    char line[160];
    while (fgets(line, sizeof(line), stdin)) {
        size_t len = strlen(line);
        if (len && line[len - 1] == '\n') line[--len] = '\0';
        if (strcmp(line, "QUIT") == 0) break;
        if (strncmp(line, "SCAN ", 5) != 0 || !valid_code(line + 5)) {
            puts("ERR INVALID_BARCODE");
            fflush(stdout);
            continue;
        }
        if (!AXIsProcessTrusted()) {
            puts("ERR ACCESSIBILITY_PERMISSION_LOST");
            fflush(stdout);
            continue;
        }
        bool success = true;
        for (const char *p = line + 5; *p; ++p) {
            if (!post_character((UniChar)(unsigned char)*p)) {
                success = false; break;
            }
        }
        puts(success ? "OK KEYBOARD_EVENTS_SENT" : "ERR KEYBOARD_EVENT_FAILED");
        fflush(stdout);
    }
    return 0;
}
