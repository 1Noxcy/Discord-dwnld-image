// Configuration du module "app" : c'est ici que sont listées les bibliothèques utilisées.
plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

android {
    namespace = "com.jarvis.assistant"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.jarvis.assistant"
        minSdk = 26          // Android 8.0 minimum (requis par le SDK Anthropic / Jackson)
        targetSdk = 35
        versionCode = 1
        versionName = "0.1-phase1"
    }

    // Clé de signature "debug" fixe, partagée entre les compilations (PC ou GitHub) :
    // sans elle, chaque nouvel APK refuserait de s'installer par-dessus l'ancien.
    // ⚠️ Usage personnel/développement uniquement, pas pour publier sur le Play Store.
    signingConfigs {
        getByName("debug") {
            storeFile = file("jarvis-debug.keystore")
            storePassword = "android"
            keyAlias = "androiddebugkey"
            keyPassword = "android"
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
    buildFeatures {
        compose = true
    }

    // Plusieurs bibliothèques Java embarquent les mêmes fichiers de licence :
    // on les ignore pour éviter les conflits à l'assemblage de l'APK.
    packaging {
        resources {
            excludes += setOf(
                "/META-INF/{AL2.0,LGPL2.1}",
                "META-INF/DEPENDENCIES",
                "META-INF/LICENSE*",
                "META-INF/NOTICE*",
                "META-INF/INDEX.LIST",
                "META-INF/*.kotlin_module",
                "META-INF/versions/**",
            )
        }
    }
}

dependencies {
    // Interface (Jetpack Compose)
    val composeBom = platform("androidx.compose:compose-bom:2024.12.01")
    implementation(composeBom)
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.7")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.7")

    // Coroutines (travail en arrière-plan sans bloquer l'écran)
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.9.0")

    // SDK officiel Anthropic (Java, utilisable depuis Kotlin) pour parler à Claude
    implementation("com.anthropic:anthropic-java:3.6.0")
}
