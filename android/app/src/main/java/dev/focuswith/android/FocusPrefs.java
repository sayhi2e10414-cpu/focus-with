package dev.focuswith.android;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;

import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;

import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

final class FocusPrefs {
    private static final String PREFS = "focuswith_companion";
    private static final String KEY_ALIAS = "focuswith_phone_token";
    private static final String TOKEN = "phone_token_ciphertext";
    private static final String DEFAULT_APPS = String.join("\n",
        "小红书 | com.xingin.xhs",
        "抖音 | com.ss.android.ugc.aweme",
        "哔哩哔哩 | tv.danmaku.bili",
        "微博 | com.sina.weibo",
        "快手 | com.smile.gifmaker",
        "Instagram | com.instagram.android",
        "TikTok | com.zhiliaoapp.musically"
    );

    private final SharedPreferences prefs;

    FocusPrefs(Context context) {
        prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    String serverUrl() {
        return prefs.getString("server_url", "");
    }

    void setServerUrl(String value) {
        String normalized = value.trim().replaceAll("/+$", "");
        prefs.edit().putString("server_url", normalized).apply();
    }

    String monitoredAppsText() {
        return prefs.getString("monitored_apps", DEFAULT_APPS);
    }

    void setMonitoredAppsText(String value) {
        prefs.edit().putString("monitored_apps", value.trim()).apply();
    }

    Map<String, String> monitoredPackages() {
        return parseMonitoredApps(monitoredAppsText());
    }

    static Map<String, String> parseMonitoredApps(String raw) {
        Map<String, String> result = new LinkedHashMap<>();
        for (String line : raw.split("\\R")) {
            String clean = line.trim();
            if (clean.isEmpty()) continue;
            String[] parts = clean.split("\\s*[|｜]\\s*", 2);
            if (parts.length != 2) continue;
            String name = parts[0].trim();
            String packageName = parts[1].trim();
            if (!name.isEmpty() && packageName.matches("[A-Za-z0-9_.]+")) {
                result.put(packageName, name);
            }
        }
        return result;
    }

    boolean overlayEnabled() {
        return prefs.getBoolean("overlay_enabled", false);
    }

    void setOverlayEnabled(boolean enabled) {
        prefs.edit().putBoolean("overlay_enabled", enabled).apply();
    }

    boolean monitorRunning() {
        return prefs.getBoolean("monitor_running", false);
    }

    void setMonitorRunning(boolean running) {
        prefs.edit().putBoolean("monitor_running", running).apply();
    }

    String deviceId() {
        String existing = prefs.getString("device_id", "");
        if (existing != null && !existing.isEmpty()) return existing;
        String created = "android-" + UUID.randomUUID().toString().substring(0, 12);
        prefs.edit().putString("device_id", created).commit();
        return created;
    }

    void setPhoneToken(String token) throws Exception {
        if (token.trim().isEmpty()) {
            prefs.edit().remove(TOKEN).apply();
            return;
        }
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.ENCRYPT_MODE, getOrCreateKey());
        byte[] encrypted = cipher.doFinal(token.trim().getBytes(StandardCharsets.UTF_8));
        byte[] packed = new byte[cipher.getIV().length + encrypted.length];
        System.arraycopy(cipher.getIV(), 0, packed, 0, cipher.getIV().length);
        System.arraycopy(encrypted, 0, packed, cipher.getIV().length, encrypted.length);
        prefs.edit().putString(TOKEN, Base64.encodeToString(packed, Base64.NO_WRAP)).apply();
    }

    String phoneToken() {
        String encoded = prefs.getString(TOKEN, "");
        if (encoded == null || encoded.isEmpty()) return "";
        try {
            byte[] packed = Base64.decode(encoded, Base64.NO_WRAP);
            if (packed.length < 13) return "";
            byte[] iv = new byte[12];
            byte[] encrypted = new byte[packed.length - iv.length];
            System.arraycopy(packed, 0, iv, 0, iv.length);
            System.arraycopy(packed, iv.length, encrypted, 0, encrypted.length);
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.DECRYPT_MODE, getOrCreateKey(), new GCMParameterSpec(128, iv));
            return new String(cipher.doFinal(encrypted), StandardCharsets.UTF_8);
        } catch (Exception ignored) {
            return "";
        }
    }

    private SecretKey getOrCreateKey() throws Exception {
        KeyStore store = KeyStore.getInstance("AndroidKeyStore");
        store.load(null);
        KeyStore.Entry entry = store.getEntry(KEY_ALIAS, null);
        if (entry instanceof KeyStore.SecretKeyEntry) {
            return ((KeyStore.SecretKeyEntry) entry).getSecretKey();
        }
        KeyGenerator generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
        generator.init(new KeyGenParameterSpec.Builder(
            KEY_ALIAS,
            KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT
        ).setBlockModes(KeyProperties.BLOCK_MODE_GCM)
            .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
            .setKeySize(256)
            .build());
        return generator.generateKey();
    }
}
