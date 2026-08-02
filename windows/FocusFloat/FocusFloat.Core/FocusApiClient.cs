using System.Net;
using System.Net.Http.Json;
using System.Text.Json;

namespace FocusFloat.Core;

public sealed record FocusSessionSnapshot(
    int Id,
    string Status,
    string SessionKind,
    string Title,
    int ElapsedSeconds,
    int? PlannedMinutes);

public sealed record RewardTargetSnapshot(
    int Id,
    string Title,
    int FocusMinutes,
    bool Repeatable);

public sealed record RewardProgressSnapshot(
    int SessionId,
    int SegmentNumber,
    int ContinuousSeconds,
    int TargetSeconds,
    string EvidenceMode,
    RewardTargetSnapshot Reward);

public sealed record FocusSnapshot(
    FocusSessionSnapshot? ActiveSession,
    RewardProgressSnapshot? RewardProgress);

public sealed class FocusApiClient : IDisposable
{
    private readonly HttpClient _http;
    private readonly bool _ownsClient;

    public FocusApiClient(Uri baseUri, string token, HttpClient? httpClient = null)
    {
        if (string.IsNullOrWhiteSpace(token))
        {
            throw new ArgumentException("The Focus API token is required.", nameof(token));
        }

        _ownsClient = httpClient is null;
        _http = httpClient ?? new HttpClient();
        _http.BaseAddress = NormalizeBaseUri(baseUri);
        _http.Timeout = TimeSpan.FromSeconds(20);
        _http.DefaultRequestHeaders.Remove("X-Focus-Token");
        _http.DefaultRequestHeaders.Add("X-Focus-Token", token);
    }

    public async Task<FocusSnapshot> GetSnapshotAsync(CancellationToken cancellationToken = default)
    {
        using var response = await _http.GetAsync("api/bootstrap", cancellationToken);
        response.EnsureSuccessStatusCode();
        using var document = JsonDocument.Parse(await response.Content.ReadAsStreamAsync(cancellationToken));
        var data = document.RootElement.GetProperty("data");
        var rewardProgress = ReadRewardProgress(data);
        if (data.GetProperty("active_session").ValueKind == JsonValueKind.Null)
        {
            return new FocusSnapshot(null, rewardProgress);
        }

        var session = data.GetProperty("active_session");
        string title = ReadString(session, "title") ?? ReadString(session, "goal") ?? "Focus session";
        if (session.TryGetProperty("task_id", out var taskIdElement) && taskIdElement.ValueKind == JsonValueKind.Number)
        {
            var taskId = taskIdElement.GetInt32();
            foreach (var task in data.GetProperty("tasks").EnumerateArray())
            {
                if (task.GetProperty("id").GetInt32() == taskId)
                {
                    title = ReadString(task, "title") ?? title;
                    break;
                }
            }
        }

        return new FocusSnapshot(new FocusSessionSnapshot(
            session.GetProperty("id").GetInt32(),
            session.GetProperty("status").GetString() ?? "",
            ReadString(session, "session_kind") ?? "work",
            title,
            session.GetProperty("elapsed_seconds").GetInt32(),
            session.TryGetProperty("planned_minutes", out var planned) && planned.ValueKind == JsonValueKind.Number
                ? planned.GetInt32()
                : null),
            rewardProgress);
    }

    public async Task ChangeSessionAsync(int sessionId, string action, CancellationToken cancellationToken = default)
    {
        using var response = await _http.PutAsJsonAsync(
            $"api/sessions/{sessionId}",
            new { action, note = (string?)null },
            FocusJson.Options,
            cancellationToken);
        response.EnsureSuccessStatusCode();
    }

    public async Task<CameraEventResult> ReportPhoneAsync(
        CameraPhoneEventRequest request,
        CancellationToken cancellationToken = default)
    {
        for (var attempt = 0; ; attempt++)
        {
            try
            {
                using var response = await _http.PostAsJsonAsync(
                    "api/vision-events/phone",
                    request,
                    FocusJson.Options,
                    cancellationToken);
                if (response.StatusCode == HttpStatusCode.Unauthorized)
                {
                    throw new InvalidOperationException("The Focus API token is invalid.");
                }
                if ((int)response.StatusCode >= 500 && attempt < 2)
                {
                    await Task.Delay(attempt == 0 ? TimeSpan.FromSeconds(2) : TimeSpan.FromSeconds(5), cancellationToken);
                    continue;
                }
                response.EnsureSuccessStatusCode();
                using var document = JsonDocument.Parse(await response.Content.ReadAsStreamAsync(cancellationToken));
                var data = document.RootElement.GetProperty("data");
                return new CameraEventResult(
                    data.GetProperty("accepted").GetBoolean(),
                    data.GetProperty("reason").GetString() ?? "",
                    data.TryGetProperty("intervention_id", out var id) && id.ValueKind == JsonValueKind.Number
                        ? id.GetInt32()
                        : null,
                    data.GetProperty("strike").GetInt32());
            }
            catch (HttpRequestException) when (attempt < 2)
            {
                await Task.Delay(attempt == 0 ? TimeSpan.FromSeconds(2) : TimeSpan.FromSeconds(5), cancellationToken);
            }
        }
    }

    public async Task ReportCameraHeartbeatAsync(
        bool observing,
        CancellationToken cancellationToken = default)
    {
        using var response = await _http.PostAsJsonAsync(
            "api/vision-events/heartbeat",
            CameraHeartbeatRequest.Create(observing),
            FocusJson.Options,
            cancellationToken);
        response.EnsureSuccessStatusCode();
    }

    public void Dispose()
    {
        if (_ownsClient)
        {
            _http.Dispose();
        }
    }

    private static Uri NormalizeBaseUri(Uri value)
    {
        if (!value.IsAbsoluteUri || value.Scheme is not ("http" or "https"))
        {
            throw new ArgumentException("Focus URL must be an absolute http or https URL.", nameof(value));
        }
        var builder = new UriBuilder(value) { Path = value.AbsolutePath.TrimEnd('/') + "/" };
        return builder.Uri;
    }

    private static string? ReadString(JsonElement element, string property) =>
        element.TryGetProperty(property, out var value) && value.ValueKind == JsonValueKind.String
            ? value.GetString()
            : null;

    private static RewardProgressSnapshot? ReadRewardProgress(JsonElement data)
    {
        if (!data.TryGetProperty("rewards", out var rewards) ||
            !rewards.TryGetProperty("progress", out var progress) ||
            progress.ValueKind != JsonValueKind.Object ||
            !progress.TryGetProperty("reward", out var reward) ||
            reward.ValueKind != JsonValueKind.Object)
        {
            return null;
        }
        return new RewardProgressSnapshot(
            progress.GetProperty("session_id").GetInt32(),
            progress.GetProperty("segment_number").GetInt32(),
            progress.GetProperty("continuous_seconds").GetInt32(),
            progress.GetProperty("target_seconds").GetInt32(),
            ReadString(progress, "evidence_mode") ?? "timer_only",
            new RewardTargetSnapshot(
                reward.GetProperty("id").GetInt32(),
                ReadString(reward, "title") ?? "Reward",
                reward.GetProperty("focus_minutes").GetInt32(),
                reward.TryGetProperty("repeatable", out var repeatable) && repeatable.GetBoolean()));
    }
}
