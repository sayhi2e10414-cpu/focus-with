#import "FocusAPIClient.h"

@interface FocusAPIClient ()
@property(nonatomic, strong) NSURL *baseURL;
@property(nonatomic, copy) NSString *token;
@property(nonatomic, strong) NSURLSession *urlSession;
@property(nonatomic, strong, nullable) NSTimer *pollTimer;
@property(nonatomic, assign) BOOL requestInFlight;
@property(nonatomic, copy, readwrite, nullable) NSDictionary *currentSession;
@property(nonatomic, copy, readwrite, nullable) NSString *currentTitle;
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
