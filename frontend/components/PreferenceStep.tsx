"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, type NextRoute } from "../lib/api";
import { featureLabel } from "../lib/featureLabels";
import { useStep } from "./useStep";
import LoadingState, { ErrorState } from "./LoadingState";
type Feature = { key: string; display_name: string; description?: string };
type State = { voice_mode?: string | null; languages?: string[]; no_preference?: boolean; groups?: Record<string, Feature[]> };
const languages = [["ko", "Korean · 한국어"], ["en", "English · 영어"], ["ja", "Japanese · 일본어"], ["other", "Other · 기타"]];
export default function PreferenceStep({ kind }: { kind: "voice" | "languages" | "extra-preferences" }) {
  const path = `/onboarding/${kind}`;
  const router = useRouter();
  const { data, busy, failed, run, retry } = useStep<State>(path);
  const [voice, setVoice] = useState<string>();
  const [selected, setSelected] = useState<string[]>();
  const [noPreference, setNoPreference] = useState<boolean>();
  const values = selected ?? (kind === "languages" ? data?.languages ?? [] : []);
  const noLanguage = noPreference ?? data?.no_preference ?? false;
  const voiceValue = voice ?? data?.voice_mode;
  function toggle(key: string) { setSelected(values.includes(key) ? values.filter(value => value !== key) : [...values, key]); }
  function submit(skip = false) {
    const body = kind === "voice" ? { voice_mode: voiceValue } : kind === "languages" ? { languages: values, no_preference: noLanguage } : { liked_features: skip ? [] : values };
    void run(async () => { const result = await api<NextRoute>(path, body); router.replace(result.next_route); });
  }
  return <main className="page"><p className="eyebrow">나의 취향</p><h1>{kind === "voice" ? "평소 어떤 ASMR을 더 선호하나요?" : kind === "languages" ? "말소리가 있는 ASMR에서 선호하는 언어는 무엇인가요?" : "평소 좋아하는 ASMR 요소가 있나요?"}</h1>
    <p>{kind === "extra-preferences" ? "이미 좋아한다고 알고 있는 항목만 선택해주세요. 선택하지 않은 항목은 싫어한다는 의미가 아니에요." : kind === "languages" ? "좋아하는 언어를 모두 선택해주세요. 추천에 참고하며, 다른 언어의 영상을 제외하지는 않아요." : "평소 즐겨 듣는 ASMR을 선택해주세요."}</p>
    {failed && <ErrorState retry={retry} korean />}{!data && !failed && <LoadingState korean />}
    {data && <form onSubmit={event => { event.preventDefault(); submit(); }}><fieldset disabled={busy}><legend className="sr-only">선호하는 항목을 선택해주세요</legend>
      {kind === "voice" && <div className="choices">{[["talking", "Talking · 말소리 있음"], ["no_talking", "No Talking · 말소리 없음"], ["both", "Both · 둘 다"]].map(([value, label]) => <label className="choice" key={value}><input type="radio" name="voice" value={value} checked={voiceValue === value} onChange={() => setVoice(value)} />{label}</label>)}</div>}
      {kind === "languages" && <div className="choices">{languages.map(([value, label]) => <label className="choice" key={value}><input type="checkbox" checked={values.includes(value)} onChange={() => { setNoPreference(false); toggle(value); }} />{label}</label>)}<label className="choice"><input type="checkbox" checked={noLanguage} onChange={event => { setNoPreference(event.target.checked); setSelected([]); }} />No preference · 상관없음</label></div>}
      {kind === "extra-preferences" && ([ ["sound", "Sound · 소리", "소리와 질감"], ["visual", "Visual · 시각", "눈으로 보는 움직임"], ["format", "Format · 형식", "영상 구성과 상황"], ["intensity", "Intensity · 강도", "자극의 강도"] ]).map(([family, label, description]) => <fieldset key={family}><legend>{label}</legend><p>{description}</p><div className="choices">{(data.groups?.[family] ?? []).map(feature => <label className="choice" key={feature.key}><input type="checkbox" checked={values.includes(feature.key)} onChange={() => toggle(feature.key)} /><span>{featureLabel(feature)}{feature.description && <small>{feature.description}</small>}</span></label>)}</div>{!data.groups?.[family]?.length && <p>이 항목에는 추가로 선택할 요소가 없어요.</p>}</fieldset>)}
      <div className="actions"><button className="primary" type="submit" disabled={kind === "voice" ? !voiceValue : kind === "languages" ? !noLanguage && values.length === 0 : false}>계속</button>{kind === "extra-preferences" && <button type="button" onClick={() => submit(true)}>건너뛰기</button>}</div>
    </fieldset>{busy && <p role="status">선택한 내용을 저장하고 있어요…</p>}</form>}
  </main>;
}
