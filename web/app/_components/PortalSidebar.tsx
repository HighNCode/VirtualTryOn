import { EmbeddedLink } from "./EmbeddedNavigation";

type MainSection = "overview" | "analytics" | "settings" | "ai";
type SettingsSection = "custom" | "privacy" | "billing" | "support";
type AiSection = "ghost" | "model-try-on" | "model-swap";

type PortalSidebarProps = {
  activeMain: MainSection;
  activeSettings?: SettingsSection;
  activeAi?: AiSection;
};

export default function PortalSidebar({ activeMain, activeSettings, activeAi }: PortalSidebarProps) {
  return (
    <aside className="portal-sidebar">
      <header className="portal-brand">
        <span className="portal-brand-mark">Optimo VTS</span>
        <h1>Merchant Control</h1>
        <p>Embedded Shopify workspace</p>
      </header>

      <nav aria-label="Primary">
        <EmbeddedLink href="/dashboard" className={`portal-nav-item${activeMain === "overview" ? " is-active" : ""}`}>
          <span aria-hidden>◉</span>
          <span>Overview</span>
        </EmbeddedLink>
        <EmbeddedLink href="/analytics" className={`portal-nav-item${activeMain === "analytics" ? " is-active" : ""}`}>
          <span aria-hidden>☰</span>
          <span>Analytics</span>
        </EmbeddedLink>
        <EmbeddedLink href="/settings" className={`portal-nav-item${activeMain === "settings" ? " is-active" : ""}`}>
          <span aria-hidden>⚙</span>
          <span>Settings</span>
        </EmbeddedLink>
        <EmbeddedLink
          href="/ai-product-shoot"
          className={`portal-nav-item portal-ai-item${activeMain === "ai" ? " is-active" : ""}`}
        >
          <span aria-hidden>✦</span>
          <span>AI Product Shoot</span>
        </EmbeddedLink>
      </nav>

      {activeMain === "settings" ? (
        <div className="portal-subnav" aria-label="Settings subsections">
          <EmbeddedLink
            href="/settings"
            className={`portal-sub-item${activeSettings === "custom" ? " is-active" : ""}`}
          >
            Custom
          </EmbeddedLink>
          <EmbeddedLink
            href="/settings/privacy"
            className={`portal-sub-item${activeSettings === "privacy" ? " is-active" : ""}`}
          >
            Privacy
          </EmbeddedLink>
          <EmbeddedLink
            href="/settings/billing"
            className={`portal-sub-item${activeSettings === "billing" ? " is-active" : ""}`}
          >
            Billing
          </EmbeddedLink>
          <EmbeddedLink
            href="/settings/support"
            className={`portal-sub-item${activeSettings === "support" ? " is-active" : ""}`}
          >
            Support
          </EmbeddedLink>
        </div>
      ) : null}

      {activeMain === "ai" ? (
        <div className="portal-subnav" aria-label="AI product shoot subsections">
          <EmbeddedLink
            href="/ai-product-shoot"
            className={`portal-sub-item${activeAi === "ghost" ? " is-active" : ""}`}
          >
            Ghost Mannequin
          </EmbeddedLink>
          <EmbeddedLink
            href="/ai-product-shoot/model-try-on"
            className={`portal-sub-item${activeAi === "model-try-on" ? " is-active" : ""}`}
          >
            Model Try-on
          </EmbeddedLink>
          <EmbeddedLink
            href="/ai-product-shoot/model-swap"
            className={`portal-sub-item${activeAi === "model-swap" ? " is-active" : ""}`}
          >
            Model Swap
          </EmbeddedLink>
        </div>
      ) : null}

      <div className="portal-sidebar-footer">
        <p className="portal-sidebar-eyebrow">Shopify Embedded App</p>
        <h2>Operational Hub</h2>
        <p>Manage onboarding, billing, analytics, and support without leaving Shopify Admin.</p>

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
