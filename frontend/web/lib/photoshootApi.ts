const DEFAULT_PROXY_BASE_PATH = "/api/backend";
const DEFAULT_TIMEOUT_MS = 150000;
const DEFAULT_POLL_MS = 2500;
const APP_BRIDGE_READY_TIMEOUT_MS = 5000;
const APP_BRIDGE_READY_POLL_MS = 50;

const SUCCESS_STATUSES = new Set(["completed", "succeeded", "success", "done"]);
const FAILURE_STATUSES = new Set(["failed", "error", "cancelled", "canceled"]);

type RequestMethod = "GET" | "POST" | "PATCH";

export type PhotoshootModelResponse = {
  id: string;
  gender: string;
  age: string | null;
  body_type: string | null;
  image_url: string;
};

export type PhotoshootModelFaceResponse = {
  id: string;
  gender: string;
  age: string | null;
  skin_tone: string | null;
  image_url: string;
};

export type PhotoshootJobResponse = {
  job_id: string;
  job_type: string;
  status: string;
  progress?: number | null;
  message?: string | null;
  result_image_url?: string | null;
  processing_time_seconds?: number | null;
  error?: string | null;
  retry_allowed?: boolean;
};

export type OnboardingStatusResponse = {
  store_id: string;
  onboarding_step: string;
  onboarding_completed: boolean;
  plan_name: string;
  billing_lock_reason?: string | null;
  trial_mode?: string | null;
  goals?: string[] | null;
  referral_source?: string | null;
  referral_detail?: string | null;
  scope_type?: string | null;
  enabled_collection_ids?: string[] | null;
  enabled_product_ids?: string[] | null;
  theme_extension_detected?: boolean;
};

export type OnboardingStepResponse = {
  saved: boolean;
  next_step: string;
};

export type WidgetScopeResponse = {
  scope_type: string;
  enabled_collection_ids: string[];
  enabled_product_ids: string[];
};

export type ThemeStatusResponse = {
  theme_extension_detected: boolean;
  themes_url: string;
  add_to_theme_url?: string;
};

export type DashboardOverviewResponse = {
  theme_extension_detected: boolean;
  themes_url: string;
  add_to_theme_url: string;
  tryon_used_30d: number;
  credits_limit: number;
  plan_name: string;
  scope_type: string;
  enabled_collections_count: number;
  enabled_products_count: number;
  feedback_submitted: boolean;
  billing_lock_reason?: string | null;
};

export type DashboardThemeStatusRecheckResponse = {
  theme_extension_detected: boolean;
  detection_source: "admin_theme_scan" | "runtime_flag" | "none";
  message?: string | null;
  themes_url: string;
  add_to_theme_url: string;
};

export type DashboardFeedbackRequest = {
  rating: number;
  improvement_text?: string | null;
};

export type DashboardFeedbackResponse = {
  saved: boolean;
  rating: number;
  submitted_at: string;
};

export type TopProductEntry = {
  shopify_product_id: string;
  title: string;
  try_on_count: number;
  cart_count: number;
  conversion_rate: number;
};

export type TrendEntry = {
  date: string;
  try_ons: number;
};

export type PerformanceTrendEntry = {
  date: string;
  try_on_sessions: number;
};

export type TopPerformingProductEntry = {
  shopify_product_id: string;
  title: string;
  try_on_sessions: number;
  conversion_rate: number | null;
  return_rate: number | null;
  revenue_impact: number | null;
};

export type StandardAnalyticsResponse = {
  period_days: number;
  period_start: string;
  period_end: string;
  widget_opens: number;
  unique_users: number;
  total_try_ons: number;
  credits_used: number;
  add_to_cart_count: number;
  conversions: number | null;
  conversion_rate: number | null;
  revenue_impact: number | null;
  return_count: number | null;
  return_reduction: number | null;
  active_users: number;
  anonymous_users: number;
  try_on_sessions: number;
  widget_click_rate: number | null;
  performance_trend: PerformanceTrendEntry[];
  top_performing_products: TopPerformingProductEntry[];
  top_products: TopProductEntry[];
  trend: TrendEntry[];
};

