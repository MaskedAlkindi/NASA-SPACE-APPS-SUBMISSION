import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import ExerciseDemo from "./ExerciseDemo";
import { FALLBACK_SPEC, POSE_INDEX, RepCounter, chooseStrategy, drawPose, landmarksFromPose, type Snapshot, type TrackingSpec } from "./counters";

type Landmarker = { detectForVideo: (video: HTMLVideoElement, timestamp: number) => { landmarks?: { x: number; y: number; visibility?: number }[][] }; close?: () => void };
type VisionModule = {
  FilesetResolver: { forVisionTasks: (wasmUrl: string) => Promise<unknown> };
  PoseLandmarker: { createFromOptions: (files: unknown, options: unknown) => Promise<Landmarker> };
};

const MEDIAPIPE_ESM = "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.18/+esm";

type Config = {
  tracked_exercises: string[];
  pose_model_url: string;
  pose_wasm_url: string;
  inference: { remote_configured: boolean; remote_frames_enabled: boolean; transmits_video_by_default: boolean };
};

const NAMES: Record<string, string> = { squat: "Squat", sumo_squat: "Wide squat", forward_lunge: "Forward lunge", pushup: "Push-up",
  arm_raise: "Arm raise", shoulder_press: "Shoulder press", bicep_curl: "Biceps curl", jumping_jack: "Jumping jacks", high_knees: "High knees" };
// camera placement per movement
const VIEW: Record<string, string> = { squat: "Side-on", forward_lunge: "Side-on", pushup: "Side-on, low camera", sumo_squat: "Face the camera",
  arm_raise: "Face the camera", shoulder_press: "Face the camera", bicep_curl: "Face the camera", jumping_jack: "Face the camera", high_knees: "Face the camera" };

async function loadLandmarker(wasmUrl: string, modelUrl: string) {
  const loader = new Function("u", "return import(u)") as (u: string) => Promise<VisionModule>;
  const vision = await loader(MEDIAPIPE_ESM);
  const files = await vision.FilesetResolver.forVisionTasks(wasmUrl);
  const options = (delegate: "GPU" | "CPU") => ({
    baseOptions: { modelAssetPath: modelUrl, delegate },
    runningMode: "VIDEO",
    numPoses: 1,
  });
  try {
    return await vision.PoseLandmarker.createFromOptions(files, options("GPU"));
  } catch {
    return await vision.PoseLandmarker.createFromOptions(files, options("CPU"));
  }
}

