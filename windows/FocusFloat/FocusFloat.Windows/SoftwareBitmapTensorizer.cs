using System.Runtime.InteropServices;
using Microsoft.ML.OnnxRuntime.Tensors;
using Windows.Graphics.Imaging;

namespace FocusFloat.Windows;

[ComImport]
[Guid("5B0D3235-4DBA-4D44-865E-8F1D0E4FD04D")]
[InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
internal unsafe interface IMemoryBufferByteAccess
{
    void GetBuffer(out byte* buffer, out uint capacity);
}

internal static class SoftwareBitmapTensorizer
{
    public const int ModelSize = 416;

    public static unsafe DenseTensor<float> Create(SoftwareBitmap bitmap)
    {
        if (bitmap.BitmapPixelFormat != BitmapPixelFormat.Bgra8)
        {
            throw new ArgumentException("SoftwareBitmap must be Bgra8.", nameof(bitmap));
        }

        var tensor = new DenseTensor<float>([1, 3, ModelSize, ModelSize]);
        tensor.Buffer.Span.Fill(128f / 255f);
        var scale = Math.Min((double)ModelSize / bitmap.PixelWidth, (double)ModelSize / bitmap.PixelHeight);
        var resizedWidth = Math.Max(1, (int)Math.Round(bitmap.PixelWidth * scale));
        var resizedHeight = Math.Max(1, (int)Math.Round(bitmap.PixelHeight * scale));
        var offsetX = (ModelSize - resizedWidth) / 2;
        var offsetY = (ModelSize - resizedHeight) / 2;
        var planeSize = ModelSize * ModelSize;

        using var buffer = bitmap.LockBuffer(BitmapBufferAccessMode.Read);
        using var reference = buffer.CreateReference();
        ((IMemoryBufferByteAccess)reference).GetBuffer(out var bytes, out _);
        var plane = buffer.GetPlaneDescription(0);
        for (var targetY = 0; targetY < resizedHeight; targetY++)
        {
            var sourceY = Math.Clamp((int)(targetY / scale), 0, bitmap.PixelHeight - 1);
            for (var targetX = 0; targetX < resizedWidth; targetX++)
            {
                var sourceX = Math.Clamp((int)(targetX / scale), 0, bitmap.PixelWidth - 1);
                var sourceOffset = plane.StartIndex + (sourceY * plane.Stride) + (sourceX * 4);
                var targetOffset = ((targetY + offsetY) * ModelSize) + targetX + offsetX;
                tensor.Buffer.Span[targetOffset] = bytes[sourceOffset + 2] / 255f;
                tensor.Buffer.Span[planeSize + targetOffset] = bytes[sourceOffset + 1] / 255f;
                tensor.Buffer.Span[(planeSize * 2) + targetOffset] = bytes[sourceOffset] / 255f;
            }
        }
        return tensor;
    }
}
