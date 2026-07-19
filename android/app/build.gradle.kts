plugins {
    id("com.android.application")
}

android {
    namespace = "dev.focuswith.android"
    compileSdk = 35

    defaultConfig {
        applicationId = "dev.focuswith.android"
        minSdk = 26
        targetSdk = 35
        versionCode = 6
        versionName = "0.4.2"
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    lint {
        abortOnError = true
        checkReleaseBuilds = true
    }
}