export type BillingStatusResponse = {
  plan_name: string;
  billing_interval: string | null;
  credits_limit: number;
  trial_ends_at: string | null;
  trial_mode?: string | null;
  trial_end_reason?: string | null;
  billing_lock_reason?: string | null;
  plan_activated_at: string | null;
  shopify_subscription_id: string | null;
  subscription_status: string | null;
  current_period_end: string | null;
  is_test_subscription: boolean | null;
  has_usage_billing: boolean;
  store_timezone: string | null;
};

export type BillingUsageSummaryResponse = {
  cycle_start_at: string | null;
  cycle_end_at: string | null;
  included_credits: number;
  consumed_credits: number;
  remaining_included_credits: number;
  overage_credits: number;
  overage_amount_usd: number;
  overage_blocked: boolean;
  overage_block_reason: string | null;
  overage_block_message: string | null;
  can_auto_charge_overage: boolean;
};

export type PlanConfigResponse = {
  id: string;
  name: string;
  display_name: string;
  price_monthly: number;
  price_annual_total: number;
  price_annual_per_month: number;
  annual_discount_pct: number;
  credits_monthly: number;
  credits_annual: number;
  overage_usd_per_tryon: number;
  usage_cap_usd: number;
  trial_days: number | null;
  trial_credits: number | null;
  features: string[];
  is_current: boolean;
  is_active: boolean;
};

export type PlansResponse = {
  plans: PlanConfigResponse[];
};

export type PlanResponse = {
  plan_name: string;
  credits_limit: number;
  plan_activated_at?: string | null;
  shopify_subscription_id?: string | null;
};

export type CreateSubscriptionRequest = {
  plan_name: string;
  billing_interval: "monthly" | "annual";
  return_url: string;
};

export type CreateSubscriptionResponse = {
  confirmation_url: string;
  shopify_subscription_id: string;
};

export type WidgetConfigResponse = {
  scope_type: string;
  enabled_collection_ids: string[];
  enabled_product_ids: string[];
  theme_extension_detected: boolean;
  widget_color: string;
  weekly_tryon_limit: number;
};

export type WidgetConfigUpdateRequest = {
  scope_type?: string | null;
  enabled_collection_ids?: string[] | null;
  enabled_product_ids?: string[] | null;
  theme_extension_detected?: boolean | null;
  widget_color?: string | null;
  weekly_tryon_limit?: number | null;
};

export type ProductImage = {
  src: string;
  alt: string | null;
};

export type ProductVariant = {
  id: string;
  title: string;
  sku: string | null;
  price: string;
  size: string | null;
};

export type ProductResponse = {
  shopify_product_id: string;
  title: string;
  description: string | null;
  product_type: string | null;
  category: string;
  vendor: string | null;
  images: ProductImage[];
  variants: ProductVariant[];
  has_size_chart: boolean;
  product_id: string;
  store_id: string;
  last_synced_at: string;
  created_at: string;
};

export type ProductSyncResponse = {
  status: string;
  products_synced: number;
  products_with_sizes: number;
  products_without_sizes: number;
  timestamp: string;
};

export type CollectionResponse = {
  id: string;
  title: string;
  handle: string | null;
  image_url: string | null;
  products_count: number | null;
};

type PollOptions = {
  timeoutMs?: number;
  intervalMs?: number;
  onUpdate?: (job: PhotoshootJobResponse) => void;
};

type ShopifyGlobal = {
  config?: {
    shop?: string;
  };
  ready?: () => Promise<void>;
  idToken?: (() => Promise<string>) | { get?: () => Promise<string> };
};

function getApiBaseUrl(): string {
  return DEFAULT_PROXY_BASE_PATH;
}

export function getDefaultStoreId(): string {
  return getDefaultShopDomain();
}

function getConfiguredShopDomain(): string {
  return normalizeShopDomain(process.env.NEXT_PUBLIC_SHOPIFY_SHOP_DOMAIN);
}

function getShopifyGlobal(): ShopifyGlobal | null {
  if (typeof window === "undefined") {
    return null;
  }

  return (globalThis as { shopify?: ShopifyGlobal }).shopify ?? null;
}