export default function CameraPanel({ astronautId, onSaved, initialExercise = "squat", lockExercise = false, compact = false }: {
  astronautId: string; onSaved: () => void; initialExercise?: string; lockExercise?: boolean; compact?: boolean }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [exerciseId, setExerciseId] = useState(initialExercise);
  const [status, setStatus] = useState("Camera is off. Video is not uploaded.");
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [running, setRunning] = useState(false);
  const [consent, setConsent] = useState(false);
  const [config, setConfig] = useState<Config | null>(null);
  const [specs, setSpecs] = useState<Record<string, TrackingSpec>>(FALLBACK_SPEC);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const counterRef = useRef<RepCounter | null>(null);
  const stopRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    api<Config>("/exercise/config").then(setConfig).catch(() => setConfig(null));
    api<{ exercises: Record<string, TrackingSpec> }>("/exercise/tracking-spec")
      .then((d) => setSpecs({ ...FALLBACK_SPEC, ...d.exercises }))
      .catch(() => setSpecs(FALLBACK_SPEC));
    return () => stopRef.current?.();
  }, []);

  function stopTracks() {
    stopRef.current?.();
    stopRef.current = null;
    const video = videoRef.current;
    video?.srcObject && (video.srcObject as MediaStream).getTracks().forEach((t) => t.stop());
    if (video) video.srcObject = null;
    setRunning(false);
  }

  async function startLocal() {
    setError(null);
    setBusy(true);
    stopTracks();
    const spec = specs[exerciseId] ?? FALLBACK_SPEC[exerciseId];
    const counter = new RepCounter(exerciseId, spec);
    counterRef.current = counter;
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user", width: 640, height: 480 }, audio: false });
    } catch (err) {
      const denied = err instanceof DOMException && (err.name === "NotAllowedError" || err.name === "PermissionDeniedError");
      const decision = chooseStrategy({
        cameraPermission: denied ? "denied" : "prompt", localPose: "unavailable",
        remoteConfigured: !!config?.inference.remote_configured, remoteConsent: consent, remoteStatus: "skipped",
      });
      setStatus(decision.reason);
      setBusy(false);
      return;
    }
    const video = videoRef.current!;
    video.srcObject = stream;
    await video.play();
    let landmarker: Landmarker;
    try {
      landmarker = await loadLandmarker(config?.pose_wasm_url ?? "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.18/wasm", config?.pose_model_url ?? "");
    } catch {
      const canRemote = !!config?.inference.remote_configured && !!config.inference.remote_frames_enabled && consent;
      if (canRemote) {
        setBusy(false);
        startRemote(stream);
        return;
      }
      stream.getTracks().forEach((t) => t.stop());
      video.srcObject = null;
      const decision = chooseStrategy({
        cameraPermission: "granted", localPose: "failed",
        remoteConfigured: !!config?.inference.remote_configured, remoteConsent: consent, remoteStatus: "skipped",
      });
      setStatus(decision.reason);
      setBusy(false);
      return;
    }
    setStatus(chooseStrategy({ cameraPermission: "granted", localPose: "ready", remoteConfigured: false, remoteConsent: false, remoteStatus: "skipped" }).reason);
    setRunning(true);
    setBusy(false);
    let raf = 0;
    let lastVideoTime = -1;
    const loop = () => {
      if (video.readyState >= 2 && video.currentTime !== lastVideoTime) {
        lastVideoTime = video.currentTime;
        const result = landmarker.detectForVideo(video, performance.now());
        const pose = result.landmarks?.[0];
        const lm = pose ? landmarksFromPose(pose) : null;
        const next = counter.update(lm, performance.now());
        setSnap(next);
        const canvas = canvasRef.current;
        if (canvas && lm) {
          canvas.width = video.videoWidth || 640;
          canvas.height = video.videoHeight || 480;
          const ctx = canvas.getContext("2d");
          if (ctx) drawPose(ctx, lm, canvas.width, canvas.height);
        }
      }
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    stopRef.current = () => {
      cancelAnimationFrame(raf);
      landmarker.close?.();
      stream.getTracks().forEach((t) => t.stop());
    };
  }

  function startRemote(stream: MediaStream) {
    setStatus("On-device pose detection failed. Sending frames to the configured inference service because you allowed it. Frames are not stored.");
    setRunning(true);
    let stopped = false;
    const timer = window.setInterval(async () => {
      if (stopped) return;
      const video = videoRef.current;
      const canvas = canvasRef.current;
      if (!video || !canvas) return;
      canvas.width = 320;
      canvas.height = 240;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      ctx.drawImage(video, 0, 0, 320, 240);
      const image = canvas.toDataURL("image/jpeg", 0.6).split(",")[1];
      try {
        const res = await api<{ snapshot: Snapshot }>("/exercise/inference/frame", {
          body: { consent: "explicit_frame_upload", exercise_id: exerciseId, image_base64: image, t_ms: Math.round(performance.now()) },
        });
        setSnap(res.snapshot);
      } catch (err) {
        stopped = true;
        window.clearInterval(timer);
        stream.getTracks().forEach((t) => t.stop());
        setRunning(false);
        const decision = chooseStrategy({
          cameraPermission: "granted", localPose: "failed",
          remoteConfigured: true, remoteConsent: true, remoteStatus: "failed",
        });
        setStatus(`${decision.reason} ${err instanceof Error ? err.message : ""}`.trim());
      }
    }, 900);
    stopRef.current = () => {
      stopped = true;
      window.clearInterval(timer);
      stream.getTracks().forEach((t) => t.stop());
    };
  }

  async function save() {
    const counter = counterRef.current;
    if (!counter || counter.reps < 1) {
      setError("Count at least one repetition, or use manual entry.");
      return;
    }
    setBusy(true);
    const end = new Date();
    const start = new Date(end.getTime() - Math.max(60_000, counter.reps * 4_000));
    try {
      await api(`/exercise/astronauts/${astronautId}/sessions`, {
        body: {
          source: "camera", started_at: start.toISOString(), ended_at: end.toISOString(),
          exercises: [{ exercise_id: exerciseId, sets: [{ reps: counter.reps, rest_s: 0 }], notes: "" }],
          summary: { reps: counter.reps, completed_sets: counter.completedSets, form_flags: counter.formFlags, strategy: "local" },
          notes: "Counted in the browser. Example tracking, not a clinical measurement.",
          client_id: `cam-${exerciseId}-${end.getTime()}`,
        },
      });
      stopTracks();
      setSnap(null);
      setStatus("Session saved. The summary was stored. The video was not.");
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save the session");
    } finally {
      setBusy(false);
    }
  }

  const tracked = config?.tracked_exercises ?? Object.keys(FALLBACK_SPEC);
  return (
    <div className="grid g2">
      <div className="video-stage">
        <video ref={videoRef} playsInline muted />
        <canvas ref={canvasRef} />
        <div className="rep-hud">
          <div className="big">{snap?.reps ?? 0}<span className="unit">reps</span></div>
          <div className="small">Set {snap?.current_set || (running ? 1 : 0)} · {snap?.status ?? "idle"}</div>
        </div>
      </div>
      <div className="col">
        <p className="small muted">{status}</p>
        <label className="field">Exercise
          <select className="input" value={exerciseId} onChange={(e) => setExerciseId(e.target.value)} disabled={running || lockExercise}>
            {tracked.map((id) => <option key={id} value={id}>{NAMES[id] ?? id}</option>)}
          </select>
        </label>
        {!compact && <div className="cam-demo"><ExerciseDemo id={exerciseId} size={150} /><div className="small"><b>{VIEW[exerciseId] ?? "Face the camera"}</b>, 2–3 m away, whole body in frame.</div></div>}
        {config?.inference.remote_configured && (
          <label className="small row">
            <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
            I allow this session to send camera frames to the configured inference service if on-device detection fails. Frames are not stored as a video.
          </label>
        )}
        <div className="row">
          {!running ? <button className="btn primary" disabled={busy} onClick={startLocal}>Start camera</button>
            : <button className="btn" onClick={() => { stopTracks(); setStatus("Camera stopped. Nothing was uploaded."); }}>Stop</button>}
          <button className="btn" disabled={busy || !snap?.reps} onClick={save}>Save session</button>
        </div>
        {snap?.feedback?.[0] && <div className="small">{snap.feedback[0]}</div>}
        {snap?.form_flags?.map((f) => <div key={f} className="small" style={{ color: "var(--caution)" }}>{f}</div>)}
        {error && <div className="err small">{error}</div>}
        {!compact && <p className="small faint">Tracking {Object.keys(POSE_INDEX).length} body points. Video stays on this device. Not a medical measurement.</p>}
      </div>
    </div>
  );
}
