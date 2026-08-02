using FocusFloat.Core;

namespace FocusFloat.Core.Tests;

public sealed class PhonePresenceTrackerTests
{
    [Fact]
    public void ConfirmsToleratesMissesAndTriggersOnce()
    {
        var tracker = new PhonePresenceTracker();
        var start = DateTimeOffset.Parse("2026-08-02T10:00:00Z");

        Assert.False(tracker.RecordDetection(true, start).Confirmed);
        Assert.True(tracker.RecordDetection(true, start.AddSeconds(.5)).Confirmed);
        Assert.True(tracker.RecordDetection(false, start.AddSeconds(1)).Confirmed);
        Assert.False(tracker.RecordDetection(true, start.AddSeconds(10)).ShouldIntervene);
        Assert.True(tracker.RecordDetection(true, start.AddSeconds(10.5)).ShouldIntervene);
        Assert.False(tracker.RecordDetection(true, start.AddSeconds(11)).ShouldIntervene);

        PhonePresenceUpdate update = null!;
        for (var index = 0; index < 4; index++)
        {
            update = tracker.RecordDetection(false, start.AddSeconds(12 + index * .5));
        }
        Assert.False(update.RecentlyVisible);
    }

    [Fact]
    public void CooldownSuppressesANewPresence()
    {
        var tracker = new PhonePresenceTracker();
        var start = DateTimeOffset.Parse("2026-08-02T10:00:00Z");
        tracker.RecordDetection(true, start);
        tracker.RecordDetection(true, start.AddSeconds(.5));
        Assert.True(tracker.RecordDetection(true, start.AddSeconds(10.5)).ShouldIntervene);
        for (var index = 0; index < 4; index++)
        {
            tracker.RecordDetection(false, start.AddSeconds(11 + index * .5));
        }
        tracker.RecordDetection(true, start.AddSeconds(14));
        tracker.RecordDetection(true, start.AddSeconds(14.5));
        var update = tracker.RecordDetection(true, start.AddSeconds(25));
        Assert.False(update.ShouldIntervene);
        Assert.True(update.CooldownRemaining > TimeSpan.Zero);
    }
}
