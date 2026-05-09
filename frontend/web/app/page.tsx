"use client";

import { useEffect, useMemo } from "react";
import { EmbeddedLink, useEmbeddedRouter } from "./_components/EmbeddedNavigation";
import { getDefaultStoreId, getOnboardingStatus } from "../lib/photoshootApi";

const ONBOARDING_AUTO_RESUME_DONE_KEY = "optimo_onboarding_autoresume_done";

const features = [
  { title: "Virtual Try-On for Customers", text: "Allow shoppers to upload their photo and preview products instantly, helping them buy with confidence." },
  { title: "AI Studio for Marketing", text: "Generate model-quality product visuals for landing pages and campaigns without a photoshoot." },
  { title: "Body Measurement Heat Map", text: "Analyze key body points from shopper images to recommend better-fitting sizes and reduce returns." },
  { title: "Marketing and User Experience", text: "Let shoppers share generated looks on social channels to amplify organic reach and engagement." }
];

const STEP_ROUTES: Record<string, string> = {
  goals: "/step-2",
  referral: "/step-3",
  widget_scope: "/step-4",
  theme_setup: "/step-5/not-detected",
  plan: "/step-6",
  complete: "/dashboard"
};

export default function Home() {
  const router = useEmbeddedRouter();
  const storeId = useMemo(() => getDefaultStoreId(), []);

  useEffect(() => {
    if (!storeId) return;
    getOnboardingStatus({ storeId })
      .then((status) => {
        if (status.billing_lock_reason) { router.replace("/settings/billing"); return; }
        const route = STEP_ROUTES[status.onboarding_step];
        if (!route || route === "/step-2") return;
        if (typeof window === "undefined") return;
        const alreadyAutoResumed = window.sessionStorage.getItem(ONBOARDING_AUTO_RESUME_DONE_KEY) === "1";
        if (alreadyAutoResumed) return;
        window.sessionStorage.setItem(ONBOARDING_AUTO_RESUME_DONE_KEY, "1");
        router.replace(route);
      })
      .catch(() => {});
  }, [router, storeId]);

  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "flex-start", justifyContent: "center", padding: "24px 16px", background: "#f6f4f4" }}>
      <div style={{ width: "100%", maxWidth: 680, background: "#fff", borderRadius: 14, overflow: "hidden", boxShadow: "0 4px 24px rgba(0,0,0,0.08)", border: "1px solid rgba(0,0,0,0.05)" }}>

        {/* Top bar */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 24px", borderBottom: "1px solid #f0f0f0" }}>
          <p style={{ margin: 0, fontSize: 13, fontWeight: 600, color: "#6b7280" }}>Welcome to Optimo VTS</p>
          <p style={{ margin: 0, fontSize: 13, color: "#9ca3af" }}>Step 1 of 6</p>
        </div>

        {/* Progress bar */}
        <div style={{ width: "100%", height: 4, background: "#f3f4f6" }}>
          <div style={{ width: "16.67%", height: "100%", background: "linear-gradient(90deg, #7E0175, #E40206)" }} />
        </div>

        {/* Content */}
        <div style={{ padding: "28px 24px 16px" }}>
          {/* Heading */}
          <div style={{ textAlign: "center", marginBottom: 24 }}>
            <h1 style={{ margin: "0 0 8px", fontSize: 26, fontWeight: 800, lineHeight: 1.2, color: "#1a1a1a" }}>
              Welcome to{" "}
              <span style={{ background: "linear-gradient(135deg, #7E0175 0%, #BC174A 55%, #E40206 100%)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent", backgroundClip: "text" }}>
                Optimo VTS AI
              </span>
            </h1>
            <p style={{ margin: 0, fontSize: 14, color: "#6b7280", lineHeight: 1.6 }}>
              The ultimate AI-powered Virtual Try-On studio<br />
              Boost confidence, reduce returns, and drive more sales.
            </p>
          </div>

          {/* Features panel */}
          <div style={{ border: "1px solid rgba(0,0,0,0.07)", borderRadius: 12, padding: "20px 20px", background: "#fafafa" }}>
            <h2 style={{ margin: "0 0 16px", fontSize: 15, fontWeight: 700, color: "#1a1a1a" }}>
              What you can do with{" "}
              <span style={{ background: "linear-gradient(135deg, #7E0175 0%, #BC174A 55%, #E40206 100%)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent", backgroundClip: "text" }}>
                Optimo VTS
              </span>
              :
            </h2>

            <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: 14 }}>
              {features.map((feature) => (
                <li key={feature.title} style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
                  <span style={{ width: 20, height: 20, borderRadius: "50%", background: "#dcfce7", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, marginTop: 2 }}>
                    <svg viewBox="0 0 24 24" width={11} height={11} aria-hidden>
                      <path d="M20 7L10 17L5 12" fill="none" stroke="#15803d" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.75" />
                    </svg>
                  </span>
                  <div>
                    <p style={{ margin: "0 0 2px", fontSize: 14, fontWeight: 600, color: "#1a1a1a" }}>{feature.title}:</p>
                    <p style={{ margin: 0, fontSize: 13, color: "#6b7280", lineHeight: 1.5 }}>{feature.text}</p>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Footer */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 24px", borderTop: "1px solid #f0f0f0" }}>
          <EmbeddedLink href="/settings/support" style={{ fontSize: 13, color: "#7E0175", textDecoration: "underline" }}>
            Need help? Contact our support team
          </EmbeddedLink>
          <EmbeddedLink
            href="/step-2"
            style={{ padding: "9px 22px", borderRadius: 10, fontSize: 13, fontWeight: 600, color: "#fff", background: "linear-gradient(135deg, #7E0175 0%, #BC174A 55%, #E40206 100%)", textDecoration: "none" }}
          >
            Continue
          </EmbeddedLink>
        </div>

      </div>
    </div>
  );
}
