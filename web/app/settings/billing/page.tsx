"use client";

import { useEffect, useMemo, useState } from "react";
import PortalSidebar from "../../_components/PortalSidebar";
import { getDefaultStoreId, getStandardAnalytics, type StandardAnalyticsResponse } from "../../../lib/photoshootApi";
import {
  createRecurringSubscription,
  getBillingCatalog,
  getBillingStatus,
  getShopifyBillingContext,
  type ShopifyBillingContext
} from "../../../lib/shopify/billing";
import type { BillingCatalogResponse, BillingCycle, BillingPlanResponse } from "../../../lib/shopify/billing-config";

function formatDateTime(value: string | null): string {
  if (!value) {
    return "-";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleDateString();
}

function formatMoney(value: number | null, currencyCode: string | null): string {
  if (value === null || !currencyCode) {
    return "-";
  }

  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: currencyCode,
    maximumFractionDigits: value % 1 === 0 ? 0 : 2
  }).format(value);
}

function isCurrentPlan(plan: BillingPlanResponse, billingContext: ShopifyBillingContext | null): boolean {
  const activeName = billingContext?.activeSubscriptions[0]?.name?.trim().toLowerCase() ?? "";
  return activeName === plan.name.toLowerCase() || activeName === plan.display_name.toLowerCase();
}

