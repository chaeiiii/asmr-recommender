export type Feature = { key: string; display_name: string; family: string };
export type Preference = Feature & { display_state: "love" | "like" | "neutral" | "dislike" | "not_tried"; evidence_count: number };
export type Preferences = {
  voice_mode: string | null; languages: string[]; no_preference: boolean;
  features: Preference[]; unknown_or_low_evidence: Preference[]; recent_discoveries?: Preference[];
};
export type Video = {
  video_id: number; youtube_video_id: string; title: string; channel_name: string;
  thumbnail_url: string | null; duration_sec: number | null;
  features: Feature[]; reasons?: Feature[];
};
export type VideoResults = { items: Video[]; next_page?: number | null };
export const languageOptions = [["ko", "Korean"], ["en", "English"], ["ja", "Japanese"], ["other", "Other"]];
export const stateLabels = { love: "Love", like: "Like", neutral: "Neutral", dislike: "Disliked", not_tried: "Not tried yet" };
