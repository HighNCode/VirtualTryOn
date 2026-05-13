"use client";

import { usePathname } from "next/navigation";
import { EmbeddedLink } from "./EmbeddedNavigation";

type TabItem = {
  href: string;
  label: string;
};

type SubTabNavProps = {
  tabs: TabItem[];
};

function normalizePath(path: string): string {
  if (!path) return "/";
  const trimmed = path.endsWith("/") && path !== "/" ? path.slice(0, -1) : path;
  return trimmed || "/";
}

function matchesTabPath(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

export default function SubTabNav({ tabs }: SubTabNavProps) {
  const pathname = normalizePath(usePathname());
  const activeHref = tabs
    .map((tab) => ({ ...tab, href: normalizePath(tab.href) }))
    .filter((tab) => matchesTabPath(pathname, tab.href))
    .sort((a, b) => b.href.length - a.href.length)[0]?.href;

  return (
    <nav
      aria-label="Section tabs"
      style={{ display: "flex", alignItems: "center", gap: 4, padding: "12px 28px", background: "#ffffff", borderBottom: "1px solid #f0f0f0" }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 4, padding: 4, borderRadius: 10, background: "#f3f4f6" }}>
        {tabs.map((tab) => {
          const normalizedHref = normalizePath(tab.href);
          const isActive = normalizedHref === activeHref;
          return (
            <EmbeddedLink
              key={tab.href}
              href={tab.href}
              aria-current={isActive ? "page" : undefined}
            >
              <span
                style={
                  isActive
                    ? { display: "block", padding: "6px 12px", fontSize: 13, fontWeight: 500, borderRadius: 8, background: "#ffffff", color: "#7E0175", boxShadow: "0 1px 3px rgba(0,0,0,0.08)" }
                    : { display: "block", padding: "6px 12px", fontSize: 13, fontWeight: 500, borderRadius: 8, color: "#6b7280" }
                }
              >
                {tab.label}
              </span>
            </EmbeddedLink>
          );
        })}
      </div>
    </nav>
  );
}
