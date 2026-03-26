export const SHOPIFY_ADMIN_API_VERSION = "2026-01";

export type BillingCycle = "monthly" | "annual";

type CurrencyPricing = {
  monthly: number;
  annualTotal: number;
};

type BillingPlanDefinition = {
  id: string;
  name: string;
  displayName: string;
  description?: string;
  prices: Record<string, CurrencyPricing>;
  creditsMonthly: number;
  creditsAnnual: number;
  trialDays: number | null;
  trialCredits: number | null;
  features: string[];
  isActive: boolean;
  isRecommended: boolean;
};

export type BillingPlanResponse = {
  id: string;
  name: string;
  display_name: string;
  description: string | null;
  currency_code: string;
  price_monthly: number;
  price_annual_total: number;
  price_annual_per_month: number;
  annual_discount_pct: number;
  credits_monthly: number;
  credits_annual: number;
  trial_days: number | null;
  trial_credits: number | null;
  features: string[];
  is_active: boolean;
  is_recommended: boolean;
};

export type BillingCatalogResponse = {
  plans: BillingPlanResponse[];
  requested_currency_code: string;
  resolved_currency_code: string;
  test_mode: boolean;
};

const DEFAULT_CURRENCY = "USD";

const DEFAULT_BILLING_PLANS: BillingPlanDefinition[] = [
  {
    id: "starter",
    name: "Starter",
    displayName: "Starter",
    description: "For smaller stores launching virtual try-on.",
    prices: {
      USD: {
        monthly: 29,
        annualTotal: 290
      }
    },
    creditsMonthly: 1500,
    creditsAnnual: 18000,
    trialDays: 7,
    trialCredits: 300,
    features: ["Virtual try-on widget", "AI product shots", "Basic analytics"],
    isActive: true,
    isRecommended: false
  },
  {
    id: "growth",
    name: "Growth",
    displayName: "Growth",
    description: "For growing stores that need more credits and analytics depth.",
    prices: {
      USD: {
        monthly: 79,
        annualTotal: 790
      }
    },
    creditsMonthly: 6000,
    creditsAnnual: 72000,
    trialDays: 7,
    trialCredits: 750,
    features: ["Everything in Starter", "Advanced analytics", "Priority rendering queue"],
    isActive: true,
    isRecommended: true
  },
  {
    id: "scale",
    name: "Scale",
    displayName: "Scale",
    description: "For high-volume stores running try-on across large catalogs.",
    prices: {
      USD: {
        monthly: 199,
        annualTotal: 1990
      }
    },
    creditsMonthly: 18000,
    creditsAnnual: 216000,
    trialDays: 14,
    trialCredits: 1500,
    features: ["Everything in Growth", "High-volume credits", "Priority support"],
    isActive: true,
    isRecommended: false
  }
];

function normalizeCurrencyCode(value: string | null | undefined): string {
  const normalized = value?.trim().toUpperCase();
  return normalized && /^[A-Z]{3}$/.test(normalized) ? normalized : DEFAULT_CURRENCY;
}

function toFiniteNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }

  if (typeof value === "string" && value.trim()) {
    const parsed = Number.parseFloat(value);
    return Number.isFinite(parsed) ? parsed : null;
  }

  return null;
}

function toNullableInteger(value: unknown): number | null {
  if (value === null || value === undefined || value === "") {
    return null;
  }

  if (typeof value === "number" && Number.isInteger(value)) {
    return value;
  }

  if (typeof value === "string" && value.trim()) {
    const parsed = Number.parseInt(value, 10);
    return Number.isInteger(parsed) ? parsed : null;
  }

  return null;
}

function normalizeFeatures(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value
    .map((entry) => (typeof entry === "string" ? entry.trim() : ""))
    .filter((entry): entry is string => entry.length > 0);
}

function normalizePricingMap(value: unknown): Record<string, CurrencyPricing> | null {
  if (!value || typeof value !== "object") {
    return null;
  }

  const normalizedEntries = Object.entries(value).flatMap(([currencyCode, pricingValue]) => {
    if (!pricingValue || typeof pricingValue !== "object") {
      return [];
    }

    const pricing = pricingValue as Record<string, unknown>;
    const monthly = toFiniteNumber(pricing.monthly);
    const annualTotal = toFiniteNumber(pricing.annualTotal ?? pricing.annual_total);
    if (monthly === null || annualTotal === null || monthly < 0 || annualTotal < 0) {
      return [];
    }

    return [
      [
        normalizeCurrencyCode(currencyCode),
        {
          monthly,
          annualTotal
        }
      ] as const
    ];
  });

  if (normalizedEntries.length === 0) {
    return null;
  }

  return Object.fromEntries(normalizedEntries);
}

