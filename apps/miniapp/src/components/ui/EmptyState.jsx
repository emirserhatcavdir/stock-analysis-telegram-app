export default function EmptyState({ title, message, action = null }) {
  return (
    <div className="ds-empty">
      <div className="ds-empty-dot" />
      <h4>{title}</h4>
      <p>{message}</p>
      {action ? <div className="ds-actions">{action}</div> : null}
    </div>
  );
}
