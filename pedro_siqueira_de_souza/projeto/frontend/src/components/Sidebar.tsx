import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import { NAV } from "../nav";
import logo from "../assets/logo_branco.svg";

type Saude = "online" | "offline" | "checando";

// Sidebar fixa de 200px (ux.md §3.1). Agrupa as páginas em
// "operacional" e "inteligência" conforme o ux.md §1.
export default function Sidebar() {
  const operacionais = NAV.filter((n) => n.group === "operacional");
  const inteligencia = NAV.filter((n) => n.group === "inteligencia");

  // Status REAL do backend: pinga /health periodicamente (não mais hardcoded).
  const [saude, setSaude] = useState<Saude>("checando");
  useEffect(() => {
    let vivo = true;
    async function ping() {
      try {
        const r = await fetch("/health");
        if (vivo) setSaude(r.ok ? "online" : "offline");
      } catch {
        if (vivo) setSaude("offline");
      }
    }
    ping();
    const id = setInterval(ping, 15000);
    return () => {
      vivo = false;
      clearInterval(id);
    };
  }, []);

  return (
    <aside className="sidebar">
      <div className="logo">
        <img src={logo} alt="NVISION" className="logo-img" />
      </div>

      <div className="sec-lbl">Operacional</div>
      {operacionais.map((n) => (
        <NavLink key={n.path} to={n.path} className="nav-item">
          {n.label}
        </NavLink>
      ))}

      {inteligencia.length > 0 && (
        <>
          <div className="sec-lbl">Inteligência</div>
          {inteligencia.map((n) => (
            <NavLink key={n.path} to={n.path} className="nav-item">
              {n.label}
            </NavLink>
          ))}
        </>
      )}

      <div className={`status-live ${saude}`}>
        <span className="dot" />
        {saude === "checando" ? "verificando…" : `sistema ${saude}`}
      </div>
    </aside>
  );
}
