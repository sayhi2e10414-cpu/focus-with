#import "FocusCameraController.h"
#import "FocusPhonePresenceTracker.h"
#import <CoreML/CoreML.h>
#import <ImageIO/ImageIO.h>
#import <Vision/Vision.h>

@interface FocusCameraController () <AVCaptureVideoDataOutputSampleBufferDelegate>
@property(nonatomic, strong, readwrite, nullable) AVCaptureSession *captureSession;
@property(nonatomic, assign, readwrite, getter=isRunning) BOOL running;
@property(nonatomic, strong) dispatch_queue_t sessionQueue;
@property(nonatomic, strong) dispatch_queue_t videoQueue;
@property(nonatomic, assign) NSUInteger requestGeneration;
@property(nonatomic, strong, nullable) AVCaptureVideoDataOutput *videoOutput;
@property(nonatomic, strong, nullable) VNCoreMLRequest *objectDetectionRequest;
@property(nonatomic, assign) BOOL detectorPreparing;
@property(nonatomic, assign) NSTimeInterval lastInferenceAt;
@property(nonatomic, assign) float lastPhoneConfidence;
@property(nonatomic, assign) CGRect lastPhoneBoundingBox;
@property(nonatomic, strong) FocusPhonePresenceTracker *phonePresenceTracker;
@end

@implementation FocusCameraController

- (instancetype)init {
    if ((self = [super init])) {
        _sessionQueue = dispatch_queue_create("app.focusstandalone.FocusFloat.camera", DISPATCH_QUEUE_SERIAL);
        _videoQueue = dispatch_queue_create("app.focusstandalone.FocusFloat.vision", DISPATCH_QUEUE_SERIAL);
        _phonePresenceTracker = [[FocusPhonePresenceTracker alloc] initWithConfirmationHits:2
                                                                              missTolerance:4
                                                                          sustainedDuration:10
                                                                           cooldownDuration:60];
    }
    return self;
}

- (void)startWithCompletion:(FocusCameraStartCompletion)completion {
    NSUInteger generation;
    @synchronized (self) {
        self.requestGeneration += 1;
        generation = self.requestGeneration;
    }
    [self startGeneration:generation completion:completion];
}

- (BOOL)isCurrentGeneration:(NSUInteger)generation {
    @synchronized (self) {
        return generation == self.requestGeneration;
    }
}

- (void)startGeneration:(NSUInteger)generation completion:(FocusCameraStartCompletion)completion {
    AVAuthorizationStatus authorization = [AVCaptureDevice authorizationStatusForMediaType:AVMediaTypeVideo];
    if (authorization == AVAuthorizationStatusNotDetermined) {
        __weak typeof(self) weakSelf = self;
        [AVCaptureDevice requestAccessForMediaType:AVMediaTypeVideo completionHandler:^(BOOL granted) {
            dispatch_async(dispatch_get_main_queue(), ^{
                typeof(self) self = weakSelf;
                if (!self) return;
                if (![self isCurrentGeneration:generation]) {
                    completion(NO, @"Camera start was cancelled.");
                } else if (!granted) {
                    completion(NO, @"Allow FocusFloat in System Settings → Privacy & Security → Camera.");
                } else {
                    [self startGeneration:generation completion:completion];
                }
            });
        }];
        return;
    }
    if (authorization != AVAuthorizationStatusAuthorized) {
        completion(NO, @"Allow FocusFloat in System Settings → Privacy & Security → Camera.");
        return;
    }

    __weak typeof(self) weakSelf = self;
    dispatch_async(self.sessionQueue, ^{
        typeof(self) self = weakSelf;
        if (!self) return;
        if (![self isCurrentGeneration:generation]) {
            dispatch_async(dispatch_get_main_queue(), ^{ completion(NO, @"Camera start was cancelled."); });
            return;
        }
        NSError *configurationError = nil;
        if (![self configureCaptureSession:&configurationError]) {
            NSString *message = configurationError.localizedDescription ?: @"No camera is available.";
            dispatch_async(dispatch_get_main_queue(), ^{ completion(NO, message); });
            return;
        }
        if (![self isCurrentGeneration:generation]) {
            dispatch_async(dispatch_get_main_queue(), ^{ completion(NO, @"Camera start was cancelled."); });
            return;
        }
        if (!self.captureSession.isRunning) [self.captureSession startRunning];
        BOOL started = self.captureSession.isRunning;
        if (started) [self prepareObjectDetectorIfNeeded];
        dispatch_async(dispatch_get_main_queue(), ^{
            self.running = started;
            completion(started, started ? nil : @"The camera could not start.");
        });
    });
}

