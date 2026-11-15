import { useId } from "react";

// Hand-drawn crew portraits (inline SVG, wobbly "pencil" lines). One look per astronaut id.
type Look = {
  bg: string; skin: string;
  hair?: "short" | "wavy" | "spiky";
  hat?: "kumma" | "mussar";
  beard?: "full" | "short" | "stubble";
  mustache?: boolean; glasses?: boolean; headset?: boolean; camera?: boolean; helmet?: boolean;
};

const LOOKS: Record<string, Look> = {
  "AST-001": { bg: "#ffd27a", skin: "#c98d63", hair: "short", beard: "short", glasses: true },
  "AST-002": { bg: "#9ad3ff", skin: "#b97c55", hair: "wavy", beard: "full" },
  "AST-003": { bg: "#ffb3a7", skin: "#d29b72", hat: "kumma", mustache: true, beard: "stubble" },
  "AST-004": { bg: "#b9e4a6", skin: "#a86f4c", hair: "spiky", beard: "stubble", headset: true },
  "AST-005": { bg: "#c9b6ff", skin: "#c48a60", hat: "mussar", beard: "short", camera: true },
  "AST-900": { bg: "#d6dde8", skin: "#c48a60", hair: "short", helmet: true },
};
const FALLBACK: Look = { bg: "#e6e1d6", skin: "#c48a60", hair: "short" };
const INK = "#17191f", HAIR = "#211a17";

