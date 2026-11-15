package org.spaceapps.healthmonitor

import android.content.Context
import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.permission.HealthPermission
import androidx.health.connect.client.records.BloodGlucoseRecord
import androidx.health.connect.client.records.BloodPressureRecord
import androidx.health.connect.client.records.BodyTemperatureRecord
import androidx.health.connect.client.records.ExerciseSessionRecord
import androidx.health.connect.client.records.HeartRateRecord
import androidx.health.connect.client.records.HeartRateVariabilityRmssdRecord
import androidx.health.connect.client.records.Record
import androidx.health.connect.client.records.RestingHeartRateRecord
import androidx.health.connect.client.records.SleepSessionRecord
import androidx.health.connect.client.records.StepsRecord
import androidx.health.connect.client.records.WeightRecord
import androidx.health.connect.client.request.AggregateGroupByPeriodRequest
import androidx.health.connect.client.request.ReadRecordsRequest
import androidx.health.connect.client.time.TimeRangeFilter
import org.json.JSONObject
import java.time.Duration
import java.time.Instant
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.Period
import java.time.ZoneId
import java.time.temporal.ChronoUnit
import kotlin.reflect.KClass

/** One implemented feature = one Health Connect READ permission, requested individually. */
data class HealthFeature(val metric: String, val title: String, val detail: String, val recordType: KClass<out Record>) {
    val permission: String get() = HealthPermission.getReadPermission(recordType)
}

class HealthConnectManager(private val context: Context) {

    val features = listOf(
        HealthFeature("heart_rate", "Heart rate", "Hourly averages", HeartRateRecord::class),
        HealthFeature("resting_heart_rate", "Resting heart rate", "Daily value", RestingHeartRateRecord::class),
        HealthFeature("hrv_rmssd", "Heart-rate variability (RMSSD)", "Daily average (kept separate from SDNN)", HeartRateVariabilityRmssdRecord::class),
        HealthFeature("sleep_duration", "Sleep", "Total sleep per night", SleepSessionRecord::class),
        HealthFeature("steps", "Steps", "Daily total", StepsRecord::class),
        HealthFeature("exercise_minutes", "Exercise sessions", "Minutes per day", ExerciseSessionRecord::class),
        HealthFeature("blood_pressure", "Blood pressure", "Daily average", BloodPressureRecord::class),
        HealthFeature("body_temperature", "Body temperature", "Daily average", BodyTemperatureRecord::class),
        HealthFeature("blood_glucose", "Blood glucose", "Daily average", BloodGlucoseRecord::class),
        HealthFeature("body_mass", "Body mass", "Daily average", WeightRecord::class),
    )

    /** SDK_AVAILABLE, SDK_UNAVAILABLE or SDK_UNAVAILABLE_PROVIDER_UPDATE_REQUIRED */
    val sdkStatus: Int get() = HealthConnectClient.getSdkStatus(context)
    val isAvailable: Boolean get() = sdkStatus == HealthConnectClient.SDK_AVAILABLE
    private val client by lazy { HealthConnectClient.getOrCreate(context) }

    suspend fun grantedPermissions(): Set<String> =
        if (isAvailable) client.permissionController.getGrantedPermissions() else emptySet()

    private val zone: ZoneId = ZoneId.systemDefault()

    private fun record(metric: String, unit: String, value: Double, ts: Instant, device: String): JSONObject =
        JSONObject()
            .put("metric", metric).put("unit", unit)
            .put("value", Math.round(value * 100) / 100.0)
            .put("timestamp", ts.toString())
            .put("source_device", device)
            .put("quality", "good")
            .put("external_id", "hc-$metric-${ts.truncatedTo(ChronoUnit.SECONDS)}")

    private fun at(day: LocalDate, hour: Int): Instant = day.atTime(hour, 0).atZone(zone).toInstant()

