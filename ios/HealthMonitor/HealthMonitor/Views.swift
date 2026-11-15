import SwiftUI
import AVFoundation
import Vision

// MARK: - Connect

struct ConnectView: View {
    @EnvironmentObject var session: SessionStore
    @State private var url = ""
    @State private var busy = false

    var body: some View {
        NotebookPage(code: "HEALTH-01  ·  \(AppInfo.team)", title: "Connect") {
            HStack(spacing: 12) {
                Image("TeamLogo").resizable().scaledToFit().frame(width: 56, height: 56)
                VStack(alignment: .leading, spacing: 2) {
                    Text("HEALTH-").font(Theme.hand(22)) + Text("01").font(Theme.hand(22)).foregroundColor(Theme.warning)
                    Text("Crew phone").font(.subheadline).foregroundStyle(Theme.muted)
                }
            }
            NoteCard {
                NoteLabel(text: "This phone's device ID")
                Text(session.deviceUUID).font(.system(.body, design: .monospaced)).textSelection(.enabled)
                Text("Show this to the operator. They assign this phone to you on the Devices page.")
                    .font(.footnote).foregroundStyle(Theme.muted)
                InkButton(title: "Copy ID") { UIPasteboard.general.string = session.deviceUUID }
            }
            NoteCard {
                NoteLabel(text: "Server")
                NoteField(placeholder: "http://192.168.1.20:8080", text: $url)
                Text("The address of the computer running HEALTH-01 on your network (not localhost).")
                    .font(.footnote).foregroundStyle(Theme.muted)
                InkButton(title: busy ? "Connecting…" : "Connect", primary: true, fill: true, disabled: busy || !url.hasPrefix("http")) {
                    busy = true
                    session.serverURL = url.trimmingCharacters(in: .whitespaces)
                    Task { await session.connect(); busy = false }
                }
            }
            NoteCard {
                NoteLabel(text: "Status")
                statusLabel
                if let m = session.message { Text(m).font(.footnote).foregroundStyle(Theme.muted) }
                InkButton(title: "Check again") { Task { await session.refresh() } }
            }
            TourAgain()
        }
        .onAppear { url = session.serverURL }
        .task(id: session.status) {
            while session.status == "pending" && !Task.isCancelled {
                try? await Task.sleep(for: .seconds(5))
                await session.refresh()
            }
        }
    }

    @ViewBuilder private var statusLabel: some View {
        switch session.status {
        case "assigned": Label("Connected as \(session.callsign ?? "crew member")", systemImage: "checkmark.circle.fill").foregroundStyle(Theme.accent)
        case "pending": Label("Waiting for the operator to assign this phone", systemImage: "hourglass").foregroundStyle(Theme.caution)
        case "revoked": Label("This phone was revoked. Ask the operator.", systemImage: "xmark.octagon").foregroundStyle(Theme.warning)
        default: Label("Not connected", systemImage: "wifi.slash").foregroundStyle(.secondary)
        }
    }
}

// MARK: - Health

struct TourAgain: View {
    @AppStorage("tour.nudge") private var nudge = 0
    var body: some View {
        InkButton(title: "Show the tour") { nudge += 1 }
    }
}

struct HealthView: View {
    @EnvironmentObject var session: SessionStore
    @EnvironmentObject var health: HealthKitManager
    @AppStorage("autosync") private var autoSync = true
    @State private var fatigue = 3
    @State private var note: String?

