#import <Cocoa/Cocoa.h>

NS_ASSUME_NONNULL_BEGIN

@class AVCaptureSession;

@protocol FocusPanelControllerDelegate <NSObject>
- (void)focusPanelDidRequestPrimaryAction;
- (void)focusPanelDidRequestCompletion;
- (void)focusPanelDidRequestOpenWeb;
- (void)focusPanelDidRequestCameraToggle;
@end

@interface FocusPanelController : NSWindowController
@property(nonatomic, weak, nullable) id<FocusPanelControllerDelegate> delegate;
- (void)showPanel:(BOOL)activate;
- (void)updateWithSession:(nullable NSDictionary *)session title:(nullable NSString *)title message:(nullable NSString *)message;
- (void)updateTimer:(NSString *)text;
- (void)updateRewardProgress:(nullable NSDictionary *)progress
                     session:(nullable NSDictionary *)session
                      atDate:(NSDate *)date;
- (void)setCameraSession:(nullable AVCaptureSession *)session;
- (void)updateCameraRunning:(BOOL)running message:(nullable NSString *)message;
- (void)updateCameraInterventionDelivery:(NSString *)message;
- (void)updatePhonePresence:(BOOL)phonePresent
                 confidence:(float)confidence
                   evidence:(NSInteger)evidence
          sustainedDuration:(NSTimeInterval)sustainedDuration
     interventionTriggered:(BOOL)interventionTriggered
                boundingBox:(CGRect)boundingBox;
- (void)setCameraBusy:(BOOL)busy;
@end

NS_ASSUME_NONNULL_END
