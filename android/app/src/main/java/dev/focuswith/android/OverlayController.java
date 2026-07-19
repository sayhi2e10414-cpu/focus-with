package dev.focuswith.android;

import android.content.Context;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.PixelFormat;
import android.graphics.drawable.GradientDrawable;
import android.provider.Settings;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.View;
import android.view.WindowManager;
import android.widget.LinearLayout;
import android.widget.TextView;

final class OverlayController {
    private final Context context;
    private final WindowManager windowManager;
    private LinearLayout capsule;
    private TextView titleView;
    private TextView timerView;
    private WindowManager.LayoutParams params;

    OverlayController(Context context) {
        this.context = context.getApplicationContext();
        windowManager = (WindowManager) context.getSystemService(Context.WINDOW_SERVICE);
    }

    void update(String title, String timer) {
        if (!Settings.canDrawOverlays(context)) {
            hide();
            return;
        }
        if (capsule == null) show();
        titleView.setText(title);
        timerView.setText(timer);
    }

    private void show() {
        capsule = new LinearLayout(context);
        capsule.setOrientation(LinearLayout.HORIZONTAL);
        capsule.setGravity(Gravity.CENTER_VERTICAL);
        int vertical = dp(10);
        int horizontal = dp(16);
        capsule.setPadding(horizontal, vertical, horizontal, vertical);
        GradientDrawable background = new GradientDrawable();
        background.setColor(Color.rgb(29, 29, 31));
        background.setCornerRadius(dp(28));
        capsule.setBackground(background);
        capsule.setElevation(dp(10));

        titleView = new TextView(context);
        titleView.setTextColor(Color.WHITE);
        titleView.setTextSize(13);
        titleView.setMaxWidth(dp(180));
        titleView.setSingleLine(true);
        titleView.setEllipsize(android.text.TextUtils.TruncateAt.END);
        capsule.addView(titleView);

        timerView = new TextView(context);
        timerView.setTextColor(Color.WHITE);
        timerView.setTextSize(16);
        timerView.setTypeface(android.graphics.Typeface.DEFAULT, android.graphics.Typeface.BOLD);
        LinearLayout.LayoutParams timerLayout = new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.WRAP_CONTENT,
            LinearLayout.LayoutParams.WRAP_CONTENT
        );
        timerLayout.leftMargin = dp(12);
        capsule.addView(timerView, timerLayout);

        params = new WindowManager.LayoutParams(
            WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE | WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
            PixelFormat.TRANSLUCENT
        );
        params.gravity = Gravity.TOP | Gravity.END;
        params.x = dp(12);
        params.y = dp(72);
        capsule.setOnTouchListener(new DragListener());
        capsule.setOnClickListener(view -> {
            Intent intent = new Intent(context, MainActivity.class)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP);
            context.startActivity(intent);
        });
        windowManager.addView(capsule, params);
    }

    void hide() {
        if (capsule == null) return;
        try {
            windowManager.removeView(capsule);
        } catch (IllegalArgumentException ignored) {
        }
        capsule = null;
        titleView = null;
        timerView = null;
        params = null;
    }

    private int dp(int value) {
        return Math.round(value * context.getResources().getDisplayMetrics().density);
    }

    private final class DragListener implements View.OnTouchListener {
        private float startRawX;
        private float startRawY;
        private int startX;
        private int startY;
        private boolean moved;

        @Override
        public boolean onTouch(View view, MotionEvent event) {
            if (params == null) return false;
            if (event.getAction() == MotionEvent.ACTION_DOWN) {
                startRawX = event.getRawX();
                startRawY = event.getRawY();
                startX = params.x;
                startY = params.y;
                moved = false;
                return true;
            }
            if (event.getAction() == MotionEvent.ACTION_MOVE) {
                float dx = event.getRawX() - startRawX;
                float dy = event.getRawY() - startRawY;
                moved = moved || Math.abs(dx) > dp(4) || Math.abs(dy) > dp(4);
                params.x = startX - Math.round(dx);
                params.y = startY + Math.round(dy);
                windowManager.updateViewLayout(capsule, params);
                return true;
            }
            if (event.getAction() == MotionEvent.ACTION_UP) {
                if (!moved) view.performClick();
                return true;
            }
            return false;
        }
    }
}
