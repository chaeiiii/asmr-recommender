"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, type NextRoute } from "../lib/api";
import { useStep } from "./useStep";
import LoadingState, { ErrorState } from "./LoadingState";
type Feature = { key: string; display_name: string; description?: string };
type State = { voice_mode?: string | null; languages?: string[]; no_preference?: boolean; groups?: Record<string, Feature[]> };
const languages = [["ko", "Korean"], ["en", "English"], ["ja", "Japanese"], ["other", "Other"]];
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
  return <main className="page"><p className="eyebrow">Your preferences</p><h1>{kind === "voice" ? "Which do you usually prefer?" : kind === "languages" ? "For ASMR with talking, which languages do you prefer?" : "Any other ASMR elements you already know you like?"}</h1>
    <p>{kind === "extra-preferences" ? "Optional: choose any you already enjoy. Leaving something unchecked does not mean you dislike it." : kind === "languages" ? "Choose any languages you enjoy. This is a soft preference, not a restriction." : "Choose the kind of listening you enjoy."}</p>
    {failed && <ErrorState retry={retry} />}{!data && !failed && <LoadingState />}
    {data && <form onSubmit={event => { event.preventDefault(); submit(); }}><fieldset disabled={busy}><legend className="sr-only">Choose your preferences</legend>
      {kind === "voice" && <div className="choices">{[["talking", "Talking"], ["no_talking", "No Talking"], ["both", "Both"]].map(([value, label]) => <label className="choice" key={value}><input type="radio" name="voice" value={value} checked={voiceValue === value} onChange={() => setVoice(value)} />{label}</label>)}</div>}
      {kind === "languages" && <div className="choices">{languages.map(([value, label]) => <label className="choice" key={value}><input type="checkbox" checked={values.includes(value)} onChange={() => { setNoPreference(false); toggle(value); }} />{label}</label>)}<label className="choice"><input type="checkbox" checked={noLanguage} onChange={event => { setNoPreference(event.target.checked); setSelected([]); }} />No preference</label></div>}
      {kind === "extra-preferences" && ([ ["sound", "Sound", "Sounds and textures · 소리와 질감"], ["visual", "Visual", "Movements you watch · 눈으로 보는 움직임"], ["format", "Format", "Video styles and situations · 영상 구성과 상황"] ]).map(([family, label, description]) => <fieldset key={family}><legend>{label}</legend><p>{description}</p><div className="choices">{(data.groups?.[family] ?? []).map(feature => <label className="choice" key={feature.key}><input type="checkbox" checked={values.includes(feature.key)} onChange={() => toggle(feature.key)} /><span>{feature.display_name}{feature.description && <small>{feature.description}</small>}</span></label>)}</div>{!data.groups?.[family]?.length && <p>No additional options in this section.</p>}</fieldset>)}
      <div className="actions"><button className="primary" type="submit" disabled={kind === "voice" ? !voiceValue : kind === "languages" ? !noLanguage && values.length === 0 : false}>Continue</button>{kind === "extra-preferences" && <button type="button" onClick={() => submit(true)}>Skip</button>}</div>
    </fieldset>{busy && <p role="status">Saving your choices…</p>}</form>}
  </main>;
}
