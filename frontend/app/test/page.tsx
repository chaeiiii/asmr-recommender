"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, type NextRoute } from "../../lib/api";
import { featureLabel } from "../../lib/featureLabels";
import { useStep } from "../../components/useStep";
import LoadingState, { ErrorState } from "../../components/LoadingState";
type Answer = "like" | "neutral" | "dislike" | "skip";
type Sample = { sample_id: number; position: number; phase: string; youtube_video_id: string; start_sec: number; end_sec: number; response: Answer | null; primary_trigger?: { key: string; display_name: string } };
const answerLabels: Record<Answer, string> = { like: "좋아요", neutral: "보통", dislike: "싫어요", skip: "건너뛰기" };
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
  return <main className="page"><p className="eyebrow">내 취향 찾기</p><h1>소리를 듣고 취향을 알려주세요</h1><p>준비되면 재생해보세요. 듣기 어렵거나 원하지 않는 소리는 건너뛸 수 있어요.</p>
    {failed && <ErrorState retry={retry} korean />}{!data && !failed && <LoadingState korean />}
    {data && samples.length === 0 && <><p>지금은 들을 수 있는 샘플이 없어요.</p><button disabled={busy} onClick={() => void run(async () => setData(await api<Samples>("/test/samples")))}>다시 시도</button></>}
    {sample && <section aria-label="현재 소리 샘플"><p className="eyebrow">{sample.phase === "optional" ? "추가 소리 · " : "소리 "}{sample.position} / {samples.length}</p>
      <iframe key={sample.sample_id} className="player" title={`소리 샘플 ${sample.position}`} src={`https://www.youtube.com/embed/${encodeURIComponent(sample.youtube_video_id)}?start=${sample.start_sec}&end=${sample.end_sec}&playsinline=1&autoplay=0&controls=1`} allow="encrypted-media; picture-in-picture; fullscreen" allowFullScreen />
      {sample.response !== null && revealed !== undefined ? <div role="status"><p>{sample.primary_trigger ? `방금 들은 소리는 ${featureLabel(sample.primary_trigger)}이에요.` : "응답을 저장했어요."}</p><button disabled={busy} onClick={() => {
        if (samples.length === 8 && samples.every(item => item.response !== null)) void run(complete);
        else setRevealed(undefined);
      }}>{samples.length === 8 && samples.every(item => item.response !== null) ? "계속" : "다음"}</button></div> : <>
        <fieldset disabled={busy}><legend>이 소리는 어떠셨나요?</legend><div className="answer-grid">{(["like", "neutral", "dislike", "skip"] as const).map(value => <button key={value} onClick={() => answer(value)}>{answerLabels[value]}</button>)}</div></fieldset>
        <details><summary>영상이 재생되지 않나요?</summary><p>건너뛰어도 싫어하는 소리로 기록되지 않아요.</p><button disabled={busy} onClick={() => answer("skip", true)}>다른 소리 듣기</button></details>
      </>}
    </section>}
    {data && samples.length > 0 && !sample && <section><h2>{samples.length === 6 ? "소리 2개를 더 들어볼까요?" : "모든 소리를 들어봤어요"}</h2><div className="actions">
      {samples.length === 6 && <button disabled={busy} onClick={() => void run(async () => { setData(await api<Samples>("/test/extend", {})); })}>2개 더 듣기</button>}
      <button disabled={busy} onClick={() => void run(complete)}>계속</button>
    </div></section>}{busy && data && <p role="status">진행 상황을 저장하고 있어요…</p>}
  </main>;
}
