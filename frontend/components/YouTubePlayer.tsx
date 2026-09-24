"use client";
import { useEffect, useRef, useState } from "react";
type Player = { destroy: () => void };
type YouTubeApi = { Player: new (element: HTMLIFrameElement, options: { events: { onError: () => void } }) => Player };
type PlayerWindow = Window & { YT?: YouTubeApi; onYouTubeIframeAPIReady?: () => void };
let apiReady: Promise<YouTubeApi> | undefined;
function loadPlayerApi() {
  const playerWindow = window as PlayerWindow;
  if (playerWindow.YT?.Player) return Promise.resolve(playerWindow.YT);
  if (!apiReady) {
    apiReady = new Promise<YouTubeApi>((resolve, reject) => {
      const previous = playerWindow.onYouTubeIframeAPIReady;
      const script = document.createElement("script");
      const timeout = window.setTimeout(() => { script.remove(); reject(new Error("Player timed out")); }, 15000);
      playerWindow.onYouTubeIframeAPIReady = () => {
        window.clearTimeout(timeout);
        if (playerWindow.YT?.Player) resolve(playerWindow.YT);
        else reject(new Error("Player unavailable"));
        previous?.();
      };
      script.src = "https://www.youtube.com/iframe_api";
      script.onerror = () => { window.clearTimeout(timeout); script.remove(); reject(new Error("Player unavailable")); };
      document.head.appendChild(script);
    }).catch(error => { apiReady = undefined; throw error; });
  }
  return apiReady;
}
export default function YouTubePlayer({ id, title, another }: { id: string; title: string; another: () => void }) {
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const container = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const host = container.current;
    if (!host || failed) return;
    let active = true;
    let player: Player | undefined;
    // Keep the full official iframe visible; the API only observes playback errors.
    const iframe = document.createElement("iframe");
    iframe.className = "player";
    iframe.title = `Play ${title}`;
    iframe.src = `https://www.youtube.com/embed/${encodeURIComponent(id)}?autoplay=1&playsinline=1&controls=1&enablejsapi=1&origin=${encodeURIComponent(window.location.origin)}`;
    iframe.allow = "autoplay; encrypted-media; picture-in-picture; fullscreen";
    iframe.allowFullscreen = true;
    iframe.referrerPolicy = "strict-origin-when-cross-origin";
    iframe.onerror = () => { if (active) setFailed(true); };
    host.appendChild(iframe);
    loadPlayerApi().then(yt => {
      if (active) player = new yt.Player(iframe, { events: { onError: () => { if (active) setFailed(true); } } });
    }).catch(() => { if (active) setFailed(true); });
    return () => { active = false; player?.destroy(); host.replaceChildren(); };
  }, [id, title, attempt, failed]);
  return <div>
    <div ref={container} />
    {failed ? <div className="error" role="alert"><p>This video could not be played. Your taste has not changed.</p><div className="card-actions"><button onClick={() => { setFailed(false); setAttempt(value => value + 1); }}>Retry player</button><button onClick={another}>Show another</button></div></div> : <button onClick={() => setFailed(true)}>Can’t play this video?</button>}
  </div>;
}
