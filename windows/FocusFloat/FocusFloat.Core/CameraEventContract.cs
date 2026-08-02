using System.Text.Json;
using System.Text.Json.Serialization;

namespace FocusFloat.Core;

public sealed record CameraPhoneEventRequest(
    [property: JsonPropertyName("event_id")] string EventId,
    [property: JsonPropertyName("duration_seconds")] int DurationSeconds,
    [property: JsonPropertyName("detected_at")] DateTimeOffset DetectedAt,
    [property: JsonPropertyName("source")] string Source)
{
    public static CameraPhoneEventRequest Create(
        TimeSpan duration,
        DateTimeOffset? detectedAt = null,
        string? eventId = null) =>
        new(
            eventId ?? Guid.NewGuid().ToString("D"),
            Math.Clamp((int)Math.Round(duration.TotalSeconds), 10, 300),
            detectedAt ?? DateTimeOffset.UtcNow,
            "windows_focus_float");

    public string ToJson() => JsonSerializer.Serialize(this, FocusJson.Options);
}

public sealed record CameraEventResult(
    bool Accepted,
    string Reason,
    int? InterventionId,
    int Strike);

internal static class FocusJson
{
    public static readonly JsonSerializerOptions Options = new(JsonSerializerDefaults.Web)
    {
        PropertyNameCaseInsensitive = true,
    };
}