    var body: some View {
        NotebookPage(code: "02  /  CHECK-IN", title: "Health") {
            NoteCard {
                NoteLabel(text: "Upload to the crew server")
                Toggle("Auto sync while the app is open", isOn: $autoSync).tint(Theme.accent)
                Text("About every 5 minutes, after this phone is assigned and you have allowed a Health type.")
                    .font(.footnote).foregroundStyle(Theme.muted)
                if let last = health.lastSync {
                    Text("Last sync \(last.formatted(date: .abbreviated, time: .shortened))")
                        .font(.footnote).foregroundStyle(Theme.muted)
                }
                InkButton(title: health.isSyncing ? "Syncing…" : "Sync now", primary: true, fill: true, disabled: health.isSyncing || !session.isAssigned) {
                    Task { await health.sync(using: session.api) }
                }
                if !session.isAssigned { Text("Connect and get assigned first.").font(.footnote).foregroundStyle(Theme.caution) }
                if let m = health.syncMessage { Text(m).font(.footnote).foregroundStyle(Theme.muted) }
            }
            NoteCard {
                NoteLabel(text: "How tired are you?")
                HStack {
                    Text("\(fatigue)").font(.system(size: 36, weight: .medium, design: .monospaced))
                    Text("/ 7").foregroundStyle(Theme.muted)
                    Spacer()
                    InkButton(title: "−", disabled: fatigue <= 1) { fatigue = max(1, fatigue - 1) }
                    InkButton(title: "+", disabled: fatigue >= 7) { fatigue = min(7, fatigue + 1) }
                }
                Text("Samn-Perelli: 1 fully alert … 7 completely exhausted.").font(.footnote).foregroundStyle(Theme.muted)
                InkButton(title: "Send check-in", primary: true, disabled: !session.isAssigned) {
                    let now = Date()
                    let rec = UploadMeasurement(metric: "fatigue_score", value: Double(fatigue), unit: "score 1-7", timestamp: now,
                                                sourceDevice: "iPhone", externalId: "ios-fatigue-\(Int(now.timeIntervalSince1970))", quality: "good")
                    Task { note = (try? await session.api.upload([rec])) != nil ? "Check-in saved." : "Not saved." }
                }
                if let note { Text(note).font(.footnote).foregroundStyle(Theme.ink) }
            }
            NoteCard {
                NoteLabel(text: "Apple Health, read-only")
                ForEach(HealthKitManager.features) { f in
                    HStack(alignment: .center, spacing: 12) {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(f.title)
                            Text(f.detail).font(.caption).foregroundStyle(Theme.muted)
                        }
                        Spacer(minLength: 8)
                        InkButton(title: health.requested.contains(f.id) ? "Asked" : "Allow", disabled: health.requested.contains(f.id)) {
                            Task {
                                await health.request(f)
                                if autoSync, session.isAssigned { await health.sync(using: session.api) }
                            }
                        }
                    }
                    if f.id != HealthKitManager.features.last?.id {
                        Rectangle().fill(Theme.grid).frame(height: 1)
                    }
                }
            }
        }
    }
}

// MARK: - Exercise (on-device rep counting; frames are never stored or uploaded)

struct ExerciseView: View {
    @EnvironmentObject var session: SessionStore
    @StateObject private var camera = PoseCamera()
    @State private var movement: Movement = .squat
    @State private var started: Date?
    @State private var note: String?

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()
            if camera.denied {
                VStack(spacing: 12) {
                    Text("Camera is off").font(Theme.hand(28))
                    Text("Turn it on in Settings › HEALTH-01 so reps can be counted on this phone.")
                        .font(.subheadline).foregroundStyle(Theme.muted).multilineTextAlignment(.center)
                }
                .padding(24)
                .background(Theme.panel)
                .clipShape(NotebookShape())
                .overlay(NotebookShape().stroke(Theme.ink, lineWidth: 2))
                .padding(28)
            } else {
                CameraPreview(session: camera.session, points: camera.skeleton)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .ignoresSafeArea()
            }
            VStack(spacing: 10) {
                HStack(alignment: .top) {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("EXERCISE").font(.system(size: 11, weight: .semibold, design: .monospaced)).tracking(1.4).foregroundStyle(Theme.constellation)
                        Menu {
                            Picker("Movement", selection: $movement) {
                                ForEach(Movement.allCases) { Text($0.title).tag($0) }
                            }
                        } label: {
                            HStack(spacing: 6) {
                                Text(movement.title).font(Theme.hand(24)).foregroundStyle(Theme.ink)
                                Image(systemName: "chevron.down").font(.caption.weight(.bold)).foregroundStyle(Theme.ink)
                            }
                        }
                        .disabled(camera.running)
                        Text(movement.cue).font(.footnote).foregroundStyle(Theme.muted)
                    }
                    .padding(12)
                    .background(Theme.panel.opacity(0.96))
                    .clipShape(NotebookShape())
                    .overlay(NotebookShape().stroke(Theme.ink, lineWidth: 2))
                    Spacer(minLength: 0)
                }
                Spacer()
                HStack(alignment: .bottom, spacing: 10) {
                    VStack(alignment: .leading, spacing: 0) {
                        Text("\(camera.reps)").font(.system(size: 52, weight: .medium, design: .monospaced)).foregroundStyle(Theme.ink)
                        Text(camera.feedback).font(.footnote).foregroundStyle(Theme.muted).lineLimit(2)
                    }
                    .padding(.horizontal, 14)
                    .padding(.vertical, 8)
                    .background(Theme.panel.opacity(0.96))
                    .clipShape(NotebookShape())
                    .overlay(NotebookShape().stroke(Theme.ink, lineWidth: 2))
                    Spacer(minLength: 8)
                    if camera.running {
                        InkButton(title: "Stop and save", primary: true) { save() }
                    } else {
                        InkButton(title: "Start", primary: true, disabled: camera.denied) {
                            started = Date(); note = nil; camera.begin(movement)
                        }
                    }
                }
                if let note { Text(note).font(.footnote).padding(8).frame(maxWidth: .infinity, alignment: .leading).background(Theme.panel.opacity(0.96)).clipShape(NotebookShape()) }
                if !session.isAssigned {
                    Text("This phone is not assigned yet, so workouts cannot be saved.")
                        .font(.caption).foregroundStyle(Theme.caution)
                        .padding(8).frame(maxWidth: .infinity, alignment: .leading)
                        .background(Theme.panel.opacity(0.96)).clipShape(NotebookShape())
                }
            }
            .padding(.horizontal, 14)
            .padding(.top, 8)
            .padding(.bottom, 10)
        }
        .onAppear { camera.openPreview() }
        .onDisappear { camera.closePreview() }
    }

    private func save() {
        let reps = camera.reps
        camera.end()
        guard reps > 0, let start = started else { note = "No reps counted, nothing saved."; return }
        let w = Workout(source: "camera", startedAt: start, endedAt: Date(),
                        exercises: [.init(exerciseId: movement.rawValue, sets: [.init(reps: reps)])],
                        clientId: "ios-\(Int(start.timeIntervalSince1970))")
        Task {
            do { _ = try await session.api.upload(workouts: [w]); note = "Saved \(reps) \(movement.title.lowercased())." }
            catch { note = "Not saved: \(error.localizedDescription)" }
        }
    }
}

