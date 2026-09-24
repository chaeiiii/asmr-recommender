import type { Feature } from "./catalogTypes";
export default function FeatureChips({ features }: { features: Feature[] }) {
  return <ul className="chips" aria-label="Video features">{features.slice(0, 4).map(feature => <li key={feature.key}>{feature.display_name}</li>)}</ul>;
}
