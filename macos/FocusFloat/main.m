#import <Cocoa/Cocoa.h>

id FocusCreateAppDelegate(void);

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        NSApplication *app = NSApplication.sharedApplication;
        app.activationPolicy = NSApplicationActivationPolicyAccessory;
        app.delegate = FocusCreateAppDelegate();
        [app run];
    }
    return 0;
}
