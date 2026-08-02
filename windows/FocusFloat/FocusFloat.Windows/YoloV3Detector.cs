using FocusFloat.Core;
using Microsoft.ML.OnnxRuntime;
using Microsoft.ML.OnnxRuntime.Tensors;
using Windows.Graphics.Imaging;

namespace FocusFloat.Windows;

internal sealed class YoloV3Detector : IDisposable
{
    private readonly InferenceSession _session;

    public YoloV3Detector(string modelPath)
    {
        var options = new SessionOptions
        {
            GraphOptimizationLevel = GraphOptimizationLevel.ORT_ENABLE_ALL,
            IntraOpNumThreads = Math.Max(1, Environment.ProcessorCount / 2),
        };
        _session = new InferenceSession(modelPath, options);
    }

    public PhoneDetection? Detect(SoftwareBitmap bitmap)
    {
        var image = SoftwareBitmapTensorizer.Create(bitmap);
        var shape = new DenseTensor<float>([1, 2]);
        shape[0, 0] = bitmap.PixelHeight;
        shape[0, 1] = bitmap.PixelWidth;
        var inputs = new[]
        {
            NamedOnnxValue.CreateFromTensor("input_1", image),
            NamedOnnxValue.CreateFromTensor("image_shape", shape),
        };
        using var results = _session.Run(inputs);
        var boxesTensor = results.First(item => item.Name == "yolonms_layer_1/ExpandDims_1:0").AsTensor<float>();
        var scoresTensor = results.First(item => item.Name == "yolonms_layer_1/ExpandDims_3:0").AsTensor<float>();
        var indicesTensor = results.First(item => item.Name == "yolonms_layer_1/concat_2:0").AsTensor<int>();
        var boxCount = boxesTensor.Dimensions[1];
        var detection = YoloPhoneDetection.FindBest(
            boxesTensor.ToArray(),
            boxCount,
            scoresTensor.ToArray(),
            indicesTensor.ToArray());
        if (detection is null)
        {
            return null;
        }
        return detection with
        {
            Box = new DetectionBox(
                Math.Clamp(detection.Box.Top / bitmap.PixelHeight, 0, 1),
                Math.Clamp(detection.Box.Left / bitmap.PixelWidth, 0, 1),
                Math.Clamp(detection.Box.Bottom / bitmap.PixelHeight, 0, 1),
                Math.Clamp(detection.Box.Right / bitmap.PixelWidth, 0, 1)),
        };
    }

    public void Dispose() => _session.Dispose();
}
