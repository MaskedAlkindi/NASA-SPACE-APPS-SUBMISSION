import Foundation
import HealthKit

/// Reads only the HealthKit types HEALTH-01 implements, each requested individually by the user.
/// Note: HealthKit never reveals whether READ access was denied - a type with no data may be
/// denied, or simply not recorded by this iPhone / Apple Watch model.
@MainActor
final class HealthKitManager: ObservableObject {
    struct Feature: Identifiable {
        let id: String              // HEALTH-01 metric
        let title: String
        let detail: String
        let type: HKObjectType
    }

    static let features: [Feature] = [
        Feature(id: "heart_rate", title: "Heart rate", detail: "Hourly averages", type: HKQuantityType(.heartRate)),
        Feature(id: "resting_heart_rate", title: "Resting heart rate", detail: "Daily value (Apple Watch)", type: HKQuantityType(.restingHeartRate)),
        Feature(id: "hrv_sdnn", title: "Heart-rate variability (SDNN)", detail: "Daily average (Apple Watch)", type: HKQuantityType(.heartRateVariabilitySDNN)),
        Feature(id: "sleep_duration", title: "Sleep", detail: "Total asleep time per night", type: HKCategoryType(.sleepAnalysis)),
        Feature(id: "steps", title: "Steps", detail: "Daily total", type: HKQuantityType(.stepCount)),
        Feature(id: "exercise_minutes", title: "Exercise minutes", detail: "Daily Apple exercise time", type: HKQuantityType(.appleExerciseTime)),
        Feature(id: "blood_pressure_systolic", title: "Blood pressure (systolic)", detail: "Daily average", type: HKQuantityType(.bloodPressureSystolic)),
        Feature(id: "blood_pressure_diastolic", title: "Blood pressure (diastolic)", detail: "Daily average", type: HKQuantityType(.bloodPressureDiastolic)),
        Feature(id: "body_temperature", title: "Body temperature", detail: "Daily average", type: HKQuantityType(.bodyTemperature)),
        Feature(id: "blood_glucose", title: "Blood glucose", detail: "Daily average", type: HKQuantityType(.bloodGlucose)),
        Feature(id: "body_mass", title: "Body mass", detail: "Daily average", type: HKQuantityType(.bodyMass)),
    ]

    @Published var requested: Set<String> = Set(UserDefaults.standard.stringArray(forKey: "hk.requested") ?? [])
    @Published var lastSync: Date? = UserDefaults.standard.object(forKey: "hk.lastSync") as? Date
    @Published var syncMessage: String?
    @Published var isSyncing = false

    private let store = HKHealthStore()
    var isAvailable: Bool { HKHealthStore.isHealthDataAvailable() }

    /// Request READ authorisation for exactly one feature (no write access is ever requested).
    func request(_ feature: Feature) async {
        guard isAvailable else { syncMessage = "Health data is not available on this device."; return }
        do {
            try await store.requestAuthorization(toShare: [], read: [feature.type])
            requested.insert(feature.id)
            UserDefaults.standard.set(Array(requested), forKey: "hk.requested")
        } catch {
            syncMessage = "Authorisation failed: \(error.localizedDescription)"
        }
    }

    // MARK: - Reading

    private func dailyStatistic(_ id: HKQuantityTypeIdentifier, unit: HKUnit, options: HKStatisticsOptions,
                                days: Int, interval: DateComponents = DateComponents(day: 1)) async throws -> [(Date, Double)] {
        let type = HKQuantityType(id)
        let cal = Calendar.current
        let end = Date()
        let start = cal.startOfDay(for: cal.date(byAdding: .day, value: -days, to: end)!)
        let predicate = HKQuery.predicateForSamples(withStart: start, end: end)
        return try await withCheckedThrowingContinuation { cont in
            let q = HKStatisticsCollectionQuery(quantityType: type, quantitySamplePredicate: predicate, options: options,
                                                anchorDate: start, intervalComponents: interval)
            q.initialResultsHandler = { _, results, error in
                if let error { cont.resume(throwing: error); return }
                var out: [(Date, Double)] = []
                results?.enumerateStatistics(from: start, to: end) { s, _ in
                    let q = options.contains(.cumulativeSum) ? s.sumQuantity() : s.averageQuantity()
                    if let q { out.append((s.startDate, q.doubleValue(for: unit))) }
                }
                cont.resume(returning: out)
            }
            store.execute(q)
        }
    }

