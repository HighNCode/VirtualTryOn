"use client";

import { useEffect, useMemo, useState } from "react";
import { usePathname } from "next/navigation";
import { BarChart3, Camera, LayoutDashboard, Settings, Sparkles } from "lucide-react";
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
  const [showLogoFallback, setShowLogoFallback] = useState(false);

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
        <img
          src="/vts-logo.png"
          alt="VTS"
          className="portal-brand-image"
          onError={() => setShowLogoFallback(true)}
          style={showLogoFallback ? { display: "none" } : undefined}
        />
        <div className="portal-brand-logo" aria-hidden style={showLogoFallback ? undefined : { display: "none" }}>
          <Sparkles size={15} color="#fff" />
        </div>
        <div className="portal-brand-copy">
          <h1>Virtual Tryon Studio</h1>
          <p>Merchant Portal</p>
        </div>
      </header>

      <nav aria-label="Primary">
        <EmbeddedLink href="/dashboard" className={`portal-nav-item${activeMain === "overview" ? " is-active" : ""}`}>
          <span aria-hidden className="portal-nav-icon">
            <LayoutDashboard size={17} />
          </span>
          <span>Overview</span>
        </EmbeddedLink>

        <EmbeddedLink href="/analytics" className={`portal-nav-item${activeMain === "analytics" ? " is-active" : ""}`}>
          <span aria-hidden className="portal-nav-icon">
            <BarChart3 size={17} />
          </span>
          <span>Analytics</span>
        </EmbeddedLink>

        <EmbeddedLink href="/settings" className={`portal-nav-item${activeMain === "settings" ? " is-active" : ""}`}>
          <span aria-hidden className="portal-nav-icon">
            <Settings size={17} />
          </span>
          <span>Settings</span>
        </EmbeddedLink>

        <EmbeddedLink href="/ai-product-shoot" className={`portal-nav-item portal-ai-item${activeMain === "ai" ? " is-active" : ""}`}>
          <span aria-hidden className="portal-nav-icon">
            <Camera size={17} />
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
