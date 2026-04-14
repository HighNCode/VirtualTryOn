"use client";

import { useEffect, useMemo, useState } from "react";
import PortalSidebar from "../../_components/PortalSidebar";
import {
  activateBillingPlan,
  cancelSubscription,
  getBillingPlans,
  getDefaultStoreId,
  getStandardAnalytics,
  type PlanConfigResponse,
  type StandardAnalyticsResponse
} from "../../../lib/photoshootApi";
import {
  createRecurringSubscription,
  getBillingStatus,
  getShopifyBillingContext,
  type ShopifyBillingContext
} from "../../../lib/shopify/billing";

type BillingCycle = "monthly" | "annual";

function formatDateTime(value: string | null): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString();
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
  const [billingContext, setBillingContext] = useState<ShopifyBillingContext | null>(null);
  const [plans, setPlans] = useState<PlanConfigResponse[]>([]);
  const [analytics, setAnalytics] = useState<StandardAnalyticsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [pendingPlanId, setPendingPlanId] = useState<string | null>(null);
  const [isCancelling, setIsCancelling] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [hasBillingReturn, setHasBillingReturn] = useState(false);

  const isAnnual = billingCycle === "annual";

  useEffect(() => {
    setHasBillingReturn(typeof window !== "undefined" && new URLSearchParams(window.location.search).has("charge_id"));
  }, []);

  // When Shopify redirects back with charge_id, activate billing in the backend
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
    }).catch(() => {
      // Activation failure is non-fatal — subscription is already approved by Shopify
    });
  }, [hasBillingReturn, storeId]);

  // Load plans, Shopify billing context, and analytics in parallel
  useEffect(() => {
    if (!storeId) return;

    const controller = new AbortController();
    let active = true;

    setIsLoading(true);
    setErrorMessage("");

    Promise.allSettled([
      getShopifyBillingContext(),
      getBillingPlans({ storeId, signal: controller.signal }),
      getStandardAnalytics({ storeId, period: 30, signal: controller.signal })
    ]).then(([contextResult, plansResult, analyticsResult]) => {
      if (!active) return;

      if (contextResult.status === "fulfilled") {
        setBillingContext(contextResult.value);
        const interval = getBillingStatus(contextResult.value).billingInterval;
        if (interval) setBillingCycle(interval);
      }

      if (plansResult.status === "fulfilled") {
        setPlans(plansResult.value.plans.filter((p) => p.is_active));
      } else if (!controller.signal.aborted) {
        setErrorMessage("Failed to load billing plans.");
      }

      if (analyticsResult.status === "fulfilled") {
        setAnalytics(analyticsResult.value);
      }
    }).finally(() => {
      if (active) setIsLoading(false);
    });

    return () => {
      active = false;
      controller.abort();
    };
  }, [storeId]);

  const billingStatus = useMemo(() => {
    if (!billingContext) return null;
    return getBillingStatus(billingContext);
  }, [billingContext]);

  const currentPlan = useMemo(() => plans.find((p) => p.is_current) ?? null, [plans]);

  const renderedPlans = useMemo(
    () =>
      plans.map((plan) => ({
        ...plan,
        displayedPrice: isAnnual ? plan.price_annual_per_month : plan.price_monthly,
        displayedCredits: isAnnual ? plan.credits_annual : plan.credits_monthly,
        isCurrentSelection: plan.is_current && billingStatus?.billingInterval === billingCycle
      })),
    [plans, billingCycle, billingStatus?.billingInterval, isAnnual]
  );

  const usageUsed = analytics?.credits_used ?? 0;
  const usageLimit = billingStatus?.billingInterval === "annual" ? currentPlan?.credits_annual ?? 0 : currentPlan?.credits_monthly ?? 0;
  const usagePercent = usageLimit > 0 ? Math.min(100, (usageUsed / usageLimit) * 100) : 0;

  const handlePlanChange = async (plan: PlanConfigResponse) => {
    if (plan.is_current && billingStatus?.billingInterval === billingCycle) return;
    if (!storeId) {
      setErrorMessage("Open the app from Shopify Admin to manage billing.");
      return;
    }

    const selectedPrice = isAnnual ? plan.price_annual_total : plan.price_monthly;
    if (selectedPrice <= 0) return;

    setPendingPlanId(plan.id);
    setErrorMessage("");

    const shopParam = storeId ? `&shop=${encodeURIComponent(storeId)}` : "";

    try {
      const result = await createRecurringSubscription({
        planDisplayName: plan.display_name,
        priceAmount: selectedPrice,
        billingCycle,
        trialDays: plan.trial_days,
        testMode: billingContext?.shopIsDevelopment ?? false,
        returnPath: `/settings/billing?plan=${encodeURIComponent(plan.name)}&interval=${billingCycle}${shopParam}`
      });
      if (result.subscriptionId) {
        window.localStorage.setItem("pending_subscription_id", result.subscriptionId);
      }
      window.open(result.confirmationUrl, "_top");
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
      // Reload billing context after cancellation
      const context = await getShopifyBillingContext();
      setBillingContext(context);
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
          <p>Shopify subscription status, plan switching, and credit usage</p>
        </header>

        {hasBillingReturn && billingStatus?.activeSubscription ? (
          <p className="ai-status-note">Shopify redirected back after charge approval. The latest subscription is shown below.</p>
        ) : null}
        {isLoading ? <p className="ai-status-note">Loading billing...</p> : null}
        {errorMessage ? <p className="ai-error-note">{errorMessage}</p> : null}

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
            <p className="billing-pay-label">{billingStatus?.planName ?? "No active subscription"}</p>
            <p>Billing interval: {billingStatus?.billingInterval ?? "-"}</p>
            <p>Subscription status: {billingStatus?.subscriptionStatus ?? "Not linked"}</p>
            <p>Recurring price: {formatMoney(billingStatus?.recurringPrice ?? null, billingStatus?.recurringCurrencyCode ?? "USD")}</p>

            <h4>Usage This Month</h4>
            <p>
              {usageUsed.toLocaleString()} / {usageLimit.toLocaleString()} Credits
            </p>
            <div className="billing-progress" aria-hidden>
              <span style={{ width: `${usagePercent}%` }} />
            </div>

            <button type="button" className="billing-link-button" disabled>
              Current Plan: {currentPlan?.display_name ?? billingStatus?.planName ?? "-"}
            </button>

            {billingStatus?.activeSubscription ? (
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
                      : plan.is_current
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
                <span>{formatDateTime(billingStatus?.activeSubscription?.createdAt ?? null)}</span>
                <span>{billingStatus?.planName ?? "-"}</span>
              </li>
              <li>
                <span>Trial duration</span>
                <span>{billingStatus?.trialDays ? `${billingStatus.trialDays} days` : "-"}</span>
                <span>{billingStatus?.billingInterval ?? "-"}</span>
              </li>
              <li>
                <span>Current period end</span>
                <span>{formatDateTime(billingStatus?.currentPeriodEnd ?? null)}</span>
                <span>{billingStatus?.subscriptionStatus ?? "-"}</span>
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
              <p className="billing-payment-text">{billingStatus?.shopifySubscriptionId ?? "Not connected"}</p>
            </article>

            <article className="settings-card billing-card billing-card-compact">
              <div className="billing-row-head">
                <h3>Next Billing Date</h3>
                <button type="button" disabled>
                  Read-only
                </button>
              </div>
              <p>{formatDateTime(billingStatus?.currentPeriodEnd ?? null)}</p>
            </article>
          </div>
        </section>
      </section>
    </main>
  );
}