/// Front camera + Vision human body pose. Each frame is analysed and dropped.
final class PoseCamera: NSObject, ObservableObject, AVCaptureVideoDataOutputSampleBufferDelegate {
    let session = AVCaptureSession()
    @Published var reps = 0
    @Published var feedback = "Choose a movement and press Start"
    @Published var running = false
    @Published var denied = false
    /// Latest body points, in the same top-left normalised space the preview uses.
    @Published var skeleton: [String: BodyPoint] = [:]
    private var counter = RepCounter(.squat)
    private var counting = false
    private let queue = DispatchQueue(label: "pose")
    private var configured = false

    private static let joints: [String: VNHumanBodyPoseObservation.JointName] = [
        "shoulder_l": .leftShoulder, "shoulder_r": .rightShoulder, "elbow_l": .leftElbow, "elbow_r": .rightElbow,
        "wrist_l": .leftWrist, "wrist_r": .rightWrist,
        "hip_l": .leftHip, "hip_r": .rightHip, "knee_l": .leftKnee, "knee_r": .rightKnee, "ankle_l": .leftAnkle, "ankle_r": .rightAnkle,
    ]

    /// Opens the front camera so the preview fills the page. Counting starts separately.
    func openPreview() {
        AVCaptureDevice.requestAccess(for: .video) { granted in
            guard granted else { DispatchQueue.main.async { self.denied = true; self.feedback = "Camera access is off (Settings › HEALTH-01)." }; return }
            self.queue.async {
                if !self.configured { self.configure() }
                if !self.session.isRunning { self.session.startRunning() }
            }
        }
    }

    func begin(_ movement: Movement) {
        queue.async {
            self.counter = RepCounter(movement)
            self.counting = true
            DispatchQueue.main.async { self.reps = 0; self.running = true; self.feedback = "Get into view" }
        }
    }

    /// Stops counting and leaves the preview up.
    func end() {
        queue.async { self.counting = false }
        running = false
    }

    func closePreview() {
        queue.async {
            self.counting = false
            if self.session.isRunning { self.session.stopRunning() }
        }
        running = false
        skeleton = [:]
    }