- (BOOL)configureCaptureSession:(NSError **)outError {
    if (self.captureSession) return YES;
    AVCaptureDevice *device = [AVCaptureDevice defaultDeviceWithMediaType:AVMediaTypeVideo];
    if (!device) {
        if (outError) *outError = [NSError errorWithDomain:@"FocusFloatCamera" code:1
                                                 userInfo:@{NSLocalizedDescriptionKey: @"No camera is available."}];
        return NO;
    }
    NSError *inputError = nil;
    AVCaptureDeviceInput *input = [AVCaptureDeviceInput deviceInputWithDevice:device error:&inputError];
    if (!input) {
        if (outError) *outError = inputError;
        return NO;
    }

    AVCaptureSession *session = [[AVCaptureSession alloc] init];
    [session beginConfiguration];
    if ([session canSetSessionPreset:AVCaptureSessionPreset640x480]) {
        session.sessionPreset = AVCaptureSessionPreset640x480;
    }
    if (![session canAddInput:input]) {
        [session commitConfiguration];
        if (outError) *outError = [NSError errorWithDomain:@"FocusFloatCamera" code:2
                                                 userInfo:@{NSLocalizedDescriptionKey: @"The camera could not be connected."}];
        return NO;
    }
    [session addInput:input];
    AVCaptureVideoDataOutput *output = [[AVCaptureVideoDataOutput alloc] init];
    output.alwaysDiscardsLateVideoFrames = YES;
    output.videoSettings = @{(NSString *)kCVPixelBufferPixelFormatTypeKey: @(kCVPixelFormatType_32BGRA)};
    [output setSampleBufferDelegate:self queue:self.videoQueue];
    if (![session canAddOutput:output]) {
        [session commitConfiguration];
        if (outError) *outError = [NSError errorWithDomain:@"FocusFloatCamera" code:3
                                                 userInfo:@{NSLocalizedDescriptionKey: @"Camera frames could not be read."}];
        return NO;
    }
    [session addOutput:output];
    [session commitConfiguration];
    self.videoOutput = output;
    self.captureSession = session;
    return YES;
}

- (void)prepareObjectDetectorIfNeeded {
    if (self.objectDetectionRequest || self.detectorPreparing) return;
    self.detectorPreparing = YES;
    [self notifyDetectorStatus:@"Loading local phone detection…"];
    NSURL *modelURL = [NSBundle.mainBundle URLForResource:@"YOLOv3FP16" withExtension:@"mlmodel"];
    if (!modelURL) {
        self.detectorPreparing = NO;
        [self notifyDetectorStatus:@"The local detection model is missing."];
        return;
    }
    NSError *error = nil;
    NSURL *compiledURL = [MLModel compileModelAtURL:modelURL error:&error];
    if (!compiledURL) {
        self.detectorPreparing = NO;
        [self notifyDetectorStatus:[NSString stringWithFormat:@"Model compile failed: %@", error.localizedDescription]];
        return;
    }
    MLModelConfiguration *configuration = [[MLModelConfiguration alloc] init];
    configuration.computeUnits = MLComputeUnitsAll;
    MLModel *model = [MLModel modelWithContentsOfURL:compiledURL configuration:configuration error:&error];
    VNCoreMLModel *visionModel = model ? [VNCoreMLModel modelForMLModel:model error:&error] : nil;
    if (!visionModel) {
        self.detectorPreparing = NO;
        [self notifyDetectorStatus:[NSString stringWithFormat:@"Model load failed: %@", error.localizedDescription]];
        return;
    }
    __weak typeof(self) weakSelf = self;
    VNCoreMLRequest *request = [[VNCoreMLRequest alloc] initWithModel:visionModel completionHandler:^(VNRequest *request, NSError *requestError) {
        typeof(self) self = weakSelf;
        if (!self) return;
        if (requestError) {
            [self notifyDetectorStatus:[NSString stringWithFormat:@"Detection failed: %@", requestError.localizedDescription]];
            return;
        }
        [self handleObjectDetectionResults:request.results ?: @[]];
    }];
    request.imageCropAndScaleOption = VNImageCropAndScaleOptionScaleFill;
    dispatch_async(self.videoQueue, ^{
        self.objectDetectionRequest = request;
        [self.phonePresenceTracker reset];
        self.lastPhoneConfidence = 0;
        self.lastPhoneBoundingBox = CGRectZero;
        self.lastInferenceAt = 0;
        self.detectorPreparing = NO;
        [self notifyDetectorStatus:@"Local detection · no phone"];
    });
}

