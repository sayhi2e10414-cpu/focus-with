#import "FocusPanelController.h"

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
@property(nonatomic, strong) NSButton *primaryButton;
@property(nonatomic, strong) NSButton *completeButton;
@property(nonatomic, strong) NSButton *openButton;
@property(nonatomic, assign) BOOL hasSession;
@end

@implementation FocusPanelController

- (instancetype)init {
    FocusPanel *panel = [[FocusPanel alloc] initWithContentRect:NSMakeRect(0, 0, 370, 214) styleMask:NSWindowStyleMaskBorderless | NSWindowStyleMaskNonactivatingPanel backing:NSBackingStoreBuffered defer:NO];
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
        self.primaryButton = [NSButton buttonWithTitle:@"Pause" target:self action:@selector(primary:)];
        self.completeButton = [NSButton buttonWithTitle:@"End session" target:self action:@selector(complete:)];
        self.openButton = [NSButton buttonWithTitle:@"Open Focus" target:self action:@selector(open:)];
        for (NSButton *button in @[self.primaryButton, self.completeButton, self.openButton]) { button.bezelStyle = NSBezelStyleRounded; button.controlSize = NSControlSizeLarge; }
        for (NSView *view in @[self.eyebrow, self.titleLabel, self.timerLabel, self.statusLabel, self.primaryButton, self.completeButton, self.openButton]) [card addSubview:view];
        self.eyebrow.frame = NSMakeRect(22, 188, 180, 16); self.titleLabel.frame = NSMakeRect(22, 160, 326, 25);
        self.timerLabel.frame = NSMakeRect(20, 76, 330, 66); self.statusLabel.frame = NSMakeRect(22, 59, 326, 18);
        self.primaryButton.frame = NSMakeRect(20, 14, 104, 36); self.completeButton.frame = NSMakeRect(132, 14, 124, 36); self.openButton.frame = NSMakeRect(20, 14, 112, 36);
        NSScreen *screen = NSScreen.mainScreen; NSRect visible = screen.visibleFrame;
        panel.frameOrigin = NSMakePoint(NSMaxX(visible) - 394, NSMaxY(visible) - 238);
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
- (void)primary:(id)sender { [self.delegate focusPanelDidRequestPrimaryAction]; }
- (void)complete:(id)sender { [self.delegate focusPanelDidRequestCompletion]; }
- (void)open:(id)sender { [self.delegate focusPanelDidRequestOpenWeb]; }
@end
