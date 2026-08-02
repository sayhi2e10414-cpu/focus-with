using System.Text.Json;
using FocusFloat.Core;

namespace FocusFloat.Core.Tests;

public sealed class CameraEventContractTests
{
    [Fact]
    public void PayloadContainsOnlyTheFourPrivacyMinimalFields()
    {
        var request = CameraPhoneEventRequest.Create(
            TimeSpan.FromSeconds(10),
            DateTimeOffset.Parse("2026-08-02T10:00:00Z"),
            "event-test-001");
        using var document = JsonDocument.Parse(request.ToJson());
        var names = document.RootElement.EnumerateObject().Select(item => item.Name).Order().ToArray();

        Assert.Equal(
            ["detected_at", "duration_seconds", "event_id", "source"],
            names);
        Assert.Equal("windows_focus_float", document.RootElement.GetProperty("source").GetString());
    }
}
