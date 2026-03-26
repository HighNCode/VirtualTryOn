import { EmbeddedLink } from "../../_components/EmbeddedNavigation";
import PortalSidebar from "../../_components/PortalSidebar";

export default function SettingsSupportPage() {
  return (
    <main className="portal-shell">
      <PortalSidebar activeMain="settings" activeSettings="support" />

      <section className="portal-main">
        <header className="portal-main-header">
          <h2>Settings</h2>
          <p>Manage your Virtual Try-on Studio preferences</p>
        </header>

        <section className="support-wrap">
          <div className="support-hero">
            <p className="support-kicker">Support</p>
            <h3>Merchant help, launch checks, and billing assistance</h3>
            <p>
              Use the channels below for installation help, billing questions, or privacy requests. This page avoids a
              fake contact form and points merchants to real support paths.
            </p>
          </div>

          <div className="support-grid">
            <article className="support-card support-card-primary">
              <p className="support-kicker">Primary channel</p>
              <h4>Email support</h4>
              <p className="support-card-copy">
                Send your request to <strong>contact@optimosolutions.com</strong> and include the shop domain,
                affected theme, and screenshots when relevant.
              </p>
              <a className="support-link-button" href="mailto:contact@optimosolutions.com?subject=Optimo%20VTS%20Support">
                contact@optimosolutions.com
              </a>
              <ul className="support-checklist">
                <li>Installation and theme app extension help</li>
                <li>Billing and subscription questions</li>
                <li>Store-specific troubleshooting</li>
              </ul>
            </article>

            <article className="support-card">
              <p className="support-kicker">Fast paths</p>
              <h4>Resolve common tasks</h4>
              <div className="support-link-list">
                <EmbeddedLink href="/settings/billing" className="support-inline-link">
                  Review billing and active subscription
                </EmbeddedLink>
                <EmbeddedLink href="/settings/privacy" className="support-inline-link">
                  Review privacy and compliance handling
                </EmbeddedLink>
                <EmbeddedLink href="/step-5/not-detected" className="support-inline-link">
                  Re-open theme activation guidance
                </EmbeddedLink>
              </div>
            </article>

            <article className="support-card">
              <p className="support-kicker">Before you contact us</p>
              <h4>Recommended details</h4>
              <ul className="support-checklist">
                <li>Shopify shop domain and theme name</li>
                <li>The exact page or onboarding step that failed</li>
                <li>A screenshot plus any visible error text</li>
              </ul>
            </article>
          </div>
        </section>
      </section>
    </main>
  );
}
