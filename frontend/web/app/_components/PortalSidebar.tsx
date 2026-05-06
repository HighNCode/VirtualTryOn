"use client";

import { useEffect, useMemo } from "react";
import { usePathname } from "next/navigation";
import { EmbeddedLink, useEmbeddedRouter } from "./EmbeddedNavigation";
import { getDefaultStoreId, getOnboardingStatus } from "../../lib/photoshootApi";

type MainSection = "overview" | "analytics" | "settings" | "ai";
type SettingsSection = "custom" | "privacy" | "billing" | "support";
type AiSection = "ghost" | "model-try-on" | "model-swap";

type PortalSidebarProps = {
  activeMain: MainSection;
  activeSettings?: SettingsSection;
  activeAi?: AiSection;
};

export default function PortalSidebar({ activeMain }: PortalSidebarProps) {
  const router = useEmbeddedRouter();
  const pathname = usePathname();
  const storeId = useMemo(() => getDefaultStoreId(), []);

  useEffect(() => {
    if (!storeId) {
      return;
    }

    if (pathname === "/settings/billing") {
      return;
    }

    const controller = new AbortController();
    getOnboardingStatus({ storeId, signal: controller.signal })
      .then((status) => {
        if (status.billing_lock_reason) {
          router.replace("/settings/billing");
        }
      })
      .catch(() => {
        // Non-blocking for sidebar rendering
      });

    return () => controller.abort();
  }, [pathname, router, storeId]);

  return (
    <aside className="portal-sidebar">
      <header className="portal-brand">
        <div className="portal-brand-logo" aria-hidden>
          <svg viewBox="0 0 24 24" role="img">
            <path d="M12 2L15.2 8.8L22 12L15.2 15.2L12 22L8.8 15.2L2 12L8.8 8.8L12 2Z" />
          </svg>
        </div>
        <div className="portal-brand-copy">
          <h1>Virtual Tryon Studio</h1>
          <p>Merchant Portal</p>
        </div>
      </header>

      <nav aria-label="Primary">
        <EmbeddedLink href="/dashboard" className={`portal-nav-item${activeMain === "overview" ? " is-active" : ""}`}>
          <span aria-hidden className="portal-nav-icon">
            <svg viewBox="0 0 24 24" role="img">
              <rect x="3.5" y="3.5" width="7" height="7" rx="1.6" />
              <rect x="13.5" y="3.5" width="7" height="7" rx="1.6" />
              <rect x="3.5" y="13.5" width="7" height="7" rx="1.6" />
              <rect x="13.5" y="13.5" width="7" height="7" rx="1.6" />
            </svg>
          </span>
          <span>Overview</span>
        </EmbeddedLink>

        <EmbeddedLink href="/analytics" className={`portal-nav-item${activeMain === "analytics" ? " is-active" : ""}`}>
          <span aria-hidden className="portal-nav-icon">
            <svg viewBox="0 0 24 24" role="img">
              <path d="M4 18.5H20" />
              <path d="M7 15V9.5" />
              <path d="M12 15V6" />
              <path d="M17 15V11.5" />
            </svg>
          </span>
          <span>Analytics</span>
        </EmbeddedLink>

        <EmbeddedLink href="/settings" className={`portal-nav-item${activeMain === "settings" ? " is-active" : ""}`}>
          <span aria-hidden className="portal-nav-icon">
            <svg viewBox="0 0 24 24" role="img">
              <path d="M12 8.2A3.8 3.8 0 1 0 12 15.8A3.8 3.8 0 1 0 12 8.2Z" />
              <path d="M19.3 15.1L21 16.1L19.4 18.9L17.5 18.2C16.9 18.8 16.2 19.3 15.4 19.6L15.1 21.6H8.9L8.6 19.6C7.8 19.3 7.1 18.8 6.5 18.2L4.6 18.9L3 16.1L4.7 15.1C4.6 14.7 4.5 14.3 4.5 13.8C4.5 13.3 4.6 12.9 4.7 12.5L3 11.5L4.6 8.7L6.5 9.4C7.1 8.8 7.8 8.3 8.6 8L8.9 6H15.1L15.4 8C16.2 8.3 16.9 8.8 17.5 9.4L19.4 8.7L21 11.5L19.3 12.5C19.4 12.9 19.5 13.3 19.5 13.8C19.5 14.3 19.4 14.7 19.3 15.1Z" />
            </svg>
          </span>
          <span>Settings</span>
        </EmbeddedLink>

        <EmbeddedLink href="/ai-product-shoot" className={`portal-nav-item portal-ai-item${activeMain === "ai" ? " is-active" : ""}`}>
          <span aria-hidden className="portal-nav-icon">
            <svg viewBox="0 0 24 24" role="img">
              <path d="M4 8.2C4 7 5 6 6.2 6H17.8C19 6 20 7 20 8.2V15.8C20 17 19 18 17.8 18H6.2C5 18 4 17 4 15.8V8.2Z" />
              <circle cx="12" cy="12" r="2.7" />
              <path d="M8.1 6L9.2 4.2H14.8L15.9 6" />
            </svg>
          </span>
          <span>AI Product Shoot</span>
        </EmbeddedLink>
      </nav>

      <div className="portal-sidebar-footer">
        <div className="portal-plan-card">
          <div className="portal-plan-head">
            <span>Pro Plan</span>
            <span>340/500</span>
          </div>
          <div className="portal-plan-progress" aria-hidden>
            <span />
          </div>
          <p>160 try-ons remaining</p>
        </div>

        <div className="portal-sidebar-links">
          <EmbeddedLink href="/settings/billing" className="portal-sidebar-link">
            Billing
          </EmbeddedLink>
          <EmbeddedLink href="/settings/support" className="portal-sidebar-link">
            Support
          </EmbeddedLink>
        </div>
      </div>
    </aside>
  );
}
