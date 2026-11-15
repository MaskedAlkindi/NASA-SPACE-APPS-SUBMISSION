import { useCallback, useEffect, useRef, useState } from "react";
import { api, getToken, type Alert } from "./api";

/** Fetch JSON from the API; re-runs when deps change. `reload` refetches. */
export function useApi<T>(path: string | null, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [tick, setTick] = useState(0);
  const pathRef = useRef(path);
  useEffect(() => {
    if (!path) {
      setData(null);
      setError(null);
      setLoading(false);
      pathRef.current = path;
      return;
    }
    // A newer request must win. React Strict Mode aborts the first one, and that
    // aborted call used to set loading back to false before the real one finished,
    // which left pages blank.
    const ctl = new AbortController();
    let live = true;
    if (pathRef.current !== path) setData(null);
    pathRef.current = path;
    setLoading(true);
    setError(null);
    api<T>(path, { signal: ctl.signal })
      .then((d) => { if (live) setData(d); })
      .catch((e) => { if (live && e.name !== "AbortError") setError(e.message); })
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; ctl.abort(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, tick, ...deps]);
  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { data, error, loading, reload };
}

export interface LiveMeasurement { astronaut_id: string | null; metric: string; value: number; unit: string; timestamp: string; data_class: string }
export type LiveEvent =
  | { type: "measurements"; items: LiveMeasurement[] }
  | { type: "alert"; alert: Alert }
  | { type: "simulation"; state: any }
  | { type: "hello"; user: string };

/** Live WebSocket feed (auth via first message). Reconnects automatically. */
export function useLive(onEvent: (e: LiveEvent) => void) {
  const handler = useRef(onEvent);
  handler.current = onEvent;
  const [connected, setConnected] = useState(false);
  useEffect(() => {
    let ws: WebSocket | null = null;
    let stopped = false;
    let retry: number | undefined;
    const connect = () => {
      const proto = location.protocol === "https:" ? "wss" : "ws";
      ws = new WebSocket(`${proto}://${location.host}/api/v1/ws/live`);
      ws.onopen = () => ws?.send(JSON.stringify({ token: getToken() }));
      ws.onmessage = (m) => {
        const ev = JSON.parse(m.data);
        if (ev.type === "hello") setConnected(true);
        handler.current(ev);
      };
      ws.onclose = () => { setConnected(false); if (!stopped) retry = window.setTimeout(connect, 3000); };
      ws.onerror = () => ws?.close();
    };
    connect();
    return () => { stopped = true; window.clearTimeout(retry); ws?.close(); };
  }, []);
  return connected;
}
