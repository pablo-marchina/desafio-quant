const scoreBands = ["Todos", "85+", "70-84", "<70"];
const statuses = ["Todos", "Validado", "Em revisão", "Validação pendente"];

function FilterGroup({ label, value, onChange, options }) {
  return (
    <label className="filter-group">
      <span>{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}

export function Sidebar({
  startups,
  selectedStartupId,
  onSelectStartup,
  segmentFilter,
  onSegmentFilterChange,
  scoreFilter,
  onScoreFilterChange,
  statusFilter,
  onStatusFilterChange,
  cityFilter,
  onCityFilterChange,
  segments,
  cities,
}) {
  return (
    <aside className="sidebar panel">
      <div className="sidebar-section">
        <div className="section-heading">
          <p className="section-label">Filtros do radar</p>
          <span>{startups.length} analisadas</span>
        </div>
        <FilterGroup
          label="Segmento"
          value={segmentFilter}
          onChange={onSegmentFilterChange}
          options={segments}
        />
        <FilterGroup
          label="Score AI-native"
          value={scoreFilter}
          onChange={onScoreFilterChange}
          options={scoreBands}
        />
      </div>

      <div className="sidebar-section">
        <div className="section-heading">
          <p className="section-label">Watchlist demo</p>
          <span>{startups.length} startups</span>
        </div>
        <div className="startup-list">
          {startups.length === 0 ? (
            <div className="empty-state">
              Nenhuma startup analisada ainda. Inicie uma análise pelo topo do dashboard.
            </div>
          ) : null}
          {startups.map((startup) => (
            <button
              key={startup.id}
              className={`startup-list-item ${
                startup.id === selectedStartupId ? "active" : ""
              }`}
              type="button"
              onClick={() => onSelectStartup(startup.id)}
            >
              <strong>{startup.name}</strong>
              <span>{startup.segment}</span>
              <small>
                {startup.city} · Score {startup.aiScore}
              </small>
            </button>
          ))}
        </div>
      </div>
    </aside>
  );
}
