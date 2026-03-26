"use client";

import { SHOPIFY_ADMIN_API_VERSION, type BillingCatalogResponse, type BillingCycle, type BillingPlanResponse } from "./billing-config";

const SHOPIFY_ADMIN_GRAPHQL_URL = `shopify:admin/api/${SHOPIFY_ADMIN_API_VERSION}/graphql.json`;
const ACTIVE_SUBSCRIPTION_STATUSES = new Set(["ACTIVE", "FROZEN"]);
const EMBEDDED_QUERY_KEYS = ["embedded", "host", "locale", "shop"] as const;

type GraphQLErrorResponse = {
  message?: string;
};

type GraphQLResponse<T> = {
  data?: T;
  errors?: GraphQLErrorResponse[];
};

type MoneyValue = {
  amount: string;
  currencyCode: string;
};

type RecurringPricingDetails = {
  __typename: "AppRecurringPricing";
  interval: "EVERY_30_DAYS" | "ANNUAL";
  price: MoneyValue;
  planHandle?: string | null;
};

type UsagePricingDetails = {
  __typename: "AppUsagePricing";
  terms: string;
  cappedAmount: MoneyValue;
  balanceUsed: MoneyValue;
};

type SubscriptionPricingDetails = RecurringPricingDetails | UsagePricingDetails;

type BillingSubscription = {
  id: string;
  name: string;
  status: string;
  test: boolean;
  createdAt: string;
  currentPeriodEnd: string | null;
  trialDays: number | null;
  lineItems: Array<{
    id: string;
    plan: {
      pricingDetails: SubscriptionPricingDetails;
    };
  }>;
};

type BillingContextResponse = {
  shop: {
    name: string;
    plan: {
      partnerDevelopment: boolean;
      publicDisplayName: string;
      shopifyPlus: boolean;
    } | null;
  };
  shopBillingPreferences: {
    currency: string;
  };
  currentAppInstallation: {
    activeSubscriptions: BillingSubscription[];
    allSubscriptions: {
      edges: Array<{
        node: BillingSubscription;
      }>;
    };
  } | null;
};

type CreateSubscriptionResponse = {
  appSubscriptionCreate: {
    confirmationUrl: string | null;
    appSubscription: {
      id: string;
      name: string;
    } | null;
    userErrors: Array<{
      field: string[] | null;
      message: string;
    }>;
  };
};

export type ShopifyBillingContext = {
  shopName: string;
  shopPlanName: string | null;
  shopIsPlus: boolean;
  shopIsDevelopment: boolean;
  billingCurrency: string;
  activeSubscriptions: BillingSubscription[];
  allSubscriptions: BillingSubscription[];
};

export type ShopifyBillingStatus = {
  activeSubscription: BillingSubscription | null;
  subscriptions: BillingSubscription[];
  planName: string;
  billingInterval: BillingCycle | null;
  subscriptionStatus: string | null;
  currentPeriodEnd: string | null;
  trialDays: number | null;
  isTestSubscription: boolean | null;
  shopifySubscriptionId: string | null;
  recurringPrice: number | null;
  recurringCurrencyCode: string | null;
};

function buildGraphQLErrorMessage(errors: GraphQLErrorResponse[] | undefined): string {
  if (!errors || errors.length === 0) {
    return "Shopify GraphQL request failed.";
  }

  const messages = errors
    .map((entry) => entry.message?.trim())
    .filter((message): message is string => Boolean(message));

  return messages.length > 0 ? messages.join(" ") : "Shopify GraphQL request failed.";
}

function formatNetworkError(error: unknown): Error {
  if (error instanceof Error) {
    if (/Failed to fetch/i.test(error.message)) {
      return new Error(
        "Shopify Admin API is only available when this app is opened inside Shopify Admin with Direct API access enabled."
      );
    }

    return error;
  }

  return new Error("Shopify Admin API request failed.");
}

async function shopifyAdminRequest<T>(query: string, variables?: Record<string, unknown>): Promise<T> {
  try {
    const response = await fetch(SHOPIFY_ADMIN_GRAPHQL_URL, {
      method: "POST",
      body: JSON.stringify({
        query,
        variables
      })
    });

    const payload = (await response.json()) as GraphQLResponse<T>;

    if (!response.ok) {
      throw new Error(buildGraphQLErrorMessage(payload.errors));
    }

    if (payload.errors && payload.errors.length > 0) {
      throw new Error(buildGraphQLErrorMessage(payload.errors));
    }

    if (!payload.data) {
      throw new Error("Shopify GraphQL response did not include data.");
    }

    return payload.data;
  } catch (error) {
    throw formatNetworkError(error);
  }
}

function convertGraphQLInterval(interval: RecurringPricingDetails["interval"]): BillingCycle {
  return interval === "ANNUAL" ? "annual" : "monthly";
}

function getRecurringPricing(subscription: BillingSubscription | null): RecurringPricingDetails | null {
  if (!subscription) {
    return null;
  }

  for (const lineItem of subscription.lineItems) {
    if (lineItem.plan.pricingDetails.__typename === "AppRecurringPricing") {
      return lineItem.plan.pricingDetails;
    }
  }

  return null;
}

function getReturnUrl(pathname: string): string {
  const url = new URL(pathname, window.location.origin);
  const currentUrl = new URL(window.location.href);

  EMBEDDED_QUERY_KEYS.forEach((key) => {
    const value = currentUrl.searchParams.get(key);
    if (value) {
      url.searchParams.set(key, value);
    }
  });

  return url.toString();
}

