"use client";
import Link from "next/link";
import { useState } from "react";
import { useResource } from "./useResource";
import LoadingState, { ErrorState } from "./LoadingState";
import VideoCard from "./VideoCard";
import type { Preferences, Video, VideoResults } from "./catalogTypes";
export default function VideoFeed({ kind }: { kind: "home" | "discover" | "favorites" }) {
  const feed = useResource<VideoResults>(kind === "home" ? "/recommendations?limit=20" : kind === "discover" ? "/discover?limit=10" : "/favorites");
  const saved = useResource<VideoResults>(kind === "favorites" ? null : "/favorites");
  const profile = useResource<Preferences>(kind === "discover" ? "/me/preferences" : null);
  const [hidden, setHidden] = useState<number[]>([]);
  function refresh() { setHidden([]); feed.retry(); profile.retry(); saved.retry(); }
  function exploration(video: Video) {
    if (kind !== "discover") return undefined;
    const liked = video.features.some(feature => profile.data?.features.some(pref => pref.key === feature.key && ["like", "love"].includes(pref.display_state)));
    const low = video.features.some(feature => profile.data?.unknown_or_low_evidence.some(pref => pref.key === feature.key));
    return liked && low ? "Near your taste · something new to explore" : low ? "Try something new · not tried or low evidence" : "Try something new";
  }
  const items = feed.data?.items.filter(video => !hidden.includes(video.video_id)) ?? [];
  return <main className="page"><p className="eyebrow">Your ASMR collection</p><h1>{kind === "home" ? "For You" : kind === "discover" ? "Discover" : "Saved"}</h1>
    <p>{kind === "home" ? "A little more of what you enjoy. Your feedback helps your taste evolve." : kind === "discover" ? "Explore sounds and styles you are still getting to know." : "Your saved videos, newest first."}</p>
    <button onClick={refresh} disabled={feed.loading}>Refresh</button>
    {feed.loading && <LoadingState />}{feed.failed && <ErrorState retry={refresh} />}
    {kind !== "favorites" && saved.failed && <div className="error"><p>Saved status could not be loaded.</p><button onClick={saved.retry}>Retry saved status</button></div>}
    {kind === "discover" && profile.failed && <div className="error"><p>Taste details could not be loaded. You can still explore.</p><button onClick={profile.retry}>Retry taste details</button></div>}
    {!feed.loading && !feed.failed && !items.length && <section className="panel"><h2>{kind === "favorites" ? "No saved videos to show" : "No more videos right now"}</h2><p>{kind === "favorites" ? "Save videos you want to return to." : "Refresh for more results, or explore another page."}</p><Link className="text-link" href={kind === "home" ? "/discover" : "/home"}>{kind === "home" ? "Explore Discover" : "See my recommendations"}</Link></section>}
    {!feed.loading && items.map(video => <VideoCard key={video.video_id} video={video} surface={kind} initialSaved={kind === "favorites" || !!saved.data?.items.some(item => item.video_id === video.video_id)} exploration={exploration(video)} onDismiss={id => setHidden(values => [...values, id])} onSavedChange={(id, value) => { if (kind === "favorites" && !value) setHidden(values => [...values, id]); }} />)}
  </main>;
}
