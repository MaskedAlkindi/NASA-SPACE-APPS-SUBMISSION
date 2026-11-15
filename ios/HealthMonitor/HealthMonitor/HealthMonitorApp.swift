import SwiftUI
import UIKit

/// HEALTH-01 phone app, kept simple on purpose: connect to a crew server, collect wearable data, count exercise reps.
/// Dashboards, alerts and the assistant live on the website / desktop app.
@main
struct HealthMonitorApp: App {
    @StateObject private var session = SessionStore()
    @StateObject private var health = HealthKitManager()

    var body: some Scene {
        WindowGroup {
            RootTabView()
                .environmentObject(session)
                .environmentObject(health)
                .preferredColorScheme(.light)
                .tint(Theme.accent)
        }
    }
}

struct RootTabView: View {
    @EnvironmentObject var session: SessionStore
    @EnvironmentObject var health: HealthKitManager
    @Environment(\.scenePhase) private var scenePhase
    @AppStorage("autosync") private var autoSync = true
    @AppStorage("tour.seen") private var tourSeen = false
    @AppStorage("tour.nudge") private var tourNudge = 0
    @State private var tab = 0
    @State private var showTour = false

    init() {
        let bar = UITabBarAppearance()
        bar.configureWithOpaqueBackground()
        bar.backgroundColor = UIColor(red: 0.984, green: 0.988, blue: 0.996, alpha: 1)
        bar.shadowColor = UIColor(red: 0.09, green: 0.098, blue: 0.122, alpha: 1)
        UITabBar.appearance().standardAppearance = bar
        UITabBar.appearance().scrollEdgeAppearance = bar
    }

    var body: some View {
        TabView(selection: $tab) {
            ConnectView().tabItem { Label("Connect", systemImage: "antenna.radiowaves.left.and.right") }.tag(0)
            HealthView().tabItem { Label("Health", systemImage: "heart.text.square") }.tag(1)
            ExerciseView().tabItem { Label("Exercise", systemImage: "figure.strengthtraining.functional") }.tag(2)
        }
        .onAppear {
            if session.isAssigned { tab = 1 }
            if !tourSeen { showTour = true }
        }
        .onChange(of: tourNudge) { _, _ in showTour = true }
        .task(id: "\(autoSync)-\(session.status)-\(scenePhase == .active)") {
            guard autoSync, session.isAssigned, scenePhase == .active else { return }
            while !Task.isCancelled {
                if !health.requested.isEmpty { await health.sync(using: session.api) }
                try? await Task.sleep(for: .seconds(5 * 60))
            }
        }
        .overlay {
            if showTour {
                Walkthrough {
                    showTour = false
                    tourSeen = true
                }
            }
        }
    }
}

/// Three short steps, shown once. Connect can open it again.
struct Walkthrough: View {
    var onDone: () -> Void
    @State private var step = 0

    private let steps: [(String, String, String)] = [
        ("01", "Connect this phone", "Type the HEALTH-01 server address and tap Connect. Copy the device ID so someone can assign this phone to you on the Devices page."),
        ("02", "Health uploads itself", "Allow the Apple Health types you want. While the app is open and this phone is assigned, those readings upload about every 5 minutes. You can still sync by hand."),
        ("03", "Count reps on camera", "Exercise fills the screen. Blue lines follow your body. Pick a movement, tap Start, and the count is saved when you stop."),
    ]

    var body: some View {
        ZStack {
            Color.black.opacity(0.35).ignoresSafeArea()
            VStack(alignment: .leading, spacing: 14) {
                Text(steps[step].0).font(.system(size: 12, weight: .semibold, design: .monospaced)).tracking(1.4).foregroundStyle(Theme.constellation)
                Text(steps[step].1).font(Theme.hand(30)).foregroundStyle(Theme.ink)
                Text(steps[step].2).font(.body).foregroundStyle(Theme.ink).fixedSize(horizontal: false, vertical: true)
                HStack {
                    Text("\(step + 1) of \(steps.count)").font(.footnote).foregroundStyle(Theme.muted)
                    Spacer()
                    if step > 0 { InkButton(title: "Back") { step -= 1 } }
                    if step < steps.count - 1 {
                        InkButton(title: "Next", primary: true) { step += 1 }
                    } else {
                        InkButton(title: "Done", primary: true) { onDone() }
                    }
                }
            }
            .padding(20)
            .background(Theme.panel)
            .clipShape(NotebookShape())
            .overlay(NotebookShape().stroke(Theme.ink, lineWidth: 2))
            .shadow(color: Theme.ink, radius: 0, x: 4, y: 4)
            .padding(24)
        }
    }
}

/// Product and team names. Change them here (iOS).
enum AppInfo {
    static let name = "HEALTH-01"
    static let team = "Team Amerat 01"
}