function getAppBridgeShopDomain(): string {
  const shopify = getShopifyGlobal();
  return normalizeShopDomain(shopify?.config?.shop);
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function getShopifySessionToken(): Promise<string> {
  if (typeof window === "undefined") {
    return "";
  }

  // If not running inside an iframe (e.g. after billing redirect), App Bridge will never
  // initialize — skip the wait entirely to avoid blocking API calls for 8 seconds.
  if (window.self === window.top) {
    return "";
  }

  // Wait for App Bridge 4.x to finish initializing before asking for the token.
  // shopify.ready() resolves once the bridge is fully set up; if unavailable, continue anyway.
  try {
    const shopify = getShopifyGlobal();
    if (shopify && typeof shopify.ready === "function") {
      await shopify.ready();
    }
  } catch {
    // ready() not available or failed — fall through to polling loop
  }

  const startedAt = Date.now();
  while (Date.now() - startedAt < APP_BRIDGE_READY_TIMEOUT_MS) {
    const shopify = getShopifyGlobal();
    const idToken = shopify?.idToken;

    try {
      if (typeof idToken === "function") {
        const token = await idToken();
        if (typeof token === "string" && token.trim().length > 0) {
          return token.trim();
        }
      }

      if (idToken && typeof idToken === "object" && typeof idToken.get === "function") {
        const token = await idToken.get();
        if (typeof token === "string" && token.trim().length > 0) {
          return token.trim();
        }
      }
    } catch {
      // idToken() threw — App Bridge may still be initializing; continue polling
    }

    await sleep(APP_BRIDGE_READY_POLL_MS);
  }

  return "";
}

function normalizeShopDomain(value: string | null | undefined): string {
  if (!value) {
    return "";
  }

  const sanitized = value.trim().toLowerCase().replace(/^https?:\/\//, "").replace(/\/.*$/, "");
  if (!/^[a-z0-9][a-z0-9-]*\.myshopify\.com$/.test(sanitized)) {
    return "";
  }

  return sanitized;
}

function getActiveShopDomain(): string {
  const fromAppBridge = getAppBridgeShopDomain();
  if (fromAppBridge) {
    return fromAppBridge;
  }

  if (typeof window !== "undefined") {
    const params = new URLSearchParams(window.location.search);
    const fromQuery = normalizeShopDomain(params.get("shop"));
    if (fromQuery) {
      return fromQuery;
    }

    const fromSession = normalizeShopDomain(window.sessionStorage.getItem("shopify_shop_domain"));
    if (fromSession) {
      return fromSession;
    }

    return normalizeShopDomain(window.localStorage.getItem("shopify_shop_domain"));
  }

  return "";
}

export function getDefaultShopDomain(): string {
  const activeShopDomain = getActiveShopDomain();
  if (activeShopDomain) {
    return activeShopDomain;
  }

  if (typeof window !== "undefined" && window.top !== window.self) {
    return "";
  }

  return getConfiguredShopDomain();
}

export function getDefaultProductGid(): string {
  return process.env.NEXT_PUBLIC_DEFAULT_PRODUCT_GID?.trim() ?? "";
}

export function getDefaultProductImageUrl(): string {
  return process.env.NEXT_PUBLIC_DEFAULT_PRODUCT_IMAGE_URL?.trim() ?? "";
}

export function getBillingReturnUrl(): string {
  const configured = process.env.NEXT_PUBLIC_BILLING_RETURN_URL?.trim();
  if (configured) {
    return configured;
  }

  if (typeof window !== "undefined") {
    return `${window.location.origin}/dashboard`;
  }

  return "/dashboard";
}

export function resolveBackendUrl(pathOrUrl: string): string {
  if (!pathOrUrl) {
    return "";
  }

  if (/^https?:\/\//i.test(pathOrUrl)) {
    return pathOrUrl;
  }

  const baseUrl = getApiBaseUrl();
  return `${baseUrl}${pathOrUrl.startsWith("/") ? "" : "/"}${pathOrUrl}`;
}

function createUrl(path: string, query?: Record<string, string | number | null | undefined>): string {
  const params = new URLSearchParams();
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (typeof value === "string" && value.trim().length > 0) {
        params.set(key, value);
      }

      if (typeof value === "number") {
        params.set(key, String(value));
      }
    }
  }

  const search = params.toString();
  return `${getApiBaseUrl()}${path}${search ? `?${search}` : ""}`;
}

function getErrorDetail(payload: unknown): string | null {
  if (!payload || typeof payload !== "object") {
    return null;
  }

  const candidate = payload as {
    detail?: unknown;
    error?: unknown;
    message?: unknown;
  };

  const detail = candidate.detail;
  if (typeof detail === "string" && detail.trim().length > 0) {
    return detail;
  }

  const error = candidate.error;
  if (typeof error === "string" && error.trim().length > 0) {
    return error;
  }

  const message = candidate.message;
  if (typeof message === "string" && message.trim().length > 0) {
    return message;
  }

  return null;
}

