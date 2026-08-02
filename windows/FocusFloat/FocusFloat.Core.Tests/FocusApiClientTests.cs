using System.Net;
using System.Text;
using System.Text.Json;
using FocusFloat.Core;

namespace FocusFloat.Core.Tests;

public sealed class FocusApiClientTests
{
    [Fact]
    public async Task SnapshotUsesTheLinkedTaskTitle()
    {
        var handler = new StubHandler(request =>
        {
            Assert.Equal("/api/bootstrap", request.RequestUri?.AbsolutePath);
            Assert.Equal("test-token", request.Headers.GetValues("X-Focus-Token").Single());
            return JsonResponse(
                """
                {
                  "success": true,
                  "data": {
                    "tasks": [{"id": 7, "title": "Write the Windows guide"}],
                    "rewards": {
                      "progress": {
                        "session_id": 11,
                        "segment_number": 2,
                        "continuous_seconds": 300,
                        "target_seconds": 1500,
                        "evidence_mode": "camera_verified",
                        "reward": {
                          "id": 3,
                          "title": "One episode",
                          "focus_minutes": 25,
                          "repeatable": false
                        }
                      }
                    },
                    "active_session": {
                      "id": 11,
                      "task_id": 7,
                      "session_kind": "work",
                      "title": null,
                      "goal": "Fallback",
                      "status": "running",
                      "elapsed_seconds": 125,
                      "planned_minutes": 25
                    }
                  }
                }
                """);
        });
        using var http = new HttpClient(handler);
        using var api = new FocusApiClient(new Uri("http://127.0.0.1:8765"), "test-token", http);

        var snapshot = await api.GetSnapshotAsync();

        Assert.NotNull(snapshot.ActiveSession);
        Assert.Equal("Write the Windows guide", snapshot.ActiveSession.Title);
        Assert.Equal(125, snapshot.ActiveSession.ElapsedSeconds);
        Assert.NotNull(snapshot.RewardProgress);
        Assert.Equal("One episode", snapshot.RewardProgress.Reward.Title);
        Assert.Equal("camera_verified", snapshot.RewardProgress.EvidenceMode);
    }

    [Fact]
    public async Task CameraHeartbeatContainsNoImageDerivedData()
    {
        var handler = new StubHandler(async (request, cancellationToken) =>
        {
            Assert.Equal("/api/vision-events/heartbeat", request.RequestUri?.AbsolutePath);
            var json = await request.Content!.ReadAsStringAsync(cancellationToken);
            using var document = JsonDocument.Parse(json);
            Assert.Equal(
                ["camera_state", "observed_at", "source"],
                document.RootElement.EnumerateObject().Select(item => item.Name).Order().ToArray());
            return JsonResponse("""{"success":true,"data":{"accepted":true}}""");
        });
        using var http = new HttpClient(handler);
        using var api = new FocusApiClient(new Uri("https://focus.example/"), "test-token", http);

        await api.ReportCameraHeartbeatAsync(observing: true);
    }

    [Fact]
    public async Task PhoneReportSendsOnlyThePrivacyMinimalContract()
    {
        var handler = new StubHandler(async (request, cancellationToken) =>
        {
            Assert.Equal(HttpMethod.Post, request.Method);
            Assert.Equal("/api/vision-events/phone", request.RequestUri?.AbsolutePath);
            Assert.Equal("test-token", request.Headers.GetValues("X-Focus-Token").Single());
            var json = await request.Content!.ReadAsStringAsync(cancellationToken);
            using var document = JsonDocument.Parse(json);
            Assert.Equal(
                ["detected_at", "duration_seconds", "event_id", "source"],
                document.RootElement.EnumerateObject().Select(item => item.Name).Order().ToArray());
            return JsonResponse(
                """
                {
                  "success": true,
                  "data": {
                    "accepted": true,
                    "reason": "notified",
                    "intervention_id": 42,
                    "strike": 1
                  }
                }
                """);
        });
        using var http = new HttpClient(handler);
        using var api = new FocusApiClient(new Uri("https://focus.example/"), "test-token", http);

        var result = await api.ReportPhoneAsync(
            CameraPhoneEventRequest.Create(
                TimeSpan.FromSeconds(10),
                DateTimeOffset.Parse("2026-08-02T10:00:00Z"),
                "event-test-002"));

        Assert.True(result.Accepted);
        Assert.Equal(42, result.InterventionId);
        Assert.Equal(1, result.Strike);
    }

    private static HttpResponseMessage JsonResponse(string json) =>
        new(HttpStatusCode.OK)
        {
            Content = new StringContent(json, Encoding.UTF8, "application/json"),
        };

    private sealed class StubHandler : HttpMessageHandler
    {
        private readonly Func<HttpRequestMessage, CancellationToken, Task<HttpResponseMessage>> _respond;

        public StubHandler(Func<HttpRequestMessage, HttpResponseMessage> respond)
            : this((request, _) => Task.FromResult(respond(request)))
        {
        }

        public StubHandler(Func<HttpRequestMessage, CancellationToken, Task<HttpResponseMessage>> respond)
        {
            _respond = respond;
        }

        protected override Task<HttpResponseMessage> SendAsync(
            HttpRequestMessage request,
            CancellationToken cancellationToken) =>
            _respond(request, cancellationToken);
    }
}
