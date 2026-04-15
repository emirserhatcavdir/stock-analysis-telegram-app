import Card from './Card';

export default function MetricTile({ label, value, help, className = '' }) {
  return (
    <Card className={`dash-card dash-anim ${className}`.trim()}>
      <p className="dash-label">{label}</p>
      <p className="dash-value">{value}</p>
      {help ? <p className="muted">{help}</p> : null}
      <div className="dash-card-glow" />
    </Card>
  );
}