function isStoreNotFoundPayload(payload: unknown): boolean {
  const detail = getErrorDetail(payload);
  return Boolean(detail && /store not found/i.test(detail));
}

function readErrorMessage(status: number, payload: unknown): string {
  if (payload && typeof payload === "object") {
    const detail = getErrorDetail(payload);
    if (detail) {
      if (/missing session token/i.test(detail)) {
        return "Missing Shopify session token. Open the app from the Shopify Admin preview link so App Bridge can authenticate requests.";
      }

      if (/signature verification failed/i.test(detail)) {
        return "Shopify session token was generated, but the upstream backend rejected its signature. Verify that the backend is configured for the same Shopify app as this frontend.";
      }

      if (/store not found/i.test(detail)) {
        return "Backend could not resolve the active Shopify store. Open the app from Shopify Admin so the store context can be provisioned, then retry.";
      }

      if (/no session token was provided/i.test(detail)) {
        return "Open the app from Shopify Admin (embedded) so App Bridge can provide a session token, then retry.";
      }

      if (/session token exchange failed/i.test(detail)) {
        return "Shopify install/auth is still incomplete for this shop. Complete the backend Shopify auth flow, then retry.";
      }

      if (/denied access to products/i.test(detail) || /access denied for products field/i.test(detail)) {
        return "Shopify denied product access. Reinstall or reauthorize the app so read_products scope is approved, then retry sync.";
      }

      if (/store installation is incomplete/i.test(detail)) {
        return "The backend store record exists, but Shopify install/auth has not finished yet. Complete the backend Shopify auth flow for this shop before using this action.";
      }

      return detail;
    }

    if (Array.isArray(detail)) {
      const first = detail[0];
      if (first && typeof first === "object" && "msg" in first) {
        const message = (first as { msg?: unknown }).msg;
        if (typeof message === "string" && message.trim().length > 0) {
          return message;
        }
      }
    }
  }

  return `API request failed with status ${status}.`;
}

async function parseResponse(response: Response): Promise<unknown> {
  const contentType = response.headers.get("content-type") ?? "";

  if (contentType.includes("application/json")) {
    return response.json();
  }

  return response.text();
}

async function requestJson<T>(
  path: string,
  options: {
    method?: RequestMethod;
    storeId?: string;
    shopDomain?: string;
    query?: Record<string, string | number | null | undefined>;
    body?: FormData | Record<string, unknown>;
    signal?: AbortSignal;
  }
  ): Promise<T> {
  const headers = new Headers();
  const activeShopDomain = normalizeShopDomain(options.shopDomain) || getActiveShopDomain();
  const resolvedShopDomain = activeShopDomain || normalizeShopDomain(options.storeId) || getConfiguredShopDomain();

  if (resolvedShopDomain) {
    headers.set("X-Shopify-Shop-Domain", resolvedShopDomain);
    headers.set("X-Shop-Domain", resolvedShopDomain);

    if (typeof window !== "undefined") {
      window.sessionStorage.setItem("shopify_shop_domain", resolvedShopDomain);
      window.localStorage.setItem("shopify_shop_domain", resolvedShopDomain);
    }
  }

  const isFormData = options.body instanceof FormData;
  let requestBody: BodyInit | undefined;

  if (options.body instanceof FormData) {
    requestBody = options.body;
  } else if (options.body !== undefined) {
    requestBody = JSON.stringify(options.body);
  }

  if (requestBody && !isFormData) {
    headers.set("Content-Type", "application/json");
  }

  const sessionToken = await getShopifySessionToken();
  if (sessionToken) {
    headers.set("Authorization", `Bearer ${sessionToken}`);
  }

  const response = await fetch(createUrl(path, options.query), {
    method: options.method ?? "GET",
    headers,
    body: requestBody,
    signal: options.signal
  });

  const payload = await parseResponse(response);

  if (!response.ok) {
    if (
      response.status === 404 &&
      path.startsWith("/api/v1/merchant/") &&
      resolvedShopDomain &&
      isStoreNotFoundPayload(payload)
    ) {
      throw new Error(
        `Backend could not resolve the store record for ${resolvedShopDomain}. Open the embedded app once so the backend can provision it, or complete the backend Shopify install/auth flow for this shop.`
      );
    }

    throw new Error(readErrorMessage(response.status, payload));
  }

  return payload as T;
}

