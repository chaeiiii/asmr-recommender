export default function LoadingState({ korean = false }: { korean?: boolean }) { return <p role="status">{korean ? "잠시만 기다려주세요…" : "Just a moment…"}</p>; }
export function ErrorState({ retry, korean = false }: { retry: () => void; korean?: boolean }) {
  return <div role="alert" className="error"><p>{korean ? "요청을 처리하지 못했어요. 다시 시도해주세요." : "We couldn’t finish that request. Please try again."}</p><button type="button" onClick={retry}>{korean ? "다시 시도" : "Try again"}</button></div>;
}
