"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { EmbeddedLink } from "../../_components/EmbeddedNavigation";
import PortalSidebar from "../../_components/PortalSidebar";
import {
  getDefaultStoreId,
  recheckDashboardThemeStatus,
  type DashboardThemeStatusRecheckResponse
} from "../../../lib/photoshootApi";

export default function DashboardThemeSetupPage() {
  const storeId = useMemo(() => getDefaultStoreId(), []);

  const [status, setStatus] = useState<DashboardThemeStatusRecheckResponse | null>(null);
  const [isChecking, setIsChecking] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [warningMessage, setWarningMessage] = useState("");

  const checkStatus = useCallback(
    async (showNotDetectedError: boolean) => {
      if (!storeId) {
        return;
      }

      setIsChecking(true);
      setErrorMessage("");
      setWarningMessage("");

      try {
        const recheck = await recheckDashboardThemeStatus({ storeId });
        setStatus(recheck);
        if (showNotDetectedError && !recheck.theme_extension_detected) {
          setErrorMessage("Theme extension is still not detected. Save changes in Shopify theme editor and retry.");
        }
        if (recheck.detection_source === "runtime_flag" && recheck.message) {
          setWarningMessage(recheck.message);
        }
      } catch (error: unknown) {
        const message = error instanceof Error ? error.message : "Failed to verify theme status.";
        setErrorMessage(message);
      } finally {
        setIsChecking(false);
      }
    },
    [storeId]
  );

  useEffect(() => {
    void checkStatus(false);
  }, [checkStatus]);

  useEffect(() => {
    const handleFocus = () => {
      void checkStatus(false);
    };

    window.addEventListener("focus", handleFocus);
    return () => {
      window.removeEventListener("focus", handleFocus);
    };
  }, [checkStatus]);

  const isDetected = Boolean(status?.theme_extension_detected);
  const themeEditorUrl = isDetected
    ? (status?.themes_url || "").trim()
    : (status?.add_to_theme_url || status?.themes_url || "").trim();

  return (
    <main className="portal-shell">
      <PortalSidebar activeMain="overview" />

      <section className="portal-main">
        <header className="portal-main-header">
          <h2>Theme Setup</h2>
          <p>Add Optimo VTS to your Shopify product template.</p>
        </header>

        <section className="welcome-card step5-card">
          <div className="step5-head-row">
            <EmbeddedLink href="/dashboard" className="back-button" aria-label="Back to overview">
              <svg viewBox="0 0 24 24" role="img">
                <path d="M14.6 5.5L8.2 12L14.6 18.5" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.8" />
              </svg>
            </EmbeddedLink>

            {isDetected ? (
              <span className="step5-status-icon step5-status-icon-success" aria-hidden>
                <svg viewBox="0 0 24 24" role="img">
                  <path d="M20 7L10 17L5 12" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.8" />
                </svg>
              </span>
            ) : (
              <span className="step5-status-icon step5-status-icon-error" aria-hidden>
                <svg viewBox="0 0 24 24" role="img">
                  <path d="M7 7L17 17M17 7L7 17" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" />
                </svg>
              </span>
            )}

            <span />
          </div>

          {isDetected ? (
            <>
              <h1 className="step5-title">
                Try-on Button <span className="step5-title-success">detected</span> in theme
              </h1>
              <p className="step5-subtitle">
                Theme block is active.
                <br />
                You can still open Shopify theme editor any time to reposition or edit it.
              </p>
            </>
          ) : (
            <>
              <h1 className="step5-title">
                Try-on Button <span className="step5-title-error">not detected</span> in theme
              </h1>
              <p className="step5-subtitle">
                Add the app block in the Shopify theme editor.
                <br />
                Then save and return here to verify detection.
              </p>
            </>
          )}

          {!storeId ? <p className="ai-error-note">Open the app from Shopify Admin to verify theme extension status.</p> : null}
          {warningMessage ? <p className="ai-error-note">{warningMessage}</p> : null}
          {errorMessage ? <p className="ai-error-note">{errorMessage}</p> : null}

          <div className="step5-primary-wrap">
            {themeEditorUrl ? (
              <a href={themeEditorUrl} target="_blank" rel="noreferrer" className="primary-action step5-primary-button">
                {isDetected ? "Edit Theme" : "+ Add to Theme"}
              </a>
            ) : (
              <button type="button" className="primary-action step5-primary-button" disabled>
                Theme editor unavailable
              </button>
            )}
          </div>

          {isDetected ? (
            <p className="step5-note">
              Click Edit Theme to open Shopify theme editor and adjust widget placement, then save changes there.
            </p>
          ) : (
            <p className="step5-note">
              Click Add to Theme, add the Optimo VTS Widget app block to your product template, then save and return.
            </p>
          )}

          <section className="step5-block">
            <h2 className="step5-section-title">Quick Instructions</h2>
            {isDetected ? (
              <ol className="step5-list">
                <li>Click Edit Theme above</li>
                <li>Adjust widget placement in the product template</li>
                <li>Save changes in Shopify theme editor</li>
                <li>Return here and click Check again if needed</li>
              </ol>
            ) : (
              <ol className="step5-list">
                <li>Click Add to Theme above</li>
                <li>Add the Optimo VTS Widget app block to the product template</li>
                <li>Save changes in Shopify theme editor</li>
                <li>Return here and click Check again</li>
              </ol>
            )}
          </section>

          <div className="step5-actions">
            <button type="button" className="retry-action" onClick={() => checkStatus(true)} disabled={isChecking}>
              {isChecking ? "Checking..." : "Check again"}
            </button>
          </div>
        </section>
      </section>
    </main>
  );
}
