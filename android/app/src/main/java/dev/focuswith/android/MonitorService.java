package dev.focuswith.android;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.IBinder;
import android.provider.Settings;

import org.json.JSONArray;
import org.json.JSONObject;

import java.time.Instant;
import java.util.Map;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

public final class MonitorService extends Service {
    static final String ACTION_START = "dev.focuswith.android.START";
    static final String ACTION_STOP = "dev.focuswith.android.STOP";
    private static final String CHANNEL_ID = "focuswith_monitor";
    private static final int NOTIFICATION_ID = 4107;

    private final ScheduledExecutorService executor = Executors.newSingleThreadScheduledExecutor();
    private FocusPrefs prefs;
    private AppUsageReader usageReader;
    private OverlayController overlay;
    private SharedPreferences queuePrefs;
    private String foregroundPackage;
    private String monitoredPackage;
    private long lastUsageQuery;
    private long lastSnapshotFetch;
    private long snapshotFetchedAt;
    private FocusApi.Snapshot snapshot = FocusApi.Snapshot.idle();
    private boolean initializedUsageState;
    private boolean scheduled;
    private volatile boolean stopping;

    @Override
    public void onCreate() {
        super.onCreate();
        prefs = new FocusPrefs(this);
        usageReader = new AppUsageReader(this);
        overlay = new OverlayController(this);
        queuePrefs = getSharedPreferences("focuswith_event_queue", MODE_PRIVATE);
        createNotificationChannel();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && ACTION_STOP.equals(intent.getAction())) {
            requestStop();
            return START_NOT_STICKY;
        }
        prefs.setMonitorRunning(true);
        startForeground(NOTIFICATION_ID, buildNotification());
        if (!scheduled) {
            scheduled = true;
            executor.scheduleAtFixedRate(this::tickSafely, 0, 2, TimeUnit.SECONDS);
        }
        return START_STICKY;
    }

    private void tickSafely() {
        if (stopping) return;
        try {
            tickUsage();
            flushEvents();
            tickSnapshot();
        } catch (Exception ignored) {
            // Monitoring continues. Queued phone events are retried on the next tick.
        }
        updateSurfaces();
    }

    private void tickUsage() {
        if (!AppUsageReader.hasUsageAccess(this)) return;
        long now = System.currentTimeMillis();
        Map<String, String> monitored = prefs.monitoredPackages();

        if (!initializedUsageState) {
            for (Map.Entry<String, String> entry : monitored.entrySet()) {
                enqueueEvent(entry.getValue(), "closed", now);
            }
            lastUsageQuery = now - TimeUnit.DAYS.toMillis(1);
            initializedUsageState = true;
        }

        String next = usageReader.foregroundPackage(
            foregroundPackage,
            foregroundPackage == null
                ? Math.max(0, now - TimeUnit.HOURS.toMillis(1))
                : Math.max(0, lastUsageQuery - 1000),
            now
        );
        lastUsageQuery = now + 1;
        if (same(next, foregroundPackage)) return;

        String nextMonitored = next != null && monitored.containsKey(next) ? next : null;
        if (monitoredPackage != null && !monitoredPackage.equals(nextMonitored)) {
            String name = monitored.get(monitoredPackage);
            if (name != null) enqueueEvent(name, "closed", now);
        }
        if (nextMonitored != null && !nextMonitored.equals(monitoredPackage)) {
            enqueueEvent(monitored.get(nextMonitored), "opened", now);
        }
        foregroundPackage = next;
        monitoredPackage = nextMonitored;
    }

    private static boolean same(String first, String second) {
        return first == null ? second == null : first.equals(second);
    }

    private void tickSnapshot() {
        long now = System.currentTimeMillis();
        if (now - lastSnapshotFetch < 5000) return;
        lastSnapshotFetch = now;
        String server = prefs.serverUrl();
        String token = prefs.phoneToken();
        if (server.isEmpty() || token.isEmpty()) {
            snapshot = FocusApi.Snapshot.idle();
            snapshotFetchedAt = now;
            return;
        }
        try {
            snapshot = FocusApi.fetchSnapshot(server, token);
            snapshotFetchedAt = now;
        } catch (Exception ignored) {
            // Keep the most recent timer during a temporary network interruption.
        }
    }

    private void enqueueEvent(String appName, String eventType, long timestamp) {
        if (appName == null || appName.isEmpty()) return;
        try {
            JSONArray queue = readQueue();
            while (queue.length() >= 500) queue.remove(0);
            queue.put(new JSONObject()
                .put("app_name", appName)
                .put("event_type", eventType)
                .put("occurred_at", Instant.ofEpochMilli(timestamp).toString()));
            queuePrefs.edit().putString("events", queue.toString()).commit();
        } catch (Exception ignored) {
        }
    }

    private JSONArray readQueue() {
        try {
            return new JSONArray(queuePrefs.getString("events", "[]"));
        } catch (Exception ignored) {
            return new JSONArray();
        }
    }

    private void flushEvents() {
        String server = prefs.serverUrl();
        String token = prefs.phoneToken();
        if (server.isEmpty() || token.isEmpty()) return;
        JSONArray queue = readQueue();
        while (queue.length() > 0) {
            try {
                JSONObject event = queue.getJSONObject(0);
                FocusApi.postPhoneEvent(
                    server,
                    token,
                    event.getString("app_name"),
                    event.getString("event_type"),
                    prefs.deviceId(),
                    event.getString("occurred_at")
                );
                queue.remove(0);
                queuePrefs.edit().putString("events", queue.toString()).commit();
            } catch (Exception ignored) {
                return;
            }
        }
    }

    private void updateSurfaces() {
        NotificationManager manager = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        manager.notify(NOTIFICATION_ID, buildNotification());
        boolean showOverlay = prefs.overlayEnabled()
            && Settings.canDrawOverlays(this)
            && snapshot.active;
        if (showOverlay) {
            overlay.update(snapshot.title, formattedTimer());
        } else {
            overlay.hide();
        }
    }

    private String formattedTimer() {
        int seconds = snapshot.displaySeconds(snapshotFetchedAt);
        int hours = seconds / 3600;
        int minutes = (seconds % 3600) / 60;
        int remainder = seconds % 60;
        if (hours > 0) return String.format(java.util.Locale.getDefault(), "%d:%02d:%02d", hours, minutes, remainder);
        return String.format(java.util.Locale.getDefault(), "%02d:%02d", minutes, remainder);
    }

    private Notification buildNotification() {
        Intent open = new Intent(this, MainActivity.class)
            .addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent openIntent = PendingIntent.getActivity(
            this, 0, open, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );
        Intent stop = new Intent(this, MonitorService.class).setAction(ACTION_STOP);
        PendingIntent stopIntent = PendingIntent.getService(
            this, 1, stop, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );

        String title = snapshot.active ? formattedTimer() + " · " + snapshot.title : getString(R.string.app_name);
        String body = snapshot.active
            ? ("paused".equals(snapshot.status) ? getString(R.string.notification_paused) : getString(R.string.status_running))
            : getString(R.string.notification_idle);
        return new Notification.Builder(this, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle(title)
            .setContentText(body)
            .setContentIntent(openIntent)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setVisibility(Notification.VISIBILITY_PRIVATE)
            .setCategory(Notification.CATEGORY_SERVICE)
            .addAction(new Notification.Action.Builder(null, getString(R.string.stop), stopIntent).build())
            .build();
    }

    private void createNotificationChannel() {
        NotificationChannel channel = new NotificationChannel(
            CHANNEL_ID,
            getString(R.string.notification_channel),
            NotificationManager.IMPORTANCE_LOW
        );
        channel.setDescription(getString(R.string.notifications_detail));
        channel.setShowBadge(false);
        ((NotificationManager) getSystemService(NOTIFICATION_SERVICE)).createNotificationChannel(channel);
    }

    private void requestStop() {
        if (stopping) return;
        stopping = true;
        executor.execute(() -> {
            if (monitoredPackage != null) {
                String name = prefs.monitoredPackages().get(monitoredPackage);
                enqueueEvent(name, "closed", System.currentTimeMillis());
                flushEvents();
            }
            stopSelf();
        });
    }

    @Override
    public void onDestroy() {
        stopping = true;
        prefs.setMonitorRunning(false);
        overlay.hide();
        executor.shutdownNow();
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
