#import "FocusPanelController.h"
#import <AVFoundation/AVFoundation.h>

@interface FocusPanel : NSPanel @end
@implementation FocusPanel
- (BOOL)canBecomeKeyWindow { return YES; }
@end

@interface FocusCard : NSView @end
@implementation FocusCard
- (BOOL)isOpaque { return NO; }
- (void)drawRect:(NSRect)dirtyRect {
    NSBezierPath *shape = [NSBezierPath bezierPathWithRoundedRect:NSInsetRect(self.bounds, 1, 1) xRadius:22 yRadius:22];
    [[NSColor colorWithSRGBRed:.105 green:.105 blue:.115 alpha:.985] setFill]; [shape fill];
}
@end

static NSTextField *Label(CGFloat size, NSFontWeight weight, NSColor *color) {
    NSTextField *label = [NSTextField labelWithString:@""];
    label.font = [NSFont systemFontOfSize:size weight:weight]; label.textColor = color;
    label.lineBreakMode = NSLineBreakByTruncatingTail; return label;
}

@interface FocusPanelController ()
@property(nonatomic, strong) NSTextField *eyebrow;
@property(nonatomic, strong) NSTextField *titleLabel;
@property(nonatomic, strong) NSTextField *timerLabel;
@property(nonatomic, strong) NSTextField *statusLabel;
@property(nonatomic, strong) NSTextField *rewardLabel;
@property(nonatomic, strong) NSTextField *cameraStatusLabel;
@property(nonatomic, strong) NSView *cameraPreviewView;
@property(nonatomic, strong, nullable) AVCaptureVideoPreviewLayer *cameraPreviewLayer;
@property(nonatomic, strong, nullable) CAShapeLayer *phoneDetectionLayer;
@property(nonatomic, strong) NSButton *primaryButton;
@property(nonatomic, strong) NSButton *completeButton;
@property(nonatomic, strong) NSButton *openButton;
@property(nonatomic, strong) NSButton *cameraButton;
@property(nonatomic, assign) BOOL hasSession;
@property(nonatomic, assign) BOOL cameraRunning;
@end

@implementation FocusPanelController

- (instancetype)init {
    FocusPanel *panel = [[FocusPanel alloc] initWithContentRect:NSMakeRect(0, 0, 380, 276) styleMask:NSWindowStyleMaskBorderless | NSWindowStyleMaskNonactivatingPanel backing:NSBackingStoreBuffered defer:NO];
    if ((self = [super initWithWindow:panel])) {
        panel.backgroundColor = NSColor.clearColor; panel.opaque = NO; panel.hasShadow = YES;
        panel.level = NSFloatingWindowLevel; panel.floatingPanel = YES; panel.hidesOnDeactivate = NO;
        panel.movableByWindowBackground = YES;
        panel.collectionBehavior = NSWindowCollectionBehaviorCanJoinAllSpaces | NSWindowCollectionBehaviorFullScreenAuxiliary;
        FocusCard *card = [[FocusCard alloc] initWithFrame:panel.contentView.bounds]; card.autoresizingMask = NSViewWidthSizable | NSViewHeightSizable;
        [panel.contentView addSubview:card];
        self.eyebrow = Label(11, NSFontWeightSemibold, [NSColor colorWithWhite:.58 alpha:1]);
        self.titleLabel = Label(18, NSFontWeightSemibold, NSColor.whiteColor);
        self.timerLabel = Label(54, NSFontWeightMedium, NSColor.whiteColor);
        self.timerLabel.font = [NSFont monospacedDigitSystemFontOfSize:54 weight:NSFontWeightMedium];
        self.statusLabel = Label(12, NSFontWeightRegular, [NSColor colorWithWhite:.60 alpha:1]);
        self.rewardLabel = Label(11, NSFontWeightSemibold, [NSColor colorWithSRGBRed:.68 green:.56 blue:1 alpha:1]);
        self.rewardLabel.stringValue = @"Choose a reward in Focus";
        self.cameraStatusLabel = Label(11, NSFontWeightSemibold, [NSColor colorWithWhite:.52 alpha:1]);
        self.cameraStatusLabel.stringValue = @"Camera companion is off";
        self.cameraPreviewView = [[NSView alloc] initWithFrame:NSZeroRect];
        self.cameraPreviewView.wantsLayer = YES;
        self.cameraPreviewView.layer.backgroundColor = [NSColor colorWithWhite:.04 alpha:1].CGColor;
        self.cameraPreviewView.layer.cornerRadius = 12;
        self.cameraPreviewView.layer.masksToBounds = YES;
        self.primaryButton = [NSButton buttonWithTitle:@"Pause" target:self action:@selector(primary:)];
        self.completeButton = [NSButton buttonWithTitle:@"End session" target:self action:@selector(complete:)];
        self.openButton = [NSButton buttonWithTitle:@"Open Focus" target:self action:@selector(open:)];
        self.cameraButton = [NSButton buttonWithTitle:@"Start camera" target:self action:@selector(camera:)];
        for (NSButton *button in @[self.primaryButton, self.completeButton, self.openButton, self.cameraButton]) { button.bezelStyle = NSBezelStyleRounded; button.controlSize = NSControlSizeLarge; }
        for (NSView *view in @[self.cameraPreviewView, self.eyebrow, self.titleLabel, self.timerLabel, self.statusLabel, self.rewardLabel, self.cameraStatusLabel, self.primaryButton, self.completeButton, self.openButton, self.cameraButton]) [card addSubview:view];
        self.eyebrow.frame = NSMakeRect(22, 250, 180, 16); self.titleLabel.frame = NSMakeRect(22, 222, 336, 25);
        self.timerLabel.frame = NSMakeRect(20, 134, 340, 66); self.statusLabel.frame = NSMakeRect(22, 117, 336, 18);
        self.rewardLabel.frame = NSMakeRect(22, 91, 336, 18);
        self.cameraStatusLabel.frame = NSMakeRect(22, 67, 336, 18);
        self.primaryButton.frame = NSMakeRect(20, 18, 104, 36); self.completeButton.frame = NSMakeRect(132, 18, 124, 36); self.openButton.frame = NSMakeRect(20, 18, 112, 36);
        self.cameraButton.frame = NSMakeRect(266, 18, 94, 36);
        self.cameraPreviewView.frame = NSMakeRect(252, 138, 108, 68);
        self.cameraPreviewView.hidden = YES;
        NSScreen *screen = NSScreen.mainScreen; NSRect visible = screen.visibleFrame;
        panel.frameOrigin = NSMakePoint(NSMaxX(visible) - 404, NSMaxY(visible) - 300);
        [self updateWithSession:nil title:nil message:nil];
    }
    return self;
}

