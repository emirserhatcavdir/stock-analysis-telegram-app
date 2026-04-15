export default function SectionBlock({ title, subtitle, actions = null, children, className = '' }) {
  return (
    <section className={`ui-section ${className}`.trim()}>
      <div className="ui-section-head">
        <div>
          <h2>{title}</h2>
          {subtitle ? <p className="muted">{subtitle}</p> : null}
        </div>
        {actions ? <div className="ui-section-actions">{actions}</div> : null}
      </div>
      {children}
    </section>
  );
}
