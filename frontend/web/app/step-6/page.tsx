"use client";

import { useEffect, useMemo, useState } from "react";
import { useEmbeddedRouter } from "../_components/EmbeddedNavigation";
import {
  activateBillingPlan,
  completeOnboardingFromBilling,
  createSubscription,
  getBillingPlans,
  getBillingStatus,
  getDefaultStoreId,
  startIntroFreeTrial,
  type BillingStatusResponse,
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

export default function StepSixPage() {
  const router = useEmbeddedRouter();
  const storeId = useMemo(() => getDefaultStoreId(), []);

  const [billingCycle, setBillingCycle] = useState<BillingCycle>("monthly");
  const [billingStatus, setBillingStatus] = useState<BillingStatusResponse | null>(null);
  const [plans, setPlans] = useState<PlanConfigResponse[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [pendingPlanId, setPendingPlanId] = useState<string | null>(null);
  const [isStartingTrial, setIsStartingTrial] = useState(false);
  const [isCompletingOnboarding, setIsCompletingOnboarding] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  const isAnnual = billingCycle === "annual";
  const introTrialConsumed =
    billingStatus?.plan_name === "free_trial" ||
    billingStatus?.plan_name === "founding_trial" ||
    billingStatus?.trial_mode === "intro_free";

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (!params.has("billing_return")) return;

    const planName = params.get("plan");
    const interval = params.get("interval") as BillingCycle | null;
    const chargeId = params.get("charge_id");

    if (!planName || !interval || !storeId) { router.push("/dashboard"); return; }

    const shopifySubscriptionId = chargeId
      ? `gid://shopify/AppSubscription/${chargeId}`
      : (window.localStorage.getItem("pending_subscription_id") ?? "");

    if (!shopifySubscriptionId) { router.push("/dashboard"); return; }

    window.localStorage.removeItem("pending_subscription_id");
    setIsLoading(true);
    setErrorMessage("");

    activateBillingPlan({ storeId, planName, billingInterval: interval, shopifySubscriptionId })
      .then(() => completeOnboardingFromBilling({ storeId }))
      .then(() => router.push("/dashboard"))
      .catch((error: unknown) => {
        setErrorMessage(error instanceof Error ? error.message : "Failed to activate billing.");
        setIsLoading(false);
      });
  }, [router, storeId]);

  useEffect(() => {
    if (!storeId) return;
    const params = new URLSearchParams(window.location.search);
    if (params.has("billing_return")) return;

    const controller = new AbortController();
    let active = true;
    setIsLoading(true);
    setErrorMessage("");

    Promise.all([
      getBillingPlans({ storeId, signal: controller.signal }),
      getBillingStatus({ storeId, signal: controller.signal })
    ])
      .then(([plansResult, statusResult]) => {
        if (!active) return;
        setPlans(plansResult.plans.filter((p) => p.is_active));
        setBillingStatus(statusResult);
        if (statusResult.billing_interval === "monthly" || statusResult.billing_interval === "annual") {
          setBillingCycle(statusResult.billing_interval);
        }
      })
      .catch((error: unknown) => {
        if (!active || controller.signal.aborted) return;
        setErrorMessage(error instanceof Error ? error.message : "Failed to load billing plans.");
      })
      .finally(() => { if (active) setIsLoading(false); });

    return () => { active = false; controller.abort(); };
  }, [storeId]);

  const renderedPlans = useMemo(
    () =>
      plans.map((plan) => ({
        ...plan,
        displayedPrice: isAnnual ? plan.price_annual_per_month : plan.price_monthly,
        displayedCredits: isAnnual ? plan.credits_annual : plan.credits_monthly,
        annualDiscountPct: plan.annual_discount_pct,
        isCurrentSelection: plan.name === billingStatus?.plan_name && billingStatus?.billing_interval === billingCycle
      })),
    [billingCycle, billingStatus?.billing_interval, billingStatus?.plan_name, isAnnual, plans]
  );

  const handlePlanSelect = async (plan: PlanConfigResponse) => {
    if (plan.name === billingStatus?.plan_name && billingStatus?.billing_interval === billingCycle) {
      if (!storeId) { setErrorMessage("Open the app from Shopify Admin to continue onboarding."); return; }
      setIsCompletingOnboarding(true);
      setErrorMessage("");
      try {
        await completeOnboardingFromBilling({ storeId });
        router.push("/dashboard");
      } catch (error: unknown) {
        setErrorMessage(error instanceof Error ? error.message : "Failed to complete onboarding.");
      } finally {
        setIsCompletingOnboarding(false);
      }
      return;
    }

    if (!storeId) { setErrorMessage("Open the app from Shopify Admin to start a subscription."); return; }

    setPendingPlanId(plan.id);
    setErrorMessage("");

    try {
      const returnUrl = new URL("/step-6", window.location.origin);
      returnUrl.searchParams.set("billing_return", "1");
      returnUrl.searchParams.set("plan", plan.name);
      returnUrl.searchParams.set("interval", billingCycle);
      returnUrl.searchParams.set("shop", storeId);

      const result = await createSubscription({ storeId, planName: plan.name, billingInterval: billingCycle, returnUrl: returnUrl.toString() });

      if (result.shopify_subscription_id) {
        window.localStorage.setItem("pending_subscription_id", result.shopify_subscription_id);
      }
      window.open(result.confirmation_url, "_top");
    } catch (error: unknown) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to start Shopify subscription.");
      setPendingPlanId(null);
    }
  };

  const handleStartFreeTrial = async () => {
    if (!storeId) { setErrorMessage("Open the app from Shopify Admin to start your free trial."); return; }
    setIsStartingTrial(true);
    setErrorMessage("");
    try {
      await startIntroFreeTrial({ storeId });
      router.push("/dashboard");
    } catch (error: unknown) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to start free trial.");
    } finally {
      setIsStartingTrial(false);
    }
  };

  const handleContinueCurrentSetup = async () => {
    if (!storeId) { setErrorMessage("Open the app from Shopify Admin to continue onboarding."); return; }
    setIsCompletingOnboarding(true);
    setErrorMessage("");
    try {
      await completeOnboardingFromBilling({ storeId });
      router.push("/dashboard");
    } catch (error: unknown) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to complete onboarding.");
    } finally {
      setIsCompletingOnboarding(false);
    }
  };

  const isBusy = isLoading || isStartingTrial || isCompletingOnboarding;

  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "flex-start", justifyContent: "center", padding: "24px 16px", background: "#f6f4f4" }}>
      <div style={{ width: "100%", maxWidth: 860, background: "#fff", borderRadius: 14, overflow: "hidden", boxShadow: "0 4px 24px rgba(0,0,0,0.08)", border: "1px solid rgba(0,0,0,0.05)" }}>

        {/* Top bar */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 24px", borderBottom: "1px solid #f0f0f0" }}>
          <p style={{ margin: 0, fontSize: 13, fontWeight: 600, color: "#6b7280" }}>Welcome to Optimo VTS</p>
          <p style={{ margin: 0, fontSize: 13, color: "#9ca3af" }}>Step 6 of 6</p>
        </div>

        {/* Progress bar */}
        <div style={{ width: "100%", height: 4, background: "#f3f4f6" }}>
          <div style={{ width: "100%", height: "100%", background: "linear-gradient(90deg, #7E0175, #E40206)" }} />
        </div>

        {/* Content */}
        <div style={{ padding: "24px 24px 16px" }}>
          <div style={{ textAlign: "center", marginBottom: 20 }}>
            <h1 style={{ margin: "0 0 4px", fontSize: 22, fontWeight: 800, color: "#1a1a1a" }}>Choose Your Plan</h1>
            <p style={{ margin: 0, fontSize: 14, color: "#6b7280" }}>
              Select a Shopify-billed plan for your store. You can switch plans later from Billing settings.
            </p>
          </div>

          {isLoading && <p style={{ fontSize: 13, marginBottom: 16, padding: "8px 12px", borderRadius: 8, background: "rgba(126,1,117,0.06)", color: "#7E0175" }}>Loading plans...</p>}
          {errorMessage && <p style={{ fontSize: 13, marginBottom: 16, padding: "8px 12px", borderRadius: 8, background: "#fff1f1", color: "#dc2626" }}>{errorMessage}</p>}

          {/* Billing cycle toggle */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 12, marginBottom: 20 }}>
            <button
              type="button"
              onClick={() => setBillingCycle("monthly")}
              style={{
                fontSize: 13, fontWeight: 600, padding: "8px 16px", borderRadius: 10,
                background: !isAnnual ? "linear-gradient(135deg, #7E0175 0%, #BC174A 55%, #E40206 100%)" : "#f3f4f6",
                color: !isAnnual ? "#fff" : "#6b7280",
                border: "none", cursor: "pointer",
              }}
            >
              Monthly
            </button>
            <button
              type="button"
              onClick={() => setBillingCycle(isAnnual ? "monthly" : "annual")}
              style={{
                width: 44, height: 24, borderRadius: 12, position: "relative", flexShrink: 0,
                background: isAnnual ? "linear-gradient(135deg, #7E0175, #E40206)" : "#d1d5db",
                border: "none", cursor: "pointer", transition: "background 200ms",
              }}
              aria-label={isAnnual ? "Switch to monthly billing" : "Switch to annual billing"}
            >
              <span
                style={{
                  position: "absolute", top: 2, width: 20, height: 20, borderRadius: "50%", background: "#fff",
                  left: isAnnual ? "calc(100% - 22px)" : 2,
                  transition: "left 200ms",
                  boxShadow: "0 1px 3px rgba(0,0,0,0.2)",
                }}
              />
            </button>
            <button
              type="button"
              onClick={() => setBillingCycle("annual")}
              style={{
                fontSize: 13, fontWeight: 600, padding: "8px 16px", borderRadius: 10,
                background: isAnnual ? "linear-gradient(135deg, #7E0175 0%, #BC174A 55%, #E40206 100%)" : "#f3f4f6",
                color: isAnnual ? "#fff" : "#6b7280",
                border: "none", cursor: "pointer",
              }}
            >
              Annual
            </button>
            <span style={{ fontSize: 11, fontWeight: 700, padding: "4px 8px", borderRadius: 999, background: "#dcfce7", color: "#15803d" }}>
              SAVE
            </span>
          </div>

          {/* Plans grid */}
          <div style={{ display: "grid", gridTemplateColumns: `repeat(${Math.max(renderedPlans.length, 1)}, 1fr)`, gap: 16, marginBottom: 20 }}>
            {renderedPlans.map((plan) => (
              <article
                key={plan.id}
                style={{
                  borderRadius: 12, padding: 16, display: "flex", flexDirection: "column", position: "relative",
                  border: plan.isCurrentSelection ? "1.5px solid #7E0175" : "1px solid rgba(0,0,0,0.07)",
                  background: plan.isCurrentSelection ? "rgba(126,1,117,0.03)" : "#fafafa",
                }}
                aria-label={`${plan.display_name} plan`}
              >
                {plan.isCurrentSelection && (
                  <span
                    style={{
                      position: "absolute", top: -10, left: "50%", transform: "translateX(-50%)",
                      fontSize: 10, fontWeight: 700, padding: "2px 10px", borderRadius: 999, color: "#fff",
                      background: "linear-gradient(135deg, #7E0175, #E40206)",
                      whiteSpace: "nowrap",
                    }}
                  >
                    Current Plan
                  </span>
                )}

                <h2 style={{ margin: "0 0 4px", fontSize: 14, fontWeight: 700, color: "#1a1a1a" }}>{plan.display_name}</h2>
                <p style={{ margin: "0 0 2px", fontSize: 22, fontWeight: 800, color: "#1a1a1a" }}>
                  {formatPrice(plan.displayedPrice, "USD")}
                  <span style={{ fontSize: 13, fontWeight: 400, color: "#9ca3af" }}>/mo</span>
                </p>
                {isAnnual && (
                  <p style={{ margin: "0 0 8px", fontSize: 11, color: "#9ca3af" }}>
                    Billed {formatPrice(plan.price_annual_total, "USD")}/year
                  </p>
                )}

                <div style={{ borderRadius: 8, padding: "8px 12px", marginBottom: 12, fontSize: 12, background: "rgba(126,1,117,0.06)" }}>
                  <p style={{ margin: 0, fontWeight: 600, color: "#7E0175" }}>{plan.displayedCredits.toLocaleString()} credits</p>
                  <p style={{ margin: 0, color: "#9ca3af" }}>
                    {introTrialConsumed ? "Intro trial already used" : plan.trial_days ? `${plan.trial_days}-day trial` : "No trial"}
                  </p>
                </div>

                <p style={{ margin: "0 0 6px", fontSize: 11, fontWeight: 600, color: "#6b7280" }}>Features</p>
                <ul style={{ listStyle: "none", margin: "0 0 12px", padding: 0, display: "flex", flexDirection: "column", gap: 6, flex: 1 }}>
                  {plan.features.map((feature) => (
                    <li key={feature} style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
                      <span style={{ width: 16, height: 16, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, marginTop: 2, background: "#dcfce7" }}>
                        <svg viewBox="0 0 24 24" width={9} height={9}>
                          <path d="M20 7L10 17L5 12" fill="none" stroke="#15803d" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.7" />
                        </svg>
                      </span>
                      <span style={{ fontSize: 12, color: "#6b7280" }}>{feature}</span>
                    </li>
                  ))}
                </ul>

                {plan.annualDiscountPct > 0 && (
                  <p style={{ margin: "0 0 8px", fontSize: 11, textAlign: "center", color: "#15803d" }}>
                    Annual discount: <strong>{plan.annualDiscountPct}%</strong>
                  </p>
                )}

                <button
                  type="button"
                  onClick={() => handlePlanSelect(plan)}
                  disabled={pendingPlanId === plan.id || isBusy}
                  style={{
                    width: "100%", padding: "10px 16px", borderRadius: 10, fontSize: 13, fontWeight: 600,
                    background: plan.isCurrentSelection ? "linear-gradient(135deg, #7E0175 0%, #BC174A 55%, #E40206 100%)" : "#fff",
                    color: plan.isCurrentSelection ? "#fff" : "#7E0175",
                    border: plan.isCurrentSelection ? "none" : "1.5px solid #7E0175",
                    cursor: pendingPlanId === plan.id || isBusy ? "not-allowed" : "pointer",
                    opacity: pendingPlanId === plan.id || isBusy ? 0.7 : 1,
                  }}
                >
                  {plan.isCurrentSelection
                    ? "Current Plan"
                    : pendingPlanId === plan.id
                      ? "Redirecting..."
                      : plan.name === billingStatus?.plan_name
                        ? `Switch to ${isAnnual ? "Annual" : "Monthly"}`
                        : `Select ${plan.display_name}`}
                </button>
              </article>
            ))}

            {!isLoading && plans.length === 0 && (
              <p style={{ fontSize: 13, gridColumn: "1 / -1", textAlign: "center", padding: "16px 0", color: "#9ca3af" }}>
                No billing plans available. Please contact support.
              </p>
            )}
          </div>

          <p style={{ margin: "0 0 20px", fontSize: 12, textAlign: "center", color: "#9ca3af" }}>
            <strong style={{ color: "#6b7280" }}>1 Try-on = 4 Credits</strong>
            {" · "}
            Billing is created through Shopify and approved on Shopify&apos;s hosted confirmation page.
          </p>

          {/* Free trial banner */}
          <div
            style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16, padding: "16px 20px", borderRadius: 12, marginBottom: 12, background: "rgba(126,1,117,0.04)", border: "1.5px solid rgba(126,1,117,0.15)" }}
          >
            <div>
              <h2 style={{ margin: "0 0 2px", fontSize: 15, fontWeight: 700, color: "#1a1a1a" }}>Start Free Trial</h2>
              <p style={{ margin: 0, fontSize: 13, color: "#6b7280" }}>14 days free trial with 80 included credits. No Shopify charge approval required today.</p>
            </div>
            <button
              type="button"
              onClick={handleStartFreeTrial}
              disabled={isBusy}
              style={{
                flexShrink: 0, padding: "10px 20px", borderRadius: 10, fontSize: 13, fontWeight: 600, color: "#fff",
                background: "linear-gradient(135deg, #7E0175 0%, #BC174A 55%, #E40206 100%)",
                border: "none",
                cursor: isBusy ? "not-allowed" : "pointer",
                opacity: isBusy ? 0.7 : 1,
              }}
            >
              {isStartingTrial ? "Starting..." : "Start Free Trial"}
            </button>
          </div>

          {/* Continue current setup */}
          {(billingStatus?.shopify_subscription_id || billingStatus?.plan_name === "free_trial" || billingStatus?.plan_name === "founding_trial") && (
            <div
              style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16, padding: "16px 20px", borderRadius: 12, marginBottom: 12, background: "#f0fdf4", border: "1.5px solid #bbf7d0" }}
            >
              <div>
                <h2 style={{ margin: "0 0 2px", fontSize: 15, fontWeight: 700, color: "#1a1a1a" }}>Continue with current setup</h2>
                <p style={{ margin: 0, fontSize: 13, color: "#6b7280" }}>Use your already active setup and complete onboarding now.</p>
              </div>
              <button
                type="button"
                onClick={handleContinueCurrentSetup}
                disabled={isBusy}
                style={{
                  flexShrink: 0, padding: "10px 20px", borderRadius: 10, fontSize: 13, fontWeight: 600,
                  background: "#15803d", color: "#fff", border: "none",
                  cursor: isBusy ? "not-allowed" : "pointer",
                  opacity: isBusy ? 0.7 : 1,
                }}
              >
                {isCompletingOnboarding ? "Continuing..." : "Continue"}
              </button>
            </div>
          )}

          <p style={{ margin: 0, fontSize: 11, textAlign: "center", color: "#d1d5db" }}>
            Powered by Shopify billing and Optimo plan configuration
          </p>
        </div>

      </div>
    </div>
  );
}
