import { useLocation } from "react-router-dom";
import { NAV } from "../nav";

// Topbar de 52px (ux.md §3.1): título + subtítulo da página ativa.
// O botão de ação contextual entra quando cada página existir de verdade.
export default function Topbar() {
  const { pathname } = useLocation();
  const entry = NAV.find((n) => n.path === pathname);

  return (
    <header className="topbar">
      <div>
        <h1>{entry?.label ?? "NVISION"}</h1>
        <div className="subtitle">{entry?.subtitle ?? ""}</div>
      </div>
    </header>
  );
}
