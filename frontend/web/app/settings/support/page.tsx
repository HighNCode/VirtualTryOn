import { Mail, ArrowRight } from "lucide-react";
import { EmbeddedLink } from "../../_components/EmbeddedNavigation";
import PortalSidebar from "../../_components/PortalSidebar";
import PortalTopbar from "../../_components/PortalTopbar";
import SubTabNav from "../../_components/SubTabNav";

const settingsTabs = [
  { href: "/settings", label: "Custom" },
  { href: "/settings/privacy", label: "Privacy" },
  { href: "/settings/billing", label: "Billing" },
  { href: "/settings/support", label: "Support" },
];

export default function SettingsSupportPage() {
  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden", background: "#f6f4f4" }}>
      <PortalSidebar activeMain="settings" activeSettings="support" />

      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "auto" }}>
        <PortalTopbar title="Settings" subtitle="Get help and contact our team" />
        <SubTabNav tabs={settingsTabs} />

        <div style={{ flex: 1, padding: 24, display: "flex", flexDirection: "column", gap: 16 }}>
          {/* Hero */}
          <div style={{ background: "#fff", borderRadius: 14, padding: 20, boxShadow: "0 1px 3px rgba(0,0,0,0.04)", border: "1px solid rgba(0,0,0,0.05)" }}>
            <span style={{ fontSize: 11, fontWeight: 600, padding: "4px 10px", borderRadius: 999, marginBottom: 12, display: "inline-block", background: "rgba(126,1,117,0.08)", color: "#7E0175" }}>
              Support
            </span>
            <h3 style={{ margin: "0 0 4px", fontSize: 17, fontWeight: 700, color: "#1a1a1a" }}>
              Merchant help, launch checks, and billing assistance
            </h3>
            <p style={{ margin: 0, fontSize: 14, color: "#6b7280" }}>
              Use the channels below for installation help, billing questions, or privacy requests.
            </p>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16 }}>
            {/* Primary email card */}
            <div style={{ background: "linear-gradient(135deg, rgba(126,1,117,0.04) 0%, rgba(228,2,6,0.03) 100%)", borderRadius: 14, padding: 20, boxShadow: "0 1px 3px rgba(0,0,0,0.04)", border: "1px solid rgba(0,0,0,0.05)" }}>
              <div style={{ width: 36, height: 36, borderRadius: 10, display: "flex", alignItems: "center", justifyContent: "center", marginBottom: 12, background: "linear-gradient(135deg, #7E0175 0%, #BC174A 55%, #E40206 100%)" }}>
                <Mail size={16} color="white" />
              </div>
              <span style={{ fontSize: 11, fontWeight: 600, display: "block", marginBottom: 4, color: "#7E0175" }}>
                Primary channel
              </span>
              <h4 style={{ margin: "0 0 8px", fontSize: 14, fontWeight: 700, color: "#1a1a1a" }}>
                Email support
              </h4>
              <p style={{ margin: "0 0 12px", fontSize: 14, color: "#6b7280" }}>
                Send your request to <strong style={{ color: "#1a1a1a" }}>contact@optimosolutions.com</strong> and include
                the shop domain, affected theme, and screenshots when relevant.
              </p>
              <a
                href="mailto:contact@optimosolutions.com?subject=Optimo%20VTS%20Support"
                style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "8px 16px", borderRadius: 10, fontSize: 14, fontWeight: 600, color: "#fff", background: "linear-gradient(135deg, #7E0175 0%, #BC174A 55%, #E40206 100%)", textDecoration: "none" }}
              >
                Send email
                <ArrowRight size={14} />
              </a>
              <ul style={{ marginTop: 16, display: "flex", flexDirection: "column", gap: 6, listStyle: "none", padding: 0 }}>
                {[
                  "Installation and theme app extension help",
                  "Billing and subscription questions",
                  "Store-specific troubleshooting",
                ].map((item) => (
                  <li key={item} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "#6b7280" }}>
                    <span style={{ width: 6, height: 6, borderRadius: "50%", flexShrink: 0, background: "#7E0175", display: "block" }} />
                    {item}
                  </li>
                ))}
              </ul>
            </div>

            {/* Fast paths */}
            <div style={{ background: "#fff", borderRadius: 14, padding: 20, boxShadow: "0 1px 3px rgba(0,0,0,0.04)", border: "1px solid rgba(0,0,0,0.05)" }}>
              <span style={{ fontSize: 11, fontWeight: 600, display: "block", marginBottom: 4, color: "#7E0175" }}>
                Fast paths
              </span>
              <h4 style={{ margin: "0 0 12px", fontSize: 14, fontWeight: 700, color: "#1a1a1a" }}>
                Resolve common tasks
              </h4>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {[
                  { href: "/settings/billing", label: "Review billing and active subscription" },
                  { href: "/settings/privacy", label: "Review privacy and compliance handling" },
                  { href: "/step-5/not-detected", label: "Re-open theme activation guidance" },
                ].map((link) => (
                  <EmbeddedLink key={link.href} href={link.href}>
                    <span style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 12px", borderRadius: 10, fontSize: 14, fontWeight: 500, background: "rgba(126,1,117,0.04)", color: "#7E0175", border: "1px solid rgba(126,1,117,0.1)" }}>
                      {link.label}
                      <ArrowRight size={13} />
                    </span>
                  </EmbeddedLink>
                ))}
              </div>
            </div>

            {/* Recommended details */}
            <div style={{ background: "#fff", borderRadius: 14, padding: 20, boxShadow: "0 1px 3px rgba(0,0,0,0.04)", border: "1px solid rgba(0,0,0,0.05)" }}>
              <span style={{ fontSize: 11, fontWeight: 600, display: "block", marginBottom: 4, color: "#6b7280" }}>
                Before you contact us
              </span>
              <h4 style={{ margin: "0 0 12px", fontSize: 14, fontWeight: 700, color: "#1a1a1a" }}>
                Recommended details
              </h4>
              <ul style={{ display: "flex", flexDirection: "column", gap: 10, listStyle: "none", padding: 0, margin: 0 }}>
                {[
                  "Shopify shop domain and theme name",
                  "The exact page or onboarding step that failed",
                  "A screenshot plus any visible error text",
                ].map((item) => (
                  <li key={item} style={{ display: "flex", alignItems: "flex-start", gap: 8, fontSize: 14, color: "#6b7280" }}>
                    <span style={{ width: 20, height: 20, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, marginTop: 2, fontSize: 10, fontWeight: 700, background: "#f3f4f6", color: "#6b7280" }}>
                      ✓
                    </span>
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
