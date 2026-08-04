function scoreTone(score) {
  if (score >= 90) return "excellent";
  if (score >= 80) return "good";
  return "fair";
}

const MAX_VISIBLE_TAGS = 4;

function getVisibleTags(tags = []) {
  const visibleTags = tags.slice(0, MAX_VISIBLE_TAGS);
  const hiddenTagCount = Math.max(tags.length - visibleTags.length, 0);
  return { visibleTags, hiddenTagCount };
}

export function StartupGrid({ startups, selectedStartupId, onSelectStartup }) {
  return (
    <section className="panel">
      <div className="section-heading">
        <div>
          <p className="section-label">Radar de startups</p>
          <h2>Pipeline priorizado para análise</h2>
        </div>
        <span>{startups.length} resultados</span>
      </div>
      <div className="startup-grid">
        {startups.map((startup) => {
          const { visibleTags, hiddenTagCount } = getVisibleTags(startup.tags);

          return (
          <article
            key={startup.id}
            className={`startup-card ${selectedStartupId === startup.id ? "selected" : ""}`}
          >
            <div className="card-topline">
              <div>
                <h3>{startup.name}</h3>
                <p>
                  {startup.segment} · {startup.city}
                </p>
              </div>
              <span className={`status-badge ${scoreTone(startup.aiScore)}`}>
                Score {startup.aiScore}
              </span>
            </div>

            <div className="meta-row">
              <span className="status-pill">{startup.validationStatus}</span>
              <span className="fit-pill">Fit NVIDIA {startup.nvidiaFit}</span>
            </div>

            <div className="score-bar">
              <div style={{ width: `${startup.aiScore}%` }} />
            </div>

            <p className="startup-summary">{startup.summary}</p>

            <div className="tag-row">
              {visibleTags.map((tag) => (
                <span key={tag} className="tag">
                  {tag}
                </span>
              ))}
              {hiddenTagCount > 0 ? (
                <span className="tag tag-muted">+{hiddenTagCount}</span>
              ) : null}
            </div>
          </article>
          );
        })}
      </div>
      {startups.length === 0 ? (
        <div className="empty-state">
          Nenhuma startup encontrada com os filtros atuais.
        </div>
      ) : null}
    </section>
  );
}
