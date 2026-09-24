export default function LoadingState() { return <p role="status">Just a moment…</p>; }
export function ErrorState({ retry }: { retry: () => void }) {
  return <div role="alert" className="error"><p>We couldn’t finish that request. Please try again.</p><button type="button" onClick={retry}>Try again</button></div>;
}
