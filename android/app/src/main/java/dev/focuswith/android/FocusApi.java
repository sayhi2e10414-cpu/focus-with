package dev.focuswith.android;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URI;
import java.net.URL;
import java.nio.charset.StandardCharsets;

final class FocusApi {
    static boolean isValidServerUrl(String value) {
        try {
            URI uri = new URI(value);
            return "https".equalsIgnoreCase(uri.getScheme())
                && uri.getHost() != null
                && uri.getUserInfo() == null
                && uri.getQuery() == null
                && uri.getFragment() == null
                && (uri.getPath() == null || uri.getPath().isEmpty() || "/".equals(uri.getPath()));
        } catch (Exception ignored) {
            return false;
        }
    }

    static final class Snapshot {
        final boolean active;
        final String title;
        final String status;
        final String mode;
        final int plannedSeconds;
        final int elapsedSeconds;

        Snapshot(boolean active, String title, String status, String mode, int plannedSeconds, int elapsedSeconds) {
            this.active = active;
            this.title = title;
            this.status = status;
            this.mode = mode;
            this.plannedSeconds = plannedSeconds;
            this.elapsedSeconds = elapsedSeconds;
        }

        static Snapshot idle() {
            return new Snapshot(false, "", "", "", 0, 0);
        }

        int displaySeconds(long fetchedAtMillis) {
            int age = status.equals("running") ? (int) Math.max(0, (System.currentTimeMillis() - fetchedAtMillis) / 1000) : 0;
            int elapsed = elapsedSeconds + age;
            if ("countup".equals(mode) || plannedSeconds <= 0) return elapsed;
            return Math.max(0, plannedSeconds - elapsed);
        }
    }

    static void postPhoneEvent(
        String serverUrl,
        String token,
        String appName,
        String eventType,
        String deviceId,
        String occurredAt
    ) throws Exception {
        JSONObject body = new JSONObject()
            .put("app_name", appName)
            .put("event_type", eventType)
            .put("device_id", deviceId)
            .put("source", "android_usage_stats")
            .put("occurred_at", occurredAt);
        request(serverUrl + "/api/phone/events", "POST", token, body.toString());
    }

    static Snapshot fetchSnapshot(String serverUrl, String token) throws Exception {
        JSONObject root = new JSONObject(request(serverUrl + "/api/phone/focus", "GET", token, null));
        JSONObject session = root.getJSONObject("data").optJSONObject("active_session");
        if (session == null) return Snapshot.idle();
        int plannedMinutes = session.isNull("planned_minutes") ? 0 : session.optInt("planned_minutes", 0);
        return new Snapshot(
            true,
            session.optString("title", "Focus"),
            session.optString("status", ""),
            session.optString("mode", ""),
            plannedMinutes * 60,
            session.optInt("elapsed_seconds", 0)
        );
    }

    private static String request(String url, String method, String token, String body) throws Exception {
        HttpURLConnection connection = (HttpURLConnection) new URL(url).openConnection();
        connection.setRequestMethod(method);
        connection.setInstanceFollowRedirects(false);
        connection.setConnectTimeout(8000);
        connection.setReadTimeout(8000);
        connection.setRequestProperty("Accept", "application/json");
        connection.setRequestProperty("X-Focus-Phone-Token", token);
        if (body != null) {
            connection.setDoOutput(true);
            connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
            try (OutputStream output = connection.getOutputStream()) {
                output.write(body.getBytes(StandardCharsets.UTF_8));
            }
        }
        int code = connection.getResponseCode();
        InputStream stream = code >= 200 && code < 300 ? connection.getInputStream() : connection.getErrorStream();
        StringBuilder text = new StringBuilder();
        if (stream != null) {
            try (BufferedReader reader = new BufferedReader(new InputStreamReader(stream, StandardCharsets.UTF_8))) {
                String line;
                while ((line = reader.readLine()) != null) text.append(line);
            }
        }
        connection.disconnect();
        if (code < 200 || code >= 300) {
            throw new IllegalStateException("FocusWith returned HTTP " + code + ": " + text);
        }
        return text.toString();
    }
}
