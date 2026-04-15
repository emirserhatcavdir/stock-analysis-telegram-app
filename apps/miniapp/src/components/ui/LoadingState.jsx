export default function LoadingState({ count = 3 }) {
  return (
    <div className="ds-loading-grid">
      {Array.from({ length: count }).map((_, index) => (
        <div className="ds-loading-card" key={index}>
          <span className="ds-loading-glow" />
          <span className="ds-loading-line ds-loading-title" />
          <span className="ds-loading-line" />
          <span className="ds-loading-line ds-loading-short" />
        </div>
      ))}
    </div>
  );
}
