"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
export function useStep<T>(path: string) {
  const [data, setData] = useState<T>();
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const lock = useRef(false);
  const last = useRef<() => Promise<void>>(async () => {});
  const run = useCallback(async (action: () => Promise<void>) => {
    if (lock.current) return;
    lock.current = true; last.current = action; setBusy(true); setFailed(false);
    try { await action(); } catch { setFailed(true); }
    finally { lock.current = false; setBusy(false); }
  }, []);
  useEffect(() => { void run(async () => setData(await api<T>(path))); }, [path, run]);
  return { data, setData, busy, failed, run, retry: () => { void run(last.current); } };
}
