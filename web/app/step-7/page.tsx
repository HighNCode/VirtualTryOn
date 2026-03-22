"use client";

import { useEffect, useMemo, useState } from "react";
import { EmbeddedLink, useEmbeddedRouter } from "../_components/EmbeddedNavigation";
import {
  createRecurringSubscription,
  getBillingCatalog,
  getBillingStatus,
  getShopifyBillingContext,
  type ShopifyBillingContext
} from "../../lib/shopify/billing";
import type { BillingCatalogResponse, BillingCycle, BillingPlanResponse } from "../../lib/shopify/billing-config";

function formatPrice(value: number, currencyCode: string): string {
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

export default function StepSevenPage() {
  const router = useEmbeddedRouter();

  const [billingCycle, setBillingCycle] = useState<BillingCycle>("monthly");
  const [billingContext, setBillingContext] = useState<ShopifyBillingContext | null>(null);
  const [catalog, setCatalog] = useState<BillingCatalogResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [pendingPlanId, setPendingPlanId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState("");

  const isAnnual = billingCycle === "annual";

  useEffect(() => {
    let active = true;

    setIsLoading(true);
    setErrorMessage("");

    getShopifyBillingContext()
      .then(async (context) => {
        const planCatalog = await getBillingCatalog(context.billingCurrency);
        if (!active) {
          return;
        }

        setBillingContext(context);
        setCatalog(planCatalog);
      })
      .catch((error: unknown) => {
        if (!active) {
          return;
        }

        const message = error instanceof Error ? error.message : "Failed to load Shopify billing.";
        setErrorMessage(message);
      })
      .finally(() => {
        if (active) {
          setIsLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, []);

  const billingStatus = useMemo(() => {
    if (!billingContext) {
      return null;
    }

    return getBillingStatus(billingContext);
  }, [billingContext]);

  const developmentStoreBypass = Boolean(billingContext?.shopIsDevelopment && catalog && !catalog.test_mode);

  const renderedPlans = useMemo(
    () =>
      (catalog?.plans ?? [])
        .filter((plan) => plan.is_active)
        .map((plan) => {
          const currentPlan = isCurrentPlan(plan, billingContext);

          return {
            ...plan,
            displayedPrice: isAnnual ? plan.price_annual_per_month : plan.price_monthly,
            displayedCredits: isAnnual ? plan.credits_annual : plan.credits_monthly,
            isCurrentSelection: currentPlan && billingStatus?.billingInterval === billingCycle,
            isCurrentPlan: currentPlan
          };
        }),
    [billingContext, billingCycle, billingStatus?.billingInterval, catalog?.plans, isAnnual]
  );

  const handlePlanSelect = async (plan: BillingPlanResponse) => {
    if (developmentStoreBypass) {
      router.push("/dashboard");
      return;
    }

    const currentSelection = isCurrentPlan(plan, billingContext) && billingStatus?.billingInterval === billingCycle;
    if (currentSelection) {
      router.push("/dashboard");
      return;
    }

    const selectedPrice = isAnnual ? plan.price_annual_total : plan.price_monthly;
    if (selectedPrice <= 0) {
      router.push("/dashboard");
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

        {developmentStoreBypass ? (
          <p className="ai-status-note">
            Partner development store detected. Live billing is skipped here unless `SHOPIFY_BILLING_TEST_MODE=true`.
          </p>
        ) : null}
        {catalog ? (
          <p className="ai-status-note">
            Billing currency: {catalog.resolved_currency_code}
            {billingContext?.shopPlanName ? ` · Store plan: ${billingContext.shopPlanName}` : ""}
          </p>
        ) : null}
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
              className={`plan-card plan-card-advanced${plan.is_recommended ? " plan-card-recommended" : ""}`}
              aria-label={`${plan.display_name} plan`}
            >
              {plan.is_recommended ? <p className="plan-badge">Recommended</p> : null}

              <h2 className="plan-name">{plan.display_name}</h2>
              <p className="plan-price plan-price-advanced">
                {formatPrice(plan.displayedPrice, plan.currency_code)}
                <small>/month</small>
              </p>

              {isAnnual ? <p className="plan-billed">Billed {formatPrice(plan.price_annual_total, plan.currency_code)}/year</p> : null}

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

              <p className="plan-extra-rate">
                Annual discount: <strong>{plan.annual_discount_pct}%</strong>
              </p>

              <button
                type="button"
                className={`plan-select-button plan-select-button-advanced${plan.is_recommended ? " plan-select-button-filled" : ""}`}
                onClick={() => handlePlanSelect(plan)}
                disabled={pendingPlanId === plan.id}
              >
                {plan.isCurrentSelection
                  ? "Current Plan"
                  : developmentStoreBypass
                    ? "Use on Development Store"
                    : pendingPlanId === plan.id
                      ? "Redirecting..."
                      : plan.isCurrentPlan
                        ? `Switch to ${isAnnual ? "Annual" : "Monthly"}`
                        : `Select ${plan.display_name}`}
              </button>
            </article>
          ))}
        </div>

        <p className="step7-credit-note">
          <strong>1 Try-on = 4 Credits</strong>
          <span>Billing is created through Shopify GraphQL and the merchant approves charges on Shopify’s hosted confirmation page.</span>
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
