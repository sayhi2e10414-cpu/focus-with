using System.Security.Cryptography;

namespace FocusFloat.Windows;

internal static class ModelManager
{
    public const string FileName = "yolov3-10.onnx";
    public const string Sha256 = "1f4613c3d04416dfd2c1960b8737aa5292994238dfecbe9c1ee7147e9a92439f";
    public static readonly Uri DownloadUri = new(
        "https://github.com/onnx/models/raw/refs/heads/main/validated/vision/object_detection_segmentation/yolov3/model/yolov3-10.onnx");

    public static async Task<string> EnsureModelAsync(
        IProgress<double>? progress = null,
        CancellationToken cancellationToken = default)
    {
        var directory = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "FocusWith",
            "FocusFloat",
            "Models");
        Directory.CreateDirectory(directory);
        var destination = Path.Combine(directory, FileName);
        if (File.Exists(destination) && await HasExpectedHashAsync(destination, cancellationToken))
        {
            progress?.Report(1);
            return destination;
        }

        var temporary = destination + ".download";
        try
        {
            using var http = new HttpClient { Timeout = TimeSpan.FromMinutes(15) };
            using var response = await http.GetAsync(
                DownloadUri,
                HttpCompletionOption.ResponseHeadersRead,
                cancellationToken);
            response.EnsureSuccessStatusCode();
            var length = response.Content.Headers.ContentLength;
            await using var input = await response.Content.ReadAsStreamAsync(cancellationToken);
            await using var output = new FileStream(
                temporary,
                FileMode.Create,
                FileAccess.Write,
                FileShare.None,
                1024 * 1024,
                useAsync: true);
            var buffer = new byte[1024 * 1024];
            long written = 0;
            while (true)
            {
                var count = await input.ReadAsync(buffer, cancellationToken);
                if (count == 0)
                {
                    break;
                }
                await output.WriteAsync(buffer.AsMemory(0, count), cancellationToken);
                written += count;
                if (length > 0)
                {
                    progress?.Report((double)written / length.Value);
                }
            }
            await output.FlushAsync(cancellationToken);
            if (!await HasExpectedHashAsync(temporary, cancellationToken))
            {
                throw new InvalidDataException("The downloaded YOLOv3 model failed SHA-256 verification.");
            }
            File.Move(temporary, destination, overwrite: true);
            progress?.Report(1);
            return destination;
        }
        finally
        {
            if (File.Exists(temporary))
            {
                File.Delete(temporary);
            }
        }
    }

    private static async Task<bool> HasExpectedHashAsync(string path, CancellationToken cancellationToken)
    {
        await using var stream = File.OpenRead(path);
        var hash = await SHA256.HashDataAsync(stream, cancellationToken);
        return Convert.ToHexString(hash).Equals(Sha256, StringComparison.OrdinalIgnoreCase);
    }
}
