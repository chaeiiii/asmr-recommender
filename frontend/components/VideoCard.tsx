"use client";
import { useRef, useState } from "react";
import { api, ApiError } from "../lib/api";
import FeatureChips from "./FeatureChips";
import YouTubePlayer from "./YouTubePlayer";
import type { Video } from "./catalogTypes";
type Action = "play" | "like" | "dislike" | "skip" | "save" | "remove";
function duration(seconds: number | null) {
  if (seconds === null) return "Duration unavailable";
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor(seconds % 3600 / 60);
  return `${hours ? `${hours}:` : ""}${hours ? String(minutes).padStart(2, "0") : minutes}:${String(seconds % 60).padStart(2, "0")}`;
}
export default function VideoCard({ video, initialSaved = false, exploration, surface, onSavedChange, onDismiss }: {
  video: Video; initialSaved?: boolean; exploration?: string;
  surface?: "home" | "discover" | "search" | "favorites";
  onSavedChange?: (id: number, saved: boolean) => void; onDismiss: (id: number) => void;
}) {
  const [savedOverride, setSaved] = useState<boolean>();
  const saved = savedOverride ?? initialSaved;
  const [sentiment, setSentiment] = useState<"like" | "dislike">();
  const [playing, setPlaying] = useState(false);
  const [busy, setBusy] = useState(false);
  const lock = useRef(false);
  const [failure, setFailure] = useState<{ action: Action; unavailable: boolean }>();
  const [message, setMessage] = useState("");
  async function act(action: Action) {
    if (lock.current) return;
    lock.current = true; setBusy(true); setFailure(undefined);
    try {
      if (action === "save" || action === "remove") {
        const result = await api<{ saved: boolean }>(`/videos/${video.video_id}/favorite`, action === "save" ? {} : undefined, action === "save" ? "POST" : "DELETE");
        setSaved(result.saved); onSavedChange?.(video.video_id, result.saved);
        setMessage(result.saved ? "Saved." : "Removed from Saved.");
      } else {
        await api(`/videos/${video.video_id}/interactions`, { type: action, surface });
        if (action === "play") setPlaying(true);
        if (action === "like" || action === "dislike") { setSentiment(action); setMessage(action === "like" ? "Liked. Your taste has been updated." : "Disliked. Your taste has been updated."); }
        if (action === "skip") onDismiss(video.video_id);
      }
    } catch (error) {
      setFailure({ action, unavailable: error instanceof ApiError && (error.code === "VIDEO_UNAVAILABLE" || error.code === "VIDEO_NOT_FOUND") });
    } finally { lock.current = false; setBusy(false); }
  }
  return <article className="video-card" aria-label={video.title}>
    {exploration && <p className="eyebrow">{exploration}</p>}
    {playing ? <YouTubePlayer id={video.youtube_video_id} title={video.title} another={() => onDismiss(video.video_id)} /> : video.thumbnail_url ? <img className="thumbnail" src={video.thumbnail_url} alt="" loading="lazy" /> : <div className="thumbnail placeholder">Preview unavailable</div>}
    <h2>{video.title}</h2><p className="video-meta">{video.channel_name} · {duration(video.duration_sec)}</p>
    <FeatureChips features={video.features} />
    {!!video.reasons?.length && <p>{exploration ? "Explore" : "Because of your interest in"} {video.reasons.map(reason => reason.display_name).join(" and ")}.</p>}
    <div className="card-actions"><button className="primary" disabled={busy} onClick={() => playing ? setPlaying(false) : void act("play")}>{playing ? "Close player" : "Play"}</button>
      <button disabled={busy} aria-pressed={sentiment === "like"} onClick={() => void act("like")}>Like</button>
      <button disabled={busy} aria-pressed={sentiment === "dislike"} onClick={() => void act("dislike")}>Dislike</button>
      <button disabled={busy} aria-pressed={saved} onClick={() => void act(saved ? "remove" : "save")}>{saved ? "Remove saved" : "Save"}</button>
      <button disabled={busy} onClick={() => void act("skip")}>Skip</button></div>
    <p role="status" className="video-meta">{busy ? "Saving…" : message}</p>
    {failure && <div role="alert" className="error"><p>{failure.unavailable ? "This video is unavailable. Retry or try another result." : "That action could not be saved. Please retry."}</p><div className="card-actions"><button disabled={busy} onClick={() => void act(failure.action)}>Retry</button>{failure.unavailable && <button onClick={() => onDismiss(video.video_id)}>Show another</button>}</div></div>}
  </article>;
}
