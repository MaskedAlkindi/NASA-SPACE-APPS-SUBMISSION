import { useState } from "react";

// A small plug-in game. The board follows the real engine: fixed inputs,
// swappable models (the registry), and one voice (offline, Ollama, or OpenAI).

type Model = { id: string; name: string; about: string };
type Voice = { id: string; name: string; about: string };

const MODELS: Model[] = [
  { id: "illness", name: "illness", about: "earth research. Stanford smartwatches. on, and it can raise an alert." },
  { id: "glucose", name: "glucose", about: "earth research. CGMacros. on, informational." },
  { id: "fatigue", name: "fatigue", about: "earth research. PMData. on, informational. the wearables alone are a weak signal." },
  { id: "sleep", name: "sleep", about: "a check of the math on MMASH. on. not a forecast." },
  { id: "ortho", name: "ortho", about: "earth research, CVES sit-to-stand. in the registry, shipped switched off." },
  { id: "anomaly", name: "anomaly", about: "simulation. the original anomaly model." },
  { id: "forecast", name: "forecast", about: "simulation. the original 7-day trend." },
  { id: "simfat", name: "sim fatigue", about: "simulation. the original fatigue estimate." },
];

const VOICES: Voice[] = [
  { id: "offline", name: "offline", about: "no LLM. a fixed explainer, so it still speaks with the wifi off." },
  { id: "qwen", name: "Qwen", about: "local, through Ollama. the health notes stay on the machine." },
  { id: "openai", name: "OpenAI", about: "a cloud model. same notes in, and the same rule against invented numbers." },
];

const INPUTS = [
  ["watch", "phone & watch"],
  ["check-in", "mood & fatigue"],
  ["cabin", "air & radiation"],
];

const START = ["illness", "glucose", "fatigue", "sleep"];

const LOOSE = "M14 18 H86 V34 C86 34 100 36 100 50 C100 64 86 66 86 66 V82 H14 V66 C14 66 0 64 0 50 C0 36 14 34 14 34 Z";

function modelById(id: string) {
  return MODELS.find((m) => m.id === id)!;
}

function Bit({
  name, label, tone = "", held = false, on = false, empty = false, locked = false, onClick,
}: {
  name: string; label: string; tone?: string; held?: boolean; on?: boolean; empty?: boolean; locked?: boolean; onClick?: () => void;
}) {
  const cls = `sk-bit ${tone} ${held ? "is-held" : ""} ${on ? "is-on" : ""} ${empty ? "is-empty" : ""} ${locked ? "is-lock" : ""}`;
  const face = (
    <>
      <svg viewBox="0 0 100 100" aria-hidden="true"><path d={LOOSE} /></svg>
      <b>{name}</b>
    </>
  );
  if (locked || !onClick) return <div className={cls}>{face}</div>;
  return (
    <button type="button" className={cls} aria-pressed={held || on} aria-label={label} onClick={onClick}>
      {face}
    </button>
  );
}

export function Puzzle() {
  const [board, setBoard] = useState<string[]>(START);
  const [held, setHeld] = useState<string | null>(null);
  const [voice, setVoice] = useState("offline");

  const bench = MODELS.filter((m) => !board.includes(m.id) && m.id !== held);
  const voiceNow = VOICES.find((v) => v.id === voice)!;
  const heldModel = held ? modelById(held) : null;

  function pick(id: string) {
    setBoard((prev) => prev.filter((s) => s !== id));
    setHeld(id);
  }

  function onBoardPiece(index: number) {
    const id = board[index];
    if (!held) {
      pick(id);
      return;
    }
    setBoard((prev) => prev.map((s, i) => (i === index ? held : s)));
    setHeld(null);
  }

  function onAdd() {
    if (!held) return;
    setBoard((prev) => [...prev, held]);
    setHeld(null);
  }

  function reset() {
    setBoard(START);
    setHeld(null);
    setVoice("offline");
  }

  const names = board.map((id) => modelById(id).name);
  const now = names.length
    ? `${names.join(" · ")}  ·  voice: ${voiceNow.name}`
    : `no models in  ·  voice: ${voiceNow.name}`;

  return (
    <div className="sk-game">
      <div className="sk-lane">
        <h3>what comes in</h3>
        <p>these stay put. every model reads the same notes.</p>
        <div className="sk-slots">
          {INPUTS.map(([name, note]) => (
            <Bit key={name} name={name} label={`${name}, ${note}. fixed.`} locked />
          ))}
        </div>
      </div>

      <div className="sk-lane">
        <h3>the models</h3>
        <p>earth research first, then the math check. simulation waits on the bench. take one out, or add another.</p>
        <div className="sk-slots">
          {board.map((id, i) => {
            const m = modelById(id);
            return (
              <Bit key={id} name={m.name} label={`${m.name}. ${m.about} tap to take it out.`} onClick={() => onBoardPiece(i)} />
            );
          })}
          {(bench.length > 0 || held) && (
            <Bit name="add" label={held ? `add ${heldModel!.name}` : "empty socket. pick up a model from the bench first."} empty onClick={onAdd} />
          )}
        </div>
        <div className="sk-bench">
          <span>on the bench</span>
          {bench.length === 0 && !held && <em>nothing waiting</em>}
          {bench.map((m) => (
            <Bit key={m.id} name={m.name} label={`${m.name}. ${m.about} tap to pick it up.`} onClick={() => pick(m.id)} />
          ))}
          {heldModel && (
            <button type="button" className="sk-reset" onClick={() => setHeld(null)}>set it aside</button>
          )}
        </div>
      </div>

      <div className="sk-lane">
        <h3>the voice</h3>
        <p>one explainer. tap another to swap it. if that one can't answer, offline does.</p>
        <div className="sk-slots">
          {VOICES.map((v) => (
            <Bit
              key={v.id}
              name={v.name}
              tone="voice"
              on={v.id === voice}
              label={v.id === voice ? `${v.name} is explaining. ${v.about}` : `swap in ${v.name}. ${v.about}`}
              onClick={() => setVoice(v.id)}
            />
          ))}
        </div>
      </div>

      <div className="sk-hand" aria-live="polite">
        {heldModel && <Bit name={heldModel.name} label="" held />}
        <p className="sk-game-now">{heldModel ? `${heldModel.name} is in your hand. ${heldModel.about}` : now}</p>
      </div>
      <p className="sk-aside">tap a model to take it out. tap one on the bench, then a model or “add”, to put it in. the others keep running.</p>
      <button type="button" className="sk-reset" onClick={reset}>back to the defaults</button>
    </div>
  );
}
