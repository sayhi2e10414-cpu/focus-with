#import <CoreML/CoreML.h>
#import <Foundation/Foundation.h>
#import <Vision/Vision.h>

static void FocusAssert(BOOL condition, NSString *message) {
    if (condition) return;
    NSLog(@"FocusVisionModelTests failed: %@", message);
    exit(1);
}

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        FocusAssert(argc == 2, @"expected one .mlmodel path");
        NSString *path = [NSString stringWithUTF8String:argv[1]];
        NSError *error = nil;
        NSURL *compiled = [MLModel compileModelAtURL:[NSURL fileURLWithPath:path] error:&error];
        FocusAssert(compiled != nil, error.localizedDescription ?: @"model compilation failed");
        MLModel *model = [MLModel modelWithContentsOfURL:compiled error:&error];
        FocusAssert(model != nil, error.localizedDescription ?: @"model loading failed");
        VNCoreMLModel *visionModel = [VNCoreMLModel modelForMLModel:model error:&error];
        FocusAssert(visionModel != nil, error.localizedDescription ?: @"Vision model creation failed");
        FocusAssert(model.modelDescription.inputDescriptionsByName.count > 0, @"model has no inputs");
        FocusAssert(model.modelDescription.outputDescriptionsByName.count > 0, @"model has no outputs");
        NSLog(@"FocusVisionModelTests passed");
    }
    return 0;
}
