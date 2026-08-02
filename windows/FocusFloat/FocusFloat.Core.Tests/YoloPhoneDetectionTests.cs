using FocusFloat.Core;

namespace FocusFloat.Core.Tests;

public sealed class YoloPhoneDetectionTests
{
    [Fact]
    public void SelectsTheHighestConfidenceCellPhoneOnly()
    {
        const int boxCount = 3;
        var boxes = new float[]
        {
            .1f, .2f, .3f, .4f,
            .2f, .3f, .6f, .7f,
            .3f, .4f, .8f, .9f,
        };
        var scores = new float[80 * boxCount];
        scores[(YoloPhoneDetection.CocoCellPhoneClassIndex * boxCount) + 1] = .42f;
        scores[(YoloPhoneDetection.CocoCellPhoneClassIndex * boxCount) + 2] = .71f;
        var indices = new int[]
        {
            0, 0, 0,
            0, YoloPhoneDetection.CocoCellPhoneClassIndex, 1,
            0, YoloPhoneDetection.CocoCellPhoneClassIndex, 2,
        };

        var result = YoloPhoneDetection.FindBest(boxes, boxCount, scores, indices);

        Assert.NotNull(result);
        Assert.Equal(.71f, result.Confidence);
        Assert.Equal(.4f, result.Box.Left);
    }
}
