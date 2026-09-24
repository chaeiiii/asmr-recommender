"use client";
import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import { useResource } from "../../components/useResource";
import LoadingState, { ErrorState } from "../../components/LoadingState";
import VideoCard from "../../components/VideoCard";
import { languageOptions, type Preferences, type VideoResults } from "../../components/catalogTypes";
type Filters = { q: string; sound: string[]; voice: string; speed: string; language: string[]; format: string[]; min_duration_sec: string; max_duration_sec: string };
const empty: Filters = { q: "", sound: [], voice: "", speed: "", language: [], format: [], min_duration_sec: "", max_duration_sec: "" };
export default function Page() {
  const taxonomy = useResource<Preferences>("/me/preferences");
  const saved = useResource<VideoResults>("/favorites");
  const [draft, setDraft] = useState<Filters>(empty);
  const [applied, setApplied] = useState<Filters>(empty);
  const [page, setPage] = useState(1);
  const [attempt, setAttempt] = useState(0);
  const [results, setResults] = useState<VideoResults>();
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [hidden, setHidden] = useState<number[]>([]);
  useEffect(() => {
  let active = true;

  const params = new URLSearchParams({
    limit: "20",
    page: String(page),
  });

  Object.entries(applied).forEach(([key, value]) => {
    if (Array.isArray(value)) {
      value.forEach(item => params.append(key, item));
    } else if (value.trim()) {
      params.set(key, value.trim());
    }
  });

  api<VideoResults>(`/search?${params}`)
    .then(data => {
      if (!active) return;

      setResults(previous => ({
        ...data,
        items:
          page === 1
            ? data.items
            : [
                ...(previous?.items ?? []),
                ...data.items.filter(
                  item =>
                    !previous?.items.some(
                      existing => existing.video_id === item.video_id,
                    ),
                ),
              ],
      }));
    })
    .catch(() => {
      if (active) setFailed(true);
    })
    .finally(() => {
      if (active) setLoading(false);
    });

  return () => {
    active = false;
  };
}, [applied, page, attempt]);
  function apply(filters: Filters) {
    setDraft(filters); setApplied({ ...filters }); setPage(1); setResults(undefined); setHidden([]); setLoading(true); setFailed(false);
  }
  function toggle(key: "sound" | "format" | "language", value: string) {
    setDraft(current => ({ ...current, [key]: current[key].includes(value) ? current[key].filter(item => item !== value) : [...current[key], value] }));
  }
  function label(key: string, value: string) {
    if (key === "q") return `Search: ${value}`;
    if (key === "min_duration_sec") return `At least ${value} seconds`;
    if (key === "max_duration_sec") return `Up to ${value} seconds`;
    return taxonomy.data?.features.find(item => item.key === value)?.display_name ?? languageOptions.find(([code]) => code === value)?.[1] ?? value;
  }
  const active = Object.entries(applied).flatMap(([key, value]) => (Array.isArray(value) ? value : value ? [value] : []).map(value => ({ key: key as keyof Filters, value })));
  const invalidRange = draft.min_duration_sec !== "" && draft.max_duration_sec !== "" && Number(draft.min_duration_sec) > Number(draft.max_duration_sec);
  const items = results?.items.filter(item => !hidden.includes(item.video_id)) ?? [];
  return <main className="page"><p className="eyebrow">Find your next listen</p><h1>Search</h1><p>Filters only change these results. They do not change your taste.</p>
    <form onSubmit={event => { event.preventDefault(); if (!invalidRange) apply(draft); }}>
      <label className="field">Search videos or channels<input type="search" value={draft.q} onChange={event => setDraft(current => ({ ...current, q: event.target.value }))} /></label>
      <details className="panel filter-sheet"><summary>Filters · Sound, Voice, Speed, Language, Format</summary>
        {taxonomy.loading && <LoadingState />}{taxonomy.failed && <ErrorState retry={taxonomy.retry} />}
        {(["sound", "voice", "speed", "format"] as const).map(family => <fieldset key={family}><legend>{family === "sound" ? "Sound" : family === "voice" ? "Voice" : family === "speed" ? "Speed" : "Format"}</legend>
          {(family === "voice" || family === "speed") && <label className="choice"><input type="radio" name={family} checked={!draft[family]} onChange={() => setDraft(current => ({ ...current, [family]: "" }))} />Any {family}</label>}
          <div className="choices">{taxonomy.data?.features.filter(feature => feature.family === family).map(feature => <label className="choice" key={feature.key}><input type={family === "sound" || family === "format" ? "checkbox" : "radio"} name={family} checked={family === "sound" || family === "format" ? draft[family].includes(feature.key) : draft[family] === feature.key} onChange={() => family === "sound" || family === "format" ? toggle(family, feature.key) : setDraft(current => ({ ...current, [family]: feature.key }))} />{feature.display_name}</label>)}</div>
          {taxonomy.data && !taxonomy.data.features.some(feature => feature.family === family) && <p>No {family} filters available.</p>}
        </fieldset>)}
        <fieldset><legend>Language</legend><div className="choices">{languageOptions.map(([value, name]) => <label className="choice" key={value}><input type="checkbox" checked={draft.language.includes(value)} onChange={() => toggle("language", value)} />{name}</label>)}</div></fieldset>
        <fieldset><legend>Duration (optional, in seconds)</legend><div className="duration-fields"><label className="field">Minimum<input type="number" min="0" step="1" value={draft.min_duration_sec} onChange={event => setDraft(current => ({ ...current, min_duration_sec: event.target.value }))} /></label><label className="field">Maximum<input type="number" min="0" step="1" value={draft.max_duration_sec} onChange={event => setDraft(current => ({ ...current, max_duration_sec: event.target.value }))} /></label></div>{invalidRange && <p role="alert">Minimum duration must not exceed maximum.</p>}</fieldset>
      </details>
      <div className="actions"><button className="primary" type="submit" disabled={invalidRange}>Search</button><button type="button" onClick={() => apply(empty)}>Clear All</button></div>
    </form>
    {!!active.length && <ul className="chips active-filters" aria-label="Active filters">{active.map(({ key, value }) => <li key={`${key}-${value}`}><button aria-label={`Remove ${label(key, value)}`} onClick={() => { const current = applied[key]; apply({ ...applied, [key]: Array.isArray(current) ? current.filter(item => item !== value) : "" }); }}>{label(key, value)} ×</button></li>)}</ul>}
    <section aria-label="Search results"><h2>Results</h2>{loading && <LoadingState />}{failed && <ErrorState retry={() => {
  setLoading(true);
  setFailed(false);
  setAttempt(value => value + 1);
}} />}
      {saved.failed && <div className="error"><p>Saved status could not be loaded.</p><button onClick={saved.retry}>Retry saved status</button></div>}
      {!loading && !failed && !items.length && <p>No videos to show. Try fewer filters or Clear All.</p>}
      {items.map(video => <VideoCard key={video.video_id} video={video} surface="search" initialSaved={!!saved.data?.items.some(item => item.video_id === video.video_id)} onDismiss={id => setHidden(current => [...current, id])} />)}
      {results?.next_page != null && <button disabled={loading || failed} onClick={() => {
  setLoading(true);
  setFailed(false);
  setPage(results.next_page!);
}}>Load more</button>}
    </section>
  </main>;
}
