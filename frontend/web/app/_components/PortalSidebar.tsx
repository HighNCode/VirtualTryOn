"use client";

import { useEffect, useMemo, useState } from "react";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import { BarChart3, Camera, LayoutDashboard, LogOut, Settings2, Sparkles } from "lucide-react";
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

const navItems = [
  { section: "overview" as MainSection, href: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { section: "analytics" as MainSection, href: "/analytics", label: "Analytics", icon: BarChart3 },
  { section: "settings" as MainSection, href: "/settings", label: "Settings", icon: Settings2 },
  { section: "ai" as MainSection, href: "/ai-product-shoot", label: "AI Product Shoot", icon: Camera },
];

export default function PortalSidebar({ activeMain }: PortalSidebarProps) {
  const router = useEmbeddedRouter();
  const pathname = usePathname();
  const storeId = useMemo(() => getDefaultStoreId(), []);
  const [showLogoFallback, setShowLogoFallback] = useState(false);

  useEffect(() => {
    if (!storeId) return;
    if (pathname === "/settings/billing") return;

    const controller = new AbortController();
    getOnboardingStatus({ storeId, signal: controller.signal })
      .then((status) => {
        if (status.billing_lock_reason) {
          router.replace("/settings/billing");
        }
      })
      .catch(() => {});

    return () => controller.abort();
  }, [pathname, router, storeId]);

  return (
    <aside
      style={{
        width: 220,
        flexShrink: 0,
        display: "flex",
        flexDirection: "column",
        height: "100vh",
        background: "#fff",
        position: "sticky",
        top: 0,
        borderRight: "1px solid #f0f0f0",
      }}
    >
      {/* Logo */}
      <div style={{ padding: "20px 16px 16px", borderBottom: "1px solid #f0f0f0" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <img
            src="/vts-logo.png"
            alt="VTS"
            style={{ height: 32, width: "auto", objectFit: "contain", flexShrink: 0, display: showLogoFallback ? "none" : "block" }}
            onError={() => setShowLogoFallback(true)}
          />
          <div
            style={{
              width: 30, height: 30, borderRadius: 10, display: showLogoFallback ? "flex" : "none",
              alignItems: "center", justifyContent: "center", flexShrink: 0,
              background: "linear-gradient(135deg, #7E0175 0%, #BC174A 55%, #E40206 100%)",
            }}
          >
            <Sparkles size={15} color="white" />
          </div>
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, lineHeight: 1.3, color: "#1a1a1a" }}>
              Virtual Tryon Studio
            </div>
            <div style={{ fontSize: 10, lineHeight: 1.3, color: "#9ca3af" }}>
              Merchant Portal
            </div>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav style={{ flex: 1, padding: "16px 12px", display: "flex", flexDirection: "column", gap: 2 }}>
        {navItems.map((item) => {
          const active = item.section === activeMain;
          return (
            <EmbeddedLink key={item.href} href={item.href}>
              <motion.div
                whileTap={{ scale: 0.98 }}
                style={{
                  display: "flex", alignItems: "center", gap: 10,
                  padding: "10px 12px", borderRadius: 10, cursor: "pointer",
                  transition: "background 180ms, color 180ms",
                  background: active ? "linear-gradient(135deg, #7E0175 0%, #BC174A 55%, #E40206 100%)" : "transparent",
                  color: active ? "#ffffff" : "#6b7280",
                }}
                onMouseEnter={(e) => {
                  if (!active) {
                    e.currentTarget.style.background = "rgba(126,1,117,0.05)";
                    e.currentTarget.style.color = "#7E0175";
                  }
                }}
                onMouseLeave={(e) => {
                  if (!active) {
                    e.currentTarget.style.background = "transparent";
                    e.currentTarget.style.color = "#6b7280";
                  }
                }}
              >
                <item.icon size={17} />
                <span style={{ fontSize: 13.5, fontWeight: 500 }}>{item.label}</span>
              </motion.div>
            </EmbeddedLink>
          );
        })}
      </nav>

      {/* Plan card + footer action */}
      <div style={{ padding: "0 12px 16px", display: "flex", flexDirection: "column", gap: 12 }}>
        <div
          style={{
            borderRadius: 11, padding: 12,
            background: "rgba(126, 1, 117, 0.05)",
            border: "1px solid rgba(126, 1, 117, 0.12)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: "#7E0175" }}>Pro Plan</span>
            <span style={{ fontSize: 10, color: "#6b7280" }}>340/500</span>
          </div>
          <div style={{ width: "100%", borderRadius: 999, overflow: "hidden", height: 5, background: "#f3f4f6" }}>
            <motion.div
              style={{ height: "100%", borderRadius: 999, background: "linear-gradient(90deg, #7E0175, #E40206)" }}
              initial={{ width: 0 }}
              animate={{ width: "68%" }}
              transition={{ duration: 0.8, ease: "easeOut" }}
            />
          </div>
          <div style={{ marginTop: 8, fontSize: 10, color: "#6b7280" }}>
            160 try-ons remaining
          </div>
        </div>

        <button
          type="button"
          style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 8, padding: "8px 12px", borderRadius: 10, fontSize: 13, fontWeight: 500, width: "100%", color: "#dc2626", background: "#fff1f1", border: "none", cursor: "pointer" }}
          onMouseEnter={(e) => (e.currentTarget.style.background = "#ffe4e4")}
          onMouseLeave={(e) => (e.currentTarget.style.background = "#fff1f1")}
        >
          <LogOut size={15} />
          Sign Out
        </button>
      </div>
    </aside>
  );
}
