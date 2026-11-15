plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

android {
    namespace = "org.spaceapps.healthmonitor"
    compileSdk = 35

    defaultConfig {
        applicationId = "org.spaceapps.healthmonitor"
        minSdk = 28            // Health Connect client requirement
        targetSdk = 35
        versionCode = 2
        versionName = "1.1"
        // Android emulator reaches the host machine (Docker) via 10.0.2.2
        buildConfigField("String", "DEFAULT_SERVER", "\"http://10.0.2.2:8000\"")
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            // Signed with the debug key so the APK installs by sideload at the hackathon.
            signingConfig = signingConfigs.getByName("debug")
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"))
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    buildFeatures {
        compose = true
        buildConfig = true
    }
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2024.12.01")
    implementation(composeBom)
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.7")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-core")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.health.connect:connect-client:1.1.0-alpha10")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.9.0")
    // exercise rep counting: camera preview + on-device pose detection (frames never leave the phone)
    implementation("androidx.camera:camera-core:1.4.1")
    implementation("androidx.camera:camera-camera2:1.4.1")
    implementation("androidx.camera:camera-lifecycle:1.4.1")
    implementation("androidx.camera:camera-view:1.4.1")
    implementation("com.google.mlkit:pose-detection:18.0.0-beta5")
    implementation("com.google.guava:guava:33.3.1-android")   // ListenableFuture used by CameraX
    debugImplementation("androidx.compose.ui:ui-tooling")
}
