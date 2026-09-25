const featureLabels: Readonly<Record<string, string>> = {
  tapping: "Tapping · 태핑",
  scratching: "Scratching · 스크래칭",
  mic_brushing: "Mic Brushing · 마이크 브러싱",
  ear_cleaning: "Ear Cleaning · 귀 청소",
  mouth_sounds: "Mouth Sounds · 입소리",
  paper_crinkling: "Paper / Crinkling · 종이 / 바스락 소리",
  typing_writing: "Typing / Writing · 타이핑 / 필기",
  fabric_soft_object: "Fabric / Soft Object · 천 / 부드러운 물체 소리",
  water_liquid: "Water / Liquid · 물 / 액체 소리",
  eating_chewing: "Eating / Chewing · 먹는 소리 / 씹는 소리",
  whisper: "Whisper · 속삭임",
  soft_spoken: "Soft Spoken · 부드러운 말소리",
  no_talking: "No Talking · 말소리 없음",
  camera_brushing: "Camera Brushing · 카메라 브러싱",
  hand_movements: "Hand Movements · 핸드 무브먼트",
  light_triggers: "Light Triggers · 불빛 트리거",
  slow_movements: "Slow Movements · 느린 움직임",
  roleplay: "Roleplay · 롤플레이",
  personal_attention: "Personal Attention · 퍼스널 어텐션",
  trigger_assortment: "Trigger Assortment · 여러 트리거 모음",
  single_trigger: "Single Trigger · 단일 트리거",
  slow: "Slow · 느림",
  normal: "Normal · 보통 속도",
  fast: "Fast · 빠름",
  gentle: "Gentle · 부드러운 자극",
  normal_intensity: "Normal Intensity · 보통 강도",
  aggressive: "Aggressive ASMR · 빠르고 강한 자극",
};

export function featureLabel(feature: { key: string; display_name: string }): string {
  return Object.hasOwn(featureLabels, feature.key) ? featureLabels[feature.key] : feature.display_name;
}
