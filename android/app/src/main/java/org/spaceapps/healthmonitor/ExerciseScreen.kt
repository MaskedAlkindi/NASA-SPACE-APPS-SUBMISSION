package org.spaceapps.healthmonitor

import android.Manifest
import android.annotation.SuppressLint
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.pose.PoseDetection
import com.google.mlkit.vision.pose.PoseLandmark
import com.google.mlkit.vision.pose.defaults.PoseDetectorOptions
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONObject
import java.time.Instant
import java.util.concurrent.Executors

private val LANDMARKS = mapOf(
    "shoulder_l" to PoseLandmark.LEFT_SHOULDER, "shoulder_r" to PoseLandmark.RIGHT_SHOULDER,
    "elbow_l" to PoseLandmark.LEFT_ELBOW, "elbow_r" to PoseLandmark.RIGHT_ELBOW,
    "wrist_l" to PoseLandmark.LEFT_WRIST, "wrist_r" to PoseLandmark.RIGHT_WRIST,
    "hip_l" to PoseLandmark.LEFT_HIP, "hip_r" to PoseLandmark.RIGHT_HIP,
    "knee_l" to PoseLandmark.LEFT_KNEE, "knee_r" to PoseLandmark.RIGHT_KNEE,
    "ankle_l" to PoseLandmark.LEFT_ANKLE, "ankle_r" to PoseLandmark.RIGHT_ANKLE,
)

private val BONES = listOf(
    "shoulder_l" to "shoulder_r", "shoulder_l" to "elbow_l", "elbow_l" to "wrist_l",
    "shoulder_r" to "elbow_r", "elbow_r" to "wrist_r", "shoulder_l" to "hip_l",
    "shoulder_r" to "hip_r", "hip_l" to "hip_r", "hip_l" to "knee_l",
    "knee_l" to "ankle_l", "hip_r" to "knee_r", "knee_r" to "ankle_r",
)

/** Normalised pose (0–1, y down) plus the upright image aspect (width / height), for drawing. */
private data class PoseFrame(val points: Map<String, Pt>, val aspect: Float)

/** Latest callback, so the camera analyzer always sees the current screen state. */
private class FrameSink { var onFrame: (PoseFrame) -> Unit = {} }

private val Paper = Color(0xFFFBFCFE)
private val Bone = Color(0xFF6C9CFF)
private val NoteShape = RoundedCornerShape(topStart = 16.dp, bottomStart = 12.dp, bottomEnd = 18.dp, topEnd = 14.dp)

/** Rep counting on the phone. Frames are analysed on the device and dropped; only the count is uploaded. */
@Composable
fun ExerciseScreen(state: AppState) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var movement by remember { mutableStateOf(Movement.SQUAT) }
    var running by remember { mutableStateOf(false) }
    var reps by remember { mutableIntStateOf(0) }
    var feedback by remember { mutableStateOf("Choose a movement and press Start") }
    var startedAt by remember { mutableStateOf<Instant?>(null) }
    var message by remember { mutableStateOf<String?>(null) }
    var hasCamera by remember { mutableStateOf(ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) }
    val askCamera = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { hasCamera = it }
    val counter = remember(movement) { RepCounter(movement) }
    var pose by remember { mutableStateOf(PoseFrame(emptyMap(), 3f / 4f)) }
    val sink = remember { FrameSink() }
    sink.onFrame = { frame ->
        pose = frame
        if (running) { reps = counter.update(frame.points); feedback = counter.feedback }
    }

    Box(Modifier.fillMaxSize().background(Color.Black)) {
        if (!hasCamera) {
            Button(onClick = { askCamera.launch(Manifest.permission.CAMERA) }, Modifier.align(Alignment.Center)) { Text("Allow camera") }
        } else {
            PoseCamera(sink, pose)
        }
        Column(Modifier.fillMaxSize().padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Column(
                Modifier.background(Paper.copy(alpha = 0.96f), NoteShape).border(2.dp, Ink, NoteShape).padding(12.dp),
            ) {
                Text("EXERCISE", fontSize = 11.sp, fontFamily = FontFamily.Monospace, color = Color(0xFF1D2BDB), fontWeight = FontWeight.SemiBold)
                Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    Movement.entries.forEach { m ->
                        FilterChip(selected = movement == m, enabled = !running, onClick = { movement = m; reps = 0 }, label = { Text(m.title) })
                    }
                }
                Text(movement.cue, fontSize = 13.sp, color = Color(0xFF535B6B))
            }
            Spacer(Modifier.weight(1f))
            Row(verticalAlignment = Alignment.Bottom, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Column(Modifier.background(Paper.copy(alpha = 0.96f), NoteShape).border(2.dp, Ink, NoteShape).padding(horizontal = 14.dp, vertical = 8.dp)) {
                    Text("$reps", fontSize = 48.sp, fontFamily = FontFamily.Monospace, color = Ink)
                    Text(feedback, fontSize = 13.sp, color = Color(0xFF535B6B))
                }
                Spacer(Modifier.weight(1f))
                if (!running) {
                    Button(enabled = hasCamera, onClick = { counter.reset(); reps = 0; feedback = "Get into view"; startedAt = Instant.now(); running = true; message = null }) { Text("Start") }
                } else {
                    Button(onClick = {
                        running = false
                        val start = startedAt ?: Instant.now()
                        val end = Instant.now()
                        val workout = JSONObject()
                            .put("source", "camera").put("started_at", start.toString()).put("ended_at", end.toString())
                            .put("client_id", "and-${start.toEpochMilli()}")
                            .put("summary", JSONObject().put("reps", reps).put("counted_on", "phone"))
                            .put("exercises", JSONArray().put(JSONObject().put("exercise_id", movement.id)
                                .put("sets", JSONArray().put(JSONObject().put("reps", reps)))))
                        if (reps == 0) { message = "No reps counted, nothing saved."; return@Button }
                        scope.launch {
                            message = try {
                                state.api.upload(workouts = listOf(workout)); "Saved $reps ${movement.title.lowercase()}."
                            } catch (e: Exception) { "Not saved: ${e.message}" }
                        }
                    }) { Text("Stop and save") }
                }
            }
            message?.let { Text(it, fontSize = 13.sp, color = Paper, modifier = Modifier.background(Ink.copy(alpha = 0.8f), NoteShape).padding(8.dp)) }
            if (!state.assigned) Text("This phone is not assigned yet, so workouts cannot be saved.", color = Caution, fontSize = 12.sp, modifier = Modifier.background(Paper.copy(alpha = 0.96f), NoteShape).padding(8.dp))
        }
    }
}