    private func configure() {
        session.beginConfiguration()
        session.sessionPreset = .vga640x480
        if let dev = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .front),
           let input = try? AVCaptureDeviceInput(device: dev), session.canAddInput(input) { session.addInput(input) }
        let out = AVCaptureVideoDataOutput()
        out.alwaysDiscardsLateVideoFrames = true
        out.setSampleBufferDelegate(self, queue: queue)
        if session.canAddOutput(out) { session.addOutput(out) }
        out.connection(with: .video)?.videoRotationAngle = 90
        session.commitConfiguration()
        configured = true
    }

    func captureOutput(_ output: AVCaptureOutput, didOutput sampleBuffer: CMSampleBuffer, from connection: AVCaptureConnection) {
        guard let buffer = CMSampleBufferGetImageBuffer(sampleBuffer) else { return }
        let req = VNDetectHumanBodyPoseRequest()
        try? VNImageRequestHandler(cvPixelBuffer: buffer, orientation: .up).perform([req])
        guard let obs = req.results?.first, let pts = try? obs.recognizedPoints(.all) else { return }
        var mapped: [String: BodyPoint] = [:]
        for (k, j) in Self.joints {
            if let p = pts[j] { mapped[k] = BodyPoint(x: p.location.x, y: 1 - p.location.y, score: p.confidence) }   // Vision y is up
        }
        if counting {
            let n = counter.update(mapped)
            let fb = counter.feedback
            DispatchQueue.main.async { self.skeleton = mapped; self.reps = n; self.feedback = fb }
        } else {
            DispatchQueue.main.async { self.skeleton = mapped }
        }
    }
}

struct CameraPreview: UIViewRepresentable {
    let session: AVCaptureSession
    var points: [String: BodyPoint]

    /// Same bones as the website's pose overlay (`drawPose` in the exercise module).
    static let edges: [(String, String)] = [
        ("shoulder_l", "shoulder_r"), ("shoulder_l", "elbow_l"), ("elbow_l", "wrist_l"),
        ("shoulder_r", "elbow_r"), ("elbow_r", "wrist_r"), ("shoulder_l", "hip_l"),
        ("shoulder_r", "hip_r"), ("hip_l", "hip_r"), ("hip_l", "knee_l"),
        ("knee_l", "ankle_l"), ("hip_r", "knee_r"), ("knee_r", "ankle_r"),
    ]

    final class PreviewView: UIView {
        override class var layerClass: AnyClass { AVCaptureVideoPreviewLayer.self }
        var preview: AVCaptureVideoPreviewLayer { layer as! AVCaptureVideoPreviewLayer }
        let bones = CAShapeLayer()
        let joints = CAShapeLayer()

        override init(frame: CGRect) {
            super.init(frame: frame)
            bones.strokeColor = UIColor(red: 0.424, green: 0.612, blue: 1, alpha: 1).cgColor
            bones.fillColor = UIColor.clear.cgColor
            bones.lineWidth = 3
            bones.lineCap = .round
            joints.fillColor = UIColor(red: 0.847, green: 0.106, blue: 0.106, alpha: 1).cgColor
            layer.addSublayer(bones)
            layer.addSublayer(joints)
        }
        required init?(coder: NSCoder) { fatalError() }

        func draw(_ points: [String: BodyPoint]) {
            bones.frame = bounds
            joints.frame = bounds
            let lines = UIBezierPath()
            let dots = UIBezierPath()
            func located(_ key: String) -> CGPoint? {
                guard let p = points[key], p.score >= 0.3 else { return nil }
                // Preview mirroring and aspect-fill crop are applied here, so lines sit on the person.
                return preview.layerPointConverted(fromCaptureDevicePoint: CGPoint(x: p.x, y: p.y))
            }
            for (a, b) in CameraPreview.edges {
                guard let pa = located(a), let pb = located(b) else { continue }
                lines.move(to: pa)
                lines.addLine(to: pb)
            }
            for key in points.keys {
                guard let p = located(key) else { continue }
                dots.append(UIBezierPath(ovalIn: CGRect(x: p.x - 4, y: p.y - 4, width: 8, height: 8)))
            }
            bones.path = lines.cgPath
            joints.path = dots.cgPath
        }
    }

    func makeUIView(context: Context) -> PreviewView {
        let v = PreviewView()
        v.preview.session = session
        v.preview.videoGravity = .resizeAspectFill
        if let conn = v.preview.connection, conn.isVideoRotationAngleSupported(90) {
            conn.videoRotationAngle = 90
        }
        return v
    }
    func updateUIView(_ uiView: PreviewView, context: Context) {
        uiView.draw(points)
    }
}
