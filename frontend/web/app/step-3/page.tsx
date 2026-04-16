"use client";

import { useEffect, useMemo, useState } from "react";
import { EmbeddedLink, useEmbeddedRouter } from "../_components/EmbeddedNavigation";
import { getDefaultStoreId, getOnboardingStatus, saveReferral } from "../../lib/photoshootApi";

type ReferralOption = {
  id: string;
  label: string;
};

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
    if (!storeId) {
      return;
    }

    const controller = new AbortController();
    let active = true;

    setIsLoading(true);

    getOnboardingStatus({ storeId, signal: controller.signal })
      .then((status) => {
        if (!active) {
          return;
        }

        const savedSource = status.referral_source ?? "";
        setSelected(savedSource);
        setOtherDetail(savedSource === "other" ? status.referral_detail ?? "" : "");
      })
      .catch((error: unknown) => {
        if (!active || controller.signal.aborted) {
          return;
        }

        const message = error instanceof Error ? error.message : "Failed to load referral selection.";
        setErrorMessage(message);
      })
      .finally(() => {
        if (active) {
          setIsLoading(false);
        }
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [storeId]);

  const handleContinue = async () => {
    if (!storeId) {
      router.push("/step-4");
      return;
    }

    if (!selected) {
      setErrorMessage("Please select how you heard about us.");
      return;
    }

    setIsSaving(true);
    setErrorMessage("");

    try {
      await saveReferral({
        storeId,
        referralSource: selected,
        referralDetail: selected === "other" ? otherDetail : undefined
      });
      router.push("/step-4");
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Failed to save referral.";
      setErrorMessage(message);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <main className="shell">
      <section className="welcome-card">
        <header className="topline">
          <p className="screen-title">Welcome to Optimo VTS</p>
          <p className="step">Step 3 of 7</p>
        </header>

        <div className="progress-track" aria-hidden>
          <span className="progress-fill progress-step3" />
        </div>

        <div className="step2-title-row">
          <EmbeddedLink href="/step-2" className="back-button" aria-label="Go to Step 2">
            <svg viewBox="0 0 24 24" role="img">
              <path d="M14.6 5.5L8.2 12L14.6 18.5" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.8" />
            </svg>
          </EmbeddedLink>
          <h1>How did you hear about us?</h1>
        </div>

        <p className="step2-subtitle">This helps us understand how merchants discover Optimo VTS.</p>

        {isLoading ? <p className="ai-status-note">Loading current selection...</p> : null}
        {errorMessage ? <p className="ai-error-note">{errorMessage}</p> : null}

        <ul className="goal-list">
          {referralOptions.map((option) => (
            <li key={option.id}>
              <label className="goal-option">
                  <input
                    type="radio"
                    name="referral"
                    value={option.id}
                    checked={selected === option.id}
                    onChange={() => {
                      setSelected(option.id);
                      setErrorMessage("");
                    }}
                  />
                <span className="goal-copy">
                  <strong>{option.label}</strong>
                </span>
              </label>
            </li>
          ))}
        </ul>

        {selected === "other" ? (
          <input
            type="text"
            className="referral-other-input"
            placeholder="Please describe..."
            value={otherDetail}
            onChange={(e) => setOtherDetail(e.target.value)}
            maxLength={200}
          />
        ) : null}

        <div className="step2-footer">
          <p className="support-link support-inline">
            <EmbeddedLink href="/settings/support">Need help? Contact our support team</EmbeddedLink>
          </p>
          <button type="button" className="primary-action" onClick={handleContinue} disabled={isSaving}>
            {isSaving ? "Saving..." : "Continue"}
          </button>
        </div>
      </section>
    </main>
  );
}
