"use client";
import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { resumeSession, type Session } from "../lib/api";
import BottomNav from "./BottomNav";
import LoadingState, { ErrorState } from "./LoadingState";
export default function SessionGate({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const router = useRouter();
  const [checked, setChecked] = useState<{ path: string; session: Session }>();
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    setError(false);
    resumeSession().then(session => {
      if (!active) return;
      const onboarding = path === "/test" || path.startsWith("/onboarding/");
      const target = session.onboarding_completed ? (path === "/" || onboarding ? "/home" : path) : session.next_route;
      if (target !== path) router.replace(target);
      else setChecked({ path, session });
    }).catch(() => { if (active) setError(true); });
    return () => { active = false; };
  }, [path, router, attempt]);
  if (error) return <main className="page"><ErrorState retry={() => setAttempt(value => value + 1)} /></main>;
  if (checked?.path !== path) return <main className="page"><h1>Find my ASMR taste</h1><p>Personalized ASMR, based on what you enjoy listening to.</p><LoadingState /></main>;
  return <>{children}{checked.session.onboarding_completed && <BottomNav />}</>;
}
