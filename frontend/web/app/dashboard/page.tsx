"use client";

import { useEffect, useMemo, useState } from "react";
import { EmbeddedLink, useEmbeddedRouter } from "../_components/EmbeddedNavigation";
import PortalSidebar from "../_components/PortalSidebar";
import {
  getBillingStatus,
  getBillingUsageSummary,
  getDashboardOverview,
  getDefaultStoreId,
  type BillingStatusResponse,
  type BillingUsageSummaryResponse,
  type DashboardOverviewResponse
} from "../../lib/photoshootApi";

function clampPercent(value: number): number {
  if (!Number.isFinite(value)) {
    return 0;
  }
  return Math.max(0, Math.min(100, value));
}

export default function DashboardPage() {
  const router = useEmbeddedRouter();
  const storeId = useMemo(() => getDefaultStoreId(), []);
  const [overview, setOverview] = useState<DashboardOverviewResponse | null>(null);
  const [billingStatus, setBillingStatus] = useState<BillingStatusResponse | null>(null);
  const [usageSummary, setUsageSummary] = useState<BillingUsageSummaryResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    if (!storeId) {
      return;
    }

    const controller = new AbortController();
    let active = true;

    setIsLoading(true);

    Promise.all([
      getDashboardOverview({ storeId, signal: controller.signal }),
      getBillingStatus({ storeId, signal: controller.signal }),
      getBillingUsageSummary({ storeId, signal: controller.signal })
    ])
      .then(([overviewData, billingData, usageData]) => {
        if (active) {
          if (overviewData.billing_lock_reason || billingData.billing_lock_reason) {
            router.replace("/settings/billing");
            return;
          }
          setOverview(overviewData);
          setBillingStatus(billingData);
          setUsageSummary(usageData);
        }
      })
      .catch((error: unknown) => {
        if (!active || controller.signal.aborted) {
          return;
        }

        const message = error instanceof Error ? error.message : "Failed to load dashboard overview.";
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
  }, [router, storeId]);

  const includedUsed = usageSummary?.consumed_credits ?? 0;
  const includedLimit = usageSummary?.included_credits ?? 0;
  const totalUsed = includedUsed + (usageSummary?.overage_credits ?? 0);
  const usagePercent = usageSummary
    ? clampPercent((includedUsed / Math.max(includedLimit, 1)) * 100)
    : 0;
  const themeEditorUrl = overview?.themes_url?.trim() ?? "";

  return (
    <main className="portal-shell">
      <PortalSidebar activeMain="overview" />

      <section className="portal-main">
        <header className="portal-main-header">
          <h2>Overview</h2>
          <p>Set up Optimo Try-on Button</p>
        </header>

        {!storeId ? <p className="ai-error-note">Open the app from Shopify Admin to load dashboard data.</p> : null}
        {isLoading ? <p className="ai-status-note">Loading dashboard...</p> : null}
        {errorMessage ? <p className="ai-error-note">{errorMessage}</p> : null}

        <section className="portal-overview-card">
          <article className="portal-section">
            <header className="portal-setup-header">
              <span aria-hidden>ⓘ</span>
              <h3>Setup</h3>
            </header>
            <p>
              {overview?.theme_extension_detected
                ? "Theme extension is detected and ready on your store."
                : "Add the Optimo VTS Try-on button to your product pages so customers can start trying on items virtually."}
            </p>
            {themeEditorUrl ? (
              <a href={themeEditorUrl} target="_blank" rel="noreferrer" className="portal-add-theme-button">
                {overview?.theme_extension_detected ? "Open Theme Editor" : "Add to Theme"}
              </a>
            ) : (
              <button type="button" className="portal-add-theme-button portal-add-theme-button-disabled" disabled>
                Theme editor unavailable
              </button>
            )}
          </article>

          <article className="portal-section">
            <div className="portal-usage-header">
              <h3>Usage Analytics</h3>
              <EmbeddedLink href="/analytics">View details</EmbeddedLink>
            </div>
            <div className="portal-usage-row">
              <p>
                {includedUsed} / {includedLimit} included credits
              </p>
              <p>{usagePercent.toFixed(0)}%</p>
            </div>
            <div className="portal-usage-progress" aria-hidden>
              <span style={{ width: `${usagePercent}%` }} />
            </div>
            <p>{totalUsed} total credits consumed this cycle</p>
          </article>

          <article className="portal-section">
            <div className="portal-usage-header">
              <h3>Current Plan</h3>
              <EmbeddedLink href="/settings/billing">Manage billing</EmbeddedLink>
            </div>
            <p>{billingStatus?.plan_name ?? overview?.plan_name ?? "Not available"}</p>
            <p>
              {usageSummary
                ? `${Math.max(usageSummary.remaining_included_credits, 0).toLocaleString()} included credits remain in the current cycle.`
                : "Billing details are shown once store usage data has loaded."}
            </p>
          </article>

          <article className="portal-section">
            <h3>Manage Enabled Products &amp; Collections</h3>
            <p>Scope type: {overview?.scope_type ?? "all"}</p>

            <div className="portal-manage-box">
              <div className="portal-manage-counts">
                <article>
                  <h4>Collections</h4>
                  <p>
                    {overview?.enabled_collections_count ?? 0} <span>Enabled</span>
                  </p>
                </article>
                <article>
                  <h4>Products</h4>
                  <p>
                    {overview?.enabled_products_count ?? 0} <span>Enabled</span>
                  </p>
                </article>
              </div>

              <EmbeddedLink href="/step-4/configured" className="portal-manage-button">
                Manage Products &amp; Collections
              </EmbeddedLink>
            </div>
          </article>
        </section>
      </section>
    </main>
  );
}
