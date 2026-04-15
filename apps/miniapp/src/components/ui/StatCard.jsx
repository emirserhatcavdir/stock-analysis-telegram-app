export default function StatCard({ label, value, helper = '', tone = 'neutral' }) {
  return (
    <article className={`ds-stat ds-${tone}`.trim()}>
      <p className="ds-stat-label">{label}</p>
      <p className="ds-stat-value">{value}</p>
      {helper ? <p className="ds-stat-helper">{helper}</p> : null}
    </article>
  );
}
