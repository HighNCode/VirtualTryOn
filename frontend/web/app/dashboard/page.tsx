"use client";

import { useEffect, useMemo, useState } from "react";
import { EmbeddedLink, useEmbeddedRouter } from "../_components/EmbeddedNavigation";
import PortalSidebar from "../_components/PortalSidebar";
import {
  getBillingStatus,
  getBillingUsageSummary,
  getDashboardOverview,
  getDefaultStoreId,
  submitDashboardFeedback,
  type BillingUsageSummaryResponse,
  type DashboardOverviewResponse
} from "../../lib/photoshootApi";

const FEEDBACK_OPTIONS = Array.from({ length: 10 }, (_, index) => (index + 1) / 2);

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
  const [usageSummary, setUsageSummary] = useState<BillingUsageSummaryResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  const [feedbackSubmitted, setFeedbackSubmitted] = useState(false);
  const [feedbackRating, setFeedbackRating] = useState<number | null>(null);
  const [feedbackDetail, setFeedbackDetail] = useState("");
  const [isFeedbackSubmitting, setIsFeedbackSubmitting] = useState(false);
  const [feedbackStatusMessage, setFeedbackStatusMessage] = useState("");
  const [feedbackErrorMessage, setFeedbackErrorMessage] = useState("");

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
          setUsageSummary(usageData);
          setFeedbackSubmitted(Boolean(overviewData.feedback_submitted));
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
  const isAllScope = overview?.scope_type === "all";
  const collectionsSummary = isAllScope ? "All" : String(overview?.enabled_collections_count ?? 0);
  const productsSummary = isAllScope ? "All" : String(overview?.enabled_products_count ?? 0);

  const handleFeedbackSubmit = async () => {
    if (!storeId) {
      setFeedbackErrorMessage("Open the app from Shopify Admin before submitting feedback.");
      return;
    }
    if (feedbackRating === null) {
      setFeedbackErrorMessage("Select a rating before submitting feedback.");
      return;
    }
    if (feedbackRating < 5 && !feedbackDetail.trim()) {
      setFeedbackErrorMessage("Tell us what can be improved for ratings below 5.0.");
      return;
    }

    setIsFeedbackSubmitting(true);
    setFeedbackErrorMessage("");
    setFeedbackStatusMessage("");

    try {
      await submitDashboardFeedback({
        storeId,
        payload: {
          rating: feedbackRating,
          improvement_text: feedbackRating < 5 ? feedbackDetail.trim() : null
        }
      });

      setFeedbackSubmitted(true);
      setFeedbackStatusMessage("Thanks for the feedback.");
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Failed to submit feedback.";
      setFeedbackErrorMessage(message);
    } finally {
      setIsFeedbackSubmitting(false);
    }
  };

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
        {feedbackStatusMessage ? <p className="ai-status-note">{feedbackStatusMessage}</p> : null}

        <section className="portal-overview-card">
          <article className="portal-section">
            <header className="portal-setup-header">
              <span aria-hidden>i</span>
              <h3>Setup</h3>
            </header>
            <p>
              {overview?.theme_extension_detected
                ? "Theme extension is detected and ready on your store."
                : "Add the Optimo VTS Try-on button to your product pages so customers can start trying on items virtually."}
            </p>
            {storeId ? (
              <EmbeddedLink href="/dashboard/theme-setup" className="portal-add-theme-button">
                {overview?.theme_extension_detected ? "View Theme Status" : "Add to Theme"}
              </EmbeddedLink>
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

          {!feedbackSubmitted ? (
            <article className="portal-section">
              <h3>Merchant Feedback</h3>
              <p>Rate your experience with Optimo VTS.</p>

              <div className="portal-feedback-options" role="radiogroup" aria-label="Feedback rating">
                {FEEDBACK_OPTIONS.map((value) => (
                  <button
                    key={value}
                    type="button"
                    className={`portal-feedback-option${feedbackRating === value ? " is-active" : ""}`}
                    onClick={() => setFeedbackRating(value)}
                    aria-pressed={feedbackRating === value}
                  >
                    {value.toFixed(1)} ★
                  </button>
                ))}
              </div>

              {feedbackRating !== null && feedbackRating < 5 ? (
                <div className="portal-feedback-detail">
                  <label htmlFor="feedback-detail">What can be improved?</label>
                  <textarea
                    id="feedback-detail"
                    value={feedbackDetail}
                    onChange={(event) => setFeedbackDetail(event.target.value)}
                    rows={3}
                    placeholder="Share details that would improve your experience."
                  />
                </div>
              ) : null}

              {feedbackErrorMessage ? <p className="ai-error-note">{feedbackErrorMessage}</p> : null}

              <button
                type="button"
                className="portal-feedback-submit"
                onClick={handleFeedbackSubmit}
                disabled={isFeedbackSubmitting}
              >
                {isFeedbackSubmitting ? "Submitting..." : "Submit Feedback"}
              </button>
            </article>
          ) : null}

          <article className="portal-section">
            <h3>Manage Enabled Products &amp; Collections</h3>

            <div className="portal-manage-box">
              <div className="portal-manage-counts">
                <article>
                  <h4>Collections</h4>
                  <p>
                    {collectionsSummary} <span>Enabled</span>
                  </p>
                </article>
                <article>
                  <h4>Products</h4>
                  <p>
                    {productsSummary} <span>Enabled</span>
                  </p>
                </article>
              </div>

              <EmbeddedLink href="/dashboard/manage-scope" className="portal-manage-button">
                Manage Products &amp; Collections
              </EmbeddedLink>
            </div>
          </article>
        </section>
      </section>
    </main>
  );
}
