import Foundation
import SwiftUI
import UIKit

/// Device pairing state. The device UUID is created once and kept; the operator matches it on the Devices page.
@MainActor
final class SessionStore: ObservableObject {
    @Published var serverURL: String { didSet { UserDefaults.standard.set(serverURL, forKey: "server"); api.baseURL = serverURL } }
    @Published private(set) var status: String = UserDefaults.standard.string(forKey: "status") ?? "not connected"
    @Published private(set) var callsign: String? = UserDefaults.standard.string(forKey: "callsign")
    @Published var message: String?

    let deviceUUID: String
    let api: APIClient
    var isAssigned: Bool { status == "assigned" }

    init() {
        let uuid = Keychain.read("device_uuid") ?? {
            let u = UUID().uuidString.lowercased()
            Keychain.save("device_uuid", u)
            return u
        }()
        deviceUUID = uuid
        let server = UserDefaults.standard.string(forKey: "server") ?? "http://192.168.1.20:8080"
        serverURL = server
        api = APIClient(baseURL: server, deviceUUID: uuid, deviceToken: Keychain.read("device_token"))
    }

    private func apply(_ d: DeviceInfo) {
        status = d.status
        callsign = d.callsign
        UserDefaults.standard.set(status, forKey: "status")
        UserDefaults.standard.set(callsign, forKey: "callsign")
    }

    func connect() async {
        do {
            let r = try await api.register(model: UIDevice.current.model, appVersion: Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "1.0")
            if let t = r.token { api.deviceToken = t; Keychain.save("device_token", t) }
            apply(r.device)
            message = isAssigned ? "Connected as \(callsign ?? "crew member")." : "Waiting for an operator to assign this phone."
        } catch {
            message = "Could not connect: \(error.localizedDescription)"
        }
    }

    func refresh() async {
        do { apply(try await api.me()) } catch let e as APIError {
            if e.statusCode == 401 { status = "not connected" }
            if e.statusCode == 403 { status = "revoked" }
            message = e.localizedDescription
        } catch { message = error.localizedDescription }
    }
}

enum Keychain {
    static func save(_ key: String, _ value: String) {
        delete(key)
        let q: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrAccount as String: key,
                                kSecValueData as String: Data(value.utf8),
                                kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly]
        SecItemAdd(q as CFDictionary, nil)
    }

    static func read(_ key: String) -> String? {
        let q: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrAccount as String: key,
                                kSecReturnData as String: true, kSecMatchLimit as String: kSecMatchLimitOne]
        var out: AnyObject?
        guard SecItemCopyMatching(q as CFDictionary, &out) == errSecSuccess, let d = out as? Data else { return nil }
        return String(data: d, encoding: .utf8)
    }

    static func delete(_ key: String) {
        SecItemDelete([kSecClass as String: kSecClassGenericPassword, kSecAttrAccount as String: key] as CFDictionary)
    }
}
