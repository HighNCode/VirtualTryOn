"use client";

import { useEffect, useMemo, useState } from "react";
import { EmbeddedLink, useEmbeddedRouter } from "../_components/EmbeddedNavigation";
import {
  createRecurringSubscription,
  getBillingStatus,
  getShopifyBillingContext,
  type ShopifyBillingContext
} from "../../lib/shopify/billing";
import {
  activateBillingPlan,
  getBillingPlans,
  getDefaultStoreId,
  type PlanConfigResponse
} from "../../lib/photoshootApi";

function formatPrice(value: number, currencyCode: string): string {
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: currencyCode,
    maximumFractionDigits: value % 1 === 0 ? 0 : 2
  }).format(value);
}

type BillingCycle = "monthly" | "annual";

export default function StepSevenPage() {
  const router = useEmbeddedRouter();
  const storeId = useMemo(() => getDefaultStoreId(), []);

  const [billingCycle, setBillingCycle] = useState<BillingCycle>("monthly");
  const [billingContext, setBillingContext] = useState<ShopifyBillingContext | null>(null);
  const [plans, setPlans] = useState<PlanConfigResponse[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [pendingPlanId, setPendingPlanId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState("");

  const isAnnual = billingCycle === "annual";

  // Detect billing return from Shopify and activate the plan in the backend
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (!params.has("billing_return")) return;

    const planName = params.get("plan");
    const interval = params.get("interval") as BillingCycle | null;
    const chargeId = params.get("charge_id");

    if (!planName || !interval || !storeId) {
      router.push("/dashboard");
      return;
    }

    const shopifySubscriptionId = chargeId
      ? `gid://shopify/AppSubscription/${chargeId}`
      : (window.localStorage.getItem("pending_subscription_id") ?? "");

    if (!shopifySubscriptionId) {
      router.push("/dashboard");
      return;
    }

    window.localStorage.removeItem("pending_subscription_id");

    setIsLoading(true);
    setErrorMessage("");

    activateBillingPlan({
      storeId,
      planName,
      billingInterval: interval,
      shopifySubscriptionId
    })
      .then(() => router.push("/dashboard"))
      .catch((error: unknown) => {
        const msg = error instanceof Error ? error.message : "Failed to activate billing.";
        setErrorMessage(msg);
        setIsLoading(false);
      });
  }, [router, storeId]);

  // Load plans and Shopify billing context in parallel
  useEffect(() => {
    if (!storeId) return;

    const params = new URLSearchParams(window.location.search);
    if (params.has("billing_return")) return; // handled by the other effect

    let active = true;
    setIsLoading(true);
    setErrorMessage("");

    Promise.allSettled([
      getShopifyBillingContext(),
      getBillingPlans({ storeId })
    ]).then(([contextResult, plansResult]) => {
      if (!active) return;

      if (contextResult.status === "fulfilled") {
        setBillingContext(contextResult.value);
      }

      if (plansResult.status === "fulfilled") {
        setPlans(plansResult.value.plans.filter((p) => p.is_active));
      } else {
        setErrorMessage("Failed to load billing plans.");
      }
    }).finally(() => {
      if (active) setIsLoading(false);
    });

    return () => {
      active = false;
    };
  }, [storeId]);

  const billingStatus = useMemo(() => {
    if (!billingContext) return null;
    return getBillingStatus(billingContext);
  }, [billingContext]);

  const renderedPlans = useMemo(
    () =>
      plans.map((plan) => ({
        ...plan,
        displayedPrice: isAnnual ? plan.price_annual_per_month : plan.price_monthly,
        displayedCredits: isAnnual ? plan.credits_annual : plan.credits_monthly,
        annualDiscountPct: plan.annual_discount_pct,
        isCurrentSelection: plan.is_current && billingStatus?.billingInterval === billingCycle
      })),
    [plans, billingCycle, billingStatus?.billingInterval, isAnnual]
  );

  const handlePlanSelect = async (plan: PlanConfigResponse) => {
    if (plan.is_current && billingStatus?.billingInterval === billingCycle) {
      router.push("/dashboard");
      return;
    }

    const selectedPrice = isAnnual ? plan.price_annual_total : plan.price_monthly;
    if (selectedPrice <= 0) {
      router.push("/dashboard");
      return;
    }

    if (!storeId) {
      setErrorMessage("Open the app from Shopify Admin to start a subscription.");
      return;
    }

    setPendingPlanId(plan.id);
    setErrorMessage("");

    try {
      const shopParam = storeId ? `&shop=${encodeURIComponent(storeId)}` : "";
      const result = await createRecurringSubscription({
        planDisplayName: plan.display_name,
        priceAmount: selectedPrice,
        billingCycle,
        trialDays: plan.trial_days,
        testMode: billingContext?.shopIsDevelopment ?? false,
        returnPath: `/step-7?billing_return=1&plan=${encodeURIComponent(plan.name)}&interval=${billingCycle}${shopParam}`
      });
      // Save subscription ID as fallback in case charge_id is missing from Shopify redirect
      if (result.subscriptionId) {
        window.localStorage.setItem("pending_subscription_id", result.subscriptionId);
      }
      window.open(result.confirmationUrl, "_top");
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Failed to start Shopify subscription.";
      setErrorMessage(message);
      setPendingPlanId(null);
    }
  };

  return (
    <main className="shell">
      <section className="welcome-card step7-card step7-card-updated">
        <header className="topline">
          <p className="screen-title">Welcome to Optimo VTS</p>
          <p className="step">Step 7 of 7</p>
        </header>

        <div className="progress-track" aria-hidden>
          <span className="progress-fill progress-step7" />
        </div>

        <div className="step7-heading">
          <h1>Choose Your Plan</h1>
          <p>Select a Shopify-billed plan for your store. You can switch plans later from Billing settings.</p>
        </div>

        {isLoading ? <p className="ai-status-note">Loading plans...</p> : null}
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

        <div className="step7-grid step7-grid-four">
          {renderedPlans.map((plan) => (
            <article
              key={plan.id}
              className={`plan-card plan-card-advanced${plan.is_current ? " plan-card-recommended" : ""}`}
              aria-label={`${plan.display_name} plan`}
            >
              {plan.is_current ? <p className="plan-badge">Current Plan</p> : null}

              <h2 className="plan-name">{plan.display_name}</h2>
              <p className="plan-price plan-price-advanced">
                {formatPrice(plan.displayedPrice, "USD")}
                <small>/month</small>
              </p>

              {isAnnual ? <p className="plan-billed">Billed {formatPrice(plan.price_annual_total, "USD")}/year</p> : null}

              <div className="plan-credit-box">
                <p>{plan.displayedCredits.toLocaleString()} credits included</p>
                <p>{plan.trial_days ? `${plan.trial_days}-day trial available` : "No trial on this plan"}</p>
              </div>

              <h3 className="plan-feature-title">Features</h3>
              <ul className="plan-feature-list">
                {plan.features.map((feature) => (
                  <li key={feature} className="plan-feature">
                    <span className="plan-feature-mark" aria-hidden>
                      <svg viewBox="0 0 24 24" role="img">
                        <path
                          d="M20 7L10 17L5 12"
                          fill="none"
                          stroke="currentColor"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth="2.7"
                        />
                      </svg>
                    </span>
                    <span>{feature}</span>
                  </li>
                ))}
              </ul>

              {plan.annualDiscountPct > 0 ? (
                <p className="plan-extra-rate">
                  Annual discount: <strong>{plan.annualDiscountPct}%</strong>
                </p>
              ) : null}

              <button
                type="button"
                className={`plan-select-button plan-select-button-advanced${plan.is_current ? " plan-select-button-filled" : ""}`}
                onClick={() => handlePlanSelect(plan)}
                disabled={pendingPlanId === plan.id || isLoading}
              >
                {plan.isCurrentSelection
                  ? "Current Plan"
                  : pendingPlanId === plan.id
                    ? "Redirecting..."
                    : plan.is_current
                      ? `Switch to ${isAnnual ? "Annual" : "Monthly"}`
                      : `Select ${plan.display_name}`}
              </button>
            </article>
          ))}

          {!isLoading && plans.length === 0 ? (
            <p className="ai-error-note">No billing plans available. Please contact support.</p>
          ) : null}
        </div>

        <p className="step7-credit-note">
          <strong>1 Try-on = 4 Credits</strong>
          <span>Billing is created through Shopify and the merchant approves charges on Shopify&apos;s hosted confirmation page.</span>
        </p>

        <section className="free-plan-banner free-plan-banner-updated">
          <div>
            <h2>Continue with current setup</h2>
            <p>{billingStatus?.activeSubscription ? "A Shopify subscription is already active for this store." : "Skip plan selection for now and finish onboarding."}</p>
          </div>

          <EmbeddedLink href="/dashboard" className="primary-action free-plan-cta">
            Continue
          </EmbeddedLink>
        </section>

        <p className="step7-powered-by">Powered by Shopify billing and Optimo plan configuration</p>
      </section>
    </main>
  );
}
