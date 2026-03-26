"use client";

import { useEffect, useMemo, useState } from "react";
import { EmbeddedLink, useEmbeddedRouter } from "../../_components/EmbeddedNavigation";
import { getDefaultStoreId, getThemeStatus, updateThemeStatus } from "../../../lib/photoshootApi";

export default function StepFiveDetectedPage() {
  const router = useEmbeddedRouter();
  const storeId = useMemo(() => getDefaultStoreId(), []);

  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    if (!storeId) {
      return;
    }

    const controller = new AbortController();
    let active = true;

    getThemeStatus({ storeId, signal: controller.signal })
      .then((status) => {
        if (!active) {
          return;
        }

        if (!status.theme_extension_detected) {
          router.replace("/step-5/not-detected");
        }
      })
      .catch(() => {
        // Let the user continue even if pre-check fails.
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [storeId, router]);

  const enableTryOn = async () => {
    if (!storeId) {
      router.push("/step-7");
      return;
    }

    setIsSaving(true);
    setErrorMessage("");

    try {
      await updateThemeStatus({ storeId, detected: true });
      router.push("/step-7");
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Failed to save theme status.";
      setErrorMessage(message);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <main className="shell">
      <section className="welcome-card step5-card step5-detected-card">
        <header className="topline">
          <p className="screen-title">Welcome to Optimo VTS</p>
          <p className="step">Step 5 of 7</p>
        </header>

        <div className="progress-track" aria-hidden>
          <span className="progress-fill progress-step5" />
        </div>

        <div className="step5-head-row">
          <EmbeddedLink href="/step-5/not-detected" className="back-button" aria-label="Go to previous screen">
            <svg viewBox="0 0 24 24" role="img">
              <path d="M14.6 5.5L8.2 12L14.6 18.5" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.8" />
            </svg>
          </EmbeddedLink>

          <span className="step5-status-icon step5-status-icon-success" aria-hidden>
            <svg viewBox="0 0 24 24" role="img">
              <path d="M20 7L10 17L5 12" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.8" />
            </svg>
          </span>

          <span />
        </div>

        <h1 className="step5-title">
          Try-on Button <span className="step5-title-success">detected</span> in theme
        </h1>
        <p className="step5-subtitle">
          The theme extension is active.
          <br />
          Continue to enable customer try-on experience.
        </p>

        {!storeId ? <p className="ai-error-note">Open the app from Shopify Admin to persist onboarding progress.</p> : null}
        {errorMessage ? <p className="ai-error-note">{errorMessage}</p> : null}

        <div className="step5-primary-wrap step5-primary-wrap-detected">
          <button type="button" className="primary-action step5-primary-button step5-detected-button" onClick={enableTryOn} disabled={isSaving}>
            {isSaving ? "Saving..." : "Enable Try-on"}
          </button>
        </div>
      </section>
    </main>
  );
}
