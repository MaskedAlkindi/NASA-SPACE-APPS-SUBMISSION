// Hand-drawn space doodles from the team's notebook mockup (Loveable/donkey-star-road), kept as inline SVG.
export type SketchKind = "planet" | "rocket" | "satellite" | "moon" | "astronaut" | "comet" | "stars" | "ufo";

export function SpaceSketch({ kind = "planet", className = "" }: { kind?: SketchKind; className?: string }) {
  return (
    <svg viewBox="0 0 120 120" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"
      strokeLinejoin="round" className={`space-sketch ${className}`} aria-hidden="true">
      {kind === "moon" ? (
        <>
          <path d="M70 14C44 16 24 38 25 63s23 45 48 44c-21-7-34-25-33-47 1-20 12-37 30-46Z" />
          <path d="M68 16C47 22 34 40 36 62c1 19 14 36 35 43" opacity=".35" />
          <path d="M44 52q3 3 7 0m-12 15q5 4 9 0" /><path d="M53 78q-4 4-9 1" />
          <circle cx="40" cy="42" r="3" opacity=".5" /><circle cx="48" cy="92" r="2.5" opacity=".5" />
          <path d="M90 30v10m-5-5h10M100 70v8m-4-4h8M84 96l2 4 4 2-4 2-2 4-2-4-4-2 4-2Z" />
        </>
      ) : kind === "astronaut" ? (
        <>
          <circle cx="60" cy="38" r="20" />
          <path d="M47 34c4-9 22-9 26 0 1 8-5 12-13 12s-14-4-13-12Z" />
          <path d="M44 56c-8 4-12 14-11 26l12 1 2-14m26-13c8 4 12 14 11 26l-12 1-2-14" />
          <path d="M46 60h28l-2 30H48Z" /><path d="M48 90l-3 18h12l3-16 3 16h12l-3-18" />
          <path d="M54 68h12v8H54Z" opacity=".6" />
          <path d="M77 60c10-6 22-4 30 4" strokeDasharray="3 4" opacity=".5" />
          <path d="M16 20v8m-4-4h8M100 100v8m-4-4h8" />
        </>
      ) : kind === "comet" ? (
        <>
          <circle cx="84" cy="34" r="9" />
          <path d="M77 40 22 92m52-46-42 52m50-60L16 76m54-26-46 50" opacity=".55" />
          <path d="M20 22v8m-4-4h8M100 86v8m-4-4h8" />
        </>
      ) : kind === "stars" ? (
        <>
          <path d="M30 22l5 12 13 1-10 8 4 13-12-7-11 7 3-13-10-8 13-1Z" />
          <path d="M84 60l3 8 9 1-7 5 3 9-8-5-8 5 2-9-7-5 9-1Z" />
          <path d="M44 88v12m-6-6h12M92 20v10m-5-5h10M70 36l1 3 3 1-3 1-1 3-1-3-3-1 3-1Z" />
          <path d="M34 44c10 14 30 20 46 20" strokeDasharray="2 5" opacity=".5" />
        </>
      ) : kind === "ufo" ? (
        <>
          <path d="M40 52c0-14 40-14 40 0" /><ellipse cx="60" cy="58" rx="40" ry="10" />
          <path d="M28 62c8 6 56 6 64 0" opacity=".5" />
          <circle cx="40" cy="58" r="2" /><circle cx="60" cy="61" r="2" /><circle cx="80" cy="58" r="2" />
          <path d="M48 70 38 104m34-34 10 34" strokeDasharray="3 4" opacity=".5" />
        </>
      ) : kind === "planet" ? (
        <>
          <path d="M38 29C64 13 91 35 85 63S43 94 30 68C19 45 26 36 38 29Z" />
          <path d="M32 38C48 18 80 31 84 48M34 71C49 88 74 76 81 66" opacity=".4" />
          <ellipse cx="58" cy="59" rx="53" ry="12" transform="rotate(-25 58 59)" />
          <path d="m48 34 13 6m-30 20 7 3m25 3 10 5m-25 4 5 2M100 20v10m-5-5h10M17 91v8m-4-4h8" />
        </>
      ) : kind === "rocket" ? (
        <>
          <path d="M47 75C33 47 61 18 82 13 93 38 79 66 60 80Z" />
          <path d="m48 43-22 10 1 23 19-9m27-6 1 23-20 14-1-19" /><circle cx="65" cy="40" r="10" />
          <path d="M43 82 32 106 53 91M39 81l-15 18m31-10-11 22M20 22v11m-5-6h10M96 85v10m-5-5h10" />
        </>
      ) : (
        <>
          <path d="m46 42 27 12-16 30-27-12Z" />
          <path d="m40 40-22-12-15 26 24 13m46-10 28 13-15 24-25-12M45 44l-12 23m27-16-14 23M18 33l-8 18m19-12-8 18m59 7-9 18m21-12-9 18M55 41l8-17m-7-4 14 7M50 85l-3 16" />
          <circle cx="64" cy="22" r="4" />
        </>
      )}
    </svg>
  );
}
