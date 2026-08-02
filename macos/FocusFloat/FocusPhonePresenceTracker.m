#import "FocusPhonePresenceTracker.h"

@interface FocusPhonePresenceUpdate ()
@property(nonatomic, assign, readwrite) BOOL recentlyVisible;
@property(nonatomic, assign, readwrite) BOOL confirmed;
@property(nonatomic, assign, readwrite) NSInteger evidence;
@property(nonatomic, assign, readwrite) NSTimeInterval sustainedDuration;
@property(nonatomic, assign, readwrite) BOOL shouldIntervene;
@property(nonatomic, assign, readwrite) BOOL interventionTriggeredForPresence;
@property(nonatomic, assign, readwrite) NSTimeInterval cooldownRemaining;
@end

@implementation FocusPhonePresenceUpdate
@end

@interface FocusPhonePresenceTracker ()
@property(nonatomic, assign) NSInteger confirmationHits;
@property(nonatomic, assign) NSInteger missTolerance;
@property(nonatomic, assign) NSTimeInterval requiredSustainedDuration;
@property(nonatomic, assign) NSTimeInterval cooldownDuration;
@property(nonatomic, assign) NSInteger evidence;
@property(nonatomic, assign) NSInteger misses;
@property(nonatomic, assign) NSTimeInterval confirmedAt;
@property(nonatomic, assign) NSTimeInterval lastInterventionAt;
@property(nonatomic, assign) BOOL interventionTriggeredForPresence;
@end

@implementation FocusPhonePresenceTracker

- (instancetype)initWithConfirmationHits:(NSInteger)confirmationHits
                            missTolerance:(NSInteger)missTolerance
                        sustainedDuration:(NSTimeInterval)sustainedDuration
                         cooldownDuration:(NSTimeInterval)cooldownDuration {
    if ((self = [super init])) {
        _confirmationHits = MAX(1, confirmationHits);
        _missTolerance = MAX(1, missTolerance);
        _requiredSustainedDuration = MAX(0, sustainedDuration);
        _cooldownDuration = MAX(0, cooldownDuration);
    }
    return self;
}

- (FocusPhonePresenceUpdate *)recordDetection:(BOOL)detected atTime:(NSTimeInterval)time {
    if (detected) {
        self.evidence = MIN(self.evidence + 1, 5);
        self.misses = 0;
    } else if (self.evidence > 0) {
        self.misses += 1;
        if (self.misses >= self.missTolerance) [self clearCurrentPresence];
    }

    BOOL recentlyVisible = self.evidence > 0;
    BOOL confirmed = self.evidence >= self.confirmationHits;
    if (confirmed && self.confirmedAt <= 0) self.confirmedAt = time;
    NSTimeInterval sustained = confirmed ? MAX(0, time - self.confirmedAt) : 0;
    NSTimeInterval cooldownRemaining = self.lastInterventionAt > 0
        ? MAX(0, self.lastInterventionAt + self.cooldownDuration - time)
        : 0;
    BOOL shouldIntervene = confirmed
        && !self.interventionTriggeredForPresence
        && sustained >= self.requiredSustainedDuration
        && cooldownRemaining <= 0;
    if (shouldIntervene) {
        self.interventionTriggeredForPresence = YES;
        self.lastInterventionAt = time;
        cooldownRemaining = self.cooldownDuration;
    }

    FocusPhonePresenceUpdate *update = [[FocusPhonePresenceUpdate alloc] init];
    update.recentlyVisible = recentlyVisible;
    update.confirmed = confirmed;
    update.evidence = self.evidence;
    update.sustainedDuration = sustained;
    update.shouldIntervene = shouldIntervene;
    update.interventionTriggeredForPresence = self.interventionTriggeredForPresence;
    update.cooldownRemaining = cooldownRemaining;
    return update;
}

- (void)clearCurrentPresence {
    self.evidence = 0;
    self.misses = 0;
    self.confirmedAt = 0;
    self.interventionTriggeredForPresence = NO;
}

- (void)reset {
    [self clearCurrentPresence];
    self.lastInterventionAt = 0;
}

@end
