import { useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import type { CrewMember } from "../api";
import { useAuth } from "../auth";
import { useApi } from "../hooks";
import Avatar from "./Avatar";

/** Selected astronaut is kept in the URL (?a=AST-001) so links are shareable. */
export function useSelectedAstronaut() {
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const crew = useApi<{ astronauts: CrewMember[] }>("/astronauts");
  const list = crew.data?.astronauts ?? [];
  const selected = params.get("a") ?? user?.astronaut_id ?? list[0]?.id ?? null;
  useEffect(() => {
    if (!params.get("a") && selected) {
      setParams((prev) => {
        const next = new URLSearchParams(prev);
        next.set("a", selected);
        return next;
      }, { replace: true });
    }
  }, [selected, params, setParams]);
  const select = (id: string) => setParams((prev) => {
    const next = new URLSearchParams(prev);
    next.set("a", id);
    return next;
  });
  return { crew: list, selected, select, current: list.find((c) => c.id === selected) };
}

export function AstronautPicker({ crew, selected, onSelect }: { crew: CrewMember[]; selected: string | null; onSelect: (id: string) => void }) {
  if (crew.length <= 1) return null;
  return (
    <div className="tabs" role="tablist" aria-label="Select astronaut">
      {crew.map((c) => (
        <button key={c.id} className={c.id === selected ? "on" : ""} onClick={() => onSelect(c.id)} role="tab" aria-selected={c.id === selected}>
          <Avatar id={c.id} size={22} />{c.callsign}{c.open_alerts > 0 && <span style={{ color: "var(--caution)", marginLeft: 6 }}>●</span>}
        </button>
      ))}
    </div>
  );
}
