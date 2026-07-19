package dev.focuswith.android;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.provider.Settings;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Switch;
import android.widget.TextView;
import android.widget.Toast;

public final class MainActivity extends Activity {
    private FocusPrefs prefs;
    private EditText serverInput;
    private EditText tokenInput;
    private EditText appsInput;
    private TextView usageStatus;
    private TextView notificationStatus;
    private TextView monitorStatus;
    private Switch overlaySwitch;
    private Button startButton;
    private Button stopButton;
    private boolean refreshing;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        prefs = new FocusPrefs(this);
        setContentView(buildContent());
    }

    @Override
    protected void onResume() {
        super.onResume();
        refreshState();
    }

    private View buildContent() {
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setBackgroundColor(Color.rgb(245, 245, 247));

        LinearLayout root = vertical();
        root.setPadding(dp(20), dp(34), dp(20), dp(44));
        scroll.addView(root);

        TextView eyebrow = text("FOCUSWITH · ANDROID", 12, Color.rgb(110, 110, 115), Typeface.BOLD);
        root.addView(eyebrow);
        TextView title = text(getString(R.string.title), 32, Color.rgb(29, 29, 31), Typeface.BOLD);
        addWithTop(root, title, 8);
        TextView subtitle = text(getString(R.string.subtitle), 16, Color.rgb(110, 110, 115), Typeface.NORMAL);
        addWithTop(root, subtitle, 8);

        monitorStatus = text(getString(R.string.status_ready), 14, Color.rgb(110, 110, 115), Typeface.BOLD);
        addWithTop(root, monitorStatus, 22);

        LinearLayout connection = card();
        addWithTop(root, connection, 20);
        connection.addView(sectionTitle(getString(R.string.server_url)));
        serverInput = input(false, 1);
        serverInput.setText(prefs.serverUrl());
        addWithTop(connection, serverInput, 10);

        connection.addView(spacer(16));
        connection.addView(sectionTitle(getString(R.string.phone_token)));
        tokenInput = input(true, 1);
        if (!prefs.phoneToken().isEmpty()) tokenInput.setHint(R.string.token_saved_hint);
        addWithTop(connection, tokenInput, 10);

        connection.addView(spacer(16));
        connection.addView(sectionTitle(getString(R.string.monitored_apps)));
        appsInput = input(false, 7);
        appsInput.setText(prefs.monitoredAppsText());
        addWithTop(connection, appsInput, 10);

        Button save = primaryButton(getString(R.string.save));
        save.setOnClickListener(view -> saveConfiguration(true));
        addWithTop(connection, save, 18);

        LinearLayout usageCard = permissionCard(
            getString(R.string.usage_access),
            getString(R.string.usage_access_detail)
        );
        usageStatus = statusText();
        usageCard.addView(usageStatus);
        Button usageButton = secondaryButton(getString(R.string.open_settings));
        usageButton.setOnClickListener(view -> startActivity(new Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS)));
        addWithTop(usageCard, usageButton, 14);
        addWithTop(root, usageCard, 14);

        LinearLayout notificationCard = permissionCard(
            getString(R.string.notifications),
            getString(R.string.notifications_detail)
        );
        notificationStatus = statusText();
        notificationCard.addView(notificationStatus);
        Button notificationButton = secondaryButton(getString(R.string.open_settings));
        notificationButton.setOnClickListener(view -> requestNotificationPermission());
        addWithTop(notificationCard, notificationButton, 14);
        addWithTop(root, notificationCard, 14);

        LinearLayout overlayCard = permissionCard(
            getString(R.string.overlay),
            getString(R.string.overlay_detail)
        );
        overlaySwitch = new Switch(this);
        overlaySwitch.setTextColor(Color.rgb(29, 29, 31));
        overlaySwitch.setText(getString(R.string.overlay));
        overlaySwitch.setTextSize(15);
        overlaySwitch.setPadding(0, dp(8), 0, 0);
        overlaySwitch.setOnCheckedChangeListener((button, checked) -> {
            if (refreshing) return;
            prefs.setOverlayEnabled(checked);
            if (checked && !Settings.canDrawOverlays(this)) requestOverlayPermission();
        });
        overlayCard.addView(overlaySwitch);
        addWithTop(root, overlayCard, 14);

        startButton = primaryButton(getString(R.string.start));
        startButton.setOnClickListener(view -> startMonitoring());
        addWithTop(root, startButton, 22);

        stopButton = secondaryButton(getString(R.string.stop));
        stopButton.setOnClickListener(view -> stopMonitoring());
        addWithTop(root, stopButton, 10);

        TextView privacy = text(
            getString(R.string.privacy_note),
            12,
            Color.rgb(134, 134, 139),
            Typeface.NORMAL
        );
        addWithTop(root, privacy, 20);
        return scroll;
    }

    private void refreshState() {
        refreshing = true;
        boolean usage = AppUsageReader.hasUsageAccess(this);
        usageStatus.setText(usage ? R.string.permission_granted : R.string.permission_needed);
        usageStatus.setTextColor(usage ? Color.rgb(28, 148, 66) : Color.rgb(174, 104, 0));

        boolean notifications = Build.VERSION.SDK_INT < 33
            || checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED;
        notificationStatus.setText(notifications ? R.string.permission_granted : R.string.permission_needed);
        notificationStatus.setTextColor(notifications ? Color.rgb(28, 148, 66) : Color.rgb(174, 104, 0));

        boolean overlayAllowed = Settings.canDrawOverlays(this);
        if (!overlayAllowed && prefs.overlayEnabled()) prefs.setOverlayEnabled(false);
        overlaySwitch.setChecked(prefs.overlayEnabled() && overlayAllowed);

        boolean running = prefs.monitorRunning();
        monitorStatus.setText(running ? R.string.status_running : R.string.status_ready);
        monitorStatus.setTextColor(running ? Color.rgb(28, 148, 66) : Color.rgb(110, 110, 115));
        startButton.setEnabled(!running);
        stopButton.setEnabled(running);
        refreshing = false;
    }

    private boolean saveConfiguration(boolean showToast) {
        String server = serverInput.getText().toString().trim().replaceAll("/+$", "");
        String token = tokenInput.getText().toString().trim();
        if (!FocusApi.isValidServerUrl(server)) {
            toast(R.string.invalid_https);
            return false;
        }
        if (token.isEmpty() && prefs.phoneToken().isEmpty()) {
            toast(R.string.missing_config);
            return false;
        }
        try {
            prefs.setServerUrl(server);
            if (!token.isEmpty()) prefs.setPhoneToken(token);
            prefs.setMonitoredAppsText(appsInput.getText().toString());
            tokenInput.setText("");
            tokenInput.setHint(R.string.token_saved_hint);
            if (showToast) toast(R.string.saved);
            return true;
        } catch (Exception error) {
            Toast.makeText(this, error.getMessage(), Toast.LENGTH_LONG).show();
            return false;
        }
    }

    private void startMonitoring() {
        if (!saveConfiguration(false)) return;
        if (!AppUsageReader.hasUsageAccess(this)) {
            toast(R.string.missing_usage);
            startActivity(new Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS));
            return;
        }
        if (Build.VERSION.SDK_INT >= 33
            && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, 43);
        }
        Intent service = new Intent(this, MonitorService.class).setAction(MonitorService.ACTION_START);
        startForegroundService(service);
        prefs.setMonitorRunning(true);
        refreshState();
    }

    private void stopMonitoring() {
        startService(new Intent(this, MonitorService.class).setAction(MonitorService.ACTION_STOP));
        prefs.setMonitorRunning(false);
        refreshState();
    }

    private void requestNotificationPermission() {
        if (Build.VERSION.SDK_INT >= 33
            && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, 43);
        } else {
            Intent intent = new Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS)
                .putExtra(Settings.EXTRA_APP_PACKAGE, getPackageName());
            startActivity(intent);
        }
    }

    private void requestOverlayPermission() {
        Intent intent = new Intent(
            Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
            Uri.parse("package:" + getPackageName())
        );
        startActivity(intent);
    }

    private LinearLayout permissionCard(String title, String detail) {
        LinearLayout card = card();
        card.addView(sectionTitle(title));
        TextView copy = text(detail, 13, Color.rgb(110, 110, 115), Typeface.NORMAL);
        addWithTop(card, copy, 6);
        return card;
    }

    private LinearLayout card() {
        LinearLayout layout = vertical();
        layout.setPadding(dp(20), dp(20), dp(20), dp(20));
        GradientDrawable background = new GradientDrawable();
        background.setColor(Color.WHITE);
        background.setCornerRadius(dp(24));
        layout.setBackground(background);
        layout.setElevation(dp(1));
        return layout;
    }

    private LinearLayout vertical() {
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setGravity(Gravity.START);
        layout.setLayoutParams(new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            LinearLayout.LayoutParams.WRAP_CONTENT
        ));
        return layout;
    }

    private TextView sectionTitle(String value) {
        return text(value, 15, Color.rgb(29, 29, 31), Typeface.BOLD);
    }

    private TextView statusText() {
        TextView view = text("", 13, Color.rgb(110, 110, 115), Typeface.BOLD);
        view.setPadding(0, dp(10), 0, 0);
        return view;
    }

    private TextView text(String value, int size, int color, int style) {
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextSize(size);
        view.setTextColor(color);
        view.setTypeface(Typeface.create("sans", style));
        view.setLineSpacing(0, 1.12f);
        return view;
    }

    private EditText input(boolean password, int lines) {
        EditText input = new EditText(this);
        input.setTextSize(15);
        input.setTextColor(Color.rgb(29, 29, 31));
        input.setHintTextColor(Color.rgb(134, 134, 139));
        input.setPadding(dp(14), dp(12), dp(14), dp(12));
        input.setGravity(Gravity.TOP | Gravity.START);
        input.setSingleLine(lines == 1);
        input.setMinLines(lines);
        input.setMaxLines(lines);
        if (password) {
            input.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        }
        GradientDrawable background = new GradientDrawable();
        background.setColor(Color.rgb(242, 242, 247));
        background.setCornerRadius(dp(14));
        input.setBackground(background);
        return input;
    }

    private Button primaryButton(String label) {
        return styledButton(label, Color.rgb(0, 113, 227), Color.WHITE);
    }

    private Button secondaryButton(String label) {
        return styledButton(label, Color.rgb(235, 235, 240), Color.rgb(29, 29, 31));
    }

    private Button styledButton(String label, int backgroundColor, int textColor) {
        Button button = new Button(this);
        button.setText(label);
        button.setTextSize(15);
        button.setTextColor(textColor);
        button.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        button.setAllCaps(false);
        button.setPadding(dp(18), dp(10), dp(18), dp(10));
        GradientDrawable background = new GradientDrawable();
        background.setColor(backgroundColor);
        background.setCornerRadius(dp(999));
        button.setBackground(background);
        return button;
    }

    private View spacer(int height) {
        View spacer = new View(this);
        spacer.setLayoutParams(new LinearLayout.LayoutParams(1, dp(height)));
        return spacer;
    }

    private void addWithTop(LinearLayout parent, View child, int topDp) {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            LinearLayout.LayoutParams.WRAP_CONTENT
        );
        params.topMargin = dp(topDp);
        parent.addView(child, params);
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private void toast(int message) {
        Toast.makeText(this, message, Toast.LENGTH_SHORT).show();
    }
}