    /// Total asleep hours per night, keyed by wake-up day. Overlapping samples from several
    /// sources (iPhone + Watch) are merged so time is not double-counted.
    private func sleepPerNight(days: Int) async throws -> [(Date, Double)] {
        let type = HKCategoryType(.sleepAnalysis)
        let start = Calendar.current.date(byAdding: .day, value: -days, to: Date())!
        let predicate = HKQuery.predicateForSamples(withStart: start, end: Date())
        let samples: [HKCategorySample] = try await withCheckedThrowingContinuation { cont in
            let q = HKSampleQuery(sampleType: type, predicate: predicate, limit: HKObjectQueryNoLimit,
                                  sortDescriptors: [NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: true)]) { _, s, e in
                if let e { cont.resume(throwing: e) } else { cont.resume(returning: (s as? [HKCategorySample]) ?? []) }
            }
            store.execute(q)
        }
        let asleep = Set(HKCategoryValueSleepAnalysis.allAsleepValues.map(\.rawValue))
        let intervals = samples.filter { asleep.contains($0.value) }.map { ($0.startDate, $0.endDate) }
        var merged: [(Date, Date)] = []
        for iv in intervals.sorted(by: { $0.0 < $1.0 }) {
            if let last = merged.last, iv.0 <= last.1 { merged[merged.count - 1].1 = max(last.1, iv.1) } else { merged.append(iv) }
        }
        var byDay: [Date: Double] = [:]
        for (s, e) in merged {
            let day = Calendar.current.startOfDay(for: e)   // attribute to wake-up date
            byDay[day, default: 0] += e.timeIntervalSince(s) / 3600
        }
        return byDay.sorted { $0.key < $1.key }.map { ($0.key, $0.value) }
    }

    /// Collect authorised measurements for the last `days` days as canonical HEALTH-01 records.
    func collect(days: Int = 14) async -> [UploadMeasurement] {
        var out: [UploadMeasurement] = []
        let fmt = ISO8601DateFormatter()
        func add(_ metric: String, _ unit: String, _ rows: [(Date, Double)], at hour: Int?) {
            for (d, v) in rows {
                var ts = d
                if let hour { ts = Calendar.current.date(bySettingHour: hour, minute: 0, second: 0, of: d) ?? d }
                out.append(UploadMeasurement(metric: metric, value: (v * 100).rounded() / 100, unit: unit, timestamp: ts,
                                             sourceDevice: "Apple Health", externalId: "hk-\(metric)-\(fmt.string(from: ts))", quality: "good"))
            }
        }
        let bpm = HKUnit.count().unitDivided(by: .minute())
        // Each block is independent: a missing permission or unsupported type never blocks the others.
        if requested.contains("heart_rate"), let r = try? await dailyStatistic(.heartRate, unit: bpm, options: .discreteAverage, days: min(days, 7), interval: DateComponents(hour: 1)) {
            add("heart_rate", "bpm", r.filter { $0.1 >= 25 && $0.1 <= 230 }, at: nil)
        }
        if requested.contains("resting_heart_rate"), let r = try? await dailyStatistic(.restingHeartRate, unit: bpm, options: .discreteAverage, days: days) {
            add("resting_heart_rate", "bpm", r, at: 7)
        }
        if requested.contains("hrv_sdnn"), let r = try? await dailyStatistic(.heartRateVariabilitySDNN, unit: .secondUnit(with: .milli), options: .discreteAverage, days: days) {
            add("hrv_sdnn", "ms", r, at: 7)
        }
        if requested.contains("steps"), let r = try? await dailyStatistic(.stepCount, unit: .count(), options: .cumulativeSum, days: days) {
            add("steps", "count", r, at: 22)
        }
        if requested.contains("exercise_minutes"), let r = try? await dailyStatistic(.appleExerciseTime, unit: .minute(), options: .cumulativeSum, days: days) {
            add("exercise_minutes", "min", r, at: 22)
        }
        let mmHg = HKUnit.millimeterOfMercury()
        if requested.contains("blood_pressure_systolic"), let r = try? await dailyStatistic(.bloodPressureSystolic, unit: mmHg, options: .discreteAverage, days: days) {
            add("blood_pressure_systolic", "mmHg", r, at: 8)
        }
        if requested.contains("blood_pressure_diastolic"), let r = try? await dailyStatistic(.bloodPressureDiastolic, unit: mmHg, options: .discreteAverage, days: days) {
            add("blood_pressure_diastolic", "mmHg", r, at: 8)
        }
        if requested.contains("body_temperature"), let r = try? await dailyStatistic(.bodyTemperature, unit: .degreeCelsius(), options: .discreteAverage, days: days) {
            add("body_temperature", "°C", r, at: 7)
        }
        if requested.contains("blood_glucose"), let r = try? await dailyStatistic(.bloodGlucose, unit: HKUnit(from: "mg/dL"), options: .discreteAverage, days: days) {
            add("blood_glucose", "mg/dL", r, at: 7)
        }
        if requested.contains("body_mass"), let r = try? await dailyStatistic(.bodyMass, unit: .gramUnit(with: .kilo), options: .discreteAverage, days: days) {
            add("body_mass", "kg", r, at: 7)
        }
        if requested.contains("sleep_duration"), let r = try? await sleepPerNight(days: days) {
            add("sleep_duration", "h", r.filter { $0.1 > 0.5 && $0.1 < 16 }, at: 7)
        }
        return out
    }

    func sync(using api: APIClient) async {
        isSyncing = true
        defer { isSyncing = false }
        let items = await collect()
        guard !items.isEmpty else {
            syncMessage = "No authorised HealthKit data found (permissions may be denied, or this device doesn't record these types)."
            return
        }
        do {
            var accepted = 0, updated = 0, rejected = 0
            for chunk in stride(from: 0, to: items.count, by: 500).map({ Array(items[$0..<min($0 + 500, items.count)]) }) {
                let r = try await api.upload(chunk)
                accepted += r.accepted; updated += r.updated; rejected += r.rejected
            }
            lastSync = Date()
            UserDefaults.standard.set(lastSync, forKey: "hk.lastSync")
            syncMessage = "Uploaded \(accepted) new, \(updated) updated, \(rejected) rejected."
        } catch {
            syncMessage = "Upload failed: \(error.localizedDescription)"
        }
    }
}
