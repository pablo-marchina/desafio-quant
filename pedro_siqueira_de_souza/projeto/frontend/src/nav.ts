// Fonte única das páginas (ux.md §1 e §6.5). Usada pela sidebar e pela
// topbar para manter título/subtítulo sincronizados com a rota ativa.
export interface NavEntry {
  path: string;
  label: string;
  subtitle: string;
  group: "operacional" | "inteligencia";
}

export const NAV: NavEntry[] = [
  // Ferramentas operacionais
  {
    path: "/pipeline",
    label: "Pipeline",
    subtitle: "Configure e acompanhe a busca em tempo real",
    group: "operacional",
  },
  {
    path: "/qualificadas",
    label: "Qualificadas",
    subtitle: "Funil de relacionamento com as startups",
    group: "operacional",
  },
  {
    path: "/analytics",
    label: "Analytics",
    subtitle: "Visão agregada do ecossistema de IA",
    group: "operacional",
  },
];
