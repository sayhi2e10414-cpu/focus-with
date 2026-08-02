#import <Foundation/Foundation.h>
#import "FocusPhonePresenceTracker.h"

static void FocusAssert(BOOL condition, NSString *message) {
    if (condition) return;
    NSLog(@"FocusPhonePresenceTrackerTests failed: %@", message);
    exit(1);
}

int main(void) {
    @autoreleasepool {
        FocusPhonePresenceTracker *tracker =
            [[FocusPhonePresenceTracker alloc] initWithConfirmationHits:2
                                                         missTolerance:4
                                                     sustainedDuration:10
                                                      cooldownDuration:60];
        FocusPhonePresenceUpdate *update = [tracker recordDetection:YES atTime:100];
        FocusAssert(update.recentlyVisible && !update.confirmed, @"first hit only starts confirmation");
        update = [tracker recordDetection:YES atTime:100.5];
        FocusAssert(update.confirmed, @"second hit confirms presence");
        update = [tracker recordDetection:NO atTime:101];
        FocusAssert(update.confirmed, @"one missed frame should not clear presence");
        update = [tracker recordDetection:YES atTime:109.5];
        FocusAssert(!update.shouldIntervene, @"presence should not trigger before ten seconds");
        update = [tracker recordDetection:YES atTime:110.5];
        FocusAssert(update.shouldIntervene, @"presence triggers after ten seconds");
        update = [tracker recordDetection:YES atTime:111];
        FocusAssert(!update.shouldIntervene, @"one presence triggers only once");
        for (NSInteger index = 0; index < 4; index++) {
            update = [tracker recordDetection:NO atTime:112 + index * 0.5];
        }
        FocusAssert(!update.recentlyVisible, @"four misses clear presence");
        [tracker recordDetection:YES atTime:114];
        [tracker recordDetection:YES atTime:114.5];
        update = [tracker recordDetection:YES atTime:125];
        FocusAssert(!update.shouldIntervene && update.cooldownRemaining > 0, @"cooldown suppresses a new reminder");
        NSLog(@"FocusPhonePresenceTrackerTests passed");
    }
    return 0;
}
