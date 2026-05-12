import PortalSidebar from "../../_components/PortalSidebar";
import PortalTopbar from "../../_components/PortalTopbar";
import SubTabNav from "../../_components/SubTabNav";

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
    text: "Customer media is cache-visible for about 1 hour; if explicit consent is collected in widget setup, photos and measurement outputs can be retained for research for a limited period.",
    status: "Configured"
  }
];

export default function SettingsPrivacyPage() {
  const settingsTabs = [
    { href: "/settings", label: "Custom" },
    { href: "/settings/privacy", label: "Privacy" },
    { href: "/settings/billing", label: "Billing" },
    { href: "/settings/support", label: "Support" }
  ];

  return (
    <main className="portal-shell">
      <PortalSidebar activeMain="settings" activeSettings="privacy" />

      <section className="portal-main">
        <PortalTopbar title="Settings" subtitle="Data privacy and security features" />
        <SubTabNav tabs={settingsTabs} />

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