- (void)showPanel:(BOOL)activate { [self showWindow:nil]; [self.window orderFrontRegardless]; if (activate) [NSApp activateIgnoringOtherApps:YES]; }

- (void)updateWithSession:(NSDictionary *)session title:(NSString *)title message:(NSString *)message {
    self.hasSession = session != nil;
    BOOL paused = [session[@"status"] isEqual:@"paused"];
    self.eyebrow.stringValue = session ? (paused ? @"PAUSED" : @"FOCUSING") : @"FOCUS";
    self.titleLabel.stringValue = session ? (title.length ? title : @"Focus session") : @"No active session";
    self.statusLabel.stringValue = message.length ? message : (session ? (paused ? @"Resume when you are ready." : @"Do only this.") : @"Start from the web or your AI assistant.");
    self.primaryButton.title = paused ? @"Resume" : @"Pause";
    self.primaryButton.hidden = !session; self.completeButton.hidden = !session; self.openButton.hidden = session != nil;
    if (!session) self.timerLabel.stringValue = @"00:00";
}

- (void)updateTimer:(NSString *)text { self.timerLabel.stringValue = text ?: @"00:00"; }

- (void)updateRewardProgress:(NSDictionary *)progress session:(NSDictionary *)session atDate:(NSDate *)date {
    NSDictionary *reward = [progress[@"reward"] isKindOfClass:NSDictionary.class] ? progress[@"reward"] : nil;
    if (!reward) {
        self.rewardLabel.stringValue = @"Choose a reward in Focus";
        return;
    }
    double continuous = [progress[@"continuous_seconds"] doubleValue];
    NSNumber *receivedAt = progress[@"_received_at"];
    if ([session[@"status"] isEqual:@"running"] && receivedAt) {
        continuous += MAX(0, date.timeIntervalSince1970 - receivedAt.doubleValue);
    }
    double target = [progress[@"target_seconds"] doubleValue];
    if ([reward[@"repeatable"] boolValue] && target > 0) continuous = fmod(continuous, target);
    NSInteger remaining = (NSInteger)MAX(0, floor(target - continuous));
    NSString *mode = [progress[@"evidence_mode"] isEqual:@"camera_verified"]
        ? @"camera verified"
        : ([progress[@"evidence_mode"] isEqual:@"timer_guarded"] ? @"timer + blocklist" : @"timer only");
    NSString *title = [reward[@"title"] isKindOfClass:NSString.class] ? reward[@"title"] : @"Reward";
    self.rewardLabel.stringValue = remaining > 0
        ? [NSString stringWithFormat:@"🎁 %@ in %ld:%02ld · %@", title, (long)(remaining / 60), (long)(remaining % 60), mode]
        : [NSString stringWithFormat:@"🎁 %@ unlocked · %@", title, mode];
}

