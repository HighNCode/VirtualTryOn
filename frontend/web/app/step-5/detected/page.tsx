"use client";

import { useEffect, useState } from "react";
import { EmbeddedLink, useEmbeddedRouter } from "../../_components/EmbeddedNavigation";
import { getDefaultStoreId, recheckOnboardingThemeStatus, updateThemeStatus } from "../../../lib/photoshootApi";

export default function StepFiveDetectedPage() {
  const router = useEmbeddedRouter();
  const [storeId, setStoreId] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    const resolvedStoreId = getDefaultStoreId();
    setStoreId(resolvedStoreId);

    if (!resolvedStoreId) {
      return () => { active = false; controller.abort(); };
    }

    recheckOnboardingThemeStatus({ storeId: resolvedStoreId, signal: controller.signal })
      .then((status) => {
        if (!active) return;
        if (!status.theme_extension_detected) router.replace("/step-5/not-detected");
      })
      .catch(() => {});

    return () => { active = false; controller.abort(); };
  }, [router]);

  const enableTryOn = async () => {
    const resolvedStoreId = getDefaultStoreId();
    setStoreId(resolvedStoreId);
    if (!resolvedStoreId) { router.push("/step-6"); return; }
    setIsSaving(true);
    setErrorMessage("");
    try {
      await updateThemeStatus({ storeId: resolvedStoreId, detected: true });
      router.push("/step-6");
    } catch (error: unknown) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to save theme status.");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "flex-start", justifyContent: "center", padding: "24px 16px", background: "#f6f4f4" }}>
      <div style={{ width: "100%", maxWidth: 680, background: "#fff", borderRadius: 14, overflow: "hidden", boxShadow: "0 4px 24px rgba(0,0,0,0.08)", border: "1px solid rgba(0,0,0,0.05)" }}>

        {/* Top bar */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 24px", borderBottom: "1px solid #f0f0f0" }}>
          <p style={{ margin: 0, fontSize: 13, fontWeight: 600, color: "#6b7280" }}>Welcome to Optimo VTS</p>
          <p style={{ margin: 0, fontSize: 13, color: "#9ca3af" }}>Step 5 of 6</p>
        </div>

        {/* Progress bar */}
        <div style={{ width: "100%", height: 4, background: "#f3f4f6" }}>
          <div style={{ width: "83.33%", height: "100%", background: "linear-gradient(90deg, #7E0175, #E40206)" }} />
        </div>

        {/* Content */}
        <div style={{ padding: "24px 24px 24px" }}>
          {/* Back + status row */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 24 }}>
            <EmbeddedLink
              href="/step-5/not-detected"
              style={{ width: 32, height: 32, borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center", background: "#f3f4f6", color: "#6b7280" }}
              aria-label="Go to previous screen"
            >
              <svg viewBox="0 0 24 24" width={16} height={16}>
                <path d="M14.6 5.5L8.2 12L14.6 18.5" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.8" />
              </svg>
            </EmbeddedLink>
            <span
              style={{ width: 48, height: 48, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", background: "#dcfce7" }}
              aria-hidden
            >
              <svg viewBox="0 0 24 24" width={22} height={22}>
                <path d="M20 7L10 17L5 12" fill="none" stroke="#15803d" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.8" />
              </svg>
            </span>
            <span style={{ width: 32 }} />
          </div>

          <div style={{ textAlign: "center", marginBottom: 24 }}>
            <h1 style={{ margin: "0 0 8px", fontSize: 22, fontWeight: 800, color: "#1a1a1a" }}>
              Try-on Button{" "}
              <span style={{ color: "#15803d" }}>detected</span>{" "}
              in theme
            </h1>
            <p style={{ margin: 0, fontSize: 14, lineHeight: 1.6, color: "#6b7280" }}>
              The theme extension is active.
              <br />
              Continue to enable customer try-on experience.
            </p>
          </div>

          {/* Success card */}
          <div
            style={{ display: "flex", alignItems: "center", gap: 16, padding: "16px 20px", borderRadius: 12, background: "#f0fdf4", border: "1.5px solid #bbf7d0" }}
          >
            <span
              style={{ width: 40, height: 40, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, background: "#dcfce7" }}
            >
              <svg viewBox="0 0 24 24" width={18} height={18}>
                <path d="M20 7L10 17L5 12" fill="none" stroke="#15803d" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.8" />
              </svg>
            </span>
            <div>
              <p style={{ margin: 0, fontSize: 14, fontWeight: 600, color: "#15803d" }}>Extension Active</p>
              <p style={{ margin: 0, fontSize: 13, color: "#166534" }}>The Optimo VTS widget block is live in your Shopify theme.</p>
            </div>
          </div>

          {!storeId && <p style={{ fontSize: 13, marginTop: 16, padding: "8px 12px", borderRadius: 8, background: "#fff1f1", color: "#dc2626" }}>Open the app from Shopify Admin to persist onboarding progress.</p>}
          {errorMessage && <p style={{ fontSize: 13, marginTop: 16, padding: "8px 12px", borderRadius: 8, background: "#fff1f1", color: "#dc2626" }}>{errorMessage}</p>}
        </div>

        {/* Footer */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 24px", borderTop: "1px solid #f0f0f0" }}>
          <EmbeddedLink href="/settings/support" style={{ fontSize: 13, color: "#7E0175", textDecoration: "underline" }}>
            Need help? Contact our support team
          </EmbeddedLink>
          <button
            type="button"
            onClick={enableTryOn}
            disabled={isSaving}
            style={{
              padding: "9px 22px", borderRadius: 10, fontSize: 13, fontWeight: 600, color: "#fff",
              background: "linear-gradient(135deg, #7E0175 0%, #BC174A 55%, #E40206 100%)",
              border: "none",
              cursor: isSaving ? "not-allowed" : "pointer",
              opacity: isSaving ? 0.7 : 1,
            }}
          >
            {isSaving ? "Saving..." : "Enable Try-on"}
          </button>
        </div>

      </div>
    </div>
  );
}
