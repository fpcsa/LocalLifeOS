"use client";

import { BrandMark } from "@locallife/ui";
import {
  CalendarDays,
  CheckSquare2,
  CircleDollarSign,
  Gauge,
  Clock3,
  FileText,
  FlaskConical,
  Goal,
  Layers3,
  Upload,
  Workflow,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Search,
  Settings,
  SunMedium,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { SystemStatus } from "@/components/system-status";
import { cn } from "@/lib/cn";
import { useUiStore } from "@/stores/ui-store";

interface NavigationItem {
  label: string;
  href: string;
  icon: LucideIcon;
}

const navigation: NavigationItem[] = [
  { label: "Today", href: "/", icon: SunMedium },
  { label: "Tasks", href: "/tasks", icon: CheckSquare2 },
  { label: "Calendar", href: "/calendar", icon: CalendarDays },
  { label: "Notes", href: "/notes", icon: FileText },
  { label: "Finance", href: "/finance", icon: CircleDollarSign },
  { label: "Goals", href: "/goals", icon: Goal },
  { label: "Commitments", href: "/commitments", icon: Layers3 },
  { label: "Capacity", href: "/capacity", icon: Gauge },
  { label: "Scenarios", href: "/scenarios", icon: FlaskConical },
  { label: "Timeline", href: "/timeline", icon: Clock3 },
  { label: "Imports", href: "/imports", icon: Upload },
  { label: "Automation", href: "/automation", icon: Workflow },
  { label: "Settings", href: "/settings", icon: Settings },
];

function isActive(pathname: string, href: string): boolean {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
}

function DesktopNavigation({ collapsed, pathname }: { collapsed: boolean; pathname: string }) {
  return (
    <nav aria-label="Primary" className="flex flex-1 flex-col gap-1 p-3">
      {navigation.map(({ label, href, icon: Icon }) => {
        const active = isActive(pathname, href);
        return (
          <Link
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex min-h-10 items-center gap-3 rounded-md px-3 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 motion-reduce:transition-none",
              active ? "bg-accent text-accent-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground",
            )}
            href={href}
            key={href}
            title={collapsed ? label : undefined}
          >
            <Icon aria-hidden="true" className="h-5 w-5 shrink-0" />
            <span className={collapsed ? "sr-only" : "truncate"}>{label}</span>
          </Link>
        );
      })}
    </nav>
  );
}

function CompactNavigation({ pathname }: { pathname: string }) {
  return (
    <nav aria-label="Primary" className="flex gap-1 overflow-x-auto border-b border-border bg-card px-3 py-2 md:hidden">
      {navigation.map(({ label, href, icon: Icon }) => {
        const active = isActive(pathname, href);
        return (
          <Link
            aria-current={active ? "page" : undefined}
            className={cn(
              "inline-flex min-h-10 shrink-0 items-center gap-2 rounded-md px-3 text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              active ? "bg-accent text-accent-foreground" : "text-muted-foreground",
            )}
            href={href}
            key={href}
          >
            <Icon aria-hidden="true" className="h-4 w-4" />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const sidebarCollapsed = useUiStore((state) => state.sidebarCollapsed);
  const toggleSidebar = useUiStore((state) => state.toggleSidebar);
  const setCommandOpen = useUiStore((state) => state.setCommandPaletteOpen);
  const openQuickCreate = useUiStore((state) => state.openQuickCreate);
  const pathname = usePathname();

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-border bg-card/95 px-4 backdrop-blur md:px-6">
        <Button aria-label={sidebarCollapsed ? "Expand navigation" : "Collapse navigation"} className="hidden md:inline-flex" onClick={toggleSidebar} size="icon" type="button" variant="ghost">
          {sidebarCollapsed ? <PanelLeftOpen aria-hidden="true" className="h-5 w-5" /> : <PanelLeftClose aria-hidden="true" className="h-5 w-5" />}
        </Button>
        <Link className="flex min-w-0 items-center gap-3 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2" href="/">
          <BrandMark className="h-8 w-8 shrink-0 text-primary" />
          <span className="hidden truncate text-sm font-semibold tracking-tight sm:inline sm:text-base">LocalLife OS</span>
        </Link>
        <button className="ml-auto hidden min-h-10 w-full max-w-sm items-center gap-2 rounded-md border border-border bg-background px-3 text-left text-sm text-muted-foreground hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring lg:flex" onClick={() => setCommandOpen(true)} type="button">
          <Search aria-hidden="true" className="h-4 w-4" />
          <span className="flex-1">Search your local workspace</span>
          <kbd className="rounded border border-border bg-muted px-1.5 py-0.5 text-xs">Ctrl K</kbd>
        </button>
        <Button aria-label="Search" className="lg:hidden" onClick={() => setCommandOpen(true)} size="icon" type="button" variant="ghost"><Search aria-hidden="true" className="h-5 w-5" /></Button>
        <Button onClick={() => openQuickCreate()} type="button"><Plus aria-hidden="true" className="h-4 w-4" /><span className="hidden sm:inline">Quick create</span></Button>
        <SystemStatus />
      </header>
      <div className="flex min-h-[calc(100vh-4rem)]">
        <aside className={cn("hidden shrink-0 flex-col border-r border-border bg-card transition-[width] duration-200 motion-reduce:transition-none md:flex", sidebarCollapsed ? "w-20" : "w-60")}>
          <DesktopNavigation collapsed={sidebarCollapsed} pathname={pathname} />
          <div className="border-t border-border p-4"><p className={sidebarCollapsed ? "sr-only" : "text-xs text-muted-foreground"}>Private. Local. Yours.</p></div>
        </aside>
        <div className="min-w-0 flex-1">
          <CompactNavigation pathname={pathname} />
          <main className="mx-auto w-full max-w-7xl px-4 py-6 md:px-8 md:py-8">{children}</main>
        </div>
      </div>
    </div>
  );
}