export default function Avatar({ id, size = 64, title }: { id?: string | null; size?: number; title?: string }) {
  const L = (id && LOOKS[id]) || FALLBACK;
  const f = `rough${useId().replace(/:/g, "")}`;
  const seed = id ? [...id].reduce((a, c) => a + c.charCodeAt(0), 0) % 97 : 3;
  const line = { stroke: INK, strokeWidth: 2.2, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  return (
    <svg className="avatar" width={size} height={size} viewBox="0 0 120 120" role="img" aria-label={title ?? "crew portrait"}>
      <defs>
        <filter id={f} x="-5%" y="-5%" width="110%" height="110%">
          <feTurbulence type="fractalNoise" baseFrequency="0.035" numOctaves="2" seed={seed} />
          <feDisplacementMap in="SourceGraphic" scale="2.6" />
        </filter>
        <clipPath id={`${f}c`}><circle cx="60" cy="60" r="57" /></clipPath>
      </defs>
      <g filter={`url(#${f})`}>
        <circle cx="60" cy="60" r="57" fill={L.bg} {...line} />
        <g clipPath={`url(#${f}c)`}>
          {/* little stars */}
          <path d="M20 30l2 5 5 2-5 2-2 5-2-5-5-2 5-2z M98 22l1.5 3.5 3.5 1.5-3.5 1.5-1.5 3.5-1.5-3.5-3.5-1.5 3.5-1.5z" fill="#fff" opacity=".8" />
          {/* suit */}
          <path d="M18 122 C20 98 38 88 60 88 C82 88 100 98 102 122 Z" fill="#f4f1ea" {...line} />
          <path d="M40 92 C46 98 74 98 80 92" fill="none" {...line} stroke="#7d8aa0" />
          <circle cx="82" cy="106" r="5" fill="#d81b1b" {...line} strokeWidth={1.6} />
          <path d="M34 104 h12" {...line} stroke="#005c96" strokeWidth={3} />
          <rect x="52" y="76" width="16" height="14" rx="4" fill={L.skin} {...line} />
        </g>
        {L.camera && (
          <g>
            <path d="M44 90 L50 104 M76 90 L70 104" {...line} strokeWidth={1.6} />
            <rect x="48" y="100" width="24" height="15" rx="3" fill="#2a2d35" {...line} />
            <circle cx="60" cy="107.5" r="4.5" fill="#6c9cff" {...line} strokeWidth={1.6} />
            <circle cx="61.5" cy="106" r="1.2" fill="#fff" />
          </g>
        )}
        {/* ears + head */}
        <circle cx="32" cy="58" r="6" fill={L.skin} {...line} />
        <circle cx="88" cy="58" r="6" fill={L.skin} {...line} />
        <circle cx="60" cy="56" r="28" fill={L.skin} {...line} />
        {/* beard */}
        {L.beard === "full" && <path d="M33 58 C34 82 46 90 60 90 C74 90 86 82 87 58 C82 72 74 77 60 77 C46 77 38 72 33 58Z" fill={HAIR} {...line} />}
        {L.beard === "short" && <path d="M35 62 C38 80 48 86 60 86 C72 86 82 80 85 62 C80 74 72 79 60 79 C48 79 40 74 35 62Z" fill={HAIR} opacity=".85" {...line} strokeWidth={1.4} />}
        {L.beard === "stubble" && <path d="M36 62 C39 79 48 84 60 84 C72 84 81 79 84 62 C80 73 72 78 60 78 C48 78 40 73 36 62Z" fill={HAIR} opacity=".28" />}
        {/* hair / hats */}
        {L.hair === "short" && <path d="M32 54 C29 31 45 23 60 23 C76 23 91 31 88 54 C84 43 76 37 60 38 C46 37 36 43 32 54Z" fill={HAIR} {...line} />}
        {L.hair === "wavy" && <path d="M31 56 C25 30 44 17 60 20 C80 17 95 32 89 56 C86 46 82 40 76 43 C72 36 66 41 60 37 C54 41 48 36 44 43 C38 40 34 47 31 56Z" fill={HAIR} {...line} />}
        {L.hair === "spiky" && <path d="M32 52 L33 34 L42 38 L45 23 L54 32 L60 18 L66 32 L75 23 L78 38 L87 34 L88 52 C80 43 70 39 60 39 C50 39 40 43 32 52Z" fill={HAIR} {...line} />}
        {L.hat === "kumma" && (
          <g>
            <path d="M31 47 C31 29 44 22 60 22 C76 22 89 29 89 47 Z" fill="#fbf7ee" {...line} />
            <path d="M33 41 H87 M40 31 C46 34 52 30 60 33 C68 30 74 34 80 31" fill="none" stroke="#d81b1b" strokeWidth={1.6} strokeLinecap="round" />
            {[40, 48, 56, 64, 72, 80].map((x) => <circle key={x} cx={x} cy="37" r="1.6" fill="#005c96" />)}
          </g>
        )}
        {L.hat === "mussar" && (
          <g>
            <path d="M27 49 C24 26 43 15 60 15 C79 15 96 26 93 49 C85 40 73 37 60 37 C47 37 35 40 27 49Z" fill="#e9b949" {...line} />
            <path d="M32 38 C46 28 74 28 88 38 M30 30 C46 20 74 20 90 30 M44 18 L54 36 M60 15 L66 36 M76 18 L80 34" fill="none" stroke="#9c3d2e" strokeWidth={1.7} strokeLinecap="round" />
            <path d="M90 32 C100 34 102 44 96 50" fill="none" {...line} stroke="#9c3d2e" />
          </g>
        )}
        {/* face */}
        <path d="M44 47 Q49 44 54 47 M66 47 Q71 44 76 47" fill="none" {...line} />
        <ellipse cx="49" cy="56" rx="4" ry="5" fill={INK} />
        <ellipse cx="71" cy="56" rx="4" ry="5" fill={INK} />
        <circle cx="50.6" cy="54" r="1.5" fill="#fff" />
        <circle cx="72.6" cy="54" r="1.5" fill="#fff" />
        <ellipse cx="41" cy="66" rx="5" ry="3" fill="#ff7a7a" opacity=".45" />
        <ellipse cx="79" cy="66" rx="5" ry="3" fill="#ff7a7a" opacity=".45" />
        {L.mustache && <path d="M50 66 C54 61.5 58 63.5 60 65.5 C62 63.5 66 61.5 70 66 C66 68 62 68 60 67 C58 68 54 68 50 66Z" fill={HAIR} />}
        <path d="M52 69 Q60 78 68 69 Q60 72 52 69Z" fill="#7a2e2e" {...line} strokeWidth={1.8} />
        {L.glasses && (
          <g fill="none" {...line} strokeWidth={2}>
            <circle cx="49" cy="56" r="8" /><circle cx="71" cy="56" r="8" /><path d="M57 55 Q60 53 63 55 M41 55 L33 53 M79 55 L87 53" />
          </g>
        )}
        {L.headset && (
          <g>
            <path d="M30 58 C28 24 92 24 90 58" fill="none" stroke="#333a47" strokeWidth={3.4} strokeLinecap="round" />
            <rect x="25" y="51" width="9" height="15" rx="4" fill="#333a47" {...line} strokeWidth={1.6} />
            <rect x="86" y="51" width="9" height="15" rx="4" fill="#333a47" {...line} strokeWidth={1.6} />
            <path d="M30 64 C32 74 40 76 47 74" fill="none" stroke="#333a47" strokeWidth={2.4} strokeLinecap="round" />
            <circle cx="48" cy="74" r="2.6" fill="#d81b1b" />
          </g>
        )}
        {L.helmet && (
          <g>
            <circle cx="60" cy="57" r="38" fill="#bfe3ff" opacity=".28" {...line} strokeWidth={3} />
            <path d="M34 38 C40 28 50 24 58 24" fill="none" stroke="#fff" strokeWidth={4} strokeLinecap="round" opacity=".9" />
          </g>
        )}
      </g>
    </svg>
  );
}
