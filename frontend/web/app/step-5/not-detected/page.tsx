"use client";

import { useCallback, useEffect, useState } from "react";
import { EmbeddedLink, useEmbeddedRouter } from "../../_components/EmbeddedNavigation";
import { getDefaultStoreId, recheckOnboardingThemeStatus } from "../../../lib/photoshootApi";

export default function StepFiveNotDetectedPage() {
  const router = useEmbeddedRouter();
  const [storeId, setStoreId] = useState("");
  const [themesUrl, setThemesUrl] = useState("");
  const [isChecking, setIsChecking] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [warningMessage, setWarningMessage] = useState("");

  const checkStatus = useCallback(
    async (markDetected: boolean) => {
      const resolvedStoreId = getDefaultStoreId();
      setStoreId(resolvedStoreId);
      setIsChecking(true);
      setErrorMessage("");
      setWarningMessage("");
      try {
        const status = await recheckOnboardingThemeStatus({ storeId: resolvedStoreId || "" });
        setThemesUrl((status.add_to_theme_url || status.themes_url || "").trim());
        if (status.theme_extension_detected) { router.push("/step-5/detected"); return; }
        if (status.detection_source === "runtime_flag" && status.message) setWarningMessage(status.message);
        if (markDetected) setErrorMessage("Theme extension is still not detected. Save changes in Shopify theme editor and retry.");
      } catch (error: unknown) {
        if (!resolvedStoreId) {
          setErrorMessage("Shop context is missing in this embedded view. Reopen the app from Shopify Admin and retry.");
        } else {
          setErrorMessage(error instanceof Error ? error.message : "Failed to verify theme status.");
        }
      } finally {
        setIsChecking(false);
      }
    },
    [router]
  );

  useEffect(() => {
    setStoreId(getDefaultStoreId());
    void checkStatus(false);
  }, [checkStatus]);

  const quickSteps = [
    "Click Add to Theme above",
    "In the theme editor, add the Optimo VTS Widget app block to the product template",
    "Click Save in the Shopify editor",
    "Return here and click Retry"
  ];

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
        <div style={{ padding: "24px 24px 16px" }}>
          {/* Back + status row */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 24 }}>
            <EmbeddedLink
              href="/step-4/configured"
              style={{ width: 32, height: 32, borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center", background: "#f3f4f6", color: "#6b7280" }}
              aria-label="Go to previous screen"
            >
              <svg viewBox="0 0 24 24" width={16} height={16}>
                <path d="M14.6 5.5L8.2 12L14.6 18.5" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.8" />
              </svg>
            </EmbeddedLink>
            <span
              style={{ width: 48, height: 48, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", background: "#fff1f1" }}
              aria-hidden
            >
              <svg viewBox="0 0 24 24" width={20} height={20}>
                <path d="M7 7L17 17M17 7L7 17" fill="none" stroke="#dc2626" strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" />
              </svg>
            </span>
            <span style={{ width: 32 }} />
          </div>

          <div style={{ textAlign: "center", marginBottom: 20 }}>
            <h1 style={{ margin: "0 0 8px", fontSize: 22, fontWeight: 800, color: "#1a1a1a" }}>
              Try-on Button{" "}
              <span style={{ color: "#dc2626" }}>not detected</span>{" "}
              in theme
            </h1>
            <p style={{ margin: 0, fontSize: 14, lineHeight: 1.6, color: "#6b7280" }}>
              To show the virtual try-on button on your storefront, add it to your theme.
            </p>
          </div>

          {!storeId && <p style={{ fontSize: 13, marginBottom: 16, padding: "8px 12px", borderRadius: 8, background: "#fff1f1", color: "#dc2626" }}>Open the app from Shopify Admin to verify theme extension status.</p>}
          {warningMessage && <p style={{ fontSize: 13, marginBottom: 16, padding: "8px 12px", borderRadius: 8, background: "#fff1f1", color: "#dc2626" }}>{warningMessage}</p>}
          {errorMessage && <p style={{ fontSize: 13, marginBottom: 16, padding: "8px 12px", borderRadius: 8, background: "#fff1f1", color: "#dc2626" }}>{errorMessage}</p>}

          {/* Add to theme CTA */}
          <div style={{ display: "flex", justifyContent: "center", marginBottom: 20 }}>
            {themesUrl ? (
              <a
                href={themesUrl}
                target="_blank"
                rel="noreferrer"
                style={{ padding: "12px 32px", borderRadius: 10, fontSize: 13, fontWeight: 600, color: "#fff", background: "linear-gradient(135deg, #7E0175 0%, #BC174A 55%, #E40206 100%)", textDecoration: "none" }}
              >
                + Add to Theme
              </a>
            ) : (
              <button
                type="button"
                style={{ padding: "12px 32px", borderRadius: 10, fontSize: 13, fontWeight: 600, color: "#fff", background: "#d1d5db", border: "none", cursor: "not-allowed" }}
                disabled
              >
                Theme editor unavailable
              </button>
            )}
          </div>

          <p style={{ margin: "0 0 20px", fontSize: 13, textAlign: "center", color: "#9ca3af" }}>
            Click Add to Theme to open the Shopify theme editor, then add the Optimo VTS widget block to product pages.
          </p>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            {/* Video tutorial placeholder */}
            <div style={{ borderRadius: 12, padding: 16, border: "1px solid rgba(0,0,0,0.07)", background: "#fafafa" }}>
              <h2 style={{ margin: "0 0 12px", fontSize: 13, fontWeight: 700, color: "#1a1a1a" }}>
                Watch{" "}
                <span style={{ background: "linear-gradient(135deg, #7E0175 0%, #E40206 100%)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent", backgroundClip: "text" }}>
                  Tutorial
                </span>
              </h2>
              <div
                style={{ borderRadius: 10, overflow: "hidden", background: "#e5e7eb", height: 90, position: "relative" }}
                aria-hidden
              >
                <div style={{ position: "absolute", inset: 0, background: "linear-gradient(135deg, rgba(126,1,117,0.1), rgba(228,2,6,0.05))" }} />
                <div style={{ position: "absolute", top: "50%", left: "50%", transform: "translate(-50%,-50%)", width: 36, height: 36, borderRadius: "50%", background: "rgba(126,1,117,0.15)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <svg viewBox="0 0 24 24" width={16} height={16} style={{ color: "#7E0175" }}>
                    <path d="M8 5v14l11-7z" fill="currentColor" />
                  </svg>
                </div>
              </div>
            </div>

            {/* Quick instructions */}
            <div style={{ borderRadius: 12, padding: 16, border: "1px solid rgba(0,0,0,0.07)", background: "#fafafa" }}>
              <h2 style={{ margin: "0 0 12px", fontSize: 13, fontWeight: 700, color: "#1a1a1a" }}>Quick Instructions</h2>
              <ol style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 8 }}>
                {quickSteps.map((step, i) => (
                  <li key={step} style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
                    <span
                      style={{ width: 20, height: 20, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, fontSize: 10, fontWeight: 700, marginTop: 2, background: "rgba(126,1,117,0.1)", color: "#7E0175" }}
                    >
                      {i + 1}
                    </span>
                    <span style={{ fontSize: 12, lineHeight: 1.6, color: "#6b7280" }}>{step}</span>
                  </li>
                ))}
              </ol>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 24px", borderTop: "1px solid #f0f0f0" }}>
          <EmbeddedLink href="/settings/support" style={{ fontSize: 13, color: "#7E0175", textDecoration: "underline" }}>
            Need help? Contact our support team
          </EmbeddedLink>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <EmbeddedLink
              href="/step-6"
              style={{ padding: "9px 20px", borderRadius: 10, fontSize: 13, fontWeight: 600, border: "1.5px solid #e5e5e5", color: "#6b7280", textDecoration: "none" }}
            >
              Skip for now
            </EmbeddedLink>
            <button
              type="button"
              onClick={() => checkStatus(true)}
              disabled={isChecking}
              style={{
                padding: "9px 22px", borderRadius: 10, fontSize: 13, fontWeight: 600, color: "#fff",
                background: "linear-gradient(135deg, #7E0175 0%, #BC174A 55%, #E40206 100%)",
                border: "none",
                cursor: isChecking ? "not-allowed" : "pointer",
                opacity: isChecking ? 0.7 : 1,
              }}
            >
              {isChecking ? "Checking..." : "Retry"}
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}
