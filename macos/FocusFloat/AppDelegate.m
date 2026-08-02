#import <Cocoa/Cocoa.h>
#import <Security/Security.h>
#import "FocusAPIClient.h"
#import "FocusCameraController.h"
#import "FocusPanelController.h"

static NSString *const FocusService = @"app.focusstandalone.FocusFloat";
static NSString *const FocusAccount = @"api-token";

static NSString *LoadToken(void) {
    NSDictionary *query = @{(__bridge id)kSecClass: (__bridge id)kSecClassGenericPassword,
                            (__bridge id)kSecAttrService: FocusService,
                            (__bridge id)kSecAttrAccount: FocusAccount,
                            (__bridge id)kSecReturnData: @YES,
                            (__bridge id)kSecMatchLimit: (__bridge id)kSecMatchLimitOne};
    CFTypeRef result = NULL;
    if (SecItemCopyMatching((__bridge CFDictionaryRef)query, &result) != errSecSuccess) return nil;
    NSData *data = CFBridgingRelease(result);
    return [[NSString alloc] initWithData:data encoding:NSUTF8StringEncoding];
}

static void SaveToken(NSString *token) {
    NSDictionary *identity = @{(__bridge id)kSecClass: (__bridge id)kSecClassGenericPassword,
                               (__bridge id)kSecAttrService: FocusService,
                               (__bridge id)kSecAttrAccount: FocusAccount};
    SecItemDelete((__bridge CFDictionaryRef)identity);
    NSMutableDictionary *item = [identity mutableCopy];
    item[(__bridge id)kSecValueData] = [token dataUsingEncoding:NSUTF8StringEncoding];
    SecItemAdd((__bridge CFDictionaryRef)item, NULL);
}

@interface AppDelegate : NSObject <NSApplicationDelegate, FocusAPIClientDelegate, FocusCameraControllerDelegate, FocusPanelControllerDelegate>
@property(nonatomic, strong) FocusAPIClient *apiClient;
@property(nonatomic, strong) FocusCameraController *cameraController;
@property(nonatomic, strong) FocusPanelController *panel;
@property(nonatomic, strong) NSStatusItem *statusItem;
@property(nonatomic, strong) NSTimer *displayTimer;
@property(nonatomic, strong, nullable) NSTimer *cameraHeartbeatTimer;
@property(nonatomic, strong, nullable) NSDate *lastCameraHeartbeatAt;
@property(nonatomic, strong) NSURL *webURL;
@property(nonatomic, assign) BOOL cameraRequestInFlight;
@end

@implementation AppDelegate

- (void)applicationDidFinishLaunching:(NSNotification *)notification {
    self.panel = [[FocusPanelController alloc] init]; self.panel.delegate = self; [self.panel showPanel:NO];
    self.cameraController = [[FocusCameraController alloc] init];
    self.cameraController.delegate = self;
    [self.panel updateCameraRunning:NO message:nil];
    [self configureStatusItem];
    if (![self configureConnectionIfNeeded:NO]) { [NSApp terminate:nil]; return; }
    self.displayTimer = [NSTimer scheduledTimerWithTimeInterval:1 target:self selector:@selector(updateTimer) userInfo:nil repeats:YES];
}

- (BOOL)configureConnectionIfNeeded:(BOOL)alwaysAsk {
    NSString *savedURL = [NSUserDefaults.standardUserDefaults stringForKey:@"FocusBaseURL"] ?: @"http://127.0.0.1:8765/";
    NSString *savedToken = LoadToken();
    if (!alwaysAsk && savedToken.length) { [self connectURL:savedURL token:savedToken]; return YES; }

    NSAlert *alert = [[NSAlert alloc] init];
    alert.messageText = @"Connect FocusFloat";
    alert.informativeText = @"Use your Focus server URL and API token. The token is stored in the macOS Keychain.";
    [alert addButtonWithTitle:@"Connect"]; [alert addButtonWithTitle:@"Cancel"];
    NSView *fields = [[NSView alloc] initWithFrame:NSMakeRect(0, 0, 360, 78)];
    NSTextField *urlField = [[NSTextField alloc] initWithFrame:NSMakeRect(0, 44, 360, 26)]; urlField.stringValue = savedURL;
    NSSecureTextField *tokenField = [[NSSecureTextField alloc] initWithFrame:NSMakeRect(0, 6, 360, 26)]; tokenField.placeholderString = @"Focus API token"; tokenField.stringValue = savedToken ?: @"";
    [fields addSubview:urlField]; [fields addSubview:tokenField]; alert.accessoryView = fields;
    if ([alert runModal] != NSAlertFirstButtonReturn || !tokenField.stringValue.length) return NO;
    NSString *url = urlField.stringValue.length ? urlField.stringValue : @"http://127.0.0.1:8765/";
    if (![url hasSuffix:@"/"]) url = [url stringByAppendingString:@"/"];
    [NSUserDefaults.standardUserDefaults setObject:url forKey:@"FocusBaseURL"];
    SaveToken(tokenField.stringValue);
    [self connectURL:url token:tokenField.stringValue];
    return YES;
}

