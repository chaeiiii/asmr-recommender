"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, type NextRoute } from "../../lib/api";
import { useStep } from "../../components/useStep";
import LoadingState, { ErrorState } from "../../components/LoadingState";
type Answer = "like" | "neutral" | "dislike" | "skip";
type Sample = { sample_id: number; position: number; phase: string; youtube_video_id: string; start_sec: number; end_sec: number; response: Answer | null; primary_trigger?: { display_name: string } };
type Samples = { samples: Sample[] };
export default function SoundTest() {
  const router = useRouter();
  const { data, setData, busy, failed, run, retry } = useStep<Samples>("/test/samples");
  const [revealed, setRevealed] = useState<number>();
  const samples = data?.samples ?? [];
  const sample = revealed === undefined ? samples.find(item => item.response === null) : samples.find(item => item.sample_id === revealed);
  const complete = async () => { const result = await api<NextRoute>("/test/complete", {}); router.replace(result.next_route); };
  function answer(value: Answer, showAnother = false) {
    if (!sample) return;
    void run(async () => {
      await api(`/test/samples/${sample.sample_id}/response`, { response: value });
      setData(await api<Samples>("/test/samples"));
      setRevealed(showAnother ? undefined : sample.sample_id);
    });
  }
  return <main className="page"><p className="eyebrow">Find your sounds</p><h1>A little listening, at your pace</h1><p>Press play when you’re ready. Skip any sound you can’t play or don’t want to try.</p>
    {failed && <ErrorState retry={retry} />}{!data && !failed && <LoadingState />}
    {data && samples.length === 0 && <><p>No samples are available right now.</p><button disabled={busy} onClick={() => void run(async () => setData(await api<Samples>("/test/samples")))}>Try again</button></>}
    {sample && <section aria-label="Current sound sample"><p className="eyebrow">{sample.phase === "optional" ? "Optional sound · " : "Sound "}{sample.position} / {samples.length}</p>
      <iframe key={sample.sample_id} className="player" title={`Sound sample ${sample.position}`} src={`https://www.youtube.com/embed/${encodeURIComponent(sample.youtube_video_id)}?start=${sample.start_sec}&end=${sample.end_sec}&playsinline=1&autoplay=0&controls=1`} allow="encrypted-media; picture-in-picture; fullscreen" allowFullScreen />
      {sample.response !== null && revealed !== undefined ? <div role="status"><p>{sample.primary_trigger ? `That was ${sample.primary_trigger.display_name}.` : "Response saved."}</p><button disabled={busy} onClick={() => {
        if (samples.length === 8 && samples.every(item => item.response !== null)) void run(complete);
        else setRevealed(undefined);
      }}>{samples.length === 8 && samples.every(item => item.response !== null) ? "Continue" : "Next"}</button></div> : <>
        <fieldset disabled={busy}><legend>How did that sound feel?</legend><div className="answer-grid">{(["like", "neutral", "dislike", "skip"] as const).map(value => <button key={value} onClick={() => answer(value)}>{value[0].toUpperCase() + value.slice(1)}</button>)}</div></fieldset>
        <details><summary>Video unavailable?</summary><p>You can skip this sample without recording a dislike.</p><button disabled={busy} onClick={() => answer("skip", true)}>Show another</button></details>
      </>}
    </section>}
    {data && samples.length > 0 && !sample && <section><h2>{samples.length === 6 ? "Want to try 2 more sounds?" : "All sounds tried"}</h2><div className="actions">
      {samples.length === 6 && <button disabled={busy} onClick={() => void run(async () => { setData(await api<Samples>("/test/extend", {})); })}>Try 2 more</button>}
      <button disabled={busy} onClick={() => void run(complete)}>Continue</button>
    </div></section>}{busy && data && <p role="status">Saving your progress…</p>}
  </main>;
}
