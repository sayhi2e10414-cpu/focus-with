#import <Foundation/Foundation.h>

NS_ASSUME_NONNULL_BEGIN

@class FocusAPIClient;

@protocol FocusAPIClientDelegate <NSObject>
- (void)focusAPIClient:(FocusAPIClient *)client didUpdateSession:(nullable NSDictionary *)session title:(nullable NSString *)title;
- (void)focusAPIClient:(FocusAPIClient *)client didFailWithMessage:(NSString *)message;
@end

@interface FocusAPIClient : NSObject
@property(nonatomic, weak, nullable) id<FocusAPIClientDelegate> delegate;
@property(nonatomic, copy, readonly, nullable) NSDictionary *currentSession;
@property(nonatomic, copy, readonly, nullable) NSString *currentTitle;
- (instancetype)initWithBaseURL:(NSURL *)baseURL token:(NSString *)token;
- (void)startPolling;
- (void)stopPolling;
- (void)refresh;
- (void)performAction:(NSString *)action completion:(void (^_Nullable)(BOOL success, NSString *_Nullable message))completion;
+ (NSString *)formattedDisplayForSession:(NSDictionary *)session atDate:(NSDate *)date;
@end

NS_ASSUME_NONNULL_END