- (void)captureOutput:(AVCaptureOutput *)output
didOutputSampleBuffer:(CMSampleBufferRef)sampleBuffer
       fromConnection:(AVCaptureConnection *)connection {
    VNCoreMLRequest *request = self.objectDetectionRequest;
    if (!request) return;
    NSTimeInterval now = NSDate.timeIntervalSinceReferenceDate;
    if (now - self.lastInferenceAt < 0.5) return;
    self.lastInferenceAt = now;
    CVPixelBufferRef pixelBuffer = CMSampleBufferGetImageBuffer(sampleBuffer);
    if (!pixelBuffer) return;
    VNImageRequestHandler *handler = [[VNImageRequestHandler alloc] initWithCVPixelBuffer:pixelBuffer
                                                                             orientation:kCGImagePropertyOrientationUp
                                                                                 options:@{}];
    NSError *error = nil;
    if (![handler performRequests:@[request] error:&error] && error) {
        [self notifyDetectorStatus:[NSString stringWithFormat:@"Detection failed: %@", error.localizedDescription]];
    }
}

- (void)handleObjectDetectionResults:(NSArray<VNObservation *> *)results {
    float bestConfidence = 0;
    CGRect bestBoundingBox = CGRectZero;
    for (VNObservation *result in results) {
        if (![result isKindOfClass:VNRecognizedObjectObservation.class]) continue;
        VNRecognizedObjectObservation *object = (VNRecognizedObjectObservation *)result;
        for (VNClassificationObservation *label in object.labels) {
            NSString *identifier = label.identifier.lowercaseString;
            BOOL isPhone = [identifier isEqualToString:@"cell phone"]
                || [identifier isEqualToString:@"mobile phone"]
                || [identifier isEqualToString:@"phone"];
            if (isPhone && label.confidence > bestConfidence) {
                bestConfidence = label.confidence;
                bestBoundingBox = object.boundingBox;
            }
        }
    }
    BOOL detected = bestConfidence >= 0.18f;
    if (detected) {
        self.lastPhoneConfidence = bestConfidence;
        self.lastPhoneBoundingBox = bestBoundingBox;
    }
    FocusPhonePresenceUpdate *presence =
        [self.phonePresenceTracker recordDetection:detected atTime:NSDate.timeIntervalSinceReferenceDate];
    if (!presence.recentlyVisible) {
        self.lastPhoneConfidence = 0;
        self.lastPhoneBoundingBox = CGRectZero;
    }
    dispatch_async(dispatch_get_main_queue(), ^{
        if (!self.isRunning) return;
        [self.delegate focusCameraController:self
                      didUpdatePhonePresence:presence.recentlyVisible
                                  confidence:presence.recentlyVisible ? self.lastPhoneConfidence : 0
                                    evidence:presence.evidence
                           sustainedDuration:presence.sustainedDuration
                      interventionTriggered:presence.interventionTriggeredForPresence
                    shouldReportIntervention:presence.shouldIntervene
                                 boundingBox:presence.recentlyVisible ? self.lastPhoneBoundingBox : CGRectZero];
    });
}

- (void)notifyDetectorStatus:(NSString *)status {
    dispatch_async(dispatch_get_main_queue(), ^{
        [self.delegate focusCameraController:self didUpdateDetectorStatus:status];
    });
}

- (void)stop {
    @synchronized (self) {
        self.requestGeneration += 1;
    }
    AVCaptureSession *session = self.captureSession;
    self.running = NO;
    dispatch_async(self.videoQueue, ^{
        [self.phonePresenceTracker reset];
        self.lastPhoneConfidence = 0;
        self.lastPhoneBoundingBox = CGRectZero;
        self.lastInferenceAt = 0;
    });
    if (!session) return;
    dispatch_async(self.sessionQueue, ^{
        if (session.isRunning) [session stopRunning];
    });
}

@end
