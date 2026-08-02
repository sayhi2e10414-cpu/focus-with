#import <Cocoa/Cocoa.h>
#import "FocusAPIClient.h"

static void FocusAssert(BOOL condition, NSString *message) {
    if (condition) return;
    NSLog(@"FocusAPIClientTests failed: %@", message);
    exit(1);
}

int main(void) {
    @autoreleasepool {
        NSDate *now = [NSDate dateWithTimeIntervalSince1970:1000000];
        NSDictionary *event = [FocusAPIClient cameraPhoneEventPayloadWithEventID:@"camera-event-test"
                                                                 durationSeconds:10
                                                                      detectedAt:now];
        FocusAssert([event[@"event_id"] isEqualToString:@"camera-event-test"], @"event ID is preserved");
        FocusAssert([event[@"duration_seconds"] integerValue] == 10, @"duration is included");
        FocusAssert([event[@"source"] isEqualToString:@"macos_focus_float"], @"source is explicit");
        FocusAssert(event[@"detected_at"] != nil, @"timestamp is included");
        FocusAssert(event.count == 4, @"payload contains no image, box, or confidence");
        NSDictionary *heartbeat = [FocusAPIClient cameraHeartbeatPayloadWithState:@"observing"
                                                                        observedAt:now];
        FocusAssert([heartbeat[@"camera_state"] isEqualToString:@"observing"], @"camera state is explicit");
        FocusAssert([heartbeat[@"source"] isEqualToString:@"macos_focus_float"], @"heartbeat source is explicit");
        FocusAssert(heartbeat[@"observed_at"] != nil, @"heartbeat timestamp is included");
        FocusAssert(heartbeat.count == 3, @"heartbeat contains no image-derived data");
        NSLog(@"FocusAPIClientTests passed");
    }
    return 0;
}
