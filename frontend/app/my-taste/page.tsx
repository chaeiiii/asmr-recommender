"use client";
import Link from "next/link";
import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { useResource } from "../../components/useResource";
import LoadingState, { ErrorState } from "../../components/LoadingState";
import { languageOptions, stateLabels, type Preference, type Preferences } from "../../components/catalogTypes";
function Group({ title, items, empty }: { title: string; items: Preference[]; empty: string }) {
  return <section className="panel"><h2>{title}</h2>{items.length ? <ul className="taste-list">{items.map(item => <li key={item.key}><span>{item.display_name}</span><span className="state-label">{stateLabels[item.display_state]}{item.evidence_count === 1 ? " · Low evidence" : ""}</span></li>)}</ul> : <p>{empty}</p>}</section>;
}
function Taste() {
  const first = useSearchParams().get("first") === "1";
  const { data, loading, failed, retry } = useResource<Preferences>("/me/preferences");
  const likes = data?.features.filter(item => item.display_state === "love" || item.display_state === "like") ?? [];
  return <main className="page"><p className="eyebrow">{first ? "Your first taste snapshot" : "Your living profile"}</p><h1>{first ? "Your current taste" : "My Taste"}</h1><p>Your taste grows as you listen and give feedback. Untried does not mean disliked.</p>
    {loading && <LoadingState />}{failed && <ErrorState retry={retry} />}
    {data && !loading && <><section className="panel"><h2>Taste Summary</h2><p>{likes.length ? `Your current likes include ${likes.slice(0, 3).map(item => item.display_name).join(", ")}.` : "Your profile is still taking shape. Try a few videos to find what you enjoy."}</p></section>
      <Group title="Favorite Sounds" items={likes.filter(item => item.family === "sound")} empty="No favorite sounds yet." />
      <section className="panel"><h2>Voice + Languages</h2><p>Voice: {({ talking: "Talking", no_talking: "No talking", both: "Talking and no talking" } as Record<string, string>)[data.voice_mode ?? ""] ?? "Not selected"}</p><p>Languages: {data.voice_mode === "no_talking" ? "Not used for no talking" : data.no_preference ? "No preference" : data.languages.length ? data.languages.map(code => languageOptions.find(([value]) => value === code)?.[1] ?? code).join(", ") : "Not selected"}</p><p>Language is a soft preference.</p></section>
      <Group title="Visual + Format likes" items={likes.filter(item => ["visual", "format"].includes(item.family))} empty="No Visual or Format likes yet." />
      {data.features.some(item => item.evidence_count > 0 && ["neutral", "dislike"].includes(item.display_state)) && <Group title="Neutral / Disliked" items={data.features.filter(item => item.evidence_count > 0 && ["neutral", "dislike"].includes(item.display_state))} empty="" />}
      <Group title="Not tried yet / Low evidence" items={data.unknown_or_low_evidence} empty="All current features have at least two observations." />
      {!!data.recent_discoveries?.length && <Group title="Recently discovered" items={data.recent_discoveries} empty="" />}
    </>}
    <div className="actions"><Link className="link-button" href="/discover">Discover new tastes</Link><Link className="link-button primary" href="/home">{first ? "See my recommendations" : "See ASMR for my taste"}</Link></div>
  </main>;
}
export default function Page() { return <Suspense fallback={<main className="page"><LoadingState /></main>}><Taste /></Suspense>; }
