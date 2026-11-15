import Foundation
import CoreGraphics

// MARK: - Device pairing

struct DeviceInfo: Codable, Equatable {
    let deviceUuid: String
    let platform: String
    let status: String            // pending | assigned | revoked
    let astronautId: String?
    let callsign: String?
    let uploads: Int?
}

struct RegisterResponse: Codable {
    let device: DeviceInfo
    let token: String?            // only returned when a new device secret is issued
}

struct DeviceUploadResult: Codable {
    let accepted: Int
    let updated: Int
    let workouts: Int
    let rejected: Int
    let errors: [String]
}

/// Canonical HEALTH-01 measurement (metric/unit/value/timestamp).
struct UploadMeasurement: Codable {
    let metric: String
    let value: Double
    let unit: String
    let timestamp: Date
    let sourceDevice: String
    let externalId: String
    let quality: String
}

/// Workout in the exercise module's format.
struct Workout: Codable {
    struct WorkSet: Codable { let reps: Int }
    struct Performed: Codable { let exerciseId: String; let sets: [WorkSet] }
    let source: String            // "camera"
    let startedAt: Date
    let endedAt: Date
    let exercises: [Performed]
    let clientId: String
}

// MARK: - Rep counting (same movements and rules as the website, Android and the server)

/// How a movement is measured. Distances are divided by torso length, so camera distance doesn't matter.
enum Signal { case kneeAngle, minKneeAngle, elbowAngle, elbowAngleAny, armElevation, kneeLift }

enum Movement: String, CaseIterable, Identifiable {
    case squat = "squat", sumoSquat = "sumo_squat", lunge = "forward_lunge", pushup = "pushup", armRaise = "arm_raise",
         shoulderPress = "shoulder_press", bicepCurl = "bicep_curl", jumpingJack = "jumping_jack", highKnees = "high_knees"
    var id: String { rawValue }

    /// (title, cue, signal, readyHigh, ready, work). readyHigh: a larger value is the resting pose.
    private var spec: (String, String, Signal, Bool, CGFloat, CGFloat) {
        switch self {
        case .squat: ("Squats", "Side-on, whole body in view.", .kneeAngle, true, 155, 110)
        case .sumoSquat: ("Wide squats", "Face the camera, wide stance.", .kneeAngle, true, 155, 115)
        case .lunge: ("Lunges", "Side-on, step forward and lower.", .minKneeAngle, true, 155, 105)
        case .pushup: ("Push-ups", "Side-on, camera low.", .elbowAngleAny, true, 150, 100)
        case .armRaise: ("Arm raises", "Face the camera, raise arms to shoulder height.", .armElevation, false, 0.12, 0.48)
        case .shoulderPress: ("Shoulder press", "Face the camera, hands from shoulders to overhead.", .armElevation, false, 0.24, 0.8)
        case .bicepCurl: ("Biceps curls", "Face the camera, elbows by your sides.", .elbowAngle, true, 145, 65)
        case .jumpingJack: ("Jumping jacks", "Face the camera, arms overhead.", .armElevation, false, -0.2, 0.6)
        case .highKnees: ("High knees", "Face the camera, knee to hip height.", .kneeLift, false, -0.56, -0.16)
        }
    }
    var title: String { spec.0 }
    var cue: String { spec.1 }
    var signal: Signal { spec.2 }
    var readyHigh: Bool { spec.3 }
    var ready: CGFloat { spec.4 }
    var work: CGFloat { spec.5 }
}

/// A body point in normalised image coordinates (y grows downwards) with the detector's confidence.
struct BodyPoint { let x: CGFloat; let y: CGFloat; let score: Float }

/// Counts repetitions with hysteresis so jitter is not counted. Low-confidence points are ignored.
final class RepCounter {
    private(set) var reps = 0
    private(set) var feedback = "Get into view"
    private var inRep = false
    let movement: Movement

    init(_ movement: Movement) { self.movement = movement }

    private func angle(_ a: BodyPoint, _ b: BodyPoint, _ c: BodyPoint) -> CGFloat? {
        let v1 = CGVector(dx: a.x - b.x, dy: a.y - b.y), v2 = CGVector(dx: c.x - b.x, dy: c.y - b.y)
        let d = hypot(v1.dx, v1.dy) * hypot(v2.dx, v2.dy)
        guard d > 0 else { return nil }
        return acos(max(-1, min(1, (v1.dx * v2.dx + v1.dy * v2.dy) / d))) * 180 / .pi
    }

    private func ok(_ p: [String: BodyPoint], _ keys: String...) -> Bool { keys.allSatisfy { (p[$0]?.score ?? 0) >= 0.5 } }

    private func torso(_ p: [String: BodyPoint]) -> CGFloat? {
        let t = ["l", "r"].filter { ok(p, "shoulder_\($0)", "hip_\($0)") }.map { abs(p["hip_\($0)"]!.y - p["shoulder_\($0)"]!.y) }
        guard !t.isEmpty else { return nil }
        return max(0.02, t.reduce(0, +) / CGFloat(t.count))
    }

    private func joints(_ p: [String: BodyPoint], _ a: String, _ b: String, _ c: String) -> [CGFloat] {
        ["l", "r"].filter { ok(p, "\(a)_\($0)", "\(b)_\($0)", "\(c)_\($0)") }
            .compactMap { angle(p["\(a)_\($0)"]!, p["\(b)_\($0)"]!, p["\(c)_\($0)"]!) }
    }

    private func value(_ p: [String: BodyPoint]) -> CGFloat? {
        switch movement.signal {
        case .kneeAngle:
            let a = joints(p, "hip", "knee", "ankle")
            return a.isEmpty ? nil : a.reduce(0, +) / CGFloat(a.count)
        case .minKneeAngle:
            return joints(p, "hip", "knee", "ankle").min()
        case .elbowAngle:
            let a = joints(p, "shoulder", "elbow", "wrist")
            return a.count == 2 ? (a[0] + a[1]) / 2 : nil
        case .elbowAngleAny:
            return joints(p, "shoulder", "elbow", "wrist").min()
        case .armElevation:
            guard let t = torso(p), ok(p, "shoulder_l", "shoulder_r", "wrist_l", "wrist_r") else { return nil }
            return ((p["shoulder_l"]!.y - p["wrist_l"]!.y) + (p["shoulder_r"]!.y - p["wrist_r"]!.y)) / 2 / t
        case .kneeLift:
            guard let t = torso(p) else { return nil }
            let l = ["l", "r"].filter { ok(p, "hip_\($0)", "knee_\($0)") }.map { p["hip_\($0)"]!.y - p["knee_\($0)"]!.y }
            return l.max().map { $0 / t }
        }
    }

    @discardableResult
    func update(_ p: [String: BodyPoint]) -> Int {
        guard let v = value(p) else { feedback = "Step back so the whole body is in view"; return reps }
        let atWork = movement.readyHigh ? v <= movement.work : v >= movement.work
        let atReady = movement.readyHigh ? v >= movement.ready : v <= movement.ready
        if !inRep && atWork { inRep = true; feedback = "Good, now back to the start" }
        else if inRep && atReady { inRep = false; reps += 1; feedback = "Rep \(reps)" }
        else if !inRep { feedback = "Go" }
        return reps
    }
}
