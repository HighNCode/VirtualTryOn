"use client";

import { motion } from "framer-motion";
import { Database, Eye, Lock, Shield, UserCheck } from "lucide-react";
import PortalSidebar from "../../_components/PortalSidebar";
import PortalTopbar from "../../_components/PortalTopbar";
import SubTabNav from "../../_components/SubTabNav";

const privacyRows = [
  {
    title: "Data Encryption",
    text: "All customer data and images are encrypted at rest and in transit using AES-256.",
    icon: Shield,
  },
  {
    title: "No Image Retention",
    text: "Uploaded images are processed and deleted immediately - never stored on our servers.",
    icon: Eye,
  },
  {
    title: "GDPR Compliant",
    text: "Our platform is fully compliant with GDPR and other major data privacy regulations.",
    icon: Database,
  },
  {
    title: "Secure Processing",
    text: "AI processing occurs in isolated, sandboxed environments with no cross-customer data access.",
    icon: Lock,
  },
  {
    title: "Consent Management",
    text: "Built-in customer consent flows ensure shoppers agree to try-on terms before uploading.",
    icon: UserCheck,
  },
];

const settingsTabs = [
  { href: "/settings", label: "Custom" },
  { href: "/settings/privacy", label: "Privacy" },
  { href: "/settings/billing", label: "Billing" },
  { href: "/settings/support", label: "Support" },
];

export default function SettingsPrivacyPage() {
  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden", background: "#f6f4f4" }}>
      <PortalSidebar activeMain="settings" activeSettings="privacy" />

      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "auto" }}>
        <PortalTopbar title="Settings" subtitle="Data privacy and security features" />
        <SubTabNav tabs={settingsTabs} />

        <div style={{ flex: 1, padding: "24px 28px", display: "flex", flexDirection: "column", gap: 12 }}>
          {privacyRows.map((row, index) => {
            const Icon = row.icon;

            return (
              <motion.div
                key={row.title}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, delay: index * 0.05 }}
                style={{
                  minHeight: 78,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: 20,
                  borderRadius: 12,
                  padding: "16px 20px",
                  background: "#f4edf3",
                  border: "1px solid rgba(126,1,117,0.16)",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 16, minWidth: 0 }}>
                  <span
                    style={{
                      width: 34,
                      height: 34,
                      borderRadius: 9,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      flexShrink: 0,
                      background: "rgba(126,1,117,0.12)",
                      color: "#9a0788",
                    }}
                    aria-hidden
                  >
                    <Icon size={16} />
                  </span>
                  <div style={{ minWidth: 0 }}>
                    <h3 style={{ margin: "0 0 4px", fontSize: 14, fontWeight: 700, color: "#1a1a1a" }}>
                      {row.title}
                    </h3>
                    <p style={{ margin: 0, fontSize: 14, lineHeight: 1.45, color: "#5f6b85" }}>
                      {row.text}
                    </p>
                  </div>
                </div>

                <span
                  style={{
                    fontSize: 12,
                    fontWeight: 600,
                    padding: "3px 10px",
                    borderRadius: 999,
                    flexShrink: 0,
                    background: "#dcfce7",
                    color: "#15803d",
                  }}
                >
                  Active
                </span>
              </motion.div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
