export function RecommendationPanel({ startup }) {
  if (!startup) {
    return (
      <section className="panel">
        <div className="section-heading">
          <div>
            <p className="section-label">Recomendacoes NVIDIA</p>
            <h2>Produtos com maior aderencia</h2>
          </div>
        </div>
        <div className="recommendation-list">
          <div className="empty-state">
            As recomendacoes serao preenchidas com base no RAG NVIDIA apos a analise da startup.
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="panel">
      <div className="section-heading">
        <div>
          <p className="section-label">Recomendacoes NVIDIA</p>
          <h2>Produtos com maior aderencia</h2>
        </div>
        <span className="fit-pill">Fit {startup.nvidiaFit}</span>
      </div>

      <div className="recommendation-list">
        {startup.recommendations.map((recommendation) => (
          <article className="recommendation-card" key={recommendation.name}>
            <div className="recommendation-header">
              <h3>{recommendation.name}</h3>
              <span>{recommendation.confidence}</span>
            </div>
            <p>{recommendation.reason}</p>
            <div className="recommendation-meta">
              <span>Aderencia: {recommendation.adherence}</span>
              <span>Confianca: {recommendation.confidence}</span>
            </div>
            <strong>Proximo passo</strong>
            <p>{recommendation.nextStep}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
