import Foundation

enum APIError: LocalizedError {
    case http(Int, String)
    case invalidURL

    var errorDescription: String? {
        switch self {
        case .http(let code, let msg): return "Server error \(code): \(msg)"
        case .invalidURL: return "Invalid server address"
        }
    }

    var statusCode: Int? { if case .http(let c, _) = self { return c } else { return nil } }
}

/// HEALTH-01 device client. The phone never logs in as a person: it enrols with its own device UUID,
/// an operator assigns it to a crew member, and uploads carry X-Device-UUID / X-Device-Token.
final class APIClient {
    var baseURL: String
    let deviceUUID: String
    var deviceToken: String?

    private let decoder: JSONDecoder = {
        let d = JSONDecoder()
        d.keyDecodingStrategy = .convertFromSnakeCase
        return d
    }()
    private let encoder: JSONEncoder = {
        let e = JSONEncoder()
        e.keyEncodingStrategy = .convertToSnakeCase
        e.dateEncodingStrategy = .iso8601
        return e
    }()
    private let session: URLSession = {
        let cfg = URLSessionConfiguration.default
        cfg.timeoutIntervalForRequest = 30
        return URLSession(configuration: cfg)
    }()

    init(baseURL: String, deviceUUID: String, deviceToken: String?) {
        self.baseURL = baseURL
        self.deviceUUID = deviceUUID
        self.deviceToken = deviceToken
    }

    private func request(_ path: String, method: String = "GET", body: Data? = nil) async throws -> Data {
        let trimmed = baseURL.trimmingCharacters(in: CharacterSet(charactersIn: "/ "))
        guard let url = URL(string: "\(trimmed)/api/v1\(path)") else { throw APIError.invalidURL }
        var req = URLRequest(url: url)
        req.httpMethod = method
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.setValue(deviceUUID, forHTTPHeaderField: "X-Device-UUID")
        if let deviceToken { req.setValue(deviceToken, forHTTPHeaderField: "X-Device-Token") }
        req.httpBody = body
        let (data, resp) = try await session.data(for: req)
        let code = (resp as? HTTPURLResponse)?.statusCode ?? 0
        guard (200..<300).contains(code) else {
            let detail = (try? JSONSerialization.jsonObject(with: data) as? [String: Any])?["detail"] as? String
            throw APIError.http(code, detail ?? HTTPURLResponse.localizedString(forStatusCode: code))
        }
        return data
    }

    private func post<T: Decodable, B: Encodable>(_ path: String, _ body: B) async throws -> T {
        try decoder.decode(T.self, from: try await request(path, method: "POST", body: try encoder.encode(body)))
    }

    func register(model: String, appVersion: String) async throws -> RegisterResponse {
        struct Body: Encodable { let deviceUuid: String; let platform: String; let model: String; let appVersion: String }
        return try await post("/devices/register", Body(deviceUuid: deviceUUID, platform: "ios", model: model, appVersion: appVersion))
    }

    func me() async throws -> DeviceInfo {
        struct Wrap: Decodable { let device: DeviceInfo }
        return try decoder.decode(Wrap.self, from: try await request("/devices/me")).device
    }

    /// Canonical measurements from HealthKit.
    func upload(_ items: [UploadMeasurement]) async throws -> DeviceUploadResult {
        struct Body: Encodable { let measurements: [UploadMeasurement]; let workouts: [Workout] }
        return try await post("/devices/upload", Body(measurements: items, workouts: []))
    }

    /// Workouts in the exercise-module format (camera rep counts).
    func upload(workouts: [Workout]) async throws -> DeviceUploadResult {
        struct Body: Encodable { let measurements: [UploadMeasurement]; let workouts: [Workout] }
        return try await post("/devices/upload", Body(measurements: [], workouts: workouts))
    }
}
