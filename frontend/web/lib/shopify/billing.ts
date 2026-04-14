"use client";

const SHOPIFY_ADMIN_GRAPHQL_URL = "shopify:admin/api/2026-01/graphql.json";
const ACTIVE_SUBSCRIPTION_STATUSES = new Set(["ACTIVE", "FROZEN"]);

type BillingCycle = "monthly" | "annual";

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
  if (!errors || errors.length === 0) return "Shopify GraphQL request failed.";
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

async function waitForAppBridge(): Promise<void> {
  const deadline = Date.now() + 8000;
  while (Date.now() < deadline) {
    const shopify = (globalThis as { shopify?: { ready?: unknown } }).shopify;
    if (shopify?.ready) {
      if (shopify.ready instanceof Promise) {
        await shopify.ready;
      } else if (typeof shopify.ready === "function") {
        await (shopify.ready as () => Promise<void>)();
      }
      return;
    }
    await new Promise<void>((resolve) => setTimeout(resolve, 50));
  }
}

async function shopifyAdminRequest<T>(query: string, variables?: Record<string, unknown>): Promise<T> {
  await waitForAppBridge();
  try {
    const response = await fetch(SHOPIFY_ADMIN_GRAPHQL_URL, {
      method: "POST",
      body: JSON.stringify({ query, variables })
    });

    const payload = (await response.json()) as GraphQLResponse<T>;

    if (!response.ok) throw new Error(buildGraphQLErrorMessage(payload.errors));
    if (payload.errors && payload.errors.length > 0) throw new Error(buildGraphQLErrorMessage(payload.errors));
    if (!payload.data) throw new Error("Shopify GraphQL response did not include data.");

    return payload.data;
  } catch (error) {
    throw formatNetworkError(error);
  }
}

function convertGraphQLInterval(interval: RecurringPricingDetails["interval"]): BillingCycle {
  return interval === "ANNUAL" ? "annual" : "monthly";
}

function getRecurringPricing(subscription: BillingSubscription | null): RecurringPricingDetails | null {
  if (!subscription) return null;
  for (const lineItem of subscription.lineItems) {
    if (lineItem.plan.pricingDetails.__typename === "AppRecurringPricing") {
      return lineItem.plan.pricingDetails;
    }
  }
  return null;
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

  const response = await shopifyAdminRequest<BillingContextResponse>(query, { historyLimit: 20 });

  const subscriptions = response.currentAppInstallation?.allSubscriptions.edges.map((edge) => edge.node) ?? [];

  return {
    shopName: response.shop.name,
    shopPlanName: response.shop.plan?.publicDisplayName ?? null,
    shopIsPlus: Boolean(response.shop.plan?.shopifyPlus),
    shopIsDevelopment:
      response.shop.plan == null ||
      Boolean(response.shop.plan.partnerDevelopment) ||
      response.shop.plan.publicDisplayName?.toLowerCase().includes("development") === true,
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

type CreateSubscriptionResponse = {
  appSubscriptionCreate: {
    confirmationUrl: string | null;
    appSubscription: { id: string; name: string; test: boolean } | null;
    userErrors: Array<{ field: string[] | null; message: string }>;
  };
};

function getReturnUrl(returnPath: string): string {
  return new URL(returnPath, window.location.origin).toString();
}

export async function createRecurringSubscription(options: {
  planDisplayName: string;
  priceAmount: number;
  billingCycle: BillingCycle;
  trialDays: number | null;
  testMode: boolean;
  returnPath: string;
}): Promise<{ confirmationUrl: string; subscriptionId: string | null }> {
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
        appSubscription { id name test }
        userErrors { field message }
      }
    }
  `;

  const response = await shopifyAdminRequest<CreateSubscriptionResponse>(query, {
    name: options.planDisplayName,
    returnUrl: getReturnUrl(options.returnPath),
    test: options.testMode,
    trialDays: options.trialDays,
    lineItems: [
      {
        plan: {
          appRecurringPricingDetails: {
            interval: options.billingCycle === "annual" ? "ANNUAL" : "EVERY_30_DAYS",
            price: { amount: options.priceAmount, currencyCode: "USD" }
          }
        }
      }
    ]
  });

  const userErrors = response.appSubscriptionCreate.userErrors;
  if (userErrors.length > 0) {
    throw new Error(userErrors.map((e) => e.message).join(" "));
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
