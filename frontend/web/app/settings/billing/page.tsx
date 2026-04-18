"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import PortalSidebar from "../../_components/PortalSidebar";
import {
  activateBillingPlan,
  cancelSubscription,
  createSubscription,
  getBillingPlans,
  getBillingStatus,
  getBillingUsageSummary,
  getDefaultStoreId,
  type BillingStatusResponse,
  type BillingUsageSummaryResponse,
  type PlanConfigResponse
} from "../../../lib/photoshootApi";

type BillingCycle = "monthly" | "annual";

function formatDateTime(value: string | null): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function formatMoney(value: number | null, currencyCode: string): string {
  if (value === null) return "-";
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: currencyCode,
    maximumFractionDigits: value % 1 === 0 ? 0 : 2
  }).format(value);
}

export default function SettingsBillingPage() {
  const storeId = useMemo(() => getDefaultStoreId(), []);

  const [billingCycle, setBillingCycle] = useState<BillingCycle>("monthly");
  const [plans, setPlans] = useState<PlanConfigResponse[]>([]);
  const [billingStatus, setBillingStatus] = useState<BillingStatusResponse | null>(null);
  const [usageSummary, setUsageSummary] = useState<BillingUsageSummaryResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [pendingPlanId, setPendingPlanId] = useState<string | null>(null);
  const [isCancelling, setIsCancelling] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [hasBillingReturn, setHasBillingReturn] = useState(false);

  const isAnnual = billingCycle === "annual";

  const loadBillingData = useCallback(async (signal?: AbortSignal) => {
    if (!storeId) {
      return;
    }

    const [plansResult, statusResult, usageResult] = await Promise.all([
      getBillingPlans({ storeId, signal }),
      getBillingStatus({ storeId, signal }),
      getBillingUsageSummary({ storeId, signal })
    ]);

    setPlans(plansResult.plans.filter((p) => p.is_active));
    setBillingStatus(statusResult);
    setUsageSummary(usageResult);

    if (statusResult.billing_interval === "monthly" || statusResult.billing_interval === "annual") {
      setBillingCycle(statusResult.billing_interval);
    }
  }, [storeId]);

  useEffect(() => {
    setHasBillingReturn(typeof window !== "undefined" && new URLSearchParams(window.location.search).has("charge_id"));
  }, []);

  // When Shopify redirects back with charge_id, activate billing in backend.
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

    activateBillingPlan({
      storeId,
      planName,
      billingInterval: interval,
      shopifySubscriptionId
    })
      .then(() => loadBillingData())
      .catch(() => {
        // Non-fatal: subscription may already be active on Shopify side.
      });
  }, [hasBillingReturn, loadBillingData, storeId]);

  useEffect(() => {
    if (!storeId) return;

    const controller = new AbortController();
    let active = true;

    setIsLoading(true);
    setErrorMessage("");

    loadBillingData(controller.signal)
      .catch((error: unknown) => {
        if (!active || controller.signal.aborted) {
          return;
        }

        const message = error instanceof Error ? error.message : "Failed to load billing data.";
        setErrorMessage(message);
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
    if (!billingStatus) {
      return plans.find((p) => p.is_current) ?? null;
    }

    return plans.find((p) => p.name === billingStatus.plan_name) ?? plans.find((p) => p.is_current) ?? null;
  }, [billingStatus, plans]);

  const renderedPlans = useMemo(
    () =>
      plans.map((plan) => ({
        ...plan,
        displayedPrice: isAnnual ? plan.price_annual_per_month : plan.price_monthly,
        displayedCredits: isAnnual ? plan.credits_annual : plan.credits_monthly,
        isCurrentSelection: plan.name === billingStatus?.plan_name && billingStatus?.billing_interval === billingCycle
      })),
    [billingCycle, billingStatus?.billing_interval, billingStatus?.plan_name, isAnnual, plans]
  );

  const usageUsedIncluded = usageSummary?.consumed_credits ?? 0;
  const usageUsedTotal = (usageSummary?.consumed_credits ?? 0) + (usageSummary?.overage_credits ?? 0);
  const usageLimit = usageSummary?.included_credits ?? 0;
  const usagePercent = usageLimit > 0 ? Math.min(100, (usageUsedIncluded / usageLimit) * 100) : 0;

  const recurringPrice = currentPlan
    ? billingStatus?.billing_interval === "annual"
      ? currentPlan.price_annual_total
      : currentPlan.price_monthly
    : null;

  const isLegacySubscription = Boolean(
    billingStatus?.shopify_subscription_id &&
    (billingStatus?.subscription_status || "").toUpperCase() === "ACTIVE" &&
    !billingStatus?.has_usage_billing
  );

  const handlePlanChange = async (plan: PlanConfigResponse) => {
    if (!storeId) {
      setErrorMessage("Open the app from Shopify Admin to manage billing.");
      return;
    }

    if (plan.name === billingStatus?.plan_name && billingStatus?.billing_interval === billingCycle) {
      return;
    }

    setPendingPlanId(plan.id);
    setErrorMessage("");

    try {
      const returnUrl = new URL("/settings/billing", window.location.origin);
      returnUrl.searchParams.set("plan", plan.name);
      returnUrl.searchParams.set("interval", billingCycle);
      if (storeId) {
        returnUrl.searchParams.set("shop", storeId);
      }

      const result = await createSubscription({
        storeId,
        planName: plan.name,
        billingInterval: billingCycle,
        returnUrl: returnUrl.toString()
      });

      if (result.shopify_subscription_id) {
        window.localStorage.setItem("pending_subscription_id", result.shopify_subscription_id);
      }

      window.open(result.confirmation_url, "_top");
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Failed to create Shopify subscription.";
      setErrorMessage(message);
      setPendingPlanId(null);
    }
  };

  const handleCancel = async () => {
    if (!storeId) return;
    if (!window.confirm("Are you sure you want to cancel your subscription? You will be moved to the free plan immediately.")) return;

    setIsCancelling(true);
    setErrorMessage("");

    try {
      await cancelSubscription({ storeId });
      await loadBillingData();
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Failed to cancel subscription.";
      setErrorMessage(message);
    } finally {
      setIsCancelling(false);
    }
  };

  return (
    <main className="portal-shell">
      <PortalSidebar activeMain="settings" activeSettings="billing" />

      <section className="portal-main">
        <header className="portal-main-header">
          <h2>Billing</h2>
          <p>Shopify subscription status, cycle usage, and plan switching</p>
        </header>

        {hasBillingReturn && billingStatus?.shopify_subscription_id ? (
          <p className="ai-status-note">Shopify redirected back after charge approval. The latest subscription is shown below.</p>
        ) : null}
        {isLoading ? <p className="ai-status-note">Loading billing...</p> : null}
        {errorMessage ? <p className="ai-error-note">{errorMessage}</p> : null}

        {isLegacySubscription ? (
          <p className="ai-error-note">
            This subscription does not include usage-based overage billing. Re-approve your current plan to enable auto-charged overage after included credits are exhausted.
          </p>
        ) : null}

        <div className="step7-billing-toggle" role="group" aria-label="Billing cycle">
          <button type="button" className={`step7-toggle-label${!isAnnual ? " is-active" : ""}`} onClick={() => setBillingCycle("monthly")}>
            Monthly
          </button>
          <button
            type="button"
            className={`step7-toggle-switch${isAnnual ? " is-annual" : ""}`}
            aria-label={isAnnual ? "Switch to monthly billing" : "Switch to annual billing"}
            onClick={() => setBillingCycle(isAnnual ? "monthly" : "annual")}
          >
            <span />
          </button>
          <button type="button" className={`step7-toggle-label${isAnnual ? " is-active" : ""}`} onClick={() => setBillingCycle("annual")}>
            Annual
          </button>
          <span className="step7-save-tag">SAVE</span>
        </div>

        <section className="billing-grid billing-grid-top">
          <article className="settings-card billing-card">
            <h3>Your Plan</h3>
            <p className="billing-pay-label">{billingStatus?.plan_name ?? "No active subscription"}</p>
            <p>Billing interval: {billingStatus?.billing_interval ?? "-"}</p>
            <p>Subscription status: {billingStatus?.subscription_status ?? "Not linked"}</p>
            <p>Plan price: {formatMoney(recurringPrice, "USD")}</p>

            <h4>Usage This Cycle</h4>
            <p>
              {usageUsedIncluded.toLocaleString()} / {usageLimit.toLocaleString()} Included Credits
            </p>
            <p>
              Total consumed: {usageUsedTotal.toLocaleString()} credits
              {usageSummary?.overage_credits ? ` (including ${usageSummary.overage_credits.toLocaleString()} overage)` : ""}
            </p>
            <div className="billing-progress" aria-hidden>
              <span style={{ width: `${usagePercent}%` }} />
            </div>

            <p>Overage amount so far: {formatMoney(usageSummary?.overage_amount_usd ?? 0, "USD")}</p>

            {usageSummary?.overage_blocked ? (
              <p className="ai-error-note">{usageSummary.overage_block_message || "Overage usage is blocked until billing is resolved."}</p>
            ) : null}

            {billingStatus?.shopify_subscription_id ? (
              <button
                type="button"
                className="billing-cancel-button"
                onClick={handleCancel}
                disabled={isCancelling}
              >
                {isCancelling ? "Cancelling..." : "Cancel Subscription"}
              </button>
            ) : null}
          </article>

          <article className="settings-card billing-card">
            <h3>Change Your Plan</h3>

            {renderedPlans.map((plan) => (
              <div key={plan.id} className="billing-offer">
                <h4>
                  {plan.display_name}
                  {plan.annual_discount_pct > 0 ? <small> (Save {plan.annual_discount_pct}% annually)</small> : null}
                </h4>
                <p>{plan.features[0] ?? "Core features"}</p>
                <p>{plan.displayedCredits.toLocaleString()} credits included</p>
                <p>Overage rate: {formatMoney(plan.overage_usd_per_tryon, "USD")} per generation</p>
                <p>Usage cap: {formatMoney(plan.usage_cap_usd, "USD")}</p>
                <strong>{formatMoney(plan.displayedPrice, "USD")} / month</strong>
                <button
                  type="button"
                  className="billing-upgrade-button"
                  onClick={() => handlePlanChange(plan)}
                  disabled={pendingPlanId === plan.id || plan.isCurrentSelection || isCancelling}
                >
                  {plan.isCurrentSelection
                    ? "Current Plan"
                    : pendingPlanId === plan.id
                      ? "Redirecting..."
                      : billingStatus?.plan_name === plan.name
                        ? `Switch to ${isAnnual ? "Annual" : "Monthly"}`
                        : `Switch to ${plan.display_name}`}
                </button>
              </div>
            ))}

            {renderedPlans.length === 0 && !isLoading ? <p>No active billing plans configured.</p> : null}
          </article>
        </section>

        <section className="billing-grid billing-grid-bottom">
          <article className="settings-card billing-card">
            <h3>Billing Timeline</h3>
            <ul className="billing-history-list">
              <li>
                <span>Plan activated</span>
                <span>{formatDateTime(billingStatus?.plan_activated_at ?? null)}</span>
                <span>{billingStatus?.plan_name ?? "-"}</span>
              </li>
              <li>
                <span>Cycle start</span>
                <span>{formatDateTime(usageSummary?.cycle_start_at ?? null)}</span>
                <span>{billingStatus?.store_timezone ?? "UTC"}</span>
              </li>
              <li>
                <span>Current period end</span>
                <span>{formatDateTime(billingStatus?.current_period_end ?? null)}</span>
                <span>{billingStatus?.subscription_status ?? "-"}</span>
              </li>
            </ul>
          </article>

          <div className="billing-stack">
            <article className="settings-card billing-card billing-card-compact">
              <div className="billing-row-head">
                <h3>Subscription ID</h3>
                <button type="button" disabled>
                  Shopify
                </button>
              </div>
              <p className="billing-payment-text">{billingStatus?.shopify_subscription_id ?? "Not connected"}</p>
            </article>

            <article className="settings-card billing-card billing-card-compact">
              <div className="billing-row-head">
                <h3>Next Billing Date</h3>
                <button type="button" disabled>
                  Read-only
                </button>
              </div>
              <p>{formatDateTime(billingStatus?.current_period_end ?? null)}</p>
            </article>
          </div>
        </section>
      </section>
    </main>
  );
}
