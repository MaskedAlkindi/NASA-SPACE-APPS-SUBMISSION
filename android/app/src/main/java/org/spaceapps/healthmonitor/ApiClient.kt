package org.spaceapps.healthmonitor

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

class ApiException(val code: Int, message: String) : Exception(message)

/**
 * HEALTH-01 device client (java.net + org.json, no extra dependencies).
 * The phone never logs in as a person: it enrols with its own device UUID, an operator assigns it to a crew member,
 * and uploads are sent with X-Device-UUID / X-Device-Token headers.
 */
class ApiClient(var baseUrl: String, var deviceUuid: String, var deviceToken: String? = null) {

    private suspend fun call(path: String, method: String = "GET", body: JSONObject? = null): JSONObject =
        withContext(Dispatchers.IO) {
            val url = URL(baseUrl.trimEnd('/', ' ') + "/api/v1" + path)
            val conn = (url.openConnection() as HttpURLConnection).apply {
                requestMethod = method
                connectTimeout = 10_000
                readTimeout = 30_000
                setRequestProperty("Content-Type", "application/json")
                setRequestProperty("X-Device-UUID", deviceUuid)
                deviceToken?.let { setRequestProperty("X-Device-Token", it) }
                if (body != null) {
                    doOutput = true
                    outputStream.use { it.write(body.toString().toByteArray()) }
                }
            }
            try {
                val code = conn.responseCode
                val stream = if (code in 200..299) conn.inputStream else conn.errorStream
                val text = stream?.bufferedReader()?.use { it.readText() } ?: ""
                if (code !in 200..299) {
                    val detail = runCatching { JSONObject(text).optString("detail", text) }.getOrDefault(text)
                    throw ApiException(code, detail)
                }
                JSONObject(text)
            } finally {
                conn.disconnect()
            }
        }

    suspend fun register(model: String, appVersion: String): JSONObject =
        call("/devices/register", "POST", JSONObject().put("device_uuid", deviceUuid).put("platform", "android")
            .put("model", model).put("app_version", appVersion))

    suspend fun me(): JSONObject = call("/devices/me")

    /** Canonical measurements (metric/unit/value/timestamp) and/or workouts in the exercise-module format. */
    suspend fun upload(measurements: List<JSONObject> = emptyList(), workouts: List<JSONObject> = emptyList()): JSONObject {
        val m = JSONArray(); measurements.forEach { m.put(it) }
        val w = JSONArray(); workouts.forEach { w.put(it) }
        return call("/devices/upload", "POST", JSONObject().put("measurements", m).put("workouts", w))
    }
}
