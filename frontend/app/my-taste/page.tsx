"use client";
import Link from "next/link";
import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { useResource } from "../../components/useResource";
import LoadingState, { ErrorState } from "../../components/LoadingState";
import { featureLabel } from "../../lib/featureLabels";
import { type Preference, type Preferences } from "../../components/catalogTypes";
const languageOptions = [["ko", "Korean · 한국어"], ["en", "English · 영어"], ["ja", "Japanese · 일본어"], ["other", "Other · 기타"]];
const stateLabels = { love: "정말 좋아해요", like: "좋아해요", neutral: "보통이에요", dislike: "싫어해요", not_tried: "아직 경험하지 않았어요" };
function Group({ title, items, empty }: { title: string; items: Preference[]; empty: string }) {
  return <section className="panel"><h2>{title}</h2>{items.length ? <ul className="taste-list">{items.map(item => <li key={item.key}><span>{featureLabel(item)}</span><span className="state-label">{stateLabels[item.display_state]}{item.evidence_count === 1 ? " · 아직 기록이 적어요" : ""}</span></li>)}</ul> : <p>{empty}</p>}</section>;
}
function Taste() {
  const first = useSearchParams().get("first") === "1";
  const { data, loading, failed, retry } = useResource<Preferences>("/me/preferences");
  const likes = data?.features.filter(item => item.display_state === "love" || item.display_state === "like") ?? [];
  return <main className="page"><p className="eyebrow">{first ? "처음 알아본 나의 취향" : "함께 자라는 나의 취향"}</p><h1>{first ? "지금의 나의 취향" : "나의 취향"}</h1><p>듣고 반응을 남길수록 취향이 더 또렷해져요. 아직 경험하지 않은 요소는 싫어한다는 의미가 아니에요.</p>
    {loading && <LoadingState korean />}{failed && <ErrorState retry={retry} korean />}
    {data && !loading && <><section className="panel"><h2>취향 요약</h2><p>{likes.length ? `지금 좋아하는 요소는 ${likes.slice(0, 3).map(item => featureLabel(item)).join(", ")} 등이에요.` : "아직 취향을 알아가는 중이에요. 영상을 들으며 좋아하는 요소를 찾아보세요."}</p></section>
      <Group title="좋아하는 소리" items={likes.filter(item => item.family === "sound")} empty="아직 좋아하는 소리가 없어요." />
      <section className="panel"><h2>말소리와 언어</h2><p>말소리: {({ talking: "Talking · 말소리 있음", no_talking: "No Talking · 말소리 없음", both: "Both · 둘 다" } as Record<string, string>)[data.voice_mode ?? ""] ?? "선택하지 않았어요"}</p><p>언어: {data.voice_mode === "no_talking" ? "말소리 없는 ASMR에는 적용되지 않아요" : data.no_preference ? "상관없음" : data.languages.length ? data.languages.map(code => languageOptions.find(([value]) => value === code)?.[1] ?? code).join(", ") : "선택하지 않았어요"}</p><p>선호 언어는 추천에 참고하며, 다른 언어의 영상을 제외하지는 않아요.</p></section>
      <Group title="좋아하는 시각 요소와 형식" items={likes.filter(item => ["visual", "format"].includes(item.family))} empty="아직 좋아하는 시각 요소나 형식이 없어요." />
      {data.features.some(item => item.evidence_count > 0 && ["neutral", "dislike"].includes(item.display_state)) && <Group title="보통이거나 싫어하는 요소" items={data.features.filter(item => item.evidence_count > 0 && ["neutral", "dislike"].includes(item.display_state))} empty="" />}
      <Group title="아직 경험하지 않았거나 기록이 적은 요소" items={data.unknown_or_low_evidence} empty="모든 요소에 두 번 이상의 취향 기록이 있어요." />
      {!!data.recent_discoveries?.length && <Group title="최근 발견한 취향" items={data.recent_discoveries} empty="" />}
    </>}
    <div className="actions"><Link className="link-button" href="/discover">새로운 취향 찾기</Link><Link className="link-button primary" href="/home">{first ? "나를 위한 추천 보기" : "내 취향의 ASMR 보기"}</Link></div>
  </main>;
}
export default function Page() { return <Suspense fallback={<main className="page"><LoadingState korean /></main>}><Taste /></Suspense>; }