    /** Read the last [days] days for every GRANTED feature. Failures in one type never block the others. */
    suspend fun collect(days: Long = 14): Pair<List<JSONObject>, List<String>> {
        val granted = grantedPermissions()
        val out = mutableListOf<JSONObject>()
        val notes = mutableListOf<String>()
        val end = Instant.now()
        val startDay = LocalDate.now(zone).minusDays(days)
        val start = startDay.atStartOfDay(zone).toInstant()
        val range = TimeRangeFilter.between(start, end)
        val localRange = TimeRangeFilter.between(LocalDateTime.ofInstant(start, zone), LocalDateTime.ofInstant(end, zone))

        fun has(m: String) = features.first { it.metric == m }.permission in granted

        suspend fun safely(label: String, block: suspend () -> Unit) {
            try { block() } catch (e: Exception) { notes += "$label: ${e.message}" }
        }

        if (has("steps")) safely("steps") {
            val res = client.aggregateGroupByPeriod(AggregateGroupByPeriodRequest(setOf(StepsRecord.COUNT_TOTAL), localRange, Period.ofDays(1)))
            res.forEach { b -> b.result[StepsRecord.COUNT_TOTAL]?.let { out += record("steps", "count", it.toDouble(), at(b.startTime.toLocalDate(), 22), "Health Connect") } }
        }
        if (has("heart_rate")) safely("heart_rate") {
            val recs = client.readRecords(ReadRecordsRequest(HeartRateRecord::class, TimeRangeFilter.between(end.minus(Duration.ofDays(7)), end))).records
            recs.flatMap { it.samples }.groupBy { it.time.truncatedTo(ChronoUnit.HOURS) }
                .forEach { (hour, s) -> out += record("heart_rate", "bpm", s.map { it.beatsPerMinute }.average(), hour, "Health Connect") }
        }
        if (has("resting_heart_rate")) safely("resting_heart_rate") {
            client.readRecords(ReadRecordsRequest(RestingHeartRateRecord::class, range)).records
                .groupBy { it.time.atZone(zone).toLocalDate() }
                .forEach { (d, r) -> out += record("resting_heart_rate", "bpm", r.map { it.beatsPerMinute.toDouble() }.average(), at(d, 7), r.first().metadata.device?.model ?: "Health Connect") }
        }
        if (has("hrv_rmssd")) safely("hrv_rmssd") {
            client.readRecords(ReadRecordsRequest(HeartRateVariabilityRmssdRecord::class, range)).records
                .groupBy { it.time.atZone(zone).toLocalDate() }
                .forEach { (d, r) -> out += record("hrv_rmssd", "ms", r.map { it.heartRateVariabilityMillis }.average(), at(d, 7), "Health Connect") }
        }
        if (has("sleep_duration")) safely("sleep_duration") {
            // Merge overlapping sessions from different apps, attribute to wake-up date.
            val sessions = client.readRecords(ReadRecordsRequest(SleepSessionRecord::class, range)).records
                .map { it.startTime to it.endTime }.sortedBy { it.first }
            val merged = mutableListOf<Pair<Instant, Instant>>()
            for (s in sessions) {
                val last = merged.lastOrNull()
                if (last != null && !s.first.isAfter(last.second)) merged[merged.size - 1] = last.first to maxOf(last.second, s.second)
                else merged += s
            }
            merged.groupBy { it.second.atZone(zone).toLocalDate() }.forEach { (d, ss) ->
                val hours = ss.sumOf { Duration.between(it.first, it.second).toMinutes() } / 60.0
                if (hours in 0.5..16.0) out += record("sleep_duration", "h", hours, at(d, 7), "Health Connect")
            }
        }
        if (has("exercise_minutes")) safely("exercise_minutes") {
            client.readRecords(ReadRecordsRequest(ExerciseSessionRecord::class, range)).records
                .groupBy { it.startTime.atZone(zone).toLocalDate() }
                .forEach { (d, r) -> out += record("exercise_minutes", "min", r.sumOf { Duration.between(it.startTime, it.endTime).toMinutes() }.toDouble().coerceAtMost(600.0), at(d, 22), "Health Connect") }
        }
        if (has("blood_pressure")) safely("blood_pressure") {
            client.readRecords(ReadRecordsRequest(BloodPressureRecord::class, range)).records
                .groupBy { it.time.atZone(zone).toLocalDate() }
                .forEach { (d, r) ->
                    out += record("blood_pressure_systolic", "mmHg", r.map { it.systolic.inMillimetersOfMercury }.average(), at(d, 8), "Health Connect")
                    out += record("blood_pressure_diastolic", "mmHg", r.map { it.diastolic.inMillimetersOfMercury }.average(), at(d, 8), "Health Connect")
                }
        }
        if (has("body_temperature")) safely("body_temperature") {
            client.readRecords(ReadRecordsRequest(BodyTemperatureRecord::class, range)).records
                .groupBy { it.time.atZone(zone).toLocalDate() }
                .forEach { (d, r) -> out += record("body_temperature", "°C", r.map { it.temperature.inCelsius }.average(), at(d, 7), "Health Connect") }
        }
        if (has("blood_glucose")) safely("blood_glucose") {
            client.readRecords(ReadRecordsRequest(BloodGlucoseRecord::class, range)).records
                .groupBy { it.time.atZone(zone).toLocalDate() }
                .forEach { (d, r) -> out += record("blood_glucose", "mg/dL", r.map { it.level.inMilligramsPerDeciliter }.average(), at(d, 7), "Health Connect") }
        }
        if (has("body_mass")) safely("body_mass") {
            client.readRecords(ReadRecordsRequest(WeightRecord::class, range)).records
                .groupBy { it.time.atZone(zone).toLocalDate() }
                .forEach { (d, r) -> out += record("body_mass", "kg", r.map { it.weight.inKilograms }.average(), at(d, 7), "Health Connect") }
        }
        return out to notes
    }
}
