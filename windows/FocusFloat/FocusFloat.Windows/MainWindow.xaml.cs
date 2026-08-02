using System.Diagnostics;
using FocusFloat.Core;
using Microsoft.UI.Windowing;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Media;
using Windows.Graphics;

namespace FocusFloat.Windows;

public sealed partial class MainWindow : Window
{
    private readonly ConnectionStore _connectionStore = new();
    private readonly CameraCaptureController _camera = new();
    private readonly DispatcherTimer _pollTimer = new() { Interval = TimeSpan.FromSeconds(4) };
    private readonly DispatcherTimer _displayTimer = new() { Interval = TimeSpan.FromSeconds(1) };
    private FocusApiClient? _api;
    private FocusSessionSnapshot? _session;
    private DateTimeOffset _snapshotReceivedAt;
    private Uri? _serverUri;

    public MainWindow()
    {
        InitializeComponent();
        Title = "FocusFloat · Windows preview";
        ConfigureWindow();
        CameraPreview.SetMediaPlayer(_camera.MediaPlayer);
        _camera.StatusChanged += Camera_StatusChanged;
        _camera.PhonePresenceChanged += Camera_PhonePresenceChanged;
        _pollTimer.Tick += async (_, _) => await RefreshSnapshotAsync();
        _displayTimer.Tick += (_, _) => UpdateTimer();
        _displayTimer.Start();
        Closed += MainWindow_Closed;
        _ = RestoreConnectionAsync();
    }

    private void ConfigureWindow()
    {
        var windowHandle = WinRT.Interop.WindowNative.GetWindowHandle(this);
        var windowId = Microsoft.UI.Win32Interop.GetWindowIdFromWindow(windowHandle);
        var appWindow = AppWindow.GetFromWindowId(windowId);
        appWindow.Resize(new SizeInt32(430, 600));
        if (appWindow.Presenter is OverlappedPresenter presenter)
        {
            presenter.IsAlwaysOnTop = true;
            presenter.IsMaximizable = false;
        }
    }

    private async Task RestoreConnectionAsync()
    {
        _serverUri = await _connectionStore.LoadServerUrlAsync() ?? new Uri("http://127.0.0.1:8765/");
        ServerUrlBox.Text = _serverUri.ToString();
        var token = _connectionStore.LoadToken();
        if (!string.IsNullOrWhiteSpace(token))
        {
            TokenBox.Password = token;
            await ConnectAsync(save: false);
        }
    }

    private async void ConnectButton_Click(object sender, RoutedEventArgs e)
    {
        await ConnectAsync(save: true);
    }

    private async Task ConnectAsync(bool save)
    {
        ConnectButton.IsEnabled = false;
        try
        {
            if (!Uri.TryCreate(ServerUrlBox.Text.Trim(), UriKind.Absolute, out var uri) ||
                uri.Scheme is not ("http" or "https"))
            {
                throw new InvalidOperationException("Enter an absolute http or https FocusWith URL.");
            }
            if (string.IsNullOrWhiteSpace(TokenBox.Password))
            {
                throw new InvalidOperationException("Enter the Focus API token.");
            }
            _api?.Dispose();
            _api = new FocusApiClient(uri, TokenBox.Password);
            _serverUri = uri;
            if (save)
            {
                await _connectionStore.SaveAsync(uri, TokenBox.Password);
            }
            await RefreshSnapshotAsync();
            _pollTimer.Start();
            SessionStatus.Text = "Connected. Frames remain local.";
        }
        catch (Exception error)
        {
            SessionStatus.Text = error.Message;
            _pollTimer.Stop();
        }
        finally
        {
            ConnectButton.IsEnabled = true;
        }
    }

    private async Task RefreshSnapshotAsync()
    {
        if (_api is null)
        {
            return;
        }
        try
        {
            var snapshot = await _api.GetSnapshotAsync();
            _session = snapshot.ActiveSession;
            _snapshotReceivedAt = DateTimeOffset.UtcNow;
            SessionTitle.Text = _session?.Title ?? "No active focus";
            PrimaryButton.IsEnabled = _session is not null;
            EndButton.IsEnabled = _session is not null;
            PrimaryButton.Content = _session?.Status == "paused" ? "Resume" : "Pause";
            UpdateTimer();
        }
        catch (Exception error)
        {
            SessionStatus.Text = $"FocusWith unavailable: {error.Message}";
        }
    }