- (void)setCameraSession:(AVCaptureSession *)session {
    [self.cameraPreviewLayer removeFromSuperlayer];
    [self.phoneDetectionLayer removeFromSuperlayer];
    self.cameraPreviewLayer = nil;
    self.phoneDetectionLayer = nil;
    if (!session) return;
    AVCaptureVideoPreviewLayer *preview = [AVCaptureVideoPreviewLayer layerWithSession:session];
    preview.videoGravity = AVLayerVideoGravityResizeAspectFill;
    preview.frame = self.cameraPreviewView.bounds;
    [self.cameraPreviewView.layer addSublayer:preview];
    self.cameraPreviewLayer = preview;
    CAShapeLayer *detection = [CAShapeLayer layer];
    detection.fillColor = NSColor.clearColor.CGColor;
    detection.strokeColor = [NSColor colorWithSRGBRed:1 green:.64 blue:.20 alpha:1].CGColor;
    detection.lineWidth = 2;
    detection.hidden = YES;
    [self.cameraPreviewView.layer addSublayer:detection];
    self.phoneDetectionLayer = detection;
}

- (void)updateCameraRunning:(BOOL)running message:(NSString *)message {
    self.cameraRunning = running;
    self.cameraButton.title = running ? @"Stop camera" : @"Start camera";
    self.cameraPreviewView.hidden = !running;
    self.timerLabel.frame = NSMakeRect(20, 134, running ? 220 : 340, 66);
    self.cameraStatusLabel.stringValue = message.length ? message : (running ? @"● Camera companion on" : @"Camera companion is off");
    self.cameraStatusLabel.textColor = running
        ? [NSColor colorWithSRGBRed:.36 green:.86 blue:.58 alpha:1]
        : [NSColor colorWithWhite:.52 alpha:1];
}

- (void)updateCameraInterventionDelivery:(NSString *)message {
    if (!self.cameraRunning) return;
    self.cameraStatusLabel.stringValue = message;
    self.cameraStatusLabel.textColor = [NSColor colorWithSRGBRed:1 green:.32 blue:.28 alpha:1];
}

- (void)updatePhonePresence:(BOOL)phonePresent
                 confidence:(float)confidence
                   evidence:(NSInteger)evidence
          sustainedDuration:(NSTimeInterval)sustainedDuration
     interventionTriggered:(BOOL)interventionTriggered
                boundingBox:(CGRect)boundingBox {
    if (!self.cameraRunning) return;
    if (!phonePresent) {
        self.cameraStatusLabel.stringValue = @"Local detection · no phone";
        self.cameraStatusLabel.textColor = [NSColor colorWithSRGBRed:.36 green:.86 blue:.58 alpha:1];
        self.phoneDetectionLayer.hidden = YES;
        return;
    }
    NSInteger percent = (NSInteger)lroundf(confidence * 100);
    if (interventionTriggered) {
        self.cameraStatusLabel.stringValue = @"Phone present for a while · sending reminder…";
        self.cameraStatusLabel.textColor = [NSColor colorWithSRGBRed:1 green:.32 blue:.28 alpha:1];
    } else if (evidence >= 2) {
        self.cameraStatusLabel.stringValue = [NSString stringWithFormat:@"Phone %ld%% · %ld/10 seconds",
            (long)percent, (long)MIN(10, (NSInteger)floor(sustainedDuration))];
        self.cameraStatusLabel.textColor = [NSColor colorWithSRGBRed:1 green:.60 blue:.26 alpha:1];
    } else {
        self.cameraStatusLabel.stringValue = [NSString stringWithFormat:@"Confirming phone %ld%% · 1/2", (long)percent];
        self.cameraStatusLabel.textColor = [NSColor colorWithSRGBRed:1 green:.70 blue:.30 alpha:1];
    }
    CGRect bounds = self.cameraPreviewView.bounds;
    CGRect previewRect = CGRectMake(
        boundingBox.origin.x * bounds.size.width,
        boundingBox.origin.y * bounds.size.height,
        boundingBox.size.width * bounds.size.width,
        boundingBox.size.height * bounds.size.height
    );
    CGPathRef path = CGPathCreateWithRoundedRect(previewRect, 5, 5, nil);
    self.phoneDetectionLayer.path = path;
    CGPathRelease(path);
    self.phoneDetectionLayer.strokeColor = self.cameraStatusLabel.textColor.CGColor;
    self.phoneDetectionLayer.hidden = CGRectIsEmpty(previewRect);
}

- (void)setCameraBusy:(BOOL)busy {
    self.cameraButton.enabled = !busy;
    if (busy) self.cameraButton.title = @"Starting…";
}

- (void)primary:(id)sender { [self.delegate focusPanelDidRequestPrimaryAction]; }
- (void)complete:(id)sender { [self.delegate focusPanelDidRequestCompletion]; }
- (void)open:(id)sender { [self.delegate focusPanelDidRequestOpenWeb]; }
- (void)camera:(id)sender { [self.delegate focusPanelDidRequestCameraToggle]; }
@end
