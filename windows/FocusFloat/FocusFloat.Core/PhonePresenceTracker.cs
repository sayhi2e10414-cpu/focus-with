namespace FocusFloat.Core;

public sealed record PhonePresenceUpdate(
    bool RecentlyVisible,
    bool Confirmed,
    int Evidence,
    TimeSpan SustainedDuration,
    bool ShouldIntervene,
    bool InterventionTriggeredForPresence,
    TimeSpan CooldownRemaining);

public sealed class PhonePresenceTracker
{
    private readonly int _confirmationHits;
    private readonly int _missTolerance;
    private readonly TimeSpan _requiredSustainedDuration;
    private readonly TimeSpan _cooldownDuration;
    private int _evidence;
    private int _misses;
    private DateTimeOffset? _confirmedAt;
    private DateTimeOffset? _lastInterventionAt;
    private bool _interventionTriggeredForPresence;

    public PhonePresenceTracker(
        int confirmationHits = 2,
        int missTolerance = 4,
        TimeSpan? sustainedDuration = null,
        TimeSpan? cooldownDuration = null)
    {
        _confirmationHits = Math.Max(1, confirmationHits);
        _missTolerance = Math.Max(1, missTolerance);
        _requiredSustainedDuration = sustainedDuration ?? TimeSpan.FromSeconds(10);
        _cooldownDuration = cooldownDuration ?? TimeSpan.FromSeconds(60);
    }

    public PhonePresenceUpdate RecordDetection(bool detected, DateTimeOffset at)
    {
        if (detected)
        {
            _evidence = Math.Min(_evidence + 1, 5);
            _misses = 0;
        }
        else if (_evidence > 0)
        {
            _misses += 1;
            if (_misses >= _missTolerance)
            {
                ClearCurrentPresence();
            }
        }

        var recentlyVisible = _evidence > 0;
        var confirmed = _evidence >= _confirmationHits;
        if (confirmed && _confirmedAt is null)
        {
            _confirmedAt = at;
        }

        var sustained = confirmed && _confirmedAt is not null
            ? Max(TimeSpan.Zero, at - _confirmedAt.Value)
            : TimeSpan.Zero;
        var cooldownRemaining = _lastInterventionAt is not null
            ? Max(TimeSpan.Zero, _lastInterventionAt.Value + _cooldownDuration - at)
            : TimeSpan.Zero;
        var shouldIntervene = confirmed
            && !_interventionTriggeredForPresence
            && sustained >= _requiredSustainedDuration
            && cooldownRemaining <= TimeSpan.Zero;

        if (shouldIntervene)
        {
            _interventionTriggeredForPresence = true;
            _lastInterventionAt = at;
            cooldownRemaining = _cooldownDuration;
        }

        return new PhonePresenceUpdate(
            recentlyVisible,
            confirmed,
            _evidence,
            sustained,
            shouldIntervene,
            _interventionTriggeredForPresence,
            cooldownRemaining);
    }

    public void Reset()
    {
        ClearCurrentPresence();
        _lastInterventionAt = null;
    }

    private void ClearCurrentPresence()
    {
        _evidence = 0;
        _misses = 0;
        _confirmedAt = null;
        _interventionTriggeredForPresence = false;
    }

    private static TimeSpan Max(TimeSpan left, TimeSpan right) => left >= right ? left : right;
}