    private void UpdateTimer()
    {
        if (_session is null)
        {
            TimerText.Text = "00:00";
            return;
        }
        var elapsed = _session.ElapsedSeconds;
        if (_session.Status == "running")
        {
            elapsed += Math.Max(0, (int)(DateTimeOffset.UtcNow - _snapshotReceivedAt).TotalSeconds);
        }
        var seconds = _session.PlannedMinutes is > 0
            ? Math.Max(0, (_session.PlannedMinutes.Value * 60) - elapsed)
            : Math.Max(0, elapsed);
        TimerText.Text = seconds >= 3600
            ? $"{seconds / 3600}:{(seconds % 3600) / 60:00}:{seconds % 60:00}"
            : $"{seconds / 60:00}:{seconds % 60:00}";
    }

    private async void PrimaryButton_Click(object sender, RoutedEventArgs e)
    {
        if (_api is null || _session is null)
        {
            return;
        }
        PrimaryButton.IsEnabled = false;
        try
        {
            await _api.ChangeSessionAsync(_session.Id, _session.Status == "paused" ? "resume" : "pause");
            await RefreshSnapshotAsync();
        }
        catch (Exception error)
        {
            SessionStatus.Text = error.Message;
        }
        finally
        {
            PrimaryButton.IsEnabled = true;
        }
    }

    private async void EndButton_Click(object sender, RoutedEventArgs e)
    {
        if (_api is null || _session is null)
        {
            return;
        }
        EndButton.IsEnabled = false;
        try
        {
            await _api.ChangeSessionAsync(_session.Id, "complete");
            await RefreshSnapshotAsync();
        }
        catch (Exception error)
        {
            SessionStatus.Text = error.Message;
        }
        finally
        {
            EndButton.IsEnabled = true;
        }
    }

    private async void CameraButton_Click(object sender, RoutedEventArgs e)
    {
        CameraButton.IsEnabled = false;
        try
        {
            if (_camera.IsRunning)
            {
                await _camera.StopAsync();
                CameraButton.Content = "Start camera";
                CameraIndicator.Text = "● CAMERA OFF";
                CameraIndicator.Foreground = new SolidColorBrush(Microsoft.UI.Colors.Gray);
                return;
            }
            var progress = new Progress<double>(value =>
                CameraStatus.Text = $"Downloading local YOLOv3 model… {value:P0}");
            await _camera.StartAsync(progress);
            CameraButton.Content = "Stop camera";
            CameraIndicator.Text = "● CAMERA ON";
            CameraIndicator.Foreground = new SolidColorBrush(Microsoft.UI.Colors.LimeGreen);
        }
        catch (Exception error)
        {
            CameraStatus.Text = $"Camera could not start: {error.Message}";
            await _camera.StopAsync();
        }
        finally
        {
            CameraButton.IsEnabled = true;
        }
    }

    private void Camera_StatusChanged(object? sender, string message)
    {
        DispatcherQueue.TryEnqueue(() => CameraStatus.Text = message);
    }

    private void Camera_PhonePresenceChanged(object? sender, PhonePresenceEvent item)
    {
        DispatcherQueue.TryEnqueue(async () =>
        {
            if (!item.Presence.RecentlyVisible)
            {
                CameraStatus.Text = "Local detection · no phone";
                return;
            }
            var confidence = item.Detection?.Confidence ?? 0;
            if (!item.Presence.InterventionTriggeredForPresence)
            {
                CameraStatus.Text = item.Presence.Confirmed
                    ? $"Phone {confidence:P0} · {Math.Min(10, (int)item.Presence.SustainedDuration.TotalSeconds)}/10 seconds"
                    : $"Confirming phone {confidence:P0} · 1/2";
                return;
            }
            if (!item.Presence.ShouldIntervene)
            {
                return;
            }
            if (_api is null || _session?.Status != "running" || _session.SessionKind == "break")
            {
                CameraStatus.Text = "Phone stayed visible · no running work session";
                return;
            }
            try
            {
                CameraStatus.Text = "Phone stayed visible · sending reminder…";
                var result = await _api.ReportPhoneAsync(CameraPhoneEventRequest.Create(TimeSpan.FromSeconds(10)));
                CameraStatus.Text = result.Accepted
                    ? $"Phone stayed visible · reminder sent (strike {result.Strike})"
                    : $"Phone stayed visible · {result.Reason}";
            }
            catch (Exception error)
            {
                CameraStatus.Text = $"Reminder was not sent: {error.Message}";
            }
        });
    }

    private async void OpenFocusButton_Click(object sender, RoutedEventArgs e)
    {
        var uri = _serverUri ?? new Uri("http://127.0.0.1:8765/");
        await global::Windows.System.Launcher.LaunchUriAsync(uri);
    }

    private async void MainWindow_Closed(object sender, WindowEventArgs args)
    {
        _pollTimer.Stop();
        _displayTimer.Stop();
        _api?.Dispose();
        await _camera.DisposeAsync();
    }
}
