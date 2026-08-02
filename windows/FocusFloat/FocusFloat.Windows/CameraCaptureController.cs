using System.Diagnostics;
using FocusFloat.Core;
using Windows.Graphics.Imaging;
using Windows.Media.Capture;
using Windows.Media.Capture.Frames;
using Windows.Media.Core;
using Windows.Media.MediaProperties;
using Windows.Media.Playback;

namespace FocusFloat.Windows;

internal sealed record PhonePresenceEvent(PhonePresenceUpdate Presence, PhoneDetection? Detection);

internal sealed class CameraCaptureController : IAsyncDisposable
{
    private readonly PhonePresenceTracker _tracker = new();
    private MediaCapture? _capture;
    private MediaFrameReader? _reader;
    private YoloV3Detector? _detector;
    private long _lastInferenceTimestamp;
    private int _inferenceInFlight;

    public CameraCaptureController()
    {
        MediaPlayer = new MediaPlayer { RealTimePlayback = true, AutoPlay = true };
    }

    public MediaPlayer MediaPlayer { get; }
    public bool IsRunning { get; private set; }
    public event EventHandler<string>? StatusChanged;
    public event EventHandler<PhonePresenceEvent>? PhonePresenceChanged;

    public async Task StartAsync(
        IProgress<double>? modelProgress = null,
        CancellationToken cancellationToken = default)
    {
        if (IsRunning)
        {
            return;
        }
        StatusChanged?.Invoke(this, "Downloading/verifying the local YOLOv3 model…");
        var modelPath = await ModelManager.EnsureModelAsync(modelProgress, cancellationToken);
        _detector = new YoloV3Detector(modelPath);

        var groups = await MediaFrameSourceGroup.FindAllAsync();
        var group = groups.FirstOrDefault(candidate =>
            candidate.SourceInfos.Any(info => info.SourceKind == MediaFrameSourceKind.Color));
        if (group is null)
        {
            throw new InvalidOperationException("No color camera is available.");
        }

        _capture = new MediaCapture();
        await _capture.InitializeAsync(new MediaCaptureInitializationSettings
        {
            SourceGroup = group,
            SharingMode = MediaCaptureSharingMode.SharedReadOnly,
            StreamingCaptureMode = StreamingCaptureMode.Video,
            MemoryPreference = MediaCaptureMemoryPreference.Cpu,
        });
        var source = _capture.FrameSources.Values.First(item => item.Info.SourceKind == MediaFrameSourceKind.Color);
        MediaPlayer.Source = MediaSource.CreateFromMediaFrameSource(source);
        MediaPlayer.Play();
        _reader = await _capture.CreateFrameReaderAsync(source, MediaEncodingSubtypes.Bgra8);
        _reader.FrameArrived += Reader_FrameArrived;
        var status = await _reader.StartAsync();
        if (status != MediaFrameReaderStartStatus.Success)
        {
            throw new InvalidOperationException($"Camera frame reader failed to start: {status}.");
        }
        IsRunning = true;
        StatusChanged?.Invoke(this, "Local detection · no phone");
    }

    public async Task StopAsync()
    {
        IsRunning = false;
        if (_reader is not null)
        {
            _reader.FrameArrived -= Reader_FrameArrived;
            await _reader.StopAsync();
            _reader.Dispose();
            _reader = null;
        }
        MediaPlayer.Pause();
        MediaPlayer.Source = null;
        _capture?.Dispose();
        _capture = null;
        _detector?.Dispose();
        _detector = null;
        _tracker.Reset();
        StatusChanged?.Invoke(this, "Camera companion is off.");
    }

    private void Reader_FrameArrived(MediaFrameReader sender, MediaFrameArrivedEventArgs args)
    {
        if (!IsRunning || _detector is null || Interlocked.CompareExchange(ref _inferenceInFlight, 1, 0) != 0)
        {
            return;
        }
        var nowTicks = Stopwatch.GetTimestamp();
        if (Stopwatch.GetElapsedTime(_lastInferenceTimestamp, nowTicks) < TimeSpan.FromMilliseconds(500))
        {
            Interlocked.Exchange(ref _inferenceInFlight, 0);
            return;
        }
        _lastInferenceTimestamp = nowTicks;
        try
        {
            using var frame = sender.TryAcquireLatestFrame();
            var sourceBitmap = frame?.VideoMediaFrame?.SoftwareBitmap;
            if (sourceBitmap is null)
            {
                return;
            }
            SoftwareBitmap? converted = null;
            try
            {
                var bitmap = sourceBitmap;
                if (bitmap.BitmapPixelFormat != BitmapPixelFormat.Bgra8 ||
                    bitmap.BitmapAlphaMode != BitmapAlphaMode.Ignore)
                {
                    converted = SoftwareBitmap.Convert(bitmap, BitmapPixelFormat.Bgra8, BitmapAlphaMode.Ignore);
                    bitmap = converted;
                }
                var detection = _detector.Detect(bitmap);
                var presence = _tracker.RecordDetection(detection is not null, DateTimeOffset.UtcNow);
                PhonePresenceChanged?.Invoke(this, new PhonePresenceEvent(presence, detection));
            }
            finally
            {
                converted?.Dispose();
            }
        }
        catch (Exception error)
        {
            StatusChanged?.Invoke(this, $"Local detection error: {error.Message}");
        }
        finally
        {
            Interlocked.Exchange(ref _inferenceInFlight, 0);
        }
    }

    public async ValueTask DisposeAsync()
    {
        await StopAsync();
        MediaPlayer.Dispose();
    }
}