export async function getOnboardingStatus(options: {
  storeId: string;
  signal?: AbortSignal;
}): Promise<OnboardingStatusResponse> {
  return requestJson<OnboardingStatusResponse>("/api/v1/merchant/onboarding/status", {
    method: "GET",
    storeId: options.storeId,
    signal: options.signal
  });
}

export async function saveOnboardingGoals(options: {
  storeId: string;
  goals: string[];
}): Promise<OnboardingStepResponse> {
  return requestJson<OnboardingStepResponse>("/api/v1/merchant/onboarding/goals", {
    method: "POST",
    storeId: options.storeId,
    body: {
      goals: options.goals
    }
  });
}

export async function saveReferral(options: {
  storeId: string;
  referralSource: string;
  referralDetail?: string;
}): Promise<OnboardingStepResponse> {
  return requestJson<OnboardingStepResponse>("/api/v1/merchant/onboarding/referral", {
    method: "POST",
    storeId: options.storeId,
    body: {
      referral_source: options.referralSource,
      referral_detail: options.referralDetail ?? null
    }
  });
}

export async function getWidgetScope(options: {
  storeId: string;
  signal?: AbortSignal;
}): Promise<WidgetScopeResponse> {
  return requestJson<WidgetScopeResponse>("/api/v1/merchant/onboarding/widget-scope", {
    method: "GET",
    storeId: options.storeId,
    signal: options.signal
  });
}

export async function saveWidgetScope(options: {
  storeId: string;
  scopeType: string;
  enabledCollectionIds?: string[];
  enabledProductIds?: string[];
}): Promise<WidgetScopeResponse> {
  return requestJson<WidgetScopeResponse>("/api/v1/merchant/onboarding/widget-scope", {
    method: "POST",
    storeId: options.storeId,
    body: {
      scope_type: options.scopeType,
      enabled_collection_ids: options.enabledCollectionIds ?? [],
      enabled_product_ids: options.enabledProductIds ?? []
    }
  });
}

export async function getThemeStatus(options: {
  storeId: string;
  signal?: AbortSignal;
}): Promise<ThemeStatusResponse> {
  return requestJson<ThemeStatusResponse>("/api/v1/merchant/onboarding/theme-status", {
    method: "GET",
    storeId: options.storeId,
    signal: options.signal
  });
}

export async function recheckOnboardingThemeStatus(options: {
  storeId: string;
  signal?: AbortSignal;
}): Promise<DashboardThemeStatusRecheckResponse> {
  return requestJson<DashboardThemeStatusRecheckResponse>("/api/v1/merchant/onboarding/theme-status/recheck", {
    method: "POST",
    storeId: options.storeId,
    signal: options.signal
  });
}

export async function updateThemeStatus(options: {
  storeId: string;
  detected: boolean;
}): Promise<OnboardingStepResponse> {
  return requestJson<OnboardingStepResponse>("/api/v1/merchant/onboarding/theme-status", {
    method: "POST",
    storeId: options.storeId,
    body: {
      detected: options.detected
    }
  });
}

export async function startIntroFreeTrial(options: {
  storeId: string;
}): Promise<OnboardingStepResponse> {
  return requestJson<OnboardingStepResponse>("/api/v1/merchant/onboarding/start-free-trial", {
    method: "POST",
    storeId: options.storeId
  });
}

export async function completeOnboardingFromBilling(options: {
  storeId: string;
}): Promise<OnboardingStepResponse> {
  return requestJson<OnboardingStepResponse>("/api/v1/merchant/onboarding/complete-from-billing", {
    method: "POST",
    storeId: options.storeId
  });
}

export async function getDashboardOverview(options: {
  storeId: string;
  signal?: AbortSignal;
}): Promise<DashboardOverviewResponse> {
  return requestJson<DashboardOverviewResponse>("/api/v1/merchant/dashboard/overview", {
    method: "GET",
    storeId: options.storeId,
    signal: options.signal
  });
}

export async function recheckDashboardThemeStatus(options: {
  storeId: string;
  signal?: AbortSignal;
}): Promise<DashboardThemeStatusRecheckResponse> {
  return requestJson<DashboardThemeStatusRecheckResponse>("/api/v1/merchant/dashboard/theme-status/recheck", {
    method: "POST",
    storeId: options.storeId,
    signal: options.signal
  });
}

