"use client";

import { useEffect, useMemo, useState } from "react";
import { Camera, Mail, TrendingDown, TrendingUp, type LucideIcon } from "lucide-react";
import { EmbeddedLink, useEmbeddedRouter } from "../_components/EmbeddedNavigation";
import { getDefaultStoreId, getOnboardingStatus, saveOnboardingGoals } from "../../lib/photoshootApi";

type GoalOption = {
  id: string;
  title: string;
  description: string;
  icon: LucideIcon;
};

const goals: GoalOption[] = [
  { id: "conversion", title: "Improve conversion rates", description: "Help customers make faster purchasing decisions", icon: TrendingUp },
  { id: "returns", title: "Reduce return rates", description: "Minimize returns due to sizing or fit issues", icon: TrendingDown },
  { id: "emails", title: "Collect customer emails", description: "Build your email list through the try-on button", icon: Mail },
  { id: "content", title: "Create marketing content", description: "Use AI Studio to generate on-model photos for ads", icon: Camera }
];

export default function StepTwoPage() {
  const router = useEmbeddedRouter();
  const storeId = useMemo(() => getDefaultStoreId(), []);

  const [selectedGoals, setSelectedGoals] = useState<string[]>([]);
  const [isSaving, setIsSaving] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    if (!storeId) return;
    const controller = new AbortController();
    let active = true;
    setIsLoading(true);

    getOnboardingStatus({ storeId, signal: controller.signal })
      .then((status) => { if (active) setSelectedGoals(status.goals ?? []); })
      .catch((error: unknown) => {
        if (!active || controller.signal.aborted) return;
        setErrorMessage(error instanceof Error ? error.message : "Failed to load onboarding goals.");
      })
      .finally(() => { if (active) setIsLoading(false); });

    return () => { active = false; controller.abort(); };
  }, [storeId]);

  const selectedSet = useMemo(() => new Set(selectedGoals), [selectedGoals]);

  const toggleGoal = (goalId: string) => {
    setSelectedGoals((current) =>
      current.includes(goalId) ? current.filter((id) => id !== goalId) : [...current, goalId]
    );
  };

  const handleContinue = async () => {
    if (!storeId) { router.push("/step-3"); return; }
    setIsSaving(true);
    setErrorMessage("");
    try {
      await saveOnboardingGoals({ storeId, goals: selectedGoals });
      router.push("/step-3");
    } catch (error: unknown) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to save goals.");
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
          <p style={{ margin: 0, fontSize: 13, color: "#9ca3af" }}>Step 2 of 6</p>
        </div>

        {/* Progress bar */}
        <div style={{ width: "100%", height: 4, background: "#f3f4f6" }}>
          <div style={{ width: "33.33%", height: "100%", background: "linear-gradient(90deg, #7E0175, #E40206)" }} />
        </div>

        {/* Content */}
        <div style={{ padding: "24px 24px 16px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 4 }}>
            <EmbeddedLink
              href="/"
              style={{ width: 32, height: 32, borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, background: "#f3f4f6", color: "#6b7280" }}
              aria-label="Go to Step 1"
            >
              <svg viewBox="0 0 24 24" width={16} height={16}>
                <path d="M14.6 5.5L8.2 12L14.6 18.5" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.8" />
              </svg>
            </EmbeddedLink>
            <h1 style={{ margin: 0, fontSize: 20, fontWeight: 800, color: "#1a1a1a" }}>What do you want to achieve?</h1>
          </div>
          <p style={{ margin: "4px 0 20px 44px", fontSize: 14, color: "#6b7280" }}>Select all that apply</p>

          {isLoading && <p style={{ fontSize: 13, marginBottom: 12, padding: "8px 12px", borderRadius: 8, background: "rgba(126,1,117,0.06)", color: "#7E0175" }}>Loading current goals...</p>}
          {!storeId && <p style={{ fontSize: 13, marginBottom: 12, padding: "8px 12px", borderRadius: 8, background: "#fff1f1", color: "#dc2626" }}>Open the app from Shopify Admin to save onboarding progress.</p>}
          {errorMessage && <p style={{ fontSize: 13, marginBottom: 12, padding: "8px 12px", borderRadius: 8, background: "#fff1f1", color: "#dc2626" }}>{errorMessage}</p>}

          <ul style={{ display: "flex", flexDirection: "column", gap: 12, listStyle: "none", margin: 0, padding: 0 }}>
            {goals.map((goal) => {
              const isSelected = selectedSet.has(goal.id);
              const Icon = goal.icon;
              return (
                <li key={goal.id}>
                  <label
                    style={{
                      display: "flex", alignItems: "center", gap: 16, padding: 16, borderRadius: 12, cursor: "pointer",
                      border: isSelected ? "1.5px solid #7E0175" : "1.5px solid #e5e5e5",
                      background: isSelected ? "rgba(126,1,117,0.04)" : "#fafafa",
                    }}
                  >
                    <input
                      type="checkbox"
                      name="goals"
                      value={goal.id}
                      checked={isSelected}
                      onChange={() => toggleGoal(goal.id)}
                      className="sr-only"
                    />
                    <span
                      style={{
                        width: 20, height: 20, borderRadius: 5, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
                        background: isSelected ? "linear-gradient(135deg, #7E0175, #E40206)" : "#fff",
                        border: isSelected ? "none" : "1.5px solid #d1d5db",
                      }}
                    >
                      {isSelected && (
                        <svg viewBox="0 0 24 24" width={12} height={12}>
                          <path d="M20 7L10 17L5 12" fill="none" stroke="white" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.8" />
                        </svg>
                      )}
                    </span>
                    <span
                      style={{ width: 36, height: 36, borderRadius: 10, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, background: isSelected ? "rgba(126,1,117,0.1)" : "#f3f4f6" }}
                    >
                      <Icon size={18} style={{ color: isSelected ? "#7E0175" : "#6b7280" }} />
                    </span>
                    <span style={{ display: "flex", flexDirection: "column" }}>
                      <span style={{ fontSize: 14, fontWeight: 600, color: "#1a1a1a" }}>{goal.title}</span>
                      <span style={{ fontSize: 13, color: "#6b7280" }}>{goal.description}</span>
                    </span>
                  </label>
                </li>
              );
            })}
          </ul>
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
