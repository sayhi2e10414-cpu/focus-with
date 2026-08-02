#import "FocusAPIClient.h"

static NSString *FocusISO8601FromDate(NSDate *date) {
    static NSISO8601DateFormatter *formatter;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{
        formatter = [[NSISO8601DateFormatter alloc] init];
        formatter.formatOptions = NSISO8601DateFormatWithInternetDateTime;
    });
    return [formatter stringFromDate:date];
}

@interface FocusAPIClient ()
@property(nonatomic, strong) NSURL *baseURL;
@property(nonatomic, copy) NSString *token;
@property(nonatomic, strong) NSURLSession *urlSession;
@property(nonatomic, strong, nullable) NSTimer *pollTimer;
@property(nonatomic, assign) BOOL requestInFlight;
@property(nonatomic, copy, readwrite, nullable) NSDictionary *currentSession;
@property(nonatomic, copy, readwrite, nullable) NSString *currentTitle;
- (void)submitCameraPhoneEventBody:(NSData *)body
                           attempt:(NSInteger)attempt
                        completion:(void (^)(BOOL accepted, NSString *_Nullable message))completion;
@end

@implementation FocusAPIClient

- (instancetype)initWithBaseURL:(NSURL *)baseURL token:(NSString *)token {
    if ((self = [super init])) {
        _baseURL = baseURL;
        _token = [token copy];
        NSURLSessionConfiguration *config = NSURLSessionConfiguration.ephemeralSessionConfiguration;
        config.timeoutIntervalForRequest = 15;
        _urlSession = [NSURLSession sessionWithConfiguration:config];
    }
    return self;
}

- (void)dealloc { [self stopPolling]; [self.urlSession invalidateAndCancel]; }

- (NSMutableURLRequest *)requestForPath:(NSString *)path method:(NSString *)method {
    NSMutableURLRequest *request = [NSMutableURLRequest requestWithURL:[NSURL URLWithString:path relativeToURL:self.baseURL]];
    request.HTTPMethod = method;
    [request setValue:self.token forHTTPHeaderField:@"X-Focus-Token"];
    [request setValue:@"application/json" forHTTPHeaderField:@"Accept"];
    return request;
}

- (void)startPolling {
    [self stopPolling];
    [self refresh];
    self.pollTimer = [NSTimer scheduledTimerWithTimeInterval:4 target:self selector:@selector(refresh) userInfo:nil repeats:YES];
    self.pollTimer.tolerance = 0.5;
}

- (void)stopPolling { [self.pollTimer invalidate]; self.pollTimer = nil; }

- (void)refresh {
    if (self.requestInFlight) return;
    self.requestInFlight = YES;
    __weak typeof(self) weakSelf = self;
    [[self.urlSession dataTaskWithRequest:[self requestForPath:@"api/bootstrap" method:@"GET"] completionHandler:^(NSData *data, NSURLResponse *response, NSError *error) {
        dispatch_async(dispatch_get_main_queue(), ^{
            typeof(self) self = weakSelf;
            if (!self) return;
            self.requestInFlight = NO;
            NSHTTPURLResponse *http = (NSHTTPURLResponse *)response;
            if (error || http.statusCode < 200 || http.statusCode >= 300) {
                NSString *message = http.statusCode == 401 ? @"The Focus API token is invalid." : @"Focus is unavailable. Retrying automatically.";
                [self.delegate focusAPIClient:self didFailWithMessage:message];
                return;
            }
            NSDictionary *root = [NSJSONSerialization JSONObjectWithData:data options:0 error:nil];
            NSDictionary *payload = [root[@"data"] isKindOfClass:NSDictionary.class] ? root[@"data"] : nil;
            if (!payload) {
                [self.delegate focusAPIClient:self didFailWithMessage:@"Focus returned an unreadable response."];
                return;
            }
            NSDictionary *rawSession = [payload[@"active_session"] isKindOfClass:NSDictionary.class] ? payload[@"active_session"] : nil;
            NSMutableDictionary *session = rawSession ? [rawSession mutableCopy] : nil;
            if (session) session[@"_received_at"] = @(NSDate.date.timeIntervalSince1970);
            NSString *title = nil;
            NSNumber *taskID = [session[@"task_id"] isKindOfClass:NSNumber.class] ? session[@"task_id"] : nil;
            for (NSDictionary *task in payload[@"tasks"]) {
                if (taskID && [task[@"id"] isEqual:taskID]) { title = task[@"title"]; break; }
            }
            if (!title.length) title = session[@"title"] ?: session[@"goal"];
            self.currentSession = session;
            self.currentTitle = title;
            [self.delegate focusAPIClient:self didUpdateSession:session title:title];
        });
    }] resume];
}