export async function submitDashboardFeedback(options: {
  storeId: string;
  payload: DashboardFeedbackRequest;
}): Promise<DashboardFeedbackResponse> {
  return requestJson<DashboardFeedbackResponse>("/api/v1/merchant/dashboard/feedback", {
    method: "POST",
    storeId: options.storeId,
    body: options.payload
  });
}

export async function getStandardAnalytics(options: {
  storeId: string;
  period?: number;
  signal?: AbortSignal;
}): Promise<StandardAnalyticsResponse> {
  return requestJson<StandardAnalyticsResponse>("/api/v1/merchant/analytics/standard", {
    method: "GET",
    storeId: options.storeId,
    query: {
      period: options.period ?? 30
    },
    signal: options.signal
  });
}

export async function getBillingStatus(options: {
  storeId: string;
  signal?: AbortSignal;
}): Promise<BillingStatusResponse> {
  return requestJson<BillingStatusResponse>("/api/v1/merchant/billing/status", {
    method: "GET",
    storeId: options.storeId,
    signal: options.signal
  });
}

export async function getBillingUsageSummary(options: {
  storeId: string;
  signal?: AbortSignal;
}): Promise<BillingUsageSummaryResponse> {
  return requestJson<BillingUsageSummaryResponse>("/api/v1/merchant/billing/usage-summary", {
    method: "GET",
    storeId: options.storeId,
    signal: options.signal
  });
}

export async function getBillingPlans(options: {
  storeId: string;
  signal?: AbortSignal;
}): Promise<PlansResponse> {
  return requestJson<PlansResponse>("/api/v1/merchant/billing/plans", {
    method: "GET",
    storeId: options.storeId,
    signal: options.signal
  });
}

export async function getCurrentPlan(options: {
  storeId: string;
  signal?: AbortSignal;
}): Promise<PlanResponse> {
  return requestJson<PlanResponse>("/api/v1/merchant/billing/plan", {
    method: "GET",
    storeId: options.storeId,
    signal: options.signal
  });
}

export async function createSubscription(options: {
  storeId: string;
  planName: string;
  billingInterval: "monthly" | "annual";
  returnUrl: string;
}): Promise<CreateSubscriptionResponse> {
  return requestJson<CreateSubscriptionResponse>("/api/v1/merchant/billing/create-subscription", {
    method: "POST",
    storeId: options.storeId,
    body: {
      plan_name: options.planName,
      billing_interval: options.billingInterval,
      return_url: options.returnUrl
    }
  });
}

export type BillingActivateResponse = {
  plan_name: string;
  credits_limit: number;
  plan_activated_at: string | null;
  shopify_subscription_id: string | null;
};

export async function activateBillingPlan(options: {
  storeId: string;
  planName: string;
  billingInterval: "monthly" | "annual";
  shopifySubscriptionId: string;
}): Promise<BillingActivateResponse> {
  return requestJson<BillingActivateResponse>("/api/v1/merchant/billing/activate", {
    method: "POST",
    storeId: options.storeId,
    body: {
      plan_name: options.planName,
      billing_interval: options.billingInterval,
      shopify_subscription_id: options.shopifySubscriptionId,
      status: "active"
    }
  });
}

export type CancelSubscriptionResponse = {
  cancelled: boolean;
  plan_name: string;
  credits_limit: number;
};

export async function cancelSubscription(options: {
  storeId: string;
}): Promise<CancelSubscriptionResponse> {
  return requestJson<CancelSubscriptionResponse>("/api/v1/merchant/billing/cancel-subscription", {
    method: "POST",
    storeId: options.storeId
  });
}

export async function getWidgetConfig(options: {
  storeId: string;
  signal?: AbortSignal;
}): Promise<WidgetConfigResponse> {
  return requestJson<WidgetConfigResponse>("/api/v1/merchant/widget-config", {
    method: "GET",
    storeId: options.storeId,
    signal: options.signal
  });
}

export async function updateWidgetConfig(options: {
  storeId: string;
  payload: WidgetConfigUpdateRequest;
}): Promise<WidgetConfigResponse> {
  return requestJson<WidgetConfigResponse>("/api/v1/merchant/widget-config", {
    method: "PATCH",
    storeId: options.storeId,
    body: options.payload
  });
}