function normalizePlanDefinition(value: unknown): BillingPlanDefinition | null {
  if (!value || typeof value !== "object") {
    return null;
  }

  const source = value as Record<string, unknown>;
  const id = typeof source.id === "string" ? source.id.trim() : "";
  const name = typeof source.name === "string" ? source.name.trim() : "";
  const displayName =
    typeof source.displayName === "string"
      ? source.displayName.trim()
      : typeof source.display_name === "string"
        ? source.display_name.trim()
        : "";
  const prices = normalizePricingMap(source.prices);
  const creditsMonthly = toFiniteNumber(source.creditsMonthly ?? source.credits_monthly);
  const creditsAnnual = toFiniteNumber(source.creditsAnnual ?? source.credits_annual);
  const trialDays = toNullableInteger(source.trialDays ?? source.trial_days);
  const trialCredits = toNullableInteger(source.trialCredits ?? source.trial_credits);
  const features = normalizeFeatures(source.features);

  if (!id || !name || !displayName || !prices || creditsMonthly === null || creditsAnnual === null || features.length === 0) {
    return null;
  }

  return {
    id,
    name,
    displayName,
    description:
      typeof source.description === "string" && source.description.trim().length > 0 ? source.description.trim() : undefined,
    prices,
    creditsMonthly,
    creditsAnnual,
    trialDays,
    trialCredits,
    features,
    isActive: source.isActive !== false && source.is_active !== false,
    isRecommended: source.isRecommended === true || source.is_recommended === true
  };
}

function loadPlansFromEnvironment(): BillingPlanDefinition[] | null {
  const raw = process.env.SHOPIFY_BILLING_PLANS_JSON?.trim();
  if (!raw) {
    return null;
  }

  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return null;
    }

    const plans = parsed
      .map(normalizePlanDefinition)
      .filter((plan): plan is BillingPlanDefinition => plan !== null);

    return plans.length > 0 ? plans : null;
  } catch {
    return null;
  }
}

function resolvePricing(prices: Record<string, CurrencyPricing>, requestedCurrencyCode: string): {
  resolvedCurrencyCode: string;
  pricing: CurrencyPricing;
} {
  const normalizedCurrencyCode = normalizeCurrencyCode(requestedCurrencyCode);
  const directMatch = prices[normalizedCurrencyCode];
  if (directMatch) {
    return {
      resolvedCurrencyCode: normalizedCurrencyCode,
      pricing: directMatch
    };
  }

  const defaultMatch = prices[DEFAULT_CURRENCY];
  if (defaultMatch) {
    return {
      resolvedCurrencyCode: DEFAULT_CURRENCY,
      pricing: defaultMatch
    };
  }

  const [firstCurrencyCode, firstPricing] = Object.entries(prices)[0];
  return {
    resolvedCurrencyCode: firstCurrencyCode,
    pricing: firstPricing
  };
}

function calculateAnnualDiscount(monthlyPrice: number, annualTotal: number): number {
  if (monthlyPrice <= 0) {
    return 0;
  }

  const fullAnnualPrice = monthlyPrice * 12;
  if (fullAnnualPrice <= 0 || annualTotal >= fullAnnualPrice) {
    return 0;
  }

  return Math.round(((fullAnnualPrice - annualTotal) / fullAnnualPrice) * 100);
}

export function isBillingTestModeEnabled(): boolean {
  return process.env.SHOPIFY_BILLING_TEST_MODE?.trim().toLowerCase() === "true";
}

export function getBillingPlanDefinitions(): BillingPlanDefinition[] {
  return loadPlansFromEnvironment() ?? DEFAULT_BILLING_PLANS;
}

export function getResolvedBillingCatalog(requestedCurrencyCode: string | null | undefined): BillingCatalogResponse {
  const normalizedCurrencyCode = normalizeCurrencyCode(requestedCurrencyCode);

  const plans = getBillingPlanDefinitions().map((plan) => {
    const { pricing, resolvedCurrencyCode } = resolvePricing(plan.prices, normalizedCurrencyCode);

    return {
      id: plan.id,
      name: plan.name,
      display_name: plan.displayName,
      description: plan.description ?? null,
      currency_code: resolvedCurrencyCode,
      price_monthly: pricing.monthly,
      price_annual_total: pricing.annualTotal,
      price_annual_per_month: Number((pricing.annualTotal / 12).toFixed(2)),
      annual_discount_pct: calculateAnnualDiscount(pricing.monthly, pricing.annualTotal),
      credits_monthly: plan.creditsMonthly,
      credits_annual: plan.creditsAnnual,
      trial_days: plan.trialDays,
      trial_credits: plan.trialCredits,
      features: plan.features,
      is_active: plan.isActive,
      is_recommended: plan.isRecommended
    };
  });

  const resolvedCurrencyCode = plans[0]?.currency_code ?? DEFAULT_CURRENCY;

  return {
    plans,
    requested_currency_code: normalizedCurrencyCode,
    resolved_currency_code: resolvedCurrencyCode,
    test_mode: isBillingTestModeEnabled()
  };
}
