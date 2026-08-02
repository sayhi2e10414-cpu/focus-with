#import <AVFoundation/AVFoundation.h>

NS_ASSUME_NONNULL_BEGIN

typedef void (^FocusCameraStartCompletion)(BOOL success, NSString *_Nullable errorMessage);

@class FocusCameraController;

@protocol FocusCameraControllerDelegate <NSObject>
- (void)focusCameraController:(FocusCameraController *)controller
       didUpdatePhonePresence:(BOOL)phonePresent
                   confidence:(float)confidence
                     evidence:(NSInteger)evidence
            sustainedDuration:(NSTimeInterval)sustainedDuration
       interventionTriggered:(BOOL)interventionTriggered
     shouldReportIntervention:(BOOL)shouldReportIntervention
                  boundingBox:(CGRect)boundingBox;
- (void)focusCameraController:(FocusCameraController *)controller
      didUpdateDetectorStatus:(NSString *)status;
@end

@interface FocusCameraController : NSObject
@property(nonatomic, weak, nullable) id<FocusCameraControllerDelegate> delegate;
@property(nonatomic, strong, readonly, nullable) AVCaptureSession *captureSession;
@property(nonatomic, assign, readonly, getter=isRunning) BOOL running;
- (void)startWithCompletion:(FocusCameraStartCompletion)completion;
- (void)stop;
@end

NS_ASSUME_NONNULL_END