export async function listProducts(options: {
  storeId: string;
  category?: string | null;
  limit?: number;
  offset?: number;
  signal?: AbortSignal;
}): Promise<ProductResponse[]> {
  return requestJson<ProductResponse[]>("/api/v1/products", {
    method: "GET",
    storeId: options.storeId,
    query: {
      category: options.category,
      limit: options.limit ?? 50,
      offset: options.offset ?? 0
    },
    signal: options.signal
  });
}

export async function syncProducts(options: {
  storeId: string;
}): Promise<ProductSyncResponse> {
  return requestJson<ProductSyncResponse>("/api/v1/products/sync", {
    method: "POST",
    storeId: options.storeId
  });
}

const configuredCollectionsRoute = process.env.NEXT_PUBLIC_COLLECTIONS_API_PATH?.trim();
const COLLECTION_ROUTE_CANDIDATES = [
  configuredCollectionsRoute,
  "/api/v1/merchant/collections",
  "/api/v1/collections/",
  "/api/v1/shopify/collections"
].filter((value): value is string => !!value && value.length > 0);

let resolvedCollectionsRoute: string | null = null;
let collectionsRouteUnavailable = false;

function isNotFoundError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error);
  return /status 404/i.test(message) || /not found/i.test(message);
}

function toCollectionResponse(item: unknown): CollectionResponse | null {
  if (!item || typeof item !== "object") {
    return null;
  }

  const source = item as Record<string, unknown>;
  const idCandidates = [source.id, source.shopify_collection_id, source.collection_id];
  const id = idCandidates.find((value) => typeof value === "string" && value.trim().length > 0);

  if (typeof id !== "string") {
    return null;
  }

  const titleCandidates = [source.title, source.name, source.handle];
  const title = titleCandidates.find((value) => typeof value === "string" && value.trim().length > 0);
  const handle = typeof source.handle === "string" && source.handle.trim() ? source.handle.trim() : null;
  const imageUrl =
    typeof source.image_url === "string"
      ? source.image_url
      : source.image && typeof source.image === "object" && "url" in source.image
        ? String((source.image as { url?: unknown }).url ?? "")
        : "";
  const productsCountRaw = source.products_count;
  const productsCount =
    typeof productsCountRaw === "number"
      ? productsCountRaw
      : typeof productsCountRaw === "string"
        ? Number.parseInt(productsCountRaw, 10)
        : null;

  return {
    id: id.trim(),
    title: typeof title === "string" ? title.trim() : id.trim(),
    handle,
    image_url: imageUrl || null,
    products_count: Number.isFinite(productsCount) ? productsCount : null
  };
}

function parseCollectionsPayload(payload: unknown): CollectionResponse[] {
  const candidateLists: unknown[] = [];

  if (Array.isArray(payload)) {
    candidateLists.push(payload);
  }

  if (payload && typeof payload === "object") {
    const source = payload as Record<string, unknown>;
    candidateLists.push(source.collections, source.items, source.data);

    if (source.data && typeof source.data === "object") {
      const nested = source.data as Record<string, unknown>;
      candidateLists.push(nested.collections, nested.items);
    }
  }

  for (const candidate of candidateLists) {
    if (!Array.isArray(candidate)) {
      continue;
    }

    const normalized = candidate.map(toCollectionResponse).filter((value): value is CollectionResponse => !!value);
    if (normalized.length > 0 || candidate.length === 0) {
      return normalized;
    }
  }

  return [];
}

export async function listCollections(options: {
  storeId: string;
  limit?: number;
  offset?: number;
  search?: string | null;
  signal?: AbortSignal;
}): Promise<CollectionResponse[]> {
  const requestOptions = {
    method: "GET" as RequestMethod,
    storeId: options.storeId,
    query: {
      limit: options.limit ?? 100,
      offset: options.offset ?? 0,
      search: options.search ?? null
    },
    signal: options.signal
  };

  if (resolvedCollectionsRoute) {
    const payload = await requestJson<unknown>(resolvedCollectionsRoute, requestOptions);
    return parseCollectionsPayload(payload);
  }

  if (collectionsRouteUnavailable) {
    return [];
  }

  let lastError: unknown = null;

  for (const path of COLLECTION_ROUTE_CANDIDATES) {
    try {
      const payload = await requestJson<unknown>(path, requestOptions);
      resolvedCollectionsRoute = path;

      return parseCollectionsPayload(payload);
    } catch (error: unknown) {
      lastError = error;
      if (isNotFoundError(error)) {
        continue;
      }

      throw error;
    }
  }

  if (lastError && !isNotFoundError(lastError)) {
    throw lastError;
  }

  collectionsRouteUnavailable = true;
  return [];
}

