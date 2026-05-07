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
  if (!path) {
    return "/";
  }

  const trimmed = path.endsWith("/") && path !== "/" ? path.slice(0, -1) : path;
  return trimmed || "/";
}

function matchesTabPath(pathname: string, href: string): boolean {
  if (href === "/") {
    return pathname === "/";
  }

  return pathname === href || pathname.startsWith(`${href}/`);
}

export default function SubTabNav({ tabs }: SubTabNavProps) {
  const pathname = normalizePath(usePathname());
  const activeHref = tabs
    .map((tab) => ({ ...tab, href: normalizePath(tab.href) }))
    .filter((tab) => matchesTabPath(pathname, tab.href))
    .sort((a, b) => b.href.length - a.href.length)[0]?.href;

  return (
    <nav className="portal-subtabs" aria-label="Section tabs">
      {tabs.map((tab) => {
        const normalizedHref = normalizePath(tab.href);
        const isActive = normalizedHref === activeHref;
        return (
          <EmbeddedLink
            key={tab.href}
            href={tab.href}
            className={`portal-subtab-item${isActive ? " is-active" : ""}`}
            aria-current={isActive ? "page" : undefined}
          >
            {tab.label}
          </EmbeddedLink>
        );
      })}
    </nav>
  );
}
