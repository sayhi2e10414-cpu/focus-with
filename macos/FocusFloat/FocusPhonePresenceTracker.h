#import <Foundation/Foundation.h>

NS_ASSUME_NONNULL_BEGIN

@interface FocusPhonePresenceUpdate : NSObject
@property(nonatomic, assign, readonly) BOOL recentlyVisible;
@property(nonatomic, assign, readonly) BOOL confirmed;
@property(nonatomic, assign, readonly) NSInteger evidence;
@property(nonatomic, assign, readonly) NSTimeInterval sustainedDuration;
@property(nonatomic, assign, readonly) BOOL shouldIntervene;
@property(nonatomic, assign, readonly) BOOL interventionTriggeredForPresence;
@property(nonatomic, assign, readonly) NSTimeInterval cooldownRemaining;
@end

@interface FocusPhonePresenceTracker : NSObject
- (instancetype)initWithConfirmationHits:(NSInteger)confirmationHits
                            missTolerance:(NSInteger)missTolerance
                        sustainedDuration:(NSTimeInterval)sustainedDuration
                         cooldownDuration:(NSTimeInterval)cooldownDuration NS_DESIGNATED_INITIALIZER;
- (instancetype)init NS_UNAVAILABLE;
- (FocusPhonePresenceUpdate *)recordDetection:(BOOL)detected atTime:(NSTimeInterval)time;
- (void)reset;
@end

NS_ASSUME_NONNULL_END