export async function listPhotoshootModels(options: {
  storeId: string;
  gender: string;
  age?: string | null;
  bodyType?: string | null;
  signal?: AbortSignal;
}): Promise<PhotoshootModelResponse[]> {
  return requestJson<PhotoshootModelResponse[]>("/api/v1/merchant/photoshoot/models", {
    method: "GET",
    storeId: options.storeId,
    query: {
      gender: options.gender,
      age: options.age,
      body_type: options.bodyType
    },
    signal: options.signal
  });
}

export async function listModelFaces(options: {
  storeId: string;
  gender: string;
  age?: string | null;
  skinTone?: string | null;
  signal?: AbortSignal;
}): Promise<PhotoshootModelFaceResponse[]> {
  return requestJson<PhotoshootModelFaceResponse[]>("/api/v1/merchant/photoshoot/model-faces", {
    method: "GET",
    storeId: options.storeId,
    query: {
      gender: options.gender,
      age: options.age,
      skin_tone: options.skinTone
    },
    signal: options.signal
  });
}

export async function startTryOnModelJob(options: {
  storeId: string;
  shopifyProductGid: string;
  productImageUrl: string;
  modelLibraryId?: string | null;
  modelImage?: File | null;
}): Promise<PhotoshootJobResponse> {
  const formData = new FormData();
  formData.append("shopify_product_gid", options.shopifyProductGid);
  formData.append("product_image_url", options.productImageUrl);

  if (options.modelLibraryId) {
    formData.append("model_library_id", options.modelLibraryId);
  }

  if (options.modelImage) {
    formData.append("model_image", options.modelImage);
  }

  return requestJson<PhotoshootJobResponse>("/api/v1/merchant/photoshoot/try-on-model", {
    method: "POST",
    storeId: options.storeId,
    body: formData
  });
}

export async function startModelSwapJob(options: {
  storeId: string;
  shopifyProductGid: string;
  originalImageUrl: string;
  faceLibraryId?: string | null;
  faceImage?: File | null;
}): Promise<PhotoshootJobResponse> {
  const formData = new FormData();
  formData.append("shopify_product_gid", options.shopifyProductGid);
  formData.append("original_image_url", options.originalImageUrl);

  if (options.faceLibraryId) {
    formData.append("face_library_id", options.faceLibraryId);
  }

  if (options.faceImage) {
    formData.append("face_image", options.faceImage);
  }

  return requestJson<PhotoshootJobResponse>("/api/v1/merchant/photoshoot/model-swap", {
    method: "POST",
    storeId: options.storeId,
    body: formData
  });
}

export async function getPhotoshootJobStatus(options: {
  storeId: string;
  jobId: string;
  signal?: AbortSignal;
}): Promise<PhotoshootJobResponse> {
  return requestJson<PhotoshootJobResponse>(`/api/v1/merchant/photoshoot/jobs/${options.jobId}/status`, {
    method: "GET",
    storeId: options.storeId,
    signal: options.signal
  });
}

export function isSuccessStatus(status: string): boolean {
  return SUCCESS_STATUSES.has(status.toLowerCase());
}

export function isFailureStatus(status: string): boolean {
  return FAILURE_STATUSES.has(status.toLowerCase());
}

export async function pollPhotoshootJob(
  storeId: string,
  jobId: string,
  options: PollOptions = {}
): Promise<PhotoshootJobResponse> {
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const intervalMs = options.intervalMs ?? DEFAULT_POLL_MS;
  const deadline = Date.now() + timeoutMs;

  while (Date.now() < deadline) {
    const job = await getPhotoshootJobStatus({ storeId, jobId });
    options.onUpdate?.(job);

    if (isSuccessStatus(job.status) || isFailureStatus(job.status)) {
      return job;
    }

    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }

  throw new Error("Timed out while waiting for job completion.");
}

export function buildJobResultUrl(jobId: string): string {
  return resolveBackendUrl(`/api/v1/merchant/photoshoot/jobs/${jobId}/result`);
}
