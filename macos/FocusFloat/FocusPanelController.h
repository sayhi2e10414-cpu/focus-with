#import <Cocoa/Cocoa.h>

NS_ASSUME_NONNULL_BEGIN

@protocol FocusPanelControllerDelegate <NSObject>
- (void)focusPanelDidRequestPrimaryAction;
- (void)focusPanelDidRequestCompletion;
- (void)focusPanelDidRequestOpenWeb;
@end

@interface FocusPanelController : NSWindowController
@property(nonatomic, weak, nullable) id<FocusPanelControllerDelegate> delegate;
- (void)showPanel:(BOOL)activate;
- (void)updateWithSession:(nullable NSDictionary *)session title:(nullable NSString *)title message:(nullable NSString *)message;
- (void)updateTimer:(NSString *)text;
@end

NS_ASSUME_NONNULL_END
