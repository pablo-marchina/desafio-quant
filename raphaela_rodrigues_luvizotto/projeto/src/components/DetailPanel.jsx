export function DetailPanel({ startup }) {
  if (!startup) {
    return (
      <section className="panel detail-panel">
        <div className="section-heading">
          <div>
            <p className="section-label">Detalhes da startup</p>
            <h2>Aguardando análise</h2>
          </div>
        </div>
        <p className="detail-description">
          Execute uma análise para visualizar descrição estruturada, evidências e próximos
          passos.
        </p>
      </section>
    );
  }

  return (
    <section className="panel detail-panel">
      <div className="section-heading">
        <div>
          <p className="section-label">Detalhes da startup</p>
          <h2>{startup.name}</h2>
        </div>
      </div>

      <p className="detail-description">{startup.description}</p>

      <div className="detail-metrics">
        <div>
          <span>Segmento</span>
          <strong>{startup.segment}</strong>
        </div>
        <div>
          <span>Cidade</span>
          <strong>{startup.city}</strong>
        </div>
        <div>
          <span>Score AI-native</span>
          <strong>{startup.aiScore}</strong>
        </div>
        <div>
          <span>Status</span>
          <strong>{startup.validationStatus}</strong>
        </div>
      </div>
      <div className="detail-section">
        <h3>Próximos passos</h3>
        <ul className="detail-list">
          {startup.nextSteps.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ul>
      </div>
    </section>
  );
}
