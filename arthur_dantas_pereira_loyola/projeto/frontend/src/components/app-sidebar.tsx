import { Link, useRouterState } from "@tanstack/react-router";
import {
  LayoutDashboard,
  ListOrdered,
  GitBranch,
  FileSearch,
  FileText,
  Cpu,
  Handshake,
  UserCircle2,
} from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarFooter,
} from "@/components/ui/sidebar";

const workspace = [
  { title: "Overview", url: "/", icon: LayoutDashboard },
  { title: "Ranking", url: "/ranking", icon: ListOrdered },
  { title: "Contatos", url: "/contacts", icon: Handshake },
  { title: "Pipeline Multiagente", url: "/pipeline", icon: GitBranch },
  { title: "Fontes & Evidências", url: "/sources", icon: FileSearch },
  { title: "Briefing Executivo", url: "/briefing", icon: FileText },
];

const account = [{ title: "Meu perfil", url: "/profile", icon: UserCircle2 }];

export function AppSidebar() {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const isActive = (url: string) => (url === "/" ? pathname === "/" : pathname.startsWith(url));

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <div className="flex items-center gap-2 px-2 py-3">
          <div className="grid h-8 w-8 shrink-0 place-items-center rounded-md bg-primary text-primary-foreground">
            <Cpu className="h-4 w-4" />
          </div>
          <div className="flex min-w-0 flex-col leading-tight group-data-[collapsible=icon]:hidden">
            <span className="text-sm font-semibold text-sidebar-foreground">NVIDIA Toph</span>
            <span className="text-[10px] uppercase tracking-wider text-sidebar-foreground/60">
              Startups Intelligence
            </span>
          </div>
        </div>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Workspace</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {workspace.map((item) => (
                <SidebarMenuItem key={item.url}>
                  <SidebarMenuButton asChild isActive={isActive(item.url)} tooltip={item.title}>
                    <Link to={item.url}>
                      <item.icon className="h-4 w-4" />
                      <span>{item.title}</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarGroup>
          <SidebarGroupLabel>Conta</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {account.map((item) => (
                <SidebarMenuItem key={item.url}>
                  <SidebarMenuButton asChild isActive={isActive(item.url)} tooltip={item.title}>
                    <Link to={item.url}>
                      <item.icon className="h-4 w-4" />
                      <span>{item.title}</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter>
        <div className="px-2 py-2 text-[10px] leading-relaxed text-sidebar-foreground/60 group-data-[collapsible=icon]:hidden">
          Apenas dados públicos. Cada recomendação é rastreável até a evidência de origem.
        </div>
      </SidebarFooter>
    </Sidebar>
  );
}
