export function Header({
  searchTerm,
  onSearchChange,
  onExport,
  onAnalyze,
  isAnalyzing,
  isExportDisabled = false,
}) {
  return (
    <header className="topbar panel">
      <div>
        <h1>NVIDIA Startup AI Radar</h1>
        <p className="subtitle">
          Inteligência de mercado para analisar startups AI-native, sinais técnicos
          e oportunidades de fit com o ecossistema NVIDIA.
        </p>
      </div>
      <div className="topbar-actions">
        <label className="search-field">
          <span>Buscar startup</span>
          <input
            type="search"
            value={searchTerm}
            onChange={(event) => onSearchChange(event.target.value)}
            placeholder="Ex.: NeuralCare AI"
          />
        </label>
        <div className="action-row">
          <button
            className="button secondary"
            type="button"
            onClick={onExport}
            disabled={isExportDisabled}
          >
            Exportar briefing
          </button>
          <button className="button primary" type="button" onClick={onAnalyze}>
            {isAnalyzing ? "Analisando..." : "Nova análise"}
          </button>
        </div>
      </div>
    </header>
  );
}
