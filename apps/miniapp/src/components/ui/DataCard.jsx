import Card from './Card';

export default function DataCard({ title, subtitle = '', actions = null, children, className = '' }) {
  const isPlainTitle = typeof title === 'string' || typeof title === 'number';

  return (
    <Card className={`ds-card ${className}`.trim()}>
      {(title || subtitle || actions) && (
        <div className="ds-card-head">
          <div>
            {title ? (isPlainTitle ? <h3>{title}</h3> : <div className="ds-title-wrap">{title}</div>) : null}
            {subtitle ? <p className="ds-subtitle">{subtitle}</p> : null}
          </div>
          {actions ? <div className="ds-actions">{actions}</div> : null}
        </div>
      )}
      <div className="ds-card-body">{children}</div>
    </Card>
  );
}