- (void)performAction:(NSString *)action completion:(void (^)(BOOL, NSString *_Nullable))completion {
    NSNumber *sessionID = [self.currentSession[@"id"] isKindOfClass:NSNumber.class] ? self.currentSession[@"id"] : nil;
    if (!sessionID) { if (completion) completion(NO, @"There is no active session."); return; }
    NSDictionary *payload = @{@"action": action, @"note": NSNull.null};
    NSData *body = [NSJSONSerialization dataWithJSONObject:payload options:0 error:nil];
    NSString *path = [NSString stringWithFormat:@"api/sessions/%@", sessionID];
    NSMutableURLRequest *request = [self requestForPath:path method:@"PUT"];
    request.HTTPBody = body;
    [request setValue:@"application/json" forHTTPHeaderField:@"Content-Type"];
    __weak typeof(self) weakSelf = self;
    [[self.urlSession dataTaskWithRequest:request completionHandler:^(NSData *data, NSURLResponse *response, NSError *error) {
        dispatch_async(dispatch_get_main_queue(), ^{
            typeof(self) self = weakSelf;
            NSHTTPURLResponse *http = (NSHTTPURLResponse *)response;
            BOOL success = !error && http.statusCode >= 200 && http.statusCode < 300;
            if (completion) completion(success, success ? nil : @"Focus did not accept that action.");
            if (success) [self refresh];
        });
    }] resume];
}

+ (NSDictionary *)cameraPhoneEventPayloadWithEventID:(NSString *)eventID
                                     durationSeconds:(NSInteger)durationSeconds
                                          detectedAt:(NSDate *)detectedAt {
    return @{
        @"event_id": eventID,
        @"duration_seconds": @(MAX(10, MIN(300, durationSeconds))),
        @"detected_at": FocusISO8601FromDate(detectedAt),
        @"source": @"macos_focus_float",
    };
}

- (void)reportCameraPhoneDistractionWithEventID:(NSString *)eventID
                               durationSeconds:(NSInteger)durationSeconds
                                    detectedAt:(NSDate *)detectedAt
                                    completion:(void (^)(BOOL, NSString *_Nullable))completion {
    NSDictionary *payload = [FocusAPIClient cameraPhoneEventPayloadWithEventID:eventID
                                                               durationSeconds:durationSeconds
                                                                    detectedAt:detectedAt];
    NSData *body = [NSJSONSerialization dataWithJSONObject:payload options:0 error:nil];
    if (!body) {
        if (completion) completion(NO, @"Could not prepare the camera event.");
        return;
    }
    [self submitCameraPhoneEventBody:body attempt:0 completion:completion];
}

- (void)submitCameraPhoneEventBody:(NSData *)body
                           attempt:(NSInteger)attempt
                        completion:(void (^)(BOOL, NSString *_Nullable))completion {
    NSMutableURLRequest *request = [self requestForPath:@"api/vision-events/phone" method:@"POST"];
    request.HTTPBody = body;
    [request setValue:@"application/json" forHTTPHeaderField:@"Content-Type"];
    __weak typeof(self) weakSelf = self;
    [[self.urlSession dataTaskWithRequest:request completionHandler:^(NSData *data, NSURLResponse *response, NSError *error) {
        typeof(self) self = weakSelf;
        if (!self) return;
        NSHTTPURLResponse *http = (NSHTTPURLResponse *)response;
        BOOL shouldRetry = error != nil || http.statusCode >= 500;
        if (shouldRetry && attempt < 2) {
            NSTimeInterval delay = attempt == 0 ? 2.0 : 5.0;
            dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(delay * NSEC_PER_SEC)),
                           dispatch_get_main_queue(), ^{
                [self submitCameraPhoneEventBody:body attempt:attempt + 1 completion:completion];
            });
            return;
        }
        dispatch_async(dispatch_get_main_queue(), ^{
            if (error) {
                if (completion) completion(NO, @"Focus did not receive this reminder.");
                return;
            }
            if (http.statusCode < 200 || http.statusCode >= 300) {
                if (completion) completion(NO, [NSString stringWithFormat:@"Camera event failed (%ld).", (long)http.statusCode]);
                return;
            }
            NSDictionary *root = data.length ? [NSJSONSerialization JSONObjectWithData:data options:0 error:nil] : nil;
            NSDictionary *result = [root[@"data"] isKindOfClass:NSDictionary.class] ? root[@"data"] : nil;
            if (!result) {
                if (completion) completion(NO, @"Focus returned an unreadable camera response.");
                return;
            }
            BOOL accepted = [result[@"accepted"] boolValue];
            NSString *reason = [result[@"reason"] isKindOfClass:NSString.class] ? result[@"reason"] : @"";
            NSString *message = nil;
            if (!accepted) {
                message = [reason isEqualToString:@"cooldown"]
                    ? @"Server reminder cooldown is active."
                    : @"No running focus session; nothing was sent.";
            }
            if (completion) completion(accepted, message);
        });
    }] resume];
}

+ (NSString *)formattedDisplayForSession:(NSDictionary *)session atDate:(NSDate *)date {
    double elapsed = [session[@"elapsed_seconds"] doubleValue];
    double planned = [session[@"planned_minutes"] doubleValue] * 60.0;
    NSNumber *receivedAt = session[@"_received_at"];
    if ([session[@"status"] isEqual:@"running"] && receivedAt) elapsed += MAX(0, date.timeIntervalSince1970 - receivedAt.doubleValue);
    NSInteger seconds = (NSInteger)floor(planned > 0 ? MAX(0, planned - elapsed) : MAX(0, elapsed));
    NSInteger hours = seconds / 3600, minutes = (seconds % 3600) / 60, remainder = seconds % 60;
    return hours ? [NSString stringWithFormat:@"%ld:%02ld:%02ld", hours, minutes, remainder] : [NSString stringWithFormat:@"%02ld:%02ld", minutes, remainder];
}

@end
