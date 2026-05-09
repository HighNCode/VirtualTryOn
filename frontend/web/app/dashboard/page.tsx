"use client";

import { useEffect, useMemo, useState } from "react";
import { motion, type Variants } from "framer-motion";
import { ArrowRight, Box, LayoutGrid, Star } from "lucide-react";
import { EmbeddedLink, useEmbeddedRouter } from "../_components/EmbeddedNavigation";
import PortalSidebar from "../_components/PortalSidebar";
import PortalTopbar from "../_components/PortalTopbar";
import {
  getBillingStatus,
  getBillingUsageSummary,
  getDashboardOverview,
  getDefaultStoreId,
  submitDashboardFeedback,
  type BillingUsageSummaryResponse,
  type DashboardOverviewResponse,
} from "../../lib/photoshootApi";

const FEEDBACK_OPTIONS = [1, 2, 3, 4, 5];

function clampPercent(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(100, value));
}

const cardVariants: Variants = {
  hidden: { opacity: 0, y: 12 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { duration: 0.35, ease: "easeOut", delay: i * 0.06 },
  }),
};

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
    if (!storeId) return;

    const controller = new AbortController();
    let active = true;
    setIsLoading(true);

    Promise.all([
      getDashboardOverview({ storeId, signal: controller.signal }),
      getBillingStatus({ storeId, signal: controller.signal }),
      getBillingUsageSummary({ storeId, signal: controller.signal }),
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
        if (!active || controller.signal.aborted) return;
        const message = error instanceof Error ? error.message : "Failed to load dashboard overview.";
        setErrorMessage(message);
      })
      .finally(() => {
        if (active) setIsLoading(false);
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
          improvement_text: feedbackRating < 5 ? feedbackDetail.trim() : null,
        },
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
    <div style={{ display: "flex", height: "100vh", overflow: "hidden", background: "#f6f4f4" }}>
      <PortalSidebar activeMain="overview" />

      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "auto" }}>
        <PortalTopbar title="Overview" subtitle="Welcome back to Virtual Fit Studio" />

        <div style={{ flex: 1, padding: 24, display: "flex", flexDirection: "column", gap: 16 }}>
          {/* Status messages */}
          {!storeId && (
            <p style={{ margin: 0, fontSize: 13, padding: "8px 16px", borderRadius: 10, background: "#fff1f1", color: "#dc2626" }}>
              Open the app from Shopify Admin to load dashboard data.
            </p>
          )}
          {isLoading && (
            <p style={{ margin: 0, fontSize: 13, padding: "8px 16px", borderRadius: 10, background: "rgba(126,1,117,0.05)", color: "#7E0175" }}>
              Loading dashboard...
            </p>
          )}
          {errorMessage && (
            <p style={{ margin: 0, fontSize: 13, padding: "8px 16px", borderRadius: 10, background: "#fff1f1", color: "#dc2626" }}>
              {errorMessage}
            </p>
          )}
          {feedbackStatusMessage && (
            <p style={{ margin: 0, fontSize: 13, padding: "8px 16px", borderRadius: 10, background: "#dcfce7", color: "#15803d" }}>
              {feedbackStatusMessage}
            </p>
          )}

          {/* Setup Card */}
          <motion.div
            custom={0}
            variants={cardVariants}
            initial="hidden"
            animate="visible"
            style={{ background: "#fff", borderRadius: 14, padding: 20, boxShadow: "0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.04)", border: "1px solid rgba(0,0,0,0.05)" }}
          >
            <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
              <div
                style={{ width: 36, height: 36, borderRadius: 10, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, background: "rgba(126,1,117,0.08)" }}
              >
                <LayoutGrid size={17} style={{ color: "#7E0175" }} />
              </div>
              <div style={{ flex: 1 }}>
                <h3 style={{ margin: "0 0 4px", fontSize: 15, fontWeight: 700, color: "#1a1a1a" }}>
                  {overview?.theme_extension_detected ? "Theme Extension Active" : "Setup"}
                </h3>
                <p style={{ margin: "0 0 12px", fontSize: 14, color: "#6b7280" }}>
                  {overview?.theme_extension_detected
                    ? "Theme extension is detected and ready on your store."
                    : "Add the Optimo VTS Try-on button to your product pages so customers can start trying on items virtually."}
                </p>
                {storeId ? (
                  <EmbeddedLink href="/dashboard/theme-setup">
                    <motion.span
                      whileHover={{ scale: 1.02 }}
                      whileTap={{ scale: 0.98 }}
                      style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "8px 16px", borderRadius: 10, fontSize: 13, fontWeight: 600, color: "#fff", background: "linear-gradient(135deg, #7E0175 0%, #BC174A 55%, #E40206 100%)" }}
                    >
                      {overview?.theme_extension_detected ? "View Theme Status" : "Add to Theme"}
                      <ArrowRight size={14} />
                    </motion.span>
                  </EmbeddedLink>
                ) : (
                  <span
                    style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "8px 16px", borderRadius: 10, fontSize: 13, fontWeight: 600, background: "#f3f4f6", color: "#9ca3af", cursor: "not-allowed" }}
                  >
                    Theme editor unavailable
                  </span>
                )}
              </div>
            </div>
          </motion.div>

          {/* Usage + Rating row */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            {/* Usage Card */}
            <motion.div
              custom={1}
              variants={cardVariants}
              initial="hidden"
              animate="visible"
              style={{ background: "#fff", borderRadius: 14, padding: 20, boxShadow: "0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.04)", border: "1px solid rgba(0,0,0,0.05)" }}
            >
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
                <h3 style={{ margin: 0, fontSize: 15, fontWeight: 700, color: "#1a1a1a" }}>
                  Usage Analytics
                </h3>
                <EmbeddedLink href="/analytics">
                  <span style={{ fontSize: 12, fontWeight: 500, color: "#7E0175" }}>
                    View details →
                  </span>
                </EmbeddedLink>
              </div>
              <p style={{ margin: "0 0 2px", fontSize: 32, fontWeight: 800, lineHeight: 1, color: "#1a1a1a" }}>
                {includedUsed}
              </p>
              <p style={{ margin: "0 0 12px", fontSize: 14, color: "#6b7280" }}>
                of {includedLimit} try-ons used · {totalUsed} total this cycle
              </p>
              <div style={{ width: "100%", borderRadius: 999, overflow: "hidden", height: 8, background: "#f3f4f6" }}>
                <motion.div
                  style={{ height: "100%", borderRadius: 999, background: "linear-gradient(90deg, #7E0175, #E40206)" }}
                  initial={{ width: 0 }}
                  animate={{ width: `${usagePercent}%` }}
                  transition={{ duration: 0.8, ease: "easeOut" }}
                />
              </div>
              <p style={{ margin: "6px 0 0", fontSize: 12, color: "#9ca3af" }}>
                {usagePercent.toFixed(0)}% of plan used
              </p>
            </motion.div>

            {/* Rating Card */}
            <motion.div
              custom={2}
              variants={cardVariants}
              initial="hidden"
              animate="visible"
              style={{ background: "#fff", borderRadius: 14, padding: 20, boxShadow: "0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.04)", border: "1px solid rgba(0,0,0,0.05)" }}
            >
              {!feedbackSubmitted ? (
                <>
                  <h3 style={{ margin: "0 0 2px", fontSize: 15, fontWeight: 700, color: "#1a1a1a" }}>
                    Merchant Feedback
                  </h3>
                  <p style={{ margin: "0 0 12px", fontSize: 14, color: "#6b7280" }}>
                    Rate your experience with Optimo VTS.
                  </p>
                  <div style={{ display: "flex", gap: 4, marginBottom: 12 }} role="radiogroup" aria-label="Feedback rating">
                    {FEEDBACK_OPTIONS.map((value) => (
                      <motion.button
                        key={value}
                        type="button"
                        whileHover={{ scale: 1.2 }}
                        whileTap={{ scale: 0.95 }}
                        onClick={() => setFeedbackRating(value)}
                        aria-pressed={feedbackRating === value}
                        aria-label={`Rate ${value} out of 5`}
                        style={{ padding: 4, border: "none", background: "transparent", cursor: "pointer" }}
                      >
                        <Star
                          size={24}
                          strokeWidth={1.5}
                          fill={feedbackRating !== null && value <= feedbackRating ? "url(#starGrad)" : "none"}
                          stroke={feedbackRating !== null && value <= feedbackRating ? "#BC174A" : "#d1d5db"}
                        />
                      </motion.button>
                    ))}
                    <svg width="0" height="0" aria-hidden>
                      <defs>
                        <linearGradient id="starGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                          <stop offset="0%" stopColor="#7E0175" />
                          <stop offset="100%" stopColor="#E40206" />
                        </linearGradient>
                      </defs>
                    </svg>
                  </div>

                  {feedbackRating !== null && feedbackRating < 5 && (
                    <div style={{ marginBottom: 12 }}>
                      <label style={{ display: "block", fontSize: 12, fontWeight: 500, marginBottom: 4, color: "#6b7280" }}>
                        What can be improved?
                      </label>
                      <textarea
                        value={feedbackDetail}
                        onChange={(e) => setFeedbackDetail(e.target.value)}
                        rows={3}
                        placeholder="Share details..."
                        style={{
                          width: "100%", borderRadius: 10, padding: "8px 12px", fontSize: 13, resize: "none",
                          border: "1.5px solid #e5e5e5", color: "#1a1a1a", outline: "none", fontFamily: "inherit", boxSizing: "border-box",
                        }}
                        onFocus={(e) => {
                          e.currentTarget.style.borderColor = "#7E0175";
                          e.currentTarget.style.boxShadow = "0 0 0 3px rgba(126,1,117,0.1)";
                        }}
                        onBlur={(e) => {
                          e.currentTarget.style.borderColor = "#e5e5e5";
                          e.currentTarget.style.boxShadow = "none";
                        }}
                      />
                    </div>
                  )}

                  {feedbackErrorMessage && (
                    <p style={{ margin: "0 0 8px", fontSize: 12, color: "#dc2626" }}>
                      {feedbackErrorMessage}
                    </p>
                  )}

                  <motion.button
                    type="button"
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={handleFeedbackSubmit}
                    disabled={isFeedbackSubmitting}
                    style={{
                      padding: "8px 16px", borderRadius: 10, fontSize: 13, fontWeight: 600, color: "#fff",
                      background: "linear-gradient(135deg, #7E0175 0%, #BC174A 55%, #E40206 100%)",
                      opacity: isFeedbackSubmitting ? 0.7 : 1,
                      cursor: isFeedbackSubmitting ? "not-allowed" : "pointer",
                      border: "none",
                    }}
                  >
                    {isFeedbackSubmitting ? "Submitting..." : "Submit Feedback"}
                  </motion.button>
                </>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100%", gap: 8, textAlign: "center", padding: "16px 0" }}>
                  <div
                    style={{ width: 40, height: 40, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", background: "#dcfce7" }}
                  >
                    <Star size={18} style={{ color: "#15803d" }} fill="#15803d" />
                  </div>
                  <p style={{ margin: 0, fontSize: 14, fontWeight: 600, color: "#15803d" }}>
                    Thanks for the feedback!
                  </p>
                </div>
              )}
            </motion.div>
          </div>

          {/* Manage Products Card */}
          <motion.div
            custom={3}
            variants={cardVariants}
            initial="hidden"
            animate="visible"
            style={{ background: "#fff", borderRadius: 14, padding: 20, boxShadow: "0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.04)", border: "1px solid rgba(0,0,0,0.05)" }}
          >
            <h3 style={{ margin: "0 0 4px", fontSize: 15, fontWeight: 700, color: "#1a1a1a" }}>
              Manage Enabled Products &amp; Collections
            </h3>
            <p style={{ margin: "0 0 16px", fontSize: 14, color: "#6b7280" }}>
              Control which products and collections have the virtual try-on button enabled.
            </p>

            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
              <div
                style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 12px", borderRadius: 11, background: "rgba(126,1,117,0.05)", border: "1px solid rgba(126,1,117,0.12)" }}
              >
                <Box size={15} style={{ color: "#7E0175" }} />
                <span style={{ fontSize: 14, fontWeight: 500, color: "#1a1a1a" }}>
                  {collectionsSummary} Collections
                </span>
                <span
                  style={{ fontSize: 11, fontWeight: 500, padding: "2px 8px", borderRadius: 999, background: "#dcfce7", color: "#15803d" }}
                >
                  Enabled
                </span>
              </div>

              <div
                style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 12px", borderRadius: 11, background: "rgba(126,1,117,0.05)", border: "1px solid rgba(126,1,117,0.12)" }}
              >
                <LayoutGrid size={15} style={{ color: "#7E0175" }} />
                <span style={{ fontSize: 14, fontWeight: 500, color: "#1a1a1a" }}>
                  {productsSummary} Products
                </span>
                <span
                  style={{ fontSize: 11, fontWeight: 500, padding: "2px 8px", borderRadius: 999, background: "#dcfce7", color: "#15803d" }}
                >
                  Enabled
                </span>
              </div>
            </div>

            <EmbeddedLink href="/dashboard/manage-scope">
              <motion.span
                whileHover={{ scale: 1.01 }}
                whileTap={{ scale: 0.98 }}
                style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "8px 16px", borderRadius: 10, fontSize: 13, fontWeight: 600, background: "#ffffff", border: "1.5px solid #7E0175", color: "#7E0175" }}
              >
                Manage Products &amp; Collections
              </motion.span>
            </EmbeddedLink>
          </motion.div>
        </div>
      </div>
    </div>
  );
}
