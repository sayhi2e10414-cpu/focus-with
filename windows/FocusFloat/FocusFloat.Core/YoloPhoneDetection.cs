namespace FocusFloat.Core;

public readonly record struct DetectionBox(float Top, float Left, float Bottom, float Right);

public sealed record PhoneDetection(float Confidence, DetectionBox Box);

public static class YoloPhoneDetection
{
    public const int CocoCellPhoneClassIndex = 67;

    public static PhoneDetection? FindBest(
        ReadOnlySpan<float> boxes,
        int boxCount,
        ReadOnlySpan<float> scores,
        ReadOnlySpan<int> selectedIndices,
        float minimumConfidence = 0.18f)
    {
        PhoneDetection? best = null;
        for (var offset = 0; offset + 2 < selectedIndices.Length; offset += 3)
        {
            var batch = selectedIndices[offset];
            var classIndex = selectedIndices[offset + 1];
            var boxIndex = selectedIndices[offset + 2];
            if (batch != 0 || classIndex != CocoCellPhoneClassIndex || boxIndex < 0 || boxIndex >= boxCount)
            {
                continue;
            }

            var scoreOffset = (classIndex * boxCount) + boxIndex;
            if (scoreOffset >= scores.Length)
            {
                continue;
            }
            var confidence = scores[scoreOffset];
            var boxOffset = boxIndex * 4;
            if (confidence < minimumConfidence || boxOffset + 3 >= boxes.Length)
            {
                continue;
            }

            var detection = new PhoneDetection(
                confidence,
                new DetectionBox(
                    boxes[boxOffset],
                    boxes[boxOffset + 1],
                    boxes[boxOffset + 2],
                    boxes[boxOffset + 3]));
            if (best is null || detection.Confidence > best.Confidence)
            {
                best = detection;
            }
        }
        return best;
    }
}
