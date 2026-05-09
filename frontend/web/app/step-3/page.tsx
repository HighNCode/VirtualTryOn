"use client";

import { useEffect, useMemo, useState } from "react";
import { EmbeddedLink, useEmbeddedRouter } from "../_components/EmbeddedNavigation";
import { getDefaultStoreId, getOnboardingStatus, saveReferral } from "../../lib/photoshootApi";

type ReferralOption = { id: string; label: string };

const referralOptions: ReferralOption[] = [
  { id: "google", label: "Google Search" },
  { id: "shopify_app_store", label: "Shopify App Store" },
  { id: "social_media", label: "Social Media" },
  { id: "friend_colleague", label: "Friend or Colleague" },
  { id: "email", label: "Email or Newsletter" },
  { id: "other", label: "Other" }
];

export default function StepThreePage() {
  const router = useEmbeddedRouter();
  const storeId = useMemo(() => getDefaultStoreId(), []);

  const [selected, setSelected] = useState("");
  const [otherDetail, setOtherDetail] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    if (!storeId) return;
    const controller = new AbortController();
    let active = true;
    setIsLoading(true);

    getOnboardingStatus({ storeId, signal: controller.signal })
      .then((status) => {
        if (!active) return;
        const savedSource = status.referral_source ?? "";
        setSelected(savedSource);
        setOtherDetail(savedSource === "other" ? status.referral_detail ?? "" : "");
      })
      .catch((error: unknown) => {
        if (!active || controller.signal.aborted) return;
        setErrorMessage(error instanceof Error ? error.message : "Failed to load referral selection.");
      })
      .finally(() => { if (active) setIsLoading(false); });

    return () => { active = false; controller.abort(); };
  }, [storeId]);

  const handleContinue = async () => {
    if (!storeId) { router.push("/step-4"); return; }
    if (!selected) { setErrorMessage("Please select how you heard about us."); return; }
    setIsSaving(true);
    setErrorMessage("");
    try {
      await saveReferral({ storeId, referralSource: selected, referralDetail: selected === "other" ? otherDetail : undefined });
      router.push("/step-4");
    } catch (error: unknown) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to save referral.");
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
          <p style={{ margin: 0, fontSize: 13, color: "#9ca3af" }}>Step 3 of 6</p>
        </div>

        {/* Progress bar */}
        <div style={{ width: "100%", height: 4, background: "#f3f4f6" }}>
          <div style={{ width: "50%", height: "100%", background: "linear-gradient(90deg, #7E0175, #E40206)" }} />
        </div>

        {/* Content */}
        <div style={{ padding: "24px 24px 16px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 4 }}>
            <EmbeddedLink
              href="/step-2"
              style={{ width: 32, height: 32, borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, background: "#f3f4f6", color: "#6b7280" }}
              aria-label="Go to Step 2"
            >
              <svg viewBox="0 0 24 24" width={16} height={16}>
                <path d="M14.6 5.5L8.2 12L14.6 18.5" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.8" />
              </svg>
            </EmbeddedLink>
            <h1 style={{ margin: 0, fontSize: 20, fontWeight: 800, color: "#1a1a1a" }}>How did you hear about us?</h1>
          </div>
          <p style={{ margin: "4px 0 20px 44px", fontSize: 14, color: "#6b7280" }}>This helps us understand how merchants discover Optimo VTS.</p>

          {isLoading && <p style={{ fontSize: 13, marginBottom: 12, padding: "8px 12px", borderRadius: 8, background: "rgba(126,1,117,0.06)", color: "#7E0175" }}>Loading current selection...</p>}
          {errorMessage && <p style={{ fontSize: 13, marginBottom: 12, padding: "8px 12px", borderRadius: 8, background: "#fff1f1", color: "#dc2626" }}>{errorMessage}</p>}

          <ul style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, listStyle: "none", margin: 0, padding: 0 }}>
            {referralOptions.map((option) => {
              const isSelected = selected === option.id;
              return (
                <li key={option.id}>
                  <label
                    style={{
                      display: "flex", alignItems: "center", gap: 12, padding: 16, borderRadius: 12, cursor: "pointer",
                      border: isSelected ? "1.5px solid #7E0175" : "1.5px solid #e5e5e5",
                      background: isSelected ? "rgba(126,1,117,0.04)" : "#fafafa",
                    }}
                  >
                    <input
                      type="radio"
                      name="referral"
                      value={option.id}
                      checked={isSelected}
                      onChange={() => { setSelected(option.id); setErrorMessage(""); }}
                      className="sr-only"
                    />
                    <span
                      style={{
                        width: 16, height: 16, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
                        border: isSelected ? "none" : "1.5px solid #d1d5db",
                        background: isSelected ? "linear-gradient(135deg, #7E0175, #E40206)" : "#fff",
                      }}
                    >
                      {isSelected && <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#fff" }} />}
                    </span>
                    <span style={{ fontSize: 14, fontWeight: 500, color: "#1a1a1a" }}>{option.label}</span>
                  </label>
                </li>
              );
            })}
          </ul>

          {selected === "other" && (
            <input
              type="text"
              style={{ width: "100%", marginTop: 16, padding: "10px 16px", borderRadius: 10, fontSize: 13, border: "1.5px solid #e5e5e5", outline: "none", color: "#1a1a1a", fontFamily: "inherit", boxSizing: "border-box" }}
              placeholder="Please describe..."
              value={otherDetail}
              onChange={(e) => setOtherDetail(e.target.value)}
              maxLength={200}
              onFocus={(e) => { e.currentTarget.style.borderColor = "#7E0175"; }}
              onBlur={(e) => { e.currentTarget.style.borderColor = "#e5e5e5"; }}
            />
          )}
        </div>

        {/* Footer */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 24px", borderTop: "1px solid #f0f0f0" }}>
          <EmbeddedLink href="/settings/support" style={{ fontSize: 13, color: "#7E0175", textDecoration: "underline" }}>
            Need help? Contact our support team
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
  );
}
