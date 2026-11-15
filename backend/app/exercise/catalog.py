"""Reusable exercise definitions. Every entry is an example, not a prescription."""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ExerciseDef:
    id: str
    name: str
    category: str          # strength | cardio | mobility | rehab
    description: str
    equipment: tuple[str, ...]
    tracking: str | None
    default_sets: int
    default_reps: int | None
    default_duration_s: int | None
    default_rest_s: int
    intensity: str
    cues: tuple[str, ...]
    steps: tuple[str, ...] = ()     # step-by-step instructions for the guided workout

    def to_dict(self) -> dict:
        raw = asdict(self)
        raw["equipment"] = list(self.equipment)
        raw["cues"] = list(self.cues)
        raw["steps"] = list(self.steps)
        raw["example_only"] = True
        return raw


EXERCISES: tuple[ExerciseDef, ...] = (
    # ---- camera-counted ------------------------------------------------------------------------------
    ExerciseDef("squat", "Bodyweight squat", "strength",
                "Sit the hips back and stand back up. Example strength movement.",
                ("bodyweight",), "squat", 3, 12, None, 60, "moderate",
                ("Full body in frame, ideally a slight side angle.", "Stop if a knee or back hurts."),
                ("Stand with feet shoulder-width apart.", "Push the hips back and bend the knees.",
                 "Go down until the thighs are about level.", "Stand back up. That is one rep.")),
    ExerciseDef("sumo_squat", "Wide squat", "strength",
                "A squat with a wide stance and toes turned out.",
                ("bodyweight",), "sumo_squat", 3, 12, None, 60, "moderate",
                ("Face the camera.", "Knees follow the toes."),
                ("Step wide, toes turned out.", "Lower straight down, knees over toes.",
                 "Pause at the bottom.", "Stand up tall.")),
    ExerciseDef("forward_lunge", "Forward lunge", "strength",
                "Step forward, bend the front knee, and return. Example strength movement.",
                ("bodyweight",), "forward_lunge", 3, 8, None, 60, "moderate",
                ("Keep the whole body visible.", "Count one repetition per step.", "Stop if a knee hurts."),
                ("Stand tall.", "Step one foot forward.", "Lower until both knees bend.", "Push back to standing. Switch legs.")),
    ExerciseDef("pushup", "Push-up", "strength",
                "Lower the chest toward the floor and push back up. A wall or knee push-up is a lighter option.",
                ("bodyweight",), "pushup", 3, 8, None, 60, "moderate",
                ("Side-on to the camera.", "Keep the body in one line."),
                ("Hands under the shoulders, body straight.", "Bend the elbows and lower the chest.",
                 "Stop with the elbows at about 90°.", "Push back up.")),
    ExerciseDef("arm_raise", "Arm raise", "mobility",
                "Raise both arms to about shoulder height and lower them. Example shoulder mobility movement.",
                ("bodyweight",), "arm_raise", 2, 12, None, 30, "easy",
                ("Face the camera.", "Keep the elbows soft."),
                ("Arms by your sides.", "Raise both arms out to shoulder height.", "Lower slowly.")),
    ExerciseDef("shoulder_press", "Shoulder press", "strength",
                "Press both hands from shoulder height to overhead. Band or light bottles add load.",
                ("bodyweight", "bands"), "shoulder_press", 3, 10, None, 45, "moderate",
                ("Face the camera.", "Do not arch the low back."),
                ("Hands at shoulder height, palms forward.", "Press straight up overhead.", "Lower back to the shoulders.")),
    ExerciseDef("bicep_curl", "Biceps curl", "strength",
                "Bend the elbows to bring the hands to the shoulders. Use a band or light bottles.",
                ("bands",), "bicep_curl", 3, 12, None, 45, "easy",
                ("Face the camera.", "Elbows stay by your sides."),
                ("Arms straight, palms forward.", "Curl the hands up to the shoulders.", "Lower slowly to straight arms.")),
    ExerciseDef("jumping_jack", "Jumping jacks", "cardio",
                "Jump the feet out while raising the arms overhead, then back. March it for a low-impact version.",
                ("bodyweight",), "jumping_jack", 3, 20, None, 30, "moderate",
                ("Face the camera.", "Land softly."),
                ("Feet together, arms down.", "Jump feet apart and swing arms overhead.", "Jump back to the start.")),
    ExerciseDef("high_knees", "High knees", "cardio",
                "March or jog in place, lifting each knee to hip height.",
                ("bodyweight",), "high_knees", 3, 20, None, 30, "moderate",
                ("Face the camera.", "Count one repetition per knee."),
                ("Stand tall.", "Lift one knee to hip height.", "Switch legs quickly.")),
    # ---- logged, not camera-counted ------------------------------------------------------------------
    ExerciseDef("glute_bridge", "Glute bridge", "strength",
                "Example hip-extension movement used when a squat is not a good fit.",
                ("bodyweight",), None, 3, 12, None, 45, "easy",
                ("Move slowly.",),
                ("Lie on your back, knees bent.", "Lift the hips until the body is straight.", "Lower slowly.")),
    ExerciseDef("plank", "Plank hold", "strength",
                "Example trunk hold, tracked by duration rather than repetitions.",
                ("bodyweight",), None, 3, None, 30, 45, "moderate",
                ("Stop if the low back hurts.",),
                ("Forearms under the shoulders.", "Body in one straight line.", "Hold and breathe.")),
    ExerciseDef("calf_raise", "Calf raise", "strength",
                "Example lower-leg movement.",
                ("bodyweight",), None, 3, 15, None, 30, "easy",
                ("Use a handhold for balance if you want to.",),
                ("Stand tall.", "Rise onto the toes.", "Lower the heels slowly.")),
    ExerciseDef("band_row", "Band row", "strength",
                "Example pulling movement. Requires a resistance band.",
                ("bands",), None, 3, 12, None, 45, "moderate",
                ("Skip this if no band is available.",),
                ("Hold the band with arms straight.", "Pull the elbows back.", "Return slowly.")),
    ExerciseDef("cycle", "Cycle ergometer", "cardio",
                "Example steady aerobic interval on a cycle ergometer or similar device.",
                ("cycle",), None, 1, None, 1200, 0, "moderate",
                ("Duration is the target, not a heart-rate prescription.",),
                ("Set a comfortable resistance.", "Pedal at a steady pace.", "Ease off for the last minute.")),
    ExerciseDef("brisk_march", "Brisk march in place", "cardio",
                "Example aerobic movement when a cycle is not available.",
                ("bodyweight",), None, 1, None, 600, 0, "moderate",
                ("Stay where you can keep your balance.",),
                ("Stand tall.", "March in place, swinging the arms.", "Keep a steady rhythm.")),
    ExerciseDef("hip_flexor_stretch", "Hip flexor stretch", "mobility",
                "Example mobility hold.",
                ("bodyweight",), None, 2, None, 30, 15, "easy",
                ("Ease into the stretch. Do not bounce.",),
                ("Kneel on one knee.", "Shift the hips forward gently.", "Hold, then switch sides.")),
    ExerciseDef("thoracic_rotation", "Thoracic rotation", "mobility",
                "Example upper-back mobility movement.",
                ("bodyweight",), None, 2, 8, None, 20, "easy",
                ("Turn only as far as is comfortable.",),
                ("Sit or kneel tall.", "Turn the chest to one side.", "Return and turn to the other side.")),
    ExerciseDef("shoulder_circles", "Shoulder circles", "mobility",
                "Example shoulder mobility movement.",
                ("bodyweight",), None, 2, 10, None, 20, "easy",
                ("Keep the movement small if the shoulder is sore.",),
                ("Arms relaxed.", "Roll the shoulders forward in circles.", "Then roll them backward.")),
    ExerciseDef("bird_dog", "Bird dog", "rehab",
                "Example slow opposite arm-and-leg reach. Used here as a gentle option, not therapy.",
                ("bodyweight",), None, 2, 6, None, 30, "easy",
                ("Move slowly.", "This is not a rehabilitation prescription."),
                ("On hands and knees.", "Reach one arm and the opposite leg out.", "Return and switch.")),
    ExerciseDef("heel_slide", "Heel slide", "rehab",
                "Example gentle knee-range movement. Used when a lunge is a poor fit. Not therapy.",
                ("bodyweight",), None, 2, 10, None, 30, "easy",
                ("Stay in a comfortable range.", "This is not a rehabilitation prescription."),
                ("Lie on your back, legs straight.", "Slide one heel toward you.", "Slide it back out.")),
)

CATALOG: dict[str, ExerciseDef] = {e.id: e for e in EXERCISES}


def catalog_list() -> list[dict]:
    return [e.to_dict() for e in EXERCISES]


def require_exercise(exercise_id: str) -> ExerciseDef:
    ex = CATALOG.get(exercise_id)
    if ex is None:
        raise KeyError(exercise_id)
    return ex