- (void)connectURL:(NSString *)urlString token:(NSString *)token {
    [self.apiClient stopPolling];
    self.webURL = [NSURL URLWithString:urlString];
    self.apiClient = [[FocusAPIClient alloc] initWithBaseURL:self.webURL token:token];
    self.apiClient.delegate = self; [self.apiClient startPolling];
}

- (void)configureStatusItem {
    self.statusItem = [NSStatusBar.systemStatusBar statusItemWithLength:NSVariableStatusItemLength];
    self.statusItem.button.title = @"◉";
    NSMenu *menu = [[NSMenu alloc] init];
    [menu addItemWithTitle:@"Show FocusFloat" action:@selector(showPanel:) keyEquivalent:@""];
    [menu addItemWithTitle:@"Open Focus" action:@selector(openWeb:) keyEquivalent:@""];
    [menu addItemWithTitle:@"Connection…" action:@selector(reconfigure:) keyEquivalent:@""];
    [menu addItem:NSMenuItem.separatorItem];
    [menu addItemWithTitle:@"Quit" action:@selector(quit:) keyEquivalent:@"q"];
    for (NSMenuItem *item in menu.itemArray) item.target = self;
    self.statusItem.menu = menu;
}

- (void)updateTimer {
    NSDictionary *session = self.apiClient.currentSession;
    if (!session) {
        self.statusItem.button.title = @"◉";
        [self.panel updateRewardProgress:nil session:nil atDate:NSDate.date];
        return;
    }
    NSString *value = [FocusAPIClient formattedDisplayForSession:session atDate:NSDate.date];
    [self.panel updateTimer:value];
    [self.panel updateRewardProgress:self.apiClient.currentRewardProgress session:session atDate:NSDate.date];
    self.statusItem.button.title = [NSString stringWithFormat:@"◉ %@", value];
}

- (void)focusAPIClient:(FocusAPIClient *)client didUpdateSession:(NSDictionary *)session title:(NSString *)title {
    [self.panel updateWithSession:session title:title message:nil];
    [self updateTimer];
    [self sendCameraHeartbeatIfNeeded];
}
- (void)focusAPIClient:(FocusAPIClient *)client didFailWithMessage:(NSString *)message { [self.panel updateWithSession:client.currentSession title:client.currentTitle message:message]; }
- (void)focusPanelDidRequestPrimaryAction { [self.apiClient performAction:[self.apiClient.currentSession[@"status"] isEqual:@"paused"] ? @"resume" : @"pause" completion:nil]; }
- (void)focusPanelDidRequestCompletion { [self.apiClient performAction:@"complete" completion:nil]; }
- (void)focusPanelDidRequestOpenWeb { [self openWeb:nil]; }
- (void)focusPanelDidRequestCameraToggle {
    if (self.cameraRequestInFlight) return;
    if (self.cameraController.isRunning) {
        [self stopCameraHeartbeat];
        [self.cameraController stop];
        [self.panel setCameraSession:nil];
        [self.panel updateCameraRunning:NO message:@"Camera companion is off"];
        return;
    }
    self.cameraRequestInFlight = YES;
    [self.panel updateCameraRunning:NO message:@"Requesting camera permission…"];
    [self.panel setCameraBusy:YES];
    __weak typeof(self) weakSelf = self;
    [self.cameraController startWithCompletion:^(BOOL success, NSString *errorMessage) {
        typeof(self) self = weakSelf;
        if (!self) return;
        self.cameraRequestInFlight = NO;
        [self.panel setCameraBusy:NO];
        if (!success) {
            [self.panel setCameraSession:nil];
            [self.panel updateCameraRunning:NO message:errorMessage];
            return;
        }
        [self.panel setCameraSession:self.cameraController.captureSession];
        [self.panel updateCameraRunning:YES message:@"● Camera companion on · local only"];
        [self startCameraHeartbeat];
    }];
}

