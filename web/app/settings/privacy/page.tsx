import PortalSidebar from "../../_components/PortalSidebar";

const privacyRows = [
  {
    title: "Shopify compliance webhooks",
    text: "The app is configured for Shopify privacy webhook topics including customer data requests and redaction callbacks.",
    status: "Configured"
  },
  {
    title: "Webhook signature validation",
    text: "Incoming Shopify webhooks are HMAC-validated before the payload is processed or forwarded.",
    status: "Verified"
  },
  {
    title: "Embedded Admin authentication",
    text: "Billing and Shopify Admin requests run inside Shopify Admin using the embedded app context and session token flow.",
    status: "Active"
  },
  {
    title: "Store scoping",
    text: "Merchant requests are tied to the active Shopify shop domain instead of exposing a private API host or store UUID in the browser.",
    status: "Hardened"
  },
  {
    title: "Policy and retention details",
    text: "Retention policy, subprocessors, and merchant-facing policy documents should be provided in the client handoff and app listing.",
    status: "Review"
  }
];

export default function SettingsPrivacyPage() {
  return (
    <main className="portal-shell">
      <PortalSidebar activeMain="settings" activeSettings="privacy" />

      <section className="portal-main">
        <header className="portal-main-header">
          <h2>Settings</h2>
          <p>Manage your Virtual Try-on Studio preferences</p>
        </header>

        <section className="settings-card">
          <h3>Privacy &amp; Data Protection</h3>
          <p className="settings-subtext">How we protect your customers&apos; data</p>

          <ul className="privacy-list">
            {privacyRows.map((row) => (
              <li key={row.title} className="privacy-item">
                <div>
                  <h4>{row.title}</h4>
                  <p>{row.text}</p>
                </div>
                <span>{row.status}</span>
              </li>
            ))}
          </ul>
        </section>
      </section>
    </main>
  );
}