export function getPreferredReturnPath(): string {
  return "/settings/billing";
}

export async function getBillingCatalog(currencyCode: string): Promise<BillingCatalogResponse> {
  const response = await fetch(`/api/shopify/billing/plans?currency=${encodeURIComponent(currencyCode)}`, {
    method: "GET",
    cache: "no-store"
  });

  const payload = (await response.json()) as BillingCatalogResponse | { error?: string };
  if (!response.ok) {
    throw new Error("error" in payload && payload.error ? payload.error : "Failed to load billing plans.");
  }

  return payload as BillingCatalogResponse;
}

export async function getShopifyBillingContext(): Promise<ShopifyBillingContext> {
  const query = `
    query BillingContext($historyLimit: Int!) {
      shop {
        name
        plan {
          partnerDevelopment
          publicDisplayName
          shopifyPlus
        }
      }
      shopBillingPreferences {
        currency
      }
      currentAppInstallation {
        activeSubscriptions {
          ...BillingSubscriptionFields
        }
        allSubscriptions(first: $historyLimit) {
          edges {
            node {
              ...BillingSubscriptionFields
            }
          }
        }
      }
    }

    fragment BillingSubscriptionFields on AppSubscription {
      id
      name
      status
      test
      createdAt
      currentPeriodEnd
      trialDays
      lineItems {
        id
        plan {
          pricingDetails {
            __typename
            ... on AppRecurringPricing {
              interval
              planHandle
              price {
                amount
                currencyCode
              }
            }
            ... on AppUsagePricing {
              terms
              cappedAmount {
                amount
                currencyCode
              }
              balanceUsed {
                amount
                currencyCode
              }
            }
          }
        }
      }
    }
  `;

  const response = await shopifyAdminRequest<BillingContextResponse>(query, {
    historyLimit: 20
  });

  const subscriptions = response.currentAppInstallation?.allSubscriptions.edges.map((edge) => edge.node) ?? [];

  return {
    shopName: response.shop.name,
    shopPlanName: response.shop.plan?.publicDisplayName ?? null,
    shopIsPlus: Boolean(response.shop.plan?.shopifyPlus),
    shopIsDevelopment: Boolean(response.shop.plan?.partnerDevelopment),
    billingCurrency: response.shopBillingPreferences.currency,
    activeSubscriptions: response.currentAppInstallation?.activeSubscriptions ?? [],
    allSubscriptions: subscriptions
  };
}

export function getBillingStatus(context: ShopifyBillingContext): ShopifyBillingStatus {
  const activeSubscription =
    context.activeSubscriptions.find((subscription) => ACTIVE_SUBSCRIPTION_STATUSES.has(subscription.status)) ??
    context.activeSubscriptions[0] ??
    null;
  const recurringPricing = getRecurringPricing(activeSubscription);

  return {
    activeSubscription,
    subscriptions: context.allSubscriptions,
    planName: activeSubscription?.name ?? "No active subscription",
    billingInterval: recurringPricing ? convertGraphQLInterval(recurringPricing.interval) : null,
    subscriptionStatus: activeSubscription?.status ?? null,
    currentPeriodEnd: activeSubscription?.currentPeriodEnd ?? null,
    trialDays: activeSubscription?.trialDays ?? null,
    isTestSubscription: activeSubscription?.test ?? null,
    shopifySubscriptionId: activeSubscription?.id ?? null,
    recurringPrice: recurringPricing ? Number.parseFloat(recurringPricing.price.amount) : null,
    recurringCurrencyCode: recurringPricing?.price.currencyCode ?? null
  };
}

export async function createRecurringSubscription(options: {
  plan: BillingPlanResponse;
  billingCycle: BillingCycle;
  testMode: boolean;
  returnPath?: string;
}): Promise<{ confirmationUrl: string; subscriptionId: string | null }> {
  const recurringPrice =
    options.billingCycle === "annual" ? options.plan.price_annual_total : options.plan.price_monthly;
  const trialDays = options.plan.trial_days;
  const query = `
    mutation CreateAppSubscription(
      $name: String!
      $returnUrl: URL!
      $lineItems: [AppSubscriptionLineItemInput!]!
      $test: Boolean
      $trialDays: Int
    ) {
      appSubscriptionCreate(
        name: $name
        returnUrl: $returnUrl
        lineItems: $lineItems
        test: $test
        trialDays: $trialDays
      ) {
        confirmationUrl
        appSubscription {
          id
          name
        }
        userErrors {
          field
          message
        }
      }
    }
  `;

  const response = await shopifyAdminRequest<CreateSubscriptionResponse>(query, {
    name: options.plan.display_name,
    returnUrl: getReturnUrl(options.returnPath ?? getPreferredReturnPath()),
    test: options.testMode,
    trialDays,
    lineItems: [
      {
        plan: {
          appRecurringPricingDetails: {
            interval: options.billingCycle === "annual" ? "ANNUAL" : "EVERY_30_DAYS",
            price: {
              amount: recurringPrice,
              currencyCode: options.plan.currency_code
            }
          }
        }
      }
    ]
  });

  const userErrors = response.appSubscriptionCreate.userErrors;
  if (userErrors.length > 0) {
    throw new Error(userErrors.map((entry) => entry.message).join(" "));
  }

  const confirmationUrl = response.appSubscriptionCreate.confirmationUrl;
  if (!confirmationUrl) {
    throw new Error("Shopify did not return a confirmation URL for the selected plan.");
  }

  return {
    confirmationUrl,
    subscriptionId: response.appSubscriptionCreate.appSubscription?.id ?? null
  };
}
