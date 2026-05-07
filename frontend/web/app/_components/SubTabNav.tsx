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

export default function SubTabNav({ tabs }: SubTabNavProps) {
  const pathname = usePathname();

  return (
    <nav className="portal-subtabs" aria-label="Section tabs">
      {tabs.map((tab) => {
        const isActive = pathname === tab.href || pathname.startsWith(`${tab.href}/`);
        return (
          <EmbeddedLink key={tab.href} href={tab.href} className={`portal-subtab-item${isActive ? " is-active" : ""}`}>
            {tab.label}
          </EmbeddedLink>
        );
      })}
    </nav>
  );
}