/// Same field-notebook palette as the website: ink lines, graph paper, steel blue, red "01".
enum Theme {
    static let paper = Color(red: 0.984, green: 0.988, blue: 0.996)
    static let grid = Color(red: 0.890, green: 0.922, blue: 0.965)
    static let panel = Color.white
    static let sunk = Color(red: 0.945, green: 0.961, blue: 0.984)
    static let ink = Color(red: 0.090, green: 0.098, blue: 0.122)
    static let muted = Color(red: 0.325, green: 0.357, blue: 0.420)
    static let faint = Color(red: 0.522, green: 0.553, blue: 0.612)
    static let accent = Color(red: 0.0, green: 0.361, blue: 0.588)
    static let constellation = Color(red: 0.114, green: 0.169, blue: 0.859)
    static let sky = Color(red: 0.424, green: 0.612, blue: 1)
    static let marker = Color(red: 0.839, green: 0.894, blue: 1)
    static let caution = Color(red: 0.722, green: 0.431, blue: 0)
    static let warning = Color(red: 0.847, green: 0.106, blue: 0.106)
    static let ok = Color(red: 0.180, green: 0.490, blue: 0.196)

    static func hand(_ size: CGFloat) -> Font { .custom("Noteworthy-Bold", size: size) }
}

/// Slightly uneven corners, like the website's hand-drawn cards. Still a clear rectangle.
struct NotebookShape: Shape {
    func path(in rect: CGRect) -> Path {
        UnevenRoundedRectangle(
            cornerRadii: .init(topLeading: 16, bottomLeading: 12, bottomTrailing: 18, topTrailing: 14)
        ).path(in: rect)
    }
}

struct GraphPaper: View {
    var body: some View {
        Canvas { context, size in
            var path = Path()
            let step: CGFloat = 24
            var x: CGFloat = 0
            while x <= size.width {
                path.move(to: CGPoint(x: x, y: 0))
                path.addLine(to: CGPoint(x: x, y: size.height))
                x += step
            }
            var y: CGFloat = 0
            while y <= size.height {
                path.move(to: CGPoint(x: 0, y: y))
                path.addLine(to: CGPoint(x: size.width, y: y))
                y += step
            }
            context.stroke(path, with: .color(Theme.grid), lineWidth: 1)
        }
        .background(Theme.paper)
        .ignoresSafeArea()
    }
}

struct NotebookPage<Content: View>: View {
    var code: String
    var title: String
    @ViewBuilder var content: Content

    var body: some View {
        ZStack {
            GraphPaper()
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(code).font(.system(size: 11, weight: .semibold, design: .monospaced)).tracking(1.6).foregroundStyle(Theme.constellation)
                        Text(title).font(Theme.hand(32)).foregroundStyle(Theme.ink)
                    }
                    content
                }
                .padding(20)
                .padding(.bottom, 12)
            }
        }
    }
}

struct NoteCard<Content: View>: View {
    @ViewBuilder var content: Content
    var body: some View {
        VStack(alignment: .leading, spacing: 10) { content }
            .padding(16)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Theme.panel)
            .clipShape(NotebookShape())
            .overlay(NotebookShape().stroke(Theme.ink, lineWidth: 2))
            .background(alignment: .topLeading) {
                NotebookShape().fill(Theme.ink).offset(x: 3, y: 3)
            }
    }
}

struct NoteLabel: View {
    var text: String
    var body: some View {
        Text(text.uppercased())
            .font(.system(size: 11, weight: .semibold))
            .tracking(1.1)
            .foregroundStyle(Theme.muted)
    }
}

struct InkButton: View {
    var title: String
    var primary = false
    var fill = false
    var disabled = false
    var action: () -> Void

    var body: some View {
        Button(action: action) {
            Text(title)
                .font(.system(size: 16, weight: .semibold))
                .foregroundStyle(primary ? Color.white : Theme.ink)
                .frame(maxWidth: fill ? .infinity : nil)
                .padding(.horizontal, 16)
                .padding(.vertical, 11)
                .background(primary ? Theme.accent : Theme.panel)
                .clipShape(NotebookShape())
                .overlay(NotebookShape().stroke(Theme.ink, lineWidth: 2))
                .shadow(color: Theme.ink, radius: 0, x: 2, y: 2)
        }
        .buttonStyle(.plain)
        .disabled(disabled)
        .opacity(disabled ? 0.45 : 1)
    }
}

struct NoteField: View {
    var placeholder: String
    @Binding var text: String
    var body: some View {
        TextField(placeholder, text: $text)
            .keyboardType(.URL)
            .textInputAutocapitalization(.never)
            .autocorrectionDisabled()
            .font(.system(.body, design: .monospaced))
            .padding(12)
            .background(Theme.sunk)
            .clipShape(NotebookShape())
            .overlay(NotebookShape().stroke(Theme.ink, lineWidth: 1.5))
    }
}