- (void)startCameraHeartbeat {
    [self.cameraHeartbeatTimer invalidate];
    self.cameraHeartbeatTimer = [NSTimer scheduledTimerWithTimeInterval:30
                                                                 target:self
                                                               selector:@selector(sendCameraHeartbeatIfNeeded)
                                                               userInfo:nil
                                                                repeats:YES];
    [self sendCameraHeartbeatIfNeeded];
}

- (void)sendCameraHeartbeatIfNeeded {
    NSDictionary *session = self.apiClient.currentSession;
    if (!self.cameraController.isRunning
        || ![session[@"status"] isEqual:@"running"]
        || [session[@"session_kind"] isEqual:@"break"]) return;
    NSDate *now = NSDate.date;
    if (self.lastCameraHeartbeatAt && [now timeIntervalSinceDate:self.lastCameraHeartbeatAt] < 25) return;
    self.lastCameraHeartbeatAt = now;
    [self.apiClient reportCameraHeartbeatState:@"observing" observedAt:now];
}

- (void)stopCameraHeartbeat {
    [self.cameraHeartbeatTimer invalidate];
    self.cameraHeartbeatTimer = nil;
    if (self.lastCameraHeartbeatAt) {
        [self.apiClient reportCameraHeartbeatState:@"stopped" observedAt:NSDate.date];
    }
    self.lastCameraHeartbeatAt = nil;
}

- (void)focusCameraController:(FocusCameraController *)controller
       didUpdatePhonePresence:(BOOL)phonePresent
                   confidence:(float)confidence
                     evidence:(NSInteger)evidence
            sustainedDuration:(NSTimeInterval)sustainedDuration
       interventionTriggered:(BOOL)interventionTriggered
     shouldReportIntervention:(BOOL)shouldReportIntervention
                  boundingBox:(CGRect)boundingBox {
    [self.panel updatePhonePresence:phonePresent
                         confidence:confidence
                           evidence:evidence
                  sustainedDuration:sustainedDuration
             interventionTriggered:interventionTriggered
                        boundingBox:boundingBox];
    if (!shouldReportIntervention) return;
    if (![self.apiClient.currentSession[@"status"] isEqual:@"running"]) {
        [self.panel updateCameraInterventionDelivery:@"Phone stayed visible · no running focus session"];
        return;
    }
    [self.panel updateCameraInterventionDelivery:@"Phone stayed visible · sending reminder…"];
    __weak typeof(self) weakSelf = self;
    [self.apiClient reportCameraPhoneDistractionWithEventID:NSUUID.UUID.UUIDString.lowercaseString
                                            durationSeconds:10
                                                 detectedAt:NSDate.date
                                                 completion:^(BOOL accepted, NSString *message) {
        typeof(self) self = weakSelf;
        if (!self) return;
        [self.panel updateCameraInterventionDelivery:
            accepted ? @"Phone stayed visible · reminder sent" : (message ?: @"Reminder was not sent")];
    }];
}

- (void)focusCameraController:(FocusCameraController *)controller didUpdateDetectorStatus:(NSString *)status {
    if (!controller.isRunning && !self.cameraRequestInFlight) return;
    [self.panel updateCameraRunning:YES message:status];
}

- (void)showPanel:(id)sender { [self.panel showPanel:YES]; }
- (void)openWeb:(id)sender { if (self.webURL) [NSWorkspace.sharedWorkspace openURL:self.webURL]; }
- (void)reconfigure:(id)sender { [self configureConnectionIfNeeded:YES]; }
- (void)quit:(id)sender { [NSApp terminate:nil]; }
- (void)applicationWillTerminate:(NSNotification *)notification {
    [self stopCameraHeartbeat];
    [self.cameraController stop];
    [self.apiClient stopPolling];
    [self.displayTimer invalidate];
}
@end

id FocusCreateAppDelegate(void) { return [[AppDelegate alloc] init]; }
