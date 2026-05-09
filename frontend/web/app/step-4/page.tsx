"use client";

import { useMemo, useState } from "react";
import { EmbeddedLink, useEmbeddedRouter } from "../_components/EmbeddedNavigation";
import { getDefaultStoreId, saveWidgetScope } from "../../lib/photoshootApi";

const placementChoices = [
  {
    id: "collections",
    description: "Enable on entire collections. This is the easiest way to manage the button.",
    actionLabel: "Select Collections",
    href: "/step-4/select-collections",
    accent: true,
  },
  {
    id: "products",
    description: "Enable on specific products. Good for testing or limited drops.",
    actionLabel: "Select Products",
    href: "/step-4/select-products",
    accent: false,
  }
];

export default function StepFourPage() {
  const router = useEmbeddedRouter();
  const storeId = useMemo(() => getDefaultStoreId(), []);
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  const handleContinue = async () => {
    if (!storeId) { router.push("/step-4/configured"); return; }
    setIsSaving(true);
    setErrorMessage("");
    try {
      await saveWidgetScope({ storeId, scopeType: "all" });
      router.push("/step-4/configured");
    } catch (error: unknown) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to save widget scope.");
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
          <p style={{ margin: 0, fontSize: 13, color: "#9ca3af" }}>Step 4 of 6</p>
        </div>

        {/* Progress bar */}
        <div style={{ width: "100%", height: 4, background: "#f3f4f6" }}>
          <div style={{ width: "66.67%", height: "100%", background: "linear-gradient(90deg, #7E0175, #E40206)" }} />
        </div>

        {/* Content */}
        <div style={{ padding: "24px 24px 16px" }}>
          <div style={{ display: "flex", alignItems: "flex-start", gap: 12, marginBottom: 20 }}>
            <EmbeddedLink
              href="/step-3"
              style={{ width: 32, height: 32, borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, marginTop: 2, background: "#f3f4f6", color: "#6b7280" }}
              aria-label="Go to previous step"
            >
              <svg viewBox="0 0 24 24" width={16} height={16}>
                <path d="M14.6 5.5L8.2 12L14.6 18.5" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.8" />
              </svg>
            </EmbeddedLink>
            <div>
              <h1 style={{ margin: 0, fontSize: 20, fontWeight: 800, color: "#1a1a1a" }}>Enable the Try-On Button</h1>
              <p style={{ margin: "4px 0 0", fontSize: 14, color: "#6b7280" }}>Choose where you want the virtual try-on button to appear on your storefront.</p>
            </div>
          </div>

          {errorMessage && <p style={{ fontSize: 13, marginBottom: 16, padding: "8px 12px", borderRadius: 8, background: "#fff1f1", color: "#dc2626" }}>{errorMessage}</p>}

          <ul style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, listStyle: "none", margin: 0, padding: 0 }}>
            {placementChoices.map((choice) => (
              <li
                key={choice.id}
                style={{ borderRadius: 12, padding: 20, display: "flex", flexDirection: "column", gap: 16, border: "1px solid rgba(0,0,0,0.07)", background: "#fafafa" }}
              >
                <p style={{ margin: 0, fontSize: 14, lineHeight: 1.6, color: "#6b7280" }}>{choice.description}</p>
                <EmbeddedLink
                  href={choice.href}
                  style={
                    choice.accent
                      ? { display: "block", textAlign: "center", padding: "10px 16px", borderRadius: 10, fontSize: 13, fontWeight: 600, background: "linear-gradient(135deg, #7E0175 0%, #BC174A 55%, #E40206 100%)", color: "#fff", textDecoration: "none" }
                      : { display: "block", textAlign: "center", padding: "10px 16px", borderRadius: 10, fontSize: 13, fontWeight: 600, background: "#fff", border: "1.5px solid #7E0175", color: "#7E0175", textDecoration: "none" }
                  }
                >
                  {choice.actionLabel}
                </EmbeddedLink>
              </li>
            ))}
          </ul>
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
              onClick={handleContinue}
              disabled={isSaving}
              style={{
                padding: "9px 22px", borderRadius: 10, fontSize: 13, fontWeight: 600, color: "#fff",
                background: "linear-gradient(135deg, #7E0175 0%, #BC174A 55%, #E40206 100%)",
                border: "none",
                cursor: isSaving ? "not-allowed" : "pointer",
                opacity: isSaving ? 0.7 : 1,
              }}
            >
              {isSaving ? "Saving..." : "Continue"}
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}
