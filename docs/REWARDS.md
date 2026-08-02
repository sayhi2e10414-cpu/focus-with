# Uninterrupted-focus rewards

FocusWith can turn one uninterrupted focus block into a user-defined reward.
Open **Rewards** in the web app to edit the included example, delete it, or add
your own targets.

Each reward has:

- a name and optional description;
- the uninterrupted focus minutes required to earn it;
- an optional reward duration;
- an option to earn another copy after every additional target interval in the
  same uninterrupted block.

Select one current target. Changing the target during an active session restarts
only the current uninterrupted progress. Already-earned rewards remain in the
reward cabinet until you explicitly redeem them, even after a distraction,
session cancellation, reward edit, or reward deletion.

## What counts as uninterrupted focus

FocusWith chooses the strongest evidence currently available:

1. **Camera verified:** an opted-in FocusFloat camera companion has sent a recent
   local-inference heartbeat.
2. **Timer + blocklist:** no recent camera heartbeat is available, but the
   current task or global policy has monitored apps.
3. **Timer only:** neither camera evidence nor a blocklist is available.

Pausing freezes progress without resetting it. A confirmed camera phone event or
a monitored app that remains open beyond its grace period starts a new
uninterrupted segment. Reminder cooldowns do not prevent that reset: cooldown
controls notification noise, not reward evidence.

“Camera verified” means local camera inference was running and did not report a
sustained phone presence. It does not claim to measure gaze, comprehension, or
whether the user looked away from the screen.

## Camera heartbeat privacy

While the camera is on during a running work session, FocusFloat sends this
heartbeat about every 30 seconds:

```json
{
  "observed_at": "2026-08-02T10:00:00Z",
  "source": "macos_focus_float",
  "camera_state": "observing"
}
```

The endpoint rejects additional properties. Heartbeats contain no image, crop,
confidence value, bounding box, embedding, detected object, or face/gaze
measurement. The server stores only the latest accepted heartbeat timestamp and
source for the current session; it does not retain a heartbeat history.

If no heartbeat arrives for 75 seconds, FocusWith automatically falls back to
timer + blocklist or timer-only evidence. Stopping the camera sends
`camera_state: "stopped"` so the change is immediate when the server is
reachable.

## Chat and MCP

The built-in companion and local/remote MCP expose:

- `get_reward_status`
- `create_reward`
- `select_reward`
- `redeem_reward`

Selecting a different reward may reset unearned progress, and redeeming consumes
an earned reward, so those tools are marked destructive for client confirmation.
MCP cannot turn on the camera. Camera permission and the visible camera control
remain local to FocusFloat.