@SuppressLint("UnsafeOptInUsageError")
@Composable
private fun PoseCamera(sink: FrameSink, frame: PoseFrame) {
    val context = LocalContext.current
    val owner = LocalLifecycleOwner.current
    val detector = remember {
        PoseDetection.getClient(PoseDetectorOptions.Builder().setDetectorMode(PoseDetectorOptions.STREAM_MODE).build())
    }
    val executor = remember { Executors.newSingleThreadExecutor() }
    DisposableEffect(Unit) { onDispose { detector.close(); executor.shutdown() } }
    Box(Modifier.fillMaxSize()) {
        AndroidView(modifier = Modifier.fillMaxSize(), factory = { ctx ->
            val view = PreviewView(ctx)
            view.scaleType = PreviewView.ScaleType.FILL_CENTER
            val providerFuture = ProcessCameraProvider.getInstance(ctx)
            providerFuture.addListener({
                val provider = providerFuture.get()
                val preview = Preview.Builder().build().also { it.surfaceProvider = view.surfaceProvider }
                val analysis = ImageAnalysis.Builder().setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST).build()
                analysis.setAnalyzer(executor) { proxy ->
                    val media = proxy.image
                    if (media == null) { proxy.close(); return@setAnalyzer }
                    val image = InputImage.fromMediaImage(media, proxy.imageInfo.rotationDegrees)
                    detector.process(image)
                        .addOnSuccessListener { pose ->
                            val w = image.width.toFloat().coerceAtLeast(1f)
                            val h = image.height.toFloat().coerceAtLeast(1f)
                            val pts = LANDMARKS.mapNotNull { (k, id) ->
                                pose.getPoseLandmark(id)?.let { k to Pt(it.position.x / w, it.position.y / h, it.inFrameLikelihood) }
                            }.toMap()
                            sink.onFrame(PoseFrame(pts, w / h))
                        }
                        .addOnCompleteListener { proxy.close() }
                }
                provider.unbindAll()
                provider.bindToLifecycle(owner, CameraSelector.DEFAULT_FRONT_CAMERA, preview, analysis)
            }, ContextCompat.getMainExecutor(context))
            view
        })
        Canvas(Modifier.fillMaxSize()) {
            fun locate(key: String): Offset? {
                val p = frame.points[key] ?: return null
                if (p.score < 0.3f) return null
                // Front preview is mirrored. FILL_CENTER crops the same way the preview does.
                val nx = 1f - p.x
                val contentW = frame.aspect.coerceAtLeast(0.01f)
                val scale = maxOf(size.width / contentW, size.height)
                val drawnW = contentW * scale
                val drawnH = scale
                val ox = (size.width - drawnW) / 2f
                val oy = (size.height - drawnH) / 2f
                return Offset(ox + nx * drawnW, oy + p.y * drawnH)
            }
            for ((a, b) in BONES) {
                val pa = locate(a) ?: continue
                val pb = locate(b) ?: continue
                drawLine(Bone, pa, pb, strokeWidth = 8f)
            }
            for (key in frame.points.keys) {
                val p = locate(key) ?: continue
                drawCircle(Warning, radius = 8f, center = p)
            }
        }
    }
}