export default function SettingsBillingPage() {
  const storeId = useMemo(() => getDefaultStoreId(), []);

  const [billingCycle, setBillingCycle] = useState<BillingCycle>("monthly");
  const [billingContext, setBillingContext] = useState<ShopifyBillingContext | null>(null);
  const [catalog, setCatalog] = useState<BillingCatalogResponse | null>(null);
  const [analytics, setAnalytics] = useState<StandardAnalyticsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [pendingPlanId, setPendingPlanId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [hasBillingReturn, setHasBillingReturn] = useState(false);

  const isAnnual = billingCycle === "annual";

  useEffect(() => {
    setHasBillingReturn(typeof window !== "undefined" && new URLSearchParams(window.location.search).has("charge_id"));
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;

    setIsLoading(true);
    setErrorMessage("");

    getShopifyBillingContext()
      .then(async (context) => {
        const tasks: [Promise<BillingCatalogResponse>, Promise<StandardAnalyticsResponse | null>] = [
          getBillingCatalog(context.billingCurrency),
          storeId ? getStandardAnalytics({ storeId, period: 30, signal: controller.signal }) : Promise.resolve(null)
        ];

        const [catalogResult, analyticsResult] = await Promise.allSettled(tasks);
        if (!active) {
          return;
        }

        setBillingContext(context);

        if (catalogResult.status === "fulfilled") {
          setCatalog(catalogResult.value);
        } else {
          throw catalogResult.reason;
        }

        if (analyticsResult.status === "fulfilled") {
          setAnalytics(analyticsResult.value);
        } else if (!controller.signal.aborted) {
          const analyticsMessage =
            analyticsResult.reason instanceof Error ? analyticsResult.reason.message : "Failed to load usage analytics.";
          setErrorMessage(analyticsMessage);
        }
      })
      .catch((error: unknown) => {
        if (!active || controller.signal.aborted) {
          return;
        }

        const message = error instanceof Error ? error.message : "Failed to load Shopify billing data.";
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
  }, [storeId]);

  const billingStatus = useMemo(() => {
    if (!billingContext) {
      return null;
    }

    return getBillingStatus(billingContext);
  }, [billingContext]);

  useEffect(() => {
    if (billingStatus?.billingInterval) {
      setBillingCycle(billingStatus.billingInterval);
    }
  }, [billingStatus?.billingInterval]);

  const currentPlan = useMemo(() => {
    return (catalog?.plans ?? []).find((plan) => isCurrentPlan(plan, billingContext)) ?? null;
  }, [billingContext, catalog?.plans]);

  const developmentStoreBypass = Boolean(billingContext?.shopIsDevelopment && catalog && !catalog.test_mode);

  const renderedPlans = useMemo(
    () =>
      (catalog?.plans ?? [])
        .filter((plan) => plan.is_active)
        .map((plan) => {
          const currentPlanMatch = isCurrentPlan(plan, billingContext);

          return {
            ...plan,
            displayedPrice: isAnnual ? plan.price_annual_per_month : plan.price_monthly,
            displayedCredits: isAnnual ? plan.credits_annual : plan.credits_monthly,
            isCurrentPlan: currentPlanMatch,
            isCurrentSelection: currentPlanMatch && billingStatus?.billingInterval === billingCycle
          };
        }),
    [billingContext, billingCycle, billingStatus?.billingInterval, catalog?.plans, isAnnual]
  );

  const usageUsed = analytics?.credits_used ?? 0;
  const usageLimit = billingStatus?.billingInterval === "annual" ? currentPlan?.credits_annual ?? 0 : currentPlan?.credits_monthly ?? 0;
  const usagePercent = usageLimit > 0 ? Math.min(100, (usageUsed / usageLimit) * 100) : 0;

  const handlePlanChange = async (plan: BillingPlanResponse) => {
    if (developmentStoreBypass) {
      return;
    }

    const currentSelection = isCurrentPlan(plan, billingContext) && billingStatus?.billingInterval === billingCycle;
    if (currentSelection) {
      return;
    }

    setPendingPlanId(plan.id);
    setErrorMessage("");

    try {
      const subscription = await createRecurringSubscription({
        plan,
        billingCycle,
        testMode: catalog?.test_mode ?? false
      });

      window.location.assign(subscription.confirmationUrl);
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Failed to create Shopify subscription.";
      setErrorMessage(message);
      setPendingPlanId(null);
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

        {developmentStoreBypass ? (
          <p className="ai-status-note">
            Partner development store detected. Live billing is bypassed until the store moves to a paid Shopify plan.
          </p>
        ) : null}
        {hasBillingReturn && billingStatus?.activeSubscription ? (
          <p className="ai-status-note">Shopify redirected back after charge approval. The latest subscription is shown below.</p>
        ) : null}
        {catalog ? (
          <p className="ai-status-note">
            Billing currency: {catalog.resolved_currency_code}
            {billingContext?.shopPlanName ? ` · Store plan: ${billingContext.shopPlanName}` : ""}
            {billingStatus?.isTestSubscription ? " · Test charge" : ""}
          </p>
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
            <p>Recurring price: {formatMoney(billingStatus?.recurringPrice ?? null, billingStatus?.recurringCurrencyCode ?? null)}</p>

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
          </article>

          <article className="settings-card billing-card">
            <h3>Change Your Plan</h3>

            {renderedPlans.map((plan) => (
              <div key={plan.id} className="billing-offer">
                <h4>
                  {plan.display_name}
                  {plan.annual_discount_pct > 0 ? <small>(Save {plan.annual_discount_pct}% annually)</small> : null}
                </h4>
                <p>{plan.description ?? "Shopify-billed recurring subscription"}</p>
                <p>{plan.displayedCredits.toLocaleString()} credits included</p>
                <p>{plan.features[0] ?? "Core features"}</p>
                <strong>{formatMoney(plan.displayedPrice, plan.currency_code)} / month</strong>
                <button
                  type="button"
                  className="billing-upgrade-button"
                  onClick={() => handlePlanChange(plan)}
                  disabled={developmentStoreBypass || pendingPlanId === plan.id || plan.isCurrentSelection}
                >
                  {plan.isCurrentSelection
                    ? "Current Plan"
                    : pendingPlanId === plan.id
                      ? "Redirecting..."
                      : plan.isCurrentPlan
                        ? `Switch to ${isAnnual ? "Annual" : "Monthly"}`
                        : `Switch to ${plan.display_name}`}
                </button>
              </div>
            ))}

            {renderedPlans.length === 0 ? <p>No active billing plans configured.</p> : null}
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
