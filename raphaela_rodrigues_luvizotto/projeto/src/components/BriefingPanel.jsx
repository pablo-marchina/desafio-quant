export function BriefingPanel({ startup, onExport, onCopy }) {
  if (!startup) {
    return (
      <section className="panel briefing-panel">
        <div className="section-heading">
          <div>
            <h2>Briefing executivo</h2>
          </div>
        </div>
        <div className="briefing-summary">
          <p>
            O briefing executivo será gerado assim que uma startup real passar pelo pipeline de
            scraping, extração, validação e recomendação.
          </p>
        </div>
      </section>
    );
  }

  return (
    <section className="panel briefing-panel">
      <div className="section-heading">
        <div>
          <h2>Briefing executivo</h2>
        </div>
      </div>

      <div className="briefing-bullets">
        {startup.executiveBrief.bullets.map((bullet) => (
          <article key={bullet.label}>
            <span>{bullet.label}</span>
            <p>{bullet.text}</p>
          </article>
        ))}
      </div>

      <div className="action-row">
        <button className="button tertiary" type="button" onClick={onCopy}>
          Copiar briefing
        </button>
      </div>
    </section>
  );
}
