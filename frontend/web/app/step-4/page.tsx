"use client";

import { useMemo, useState } from "react";
import { EmbeddedLink, useEmbeddedRouter } from "../_components/EmbeddedNavigation";
import { getDefaultStoreId, saveWidgetScope } from "../../lib/photoshootApi";

const placementChoices = [
  {
    id: "collections",
    description: "Enable on entire collections. This is the easiest way to manage the button.",
    actionLabel: "Select Collections",
    actionClassName: "select-option select-option-accent",
    href: "/step-4/select-collections"
  },
  {
    id: "products",
    description: "Enable on specific products. Good for testing or limited drops.",
    actionLabel: "Select Products",
    actionClassName: "select-option select-option-neutral",
    href: "/step-4/select-products"
  }
];

export default function StepFourPage() {
  const router = useEmbeddedRouter();
  const storeId = useMemo(() => getDefaultStoreId(), []);
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  const handleContinue = async () => {
    if (!storeId) {
      router.push("/step-4/configured");
      return;
    }

    setIsSaving(true);
    setErrorMessage("");

    try {
      await saveWidgetScope({ storeId, scopeType: "all" });
      router.push("/step-4/configured");
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Failed to save widget scope.";
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
          <p className="step">Step 4 of 7</p>
        </header>

        <div className="progress-track" aria-hidden>
          <span className="progress-fill progress-step4" />
        </div>

        <div className="step4-heading-row">
          <EmbeddedLink href="/step-3" className="back-button" aria-label="Go to previous step">
            <svg viewBox="0 0 24 24" role="img">
              <path
                d="M14.6 5.5L8.2 12L14.6 18.5"
                fill="none"
                stroke="currentColor"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2.8"
              />
            </svg>
          </EmbeddedLink>
          <div className="step4-heading-copy">
            <h1>Enable the Try-On Button</h1>
            <p>Choose where you want the virtual try-on button to appear on your storefront.</p>
          </div>
        </div>

        {errorMessage ? <p className="ai-error-note">{errorMessage}</p> : null}

        <ul className="placement-grid">
          {placementChoices.map((choice) => (
            <li key={choice.id} className="placement-card">
              <p>{choice.description}</p>
              <EmbeddedLink href={choice.href} className={choice.actionClassName}>
                {choice.actionLabel}
              </EmbeddedLink>
            </li>
          ))}
        </ul>

        <div className="step4-actions">
          <EmbeddedLink href="/step-7" className="secondary-action">
            Skip for now
          </EmbeddedLink>
          <button type="button" className="primary-action" onClick={handleContinue} disabled={isSaving}>
            {isSaving ? "Saving..." : "Continue"}
          </button>
        </div>

        <p className="support-link">
          <EmbeddedLink href="/settings/support">Need help? Contact our support team</EmbeddedLink>
        </p>
      </section>
    </main>
  );
}
