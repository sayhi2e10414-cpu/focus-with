# iPhone app events with Shortcuts

Focus can receive app-open and app-close events from iOS Shortcuts. It records usage events even when no Focus session is active. During an active session, a monitored app produces at most one strike per distinct opening after the grace period.

## Endpoint

Send a `POST` request to:

```text
https://YOUR-FOCUS-HOST/api/phone/events
```

Headers:

```text
Content-Type: application/json
X-Focus-Phone-Token: YOUR_PHONE_TOKEN
```

Body for an open automation:

```json
{
  "app_name": "Instagram",
  "event_type": "opened",
  "device_id": "iphone",
  "source": "shortcut"
}
```

Use the same body with `"event_type": "closed"` for the close automation.

## iOS automation

1. In Shortcuts → Automation, create an automation for “App is opened”.
2. Select each app you want to monitor and add “Get Contents of URL”.
3. Choose POST, JSON, add the phone-token header, and use the open body above.
4. Create a second automation for “App is closed” with the close body.
5. Turn off “Ask Before Running” if iOS offers that option.

The Focus server must be reachable from the phone. Do not expose the local server directly to the internet; use HTTPS through a private network such as Tailscale or a properly authenticated reverse proxy.

Daily usage is available from `GET /api/phone/usage?date=YYYY-MM-DD` with the same phone token. If iOS skips a close automation, the current open interval remains open until a later close event; this is a limitation of event-based Shortcuts tracking, not a claim of Screen Time-level accuracy.
