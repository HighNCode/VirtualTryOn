"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { EmbeddedLink, useEmbeddedRouter } from "../../_components/EmbeddedNavigation";
import { getDefaultStoreId, getThemeStatus, updateThemeStatus } from "../../../lib/photoshootApi";

export default function StepFiveNotDetectedPage() {
  const router = useEmbeddedRouter();
  const storeId = useMemo(() => getDefaultStoreId(), []);

  const [themesUrl, setThemesUrl] = useState("");
  const [isChecking, setIsChecking] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  const checkStatus = useCallback(
    async (markDetected: boolean) => {
      if (!storeId) {
        return;
      }

      setIsChecking(true);
      setErrorMessage("");

      try {
        const status = await getThemeStatus({ storeId });
        setThemesUrl(status.themes_url);

        if (status.theme_extension_detected) {
          if (markDetected) {
            await updateThemeStatus({ storeId, detected: true });
          }

          router.push("/step-5/detected");
          return;
        }

        if (markDetected) {
          setErrorMessage("Theme extension is still not detected. Save changes in Shopify theme editor and retry.");
        }
      } catch (error: unknown) {
        const message = error instanceof Error ? error.message : "Failed to verify theme status.";
        setErrorMessage(message);
      } finally {
        setIsChecking(false);
      }
    },
    [router, storeId]
  );

  useEffect(() => {
    void checkStatus(false);
  }, [checkStatus]);

  return (
    <main className="shell">
      <section className="welcome-card step5-card">
        <header className="topline">
          <p className="screen-title">Welcome to Optimo VTS</p>
          <p className="step">Step 5 of 7</p>
        </header>

        <div className="progress-track" aria-hidden>
          <span className="progress-fill progress-step5" />
        </div>

        <div className="step5-head-row">
          <EmbeddedLink href="/step-4/configured" className="back-button" aria-label="Go to previous screen">
            <svg viewBox="0 0 24 24" role="img">
              <path d="M14.6 5.5L8.2 12L14.6 18.5" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.8" />
            </svg>
          </EmbeddedLink>

          <span className="step5-status-icon step5-status-icon-error" aria-hidden>
            <svg viewBox="0 0 24 24" role="img">
              <path d="M7 7L17 17M17 7L7 17" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" />
            </svg>
          </span>

          <span />
        </div>

        <h1 className="step5-title">
          Try-on Button <span className="step5-title-error">not detected</span> in theme
        </h1>
        <p className="step5-subtitle">
          To show the virtual try-on button on
          <br />
          your storefront, add it to your theme.
        </p>

        {!storeId ? <p className="ai-error-note">Open the app from Shopify Admin to verify theme extension status.</p> : null}
        {errorMessage ? <p className="ai-error-note">{errorMessage}</p> : null}

        <div className="step5-primary-wrap">
          {themesUrl ? (
            <a href={themesUrl} target="_blank" rel="noreferrer" className="primary-action step5-primary-button">
              + Add to Theme
            </a>
          ) : (
            <button type="button" className="primary-action step5-primary-button" disabled>
              Theme editor unavailable
            </button>
          )}
        </div>

        <p className="step5-note">
          Click Add to Theme to open the Shopify theme editor, then add the Optimo VTS widget block to product pages.
        </p>

        <section className="step5-block">
          <h2 className="step5-section-title">
            Watch <span>Tutorial</span>
          </h2>

          <div className="step5-video-mock" aria-hidden>
            <div className="step5-video-bar" />
            <div className="step5-video-panel" />
            <div className="step5-video-avatar" />
          </div>
        </section>

        <section className="step5-block">
          <h2 className="step5-section-title">Quick Instructions</h2>
          <ol className="step5-list">
            <li>Click Add to Theme above</li>
            <li>In the theme editor, add the Optimo VTS Widget app block to the product template</li>
            <li>Click Save in the Shopify editor</li>
            <li>Return here and click Retry</li>
          </ol>
        </section>

        <div className="step5-actions">
          <EmbeddedLink href="/step-7" className="secondary-action">
            Skip for now
          </EmbeddedLink>
          <button type="button" className="retry-action" onClick={() => checkStatus(true)} disabled={isChecking}>
            {isChecking ? "Checking..." : "Retry"}
          </button>
        </div>

        <p className="support-link">
          <EmbeddedLink href="/settings/support">Need help? Contact our support team</EmbeddedLink>
        </p>
      </section>
    </main>
  );
}
