package org.spaceapps.healthmonitor

import kotlin.math.abs
import kotlin.math.acos
import kotlin.math.sqrt

/** One body point in image coordinates (y grows downwards) with the detector's confidence. */
data class Pt(val x: Float, val y: Float, val score: Float)

/** How a movement is measured. Distances are divided by torso length, so the camera distance doesn't matter. */
enum class Signal { KNEE_ANGLE, MIN_KNEE_ANGLE, ELBOW_ANGLE, ELBOW_ANGLE_ANY, ARM_ELEVATION, KNEE_LIFT }

/**
 * Same movements and rules as the website and the server (backend/app/exercise/tracking.py).
 * readyHigh = true: a larger value is the resting pose (e.g. straight knees). A rep counts when the value
 * passes [work] and then returns past [ready] (hysteresis, so jitter is not counted).
 */
enum class Movement(val id: String, val title: String, val cue: String, val signal: Signal, val readyHigh: Boolean,
                    val ready: Float, val work: Float) {
    SQUAT("squat", "Squats", "Side-on, whole body in view.", Signal.KNEE_ANGLE, true, 155f, 110f),
    SUMO_SQUAT("sumo_squat", "Wide squats", "Face the camera, wide stance.", Signal.KNEE_ANGLE, true, 155f, 115f),
    LUNGE("forward_lunge", "Lunges", "Side-on, step forward and lower.", Signal.MIN_KNEE_ANGLE, true, 155f, 105f),
    PUSHUP("pushup", "Push-ups", "Side-on, camera low.", Signal.ELBOW_ANGLE_ANY, true, 150f, 100f),
    ARM_RAISE("arm_raise", "Arm raises", "Face the camera, raise arms to shoulder height.", Signal.ARM_ELEVATION, false, 0.12f, 0.48f),
    SHOULDER_PRESS("shoulder_press", "Shoulder press", "Face the camera, hands from shoulders to overhead.", Signal.ARM_ELEVATION, false, 0.24f, 0.8f),
    BICEP_CURL("bicep_curl", "Biceps curls", "Face the camera, elbows by your sides.", Signal.ELBOW_ANGLE, true, 145f, 65f),
    JUMPING_JACK("jumping_jack", "Jumping jacks", "Face the camera, arms overhead.", Signal.ARM_ELEVATION, false, -0.2f, 0.6f),
    HIGH_KNEES("high_knees", "High knees", "Face the camera, knee to hip height.", Signal.KNEE_LIFT, false, -0.56f, -0.16f),
}

class RepCounter(private val movement: Movement) {
    var reps = 0
        private set
    var feedback = "Get into view"
        private set
    private var inRep = false

    private fun angle(a: Pt, b: Pt, c: Pt): Float? {
        val v1x = a.x - b.x; val v1y = a.y - b.y; val v2x = c.x - b.x; val v2y = c.y - b.y
        val d = sqrt(v1x * v1x + v1y * v1y) * sqrt(v2x * v2x + v2y * v2y)
        if (d == 0f) return null
        return Math.toDegrees(acos(((v1x * v2x + v1y * v2y) / d).coerceIn(-1f, 1f)).toDouble()).toFloat()
    }

    private fun ok(p: Map<String, Pt>, vararg k: String) = k.all { (p[it]?.score ?: 0f) >= 0.5f }

    private fun torso(p: Map<String, Pt>): Float? {
        val sides = listOf("l", "r").filter { ok(p, "shoulder_$it", "hip_$it") }
        if (sides.isEmpty()) return null
        return sides.map { abs(p["hip_$it"]!!.y - p["shoulder_$it"]!!.y) }.average().toFloat().coerceAtLeast(1f)
    }

    /** The movement's signal, or null when the needed body points aren't visible. */
    private fun value(p: Map<String, Pt>): Float? = when (movement.signal) {
        Signal.KNEE_ANGLE, Signal.MIN_KNEE_ANGLE -> {
            val a = listOf("l", "r").filter { ok(p, "hip_$it", "knee_$it", "ankle_$it") }
                .mapNotNull { angle(p["hip_$it"]!!, p["knee_$it"]!!, p["ankle_$it"]!!) }
            when {
                movement.signal == Signal.KNEE_ANGLE && a.size == 2 -> a.average().toFloat()
                movement.signal == Signal.KNEE_ANGLE && a.size == 1 -> a[0]          // side view: one leg hidden
                movement.signal == Signal.MIN_KNEE_ANGLE && a.isNotEmpty() -> a.min()
                else -> null
            }
        }
        Signal.ELBOW_ANGLE, Signal.ELBOW_ANGLE_ANY -> {
            val a = listOf("l", "r").filter { ok(p, "shoulder_$it", "elbow_$it", "wrist_$it") }
                .mapNotNull { angle(p["shoulder_$it"]!!, p["elbow_$it"]!!, p["wrist_$it"]!!) }
            when {
                movement.signal == Signal.ELBOW_ANGLE && a.size == 2 -> a.average().toFloat()
                movement.signal == Signal.ELBOW_ANGLE_ANY && a.isNotEmpty() -> a.min()
                else -> null
            }
        }
        Signal.ARM_ELEVATION -> {
            val t = torso(p)
            if (t == null || !ok(p, "shoulder_l", "shoulder_r", "wrist_l", "wrist_r")) null
            else ((p["shoulder_l"]!!.y - p["wrist_l"]!!.y) + (p["shoulder_r"]!!.y - p["wrist_r"]!!.y)) / 2f / t
        }
        Signal.KNEE_LIFT -> {
            val t = torso(p)
            val l = listOf("l", "r").filter { ok(p, "hip_$it", "knee_$it") }.map { p["hip_$it"]!!.y - p["knee_$it"]!!.y }
            if (t == null || l.isEmpty()) null else l.max() / t
        }
    }

    fun update(points: Map<String, Pt>): Int {
        val v = value(points)
        if (v == null) { feedback = "Step back so the whole body is in view"; return reps }
        val atWork = if (movement.readyHigh) v <= movement.work else v >= movement.work
        val atReady = if (movement.readyHigh) v >= movement.ready else v <= movement.ready
        if (!inRep && atWork) { inRep = true; feedback = "Good, now back to the start" }
        else if (inRep && atReady) { inRep = false; reps++; feedback = "Rep $reps" }
        else if (!inRep) feedback = "Go"
        return reps
    }

    fun reset() { reps = 0; inRep = false; feedback = "Get into view" }

}
