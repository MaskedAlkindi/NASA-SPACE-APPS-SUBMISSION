package org.spaceapps.healthmonitor

import android.content.Context
import android.os.Build
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import java.util.UUID

/** Device pairing state. The device UUID is created once and kept; the operator matches it on the Devices page. */
class AppState(context: Context) {
    private val prefs = context.getSharedPreferences("health01", Context.MODE_PRIVATE)

    val deviceUuid: String = prefs.getString("device_uuid", null) ?: UUID.randomUUID().toString().also {
        prefs.edit().putString("device_uuid", it).apply()
    }
    var serverUrl by mutableStateOf(prefs.getString("server", BuildConfig.DEFAULT_SERVER)!!)
        private set
    var status by mutableStateOf(prefs.getString("status", "not connected")!!)   // not connected | pending | assigned | revoked
        private set
    var callsign by mutableStateOf(prefs.getString("callsign", null))
        private set
    var lastMessage by mutableStateOf<String?>(null)
    var autoSync by mutableStateOf(prefs.getBoolean("autosync", true))
        private set
    var showTour by mutableStateOf(!prefs.getBoolean("tour", false))
        private set
    var lastSyncMessage by mutableStateOf<String?>(null)

    val api = ApiClient(serverUrl, deviceUuid, prefs.getString("token", null))
    val assigned get() = status == "assigned"

    fun updateAutoSync(on: Boolean) {
        autoSync = on
        prefs.edit().putBoolean("autosync", on).apply()
    }

    fun closeTour() {
        showTour = false
        prefs.edit().putBoolean("tour", true).apply()
    }

    fun openTour() { showTour = true }

    fun setServer(url: String) {
        serverUrl = url.trim()
        api.baseUrl = serverUrl
        prefs.edit().putString("server", serverUrl).apply()
    }

    private fun apply(device: org.json.JSONObject) {
        status = device.optString("status", "pending")
        callsign = device.optString("callsign").takeIf { it.isNotBlank() && it != "null" }
        prefs.edit().putString("status", status).putString("callsign", callsign).apply()
    }

    /** Enrol (first time) or refresh status. */
    suspend fun connect() {
        val r = api.register("${Build.MANUFACTURER} ${Build.MODEL}", BuildConfig.VERSION_NAME)
        r.optString("token").takeIf { it.isNotBlank() && it != "null" }?.let {
            api.deviceToken = it
            prefs.edit().putString("token", it).apply()
        }
        apply(r.getJSONObject("device"))
        lastMessage = if (assigned) "Connected as $callsign." else "Waiting for an operator to assign this phone."
    }

    suspend fun refresh() {
        try {
            apply(api.me().getJSONObject("device"))
        } catch (e: ApiException) {
            if (e.code == 401) { status = "not connected"; prefs.edit().putString("status", status).apply() }
            if (e.code == 403) { status = "revoked"; prefs.edit().putString("status", status).apply() }
            lastMessage = e.message
        }
    }
}
