"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Check } from "lucide-react";
import PortalSidebar from "../../_components/PortalSidebar";
import PortalTopbar from "../../_components/PortalTopbar";
import SubTabNav from "../../_components/SubTabNav";
import {
  activateBillingPlan,
  createSubscription,
  getBillingPlans,
  getBillingStatus,
  getBillingUsageSummary,
  getDefaultStoreId,
  type BillingStatusResponse,
  type BillingUsageSummaryResponse,
  type PlanConfigResponse,
} from "../../../lib/photoshootApi";

type BillingCycle = "monthly" | "annual";

function formatMoney(value: number | null | undefined, currencyCode: string): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "-";
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: currencyCode,
    maximumFractionDigits: value % 1 === 0 ? 0 : 2,
  }).format(value);
}

const PLAN_LABEL_OVERRIDES: Record<string, string> = {
  free_plan: "Free Plan",
  free_trial: "Free Trial",
  founding_trial: "Founding Trial",
};

function formatPlanLabel(value: string | null | undefined): string {
  if (!value) return "-";
  const normalized = value.trim().toLowerCase();
  if (!normalized) return "-";
  const override = PLAN_LABEL_OVERRIDES[normalized];
  if (override) return override;
  return normalized
    .split(/[_-]+/g)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

const settingsTabs = [
  { href: "/settings", label: "Custom" },
  { href: "/settings/privacy", label: "Privacy" },
  { href: "/settings/billing", label: "Billing" },
  { href: "/settings/support", label: "Support" },
];

export default function SettingsBillingPage() {
  const storeId = useMemo(() => getDefaultStoreId(), []);

  const [billingCycle, setBillingCycle] = useState<BillingCycle>("monthly");
  const [plans, setPlans] = useState<PlanConfigResponse[]>([]);
  const [billingStatus, setBillingStatus] = useState<BillingStatusResponse | null>(null);
  const [usageSummary, setUsageSummary] = useState<BillingUsageSummaryResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [pendingPlanId, setPendingPlanId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [hasBillingReturn, setHasBillingReturn] = useState(false);

  const loadBillingData = useCallback(
    async (signal?: AbortSignal) => {
      if (!storeId) return;
      const [plansResult, statusResult, usageResult] = await Promise.all([
        getBillingPlans({ storeId, signal }),
        getBillingStatus({ storeId, signal }),
        getBillingUsageSummary({ storeId, signal }),
      ]);
      setPlans(plansResult.plans.filter((p) => p.is_active));
      setBillingStatus(statusResult);
      setUsageSummary(usageResult);
      if (statusResult.billing_interval === "monthly" || statusResult.billing_interval === "annual") {
        setBillingCycle(statusResult.billing_interval);
      }
    },
    [storeId]
  );

  useEffect(() => {
    setHasBillingReturn(
      typeof window !== "undefined" && new URLSearchParams(window.location.search).has("charge_id")
    );
  }, []);

  useEffect(() => {
    if (!hasBillingReturn || !storeId) return;
    const params = new URLSearchParams(window.location.search);
    const planName = params.get("plan");
    const interval = params.get("interval") as BillingCycle | null;
    const chargeId = params.get("charge_id");
    if (!planName || !interval) return;

    const shopifySubscriptionId = chargeId
      ? `gid://shopify/AppSubscription/${chargeId}`
      : (window.localStorage.getItem("pending_subscription_id") ?? "");
    if (!shopifySubscriptionId) return;

    window.localStorage.removeItem("pending_subscription_id");
    activateBillingPlan({ storeId, planName, billingInterval: interval, shopifySubscriptionId })
      .then(() => loadBillingData())
      .catch(() => {});
  }, [hasBillingReturn, loadBillingData, storeId]);

  useEffect(() => {
    if (!storeId) return;
    const controller = new AbortController();
    let active = true;
    setIsLoading(true);
    setErrorMessage("");

    loadBillingData(controller.signal)
      .catch((error: unknown) => {
        if (!active || controller.signal.aborted) return;
        setErrorMessage(error instanceof Error ? error.message : "Failed to load billing data.");
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [loadBillingData, storeId]);

  const currentPlan = useMemo(() => {
    if (!billingStatus) return plans.find((p) => p.is_current) ?? null;
    return plans.find((p) => p.name === billingStatus.plan_name) ?? plans.find((p) => p.is_current) ?? null;
  }, [billingStatus, plans]);

  const businessPlan = useMemo(() => {
    const nonCurrentPlans = plans.filter((plan) => plan.name !== billingStatus?.plan_name);
    return nonCurrentPlans.find((plan) => /business/i.test(plan.display_name || plan.name)) ?? nonCurrentPlans[0] ?? plans[0] ?? null;
  }, [billingStatus?.plan_name, plans]);

  const displayCurrentPlanName = useMemo(() => {
    if (currentPlan?.display_name) return currentPlan.display_name;
    if (!billingStatus?.plan_name) return "No active subscription";
    return formatPlanLabel(billingStatus.plan_name);
  }, [billingStatus?.plan_name, currentPlan?.display_name]);

  const usageUsedIncluded = usageSummary?.consumed_credits ?? 0;
  const usageUsedTotal = (usageSummary?.consumed_credits ?? 0) + (usageSummary?.overage_credits ?? 0);
  const usageLimit = usageSummary?.included_credits ?? 0;
  const usagePercent = usageLimit > 0 ? Math.min(100, (usageUsedIncluded / usageLimit) * 100) : 0;

  const currentMonthlyPrice = currentPlan
    ? billingStatus?.billing_interval === "annual"
      ? currentPlan.price_annual_per_month
      : currentPlan.price_monthly
    : null;
  const currentIntervalLabel = billingStatus?.billing_interval === "annual" ? "month, billed annually" : "month";
  const overagePrice = currentPlan?.overage_usd_per_tryon ?? businessPlan?.overage_usd_per_tryon ?? 0.01;
  const businessPrice = businessPlan
    ? billingCycle === "annual"
      ? businessPlan.price_annual_per_month
      : businessPlan.price_monthly
    : null;
  const businessCredits = businessPlan
    ? billingCycle === "annual"
      ? businessPlan.credits_annual
      : businessPlan.credits_monthly
    : null;
  const statusLabel = billingStatus?.subscription_status ?? (billingStatus?.plan_name ? "Active" : "Not connected");

  const handlePlanChange = async (plan: PlanConfigResponse) => {
    if (!storeId) {
      setErrorMessage("Open the app from Shopify Admin to manage billing.");
      return;
    }
    if (plan.name === billingStatus?.plan_name && billingStatus?.billing_interval === billingCycle) return;
    setPendingPlanId(plan.id);
    setErrorMessage("");

    try {
      const returnUrl = new URL("/settings/billing", window.location.origin);
      returnUrl.searchParams.set("plan", plan.name);
      returnUrl.searchParams.set("interval", billingCycle);
      returnUrl.searchParams.set("shop", storeId);
      const result = await createSubscription({
        storeId,
        planName: plan.name,
        billingInterval: billingCycle,
        returnUrl: returnUrl.toString(),
      });
      if (result.shopify_subscription_id) {
        window.localStorage.setItem("pending_subscription_id", result.shopify_subscription_id);
      }
      window.open(result.confirmation_url, "_top");
    } catch (error: unknown) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to create Shopify subscription.");
      setPendingPlanId(null);
    }
  };

  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden", background: "#f6f4f4" }}>
      <PortalSidebar activeMain="settings" activeSettings="billing" />

      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "auto" }}>
        <PortalTopbar title="Settings" subtitle="Manage your plan and billing" />
        <SubTabNav tabs={settingsTabs} />

        <div style={{ flex: 1, padding: "24px 28px", display: "flex", flexDirection: "column", gap: 20 }}>
          {hasBillingReturn && billingStatus?.shopify_subscription_id && (
            <p style={{ margin: 0, fontSize: 13, padding: "8px 16px", borderRadius: 10, background: "rgba(126,1,117,0.05)", color: "#7E0175" }}>
              Shopify redirected back after charge approval. The latest subscription is shown below.
            </p>
          )}
          {isLoading && (
            <p style={{ margin: 0, fontSize: 13, padding: "8px 16px", borderRadius: 10, background: "rgba(126,1,117,0.05)", color: "#7E0175" }}>
              Loading billing...
            </p>
          )}
          {errorMessage && (
            <p style={{ margin: 0, fontSize: 13, padding: "8px 16px", borderRadius: 10, background: "#fff1f1", color: "#dc2626" }}>
              {errorMessage}
            </p>
          )}
          {billingStatus?.billing_lock_reason && (
            <p style={{ margin: 0, fontSize: 13, padding: "8px 16px", borderRadius: 10, background: "#fff1f1", color: "#dc2626" }}>
              Trial ended. Select a plan to re-enable widget and customer try-ons.
            </p>
          )}

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
            <motion.section
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.28 }}
              style={{ position: "relative", minHeight: 276, background: "#fff", borderRadius: 12, padding: 20, boxShadow: "0 1px 3px rgba(0,0,0,0.06)", border: "1px solid rgba(0,0,0,0.06)" }}
            >
              <span style={{ fontSize: 12, letterSpacing: 1, textTransform: "uppercase", color: "#5f6b85" }}>
                Current Plan
              </span>
              <span style={{ position: "absolute", top: 18, right: 20, padding: "3px 10px", borderRadius: 999, fontSize: 12, fontWeight: 700, color: "#fff", background: "#b0006f" }}>
                {statusLabel}
              </span>
              <h3 style={{ margin: "8px 0 2px", fontSize: 22, fontWeight: 800, color: "#111827" }}>
                {displayCurrentPlanName}
              </h3>
              <p style={{ margin: 0, fontSize: 14, color: "#5f6b85" }}>
                {formatMoney(currentMonthlyPrice, "USD")} / {currentIntervalLabel}
              </p>

              <div style={{ marginTop: 22 }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 7 }}>
                  <span style={{ fontSize: 14, color: "#5f6b85" }}>Usage</span>
                  <span style={{ fontSize: 14, fontWeight: 700, color: "#111827" }}>
                    {usageUsedIncluded.toLocaleString()}/{Math.max(usageLimit, 1).toLocaleString()}
                  </span>
                </div>
                <div style={{ height: 8, borderRadius: 999, overflow: "hidden", background: "#f0f0f0" }}>
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${usagePercent}%` }}
                    transition={{ duration: 0.75, ease: "easeOut" }}
                    style={{ height: "100%", borderRadius: 999, background: "linear-gradient(90deg, #8d007c 0%, #E40206 100%)" }}
                  />
                </div>
              </div>

              <div style={{ marginTop: 28, display: "flex", flexDirection: "column", gap: 7, fontSize: 14, color: "#5f6b85" }}>
                <p style={{ margin: 0 }}>
                  <strong style={{ color: "#111827" }}>{formatMoney(overagePrice, "USD")}</strong> per overage try-on
                </p>
                <p style={{ margin: 0 }}>
                  <strong style={{ color: "#111827" }}>Consumed Credits:</strong> {usageUsedTotal.toLocaleString()} this cycle
                </p>
                <p style={{ margin: 0 }}>
                  <strong style={{ color: "#111827" }}>Current Overage:</strong>{" "}
                  <strong style={{ color: "#b0006f" }}>{formatMoney(usageSummary?.overage_amount_usd ?? 0, "USD")}</strong>
                </p>
              </div>

              <button
                type="button"
                onClick={() => businessPlan && handlePlanChange(businessPlan)}
                disabled={!businessPlan || pendingPlanId === businessPlan.id}
                style={{
                  marginTop: 18,
                  padding: 0,
                  border: "none",
                  background: "transparent",
                  color: "#9a007f",
                  fontSize: 14,
                  fontWeight: 700,
                  cursor: businessPlan ? "pointer" : "not-allowed",
                }}
              >
                {pendingPlanId === businessPlan?.id ? "Redirecting..." : "Change Plan ->"}
              </button>
            </motion.section>

            <motion.section
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.28, delay: 0.05 }}
              style={{ minHeight: 276, background: "#f4edf3", borderRadius: 12, padding: 20, border: "1px solid rgba(126,1,117,0.16)" }}
            >
              <span style={{ fontSize: 12, letterSpacing: 1, textTransform: "uppercase", color: "#5f6b85" }}>
                {businessPlan ? `Upgrade to ${businessPlan.display_name}` : "Available Plans"}
              </span>
              <p style={{ margin: "18px 0 18px", fontSize: 14, color: "#5f6b85" }}>
                <strong style={{ fontSize: 24, color: "#111827" }}>{formatMoney(businessPrice, "USD")}</strong> / month
              </p>
              <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: 12 }}>
                {businessPlan && (
                  <li style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 14, color: "#111827" }}>
                    <Check size={14} style={{ color: "#15803d", flexShrink: 0 }} />
                    {businessCredits?.toLocaleString()} included credits
                  </li>
                )}
                {businessPlan && (
                  <li style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 14, color: "#111827" }}>
                    <Check size={14} style={{ color: "#15803d", flexShrink: 0 }} />
                    {formatMoney(businessPlan.overage_usd_per_tryon, "USD")} per overage try-on
                  </li>
                )}
                {businessPlan?.features.map((feature) => (
                  <li key={feature} style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 14, color: "#111827" }}>
                    <Check size={14} style={{ color: "#15803d", flexShrink: 0 }} />
                    {feature}
                  </li>
                ))}
                {!businessPlan && (
                  <li style={{ fontSize: 14, color: "#5f6b85" }}>No active upgrade plan is configured.</li>
                )}
              </ul>
              <button
                type="button"
                onClick={() => businessPlan && handlePlanChange(businessPlan)}
                disabled={!businessPlan || pendingPlanId === businessPlan.id}
                style={{
                  width: "100%",
                  marginTop: 22,
                  padding: "14px 18px",
                  borderRadius: 9,
                  border: "none",
                  color: "#fff",
                  fontSize: 15,
                  fontWeight: 800,
                  cursor: businessPlan ? "pointer" : "not-allowed",
                  opacity: pendingPlanId === businessPlan?.id ? 0.7 : 1,
                  background: "linear-gradient(90deg, #8d007c 0%, #E40206 100%)",
                }}
              >
                {pendingPlanId === businessPlan?.id ? "Redirecting..." : "Upgrade Now"}
              </button>
            </motion.section>
          </div>

          <section style={{ background: "#fff", borderRadius: 12, padding: "22px 20px", boxShadow: "0 1px 3px rgba(0,0,0,0.06)", border: "1px solid rgba(0,0,0,0.06)" }}>
            <h3 style={{ margin: "0 0 16px", fontSize: 15, fontWeight: 800, color: "#111827" }}>
              Subscription Details
            </h3>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))", gap: 14 }}>
              {[
                { label: "Shopify Subscription", value: billingStatus?.shopify_subscription_id ?? "Not connected" },
                { label: "Billing Interval", value: billingStatus?.billing_interval ?? "-" },
                { label: "Current Period End", value: billingStatus?.current_period_end ? new Date(billingStatus.current_period_end).toLocaleString() : "-" },
                { label: "Test Subscription", value: billingStatus?.is_test_subscription === null || billingStatus?.is_test_subscription === undefined ? "-" : billingStatus.is_test_subscription ? "Yes" : "No" },
              ].map((item) => (
                <div key={item.label} style={{ padding: 14, borderRadius: 10, background: "#fafafa", border: "1px solid #eef0f3", minWidth: 0 }}>
                  <p style={{ margin: "0 0 6px", fontSize: 12, color: "#5f6b85" }}>{item.label}</p>
                  <p style={{ margin: 0, fontSize: 13, fontWeight: 700, color: "#111827", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {item.value}
                  </p>
                </div>
              ))}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
