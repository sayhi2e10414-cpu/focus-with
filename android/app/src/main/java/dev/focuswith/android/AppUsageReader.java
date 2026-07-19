package dev.focuswith.android;

import android.app.AppOpsManager;
import android.app.KeyguardManager;
import android.app.usage.UsageEvents;
import android.app.usage.UsageStatsManager;
import android.content.Context;
import android.os.PowerManager;
import android.os.Process;
import android.os.Build;

final class AppUsageReader {
    private final Context context;
    private final UsageStatsManager usageStats;

    AppUsageReader(Context context) {
        this.context = context.getApplicationContext();
        usageStats = (UsageStatsManager) context.getSystemService(Context.USAGE_STATS_SERVICE);
    }

    @SuppressWarnings("deprecation")
    static boolean hasUsageAccess(Context context) {
        AppOpsManager manager = (AppOpsManager) context.getSystemService(Context.APP_OPS_SERVICE);
        int mode = Build.VERSION.SDK_INT >= 29
            ? manager.unsafeCheckOpNoThrow(
                AppOpsManager.OPSTR_GET_USAGE_STATS,
                Process.myUid(),
                context.getPackageName()
            )
            : manager.checkOpNoThrow(
                AppOpsManager.OPSTR_GET_USAGE_STATS,
                Process.myUid(),
                context.getPackageName()
            );
        return mode == AppOpsManager.MODE_ALLOWED;
    }

    String foregroundPackage(String previous, long fromMillis, long toMillis) {
        PowerManager power = (PowerManager) context.getSystemService(Context.POWER_SERVICE);
        KeyguardManager keyguard = (KeyguardManager) context.getSystemService(Context.KEYGUARD_SERVICE);
        if (!power.isInteractive() || keyguard.isKeyguardLocked()) return null;

        String current = previous;
        UsageEvents events = usageStats.queryEvents(fromMillis, toMillis);
        if (events == null) return current;
        UsageEvents.Event event = new UsageEvents.Event();
        while (events.hasNextEvent()) {
            events.getNextEvent(event);
            int type = event.getEventType();
            if (type == UsageEvents.Event.ACTIVITY_RESUMED) {
                current = event.getPackageName();
            } else if (
                (type == UsageEvents.Event.ACTIVITY_PAUSED
                    || type == UsageEvents.Event.ACTIVITY_STOPPED)
                    && event.getPackageName() != null
                    && event.getPackageName().equals(current)
            ) {
                current = null;
            } else if (type == UsageEvents.Event.SCREEN_NON_INTERACTIVE) {
                current = null;
            }
        }
        return current;
    }
}
