import { createHmac, randomUUID, timingSafeEqual } from "node:crypto";
import { NextRequest, NextResponse } from "next/server";

const FORWARDED_REQUEST_HEADERS = [
  "accept",
  "content-type",
  "x-session-id",
  "x-store-id",
  "x-shop-domain",
  "x-shopify-shop-domain",
  "x-logged-in-customer-id",
  "x-forwarded-for",
  "x-real-ip"
] as const;

const FORWARDED_RESPONSE_HEADERS = [
  "cache-control",
  "content-disposition",
  "content-type",
  "location"
] as const;

const SHOPIFY_PROXY_QUERY_KEYS = new Set([
  "hmac",
  "locale",
  "logged_in_customer_id",
  "path_prefix",
  "session_id",
  "shop",
  "signature",
  "timestamp"
]);

const ANON_COOKIE_NAME = "optimo_vts_anon";
const ANON_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 180;
const DEFAULT_PROXY_MAX_SKEW_SECONDS = 300;

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

function getShopifyApiSecret(): string {
  return (
    process.env.SHOPIFY_API_SECRET?.trim() ||
    process.env.SHOPIFY_API_SECRET_KEY?.trim() ||
    ""
  );
}

function getProxySharedSecret(): string {
  return (
    process.env.WIDGET_PROXY_SHARED_SECRET?.trim() ||
    getShopifyApiSecret()
  );
}

function getUpstreamBaseUrl(): string {
  const configuredUrl =
    process.env.API_BASE_URL?.trim() ||
    process.env.BACKEND_URL?.trim() ||
    process.env.NEXT_PUBLIC_API_BASE_URL?.trim() ||
    "";

  return configuredUrl.replace(/\/+$/, "");
}

function getMaxProxySkewSeconds(): number {
  const raw = process.env.WIDGET_PROXY_MAX_SKEW_SECONDS?.trim() || "";
  const parsed = Number(raw);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return DEFAULT_PROXY_MAX_SKEW_SECONDS;
  }
  return Math.floor(parsed);
}

function isProxySignatureDebugEnabled(): boolean {
  const raw = process.env.WIDGET_PROXY_DEBUG_SIGNATURE?.trim().toLowerCase() ?? "";
  return raw === "1" || raw === "true" || raw === "yes" || raw === "on";
}

function toPrefix(value: string, length = 8): string {
  return (value || "").slice(0, length);
}

function logProxySignatureFailure(args: {
  reason: "missing" | "stale" | "invalid";
  request: NextRequest;
  timestampRaw: string;
  nowSeconds: number;
  providedHmac?: string;
  providedSignature?: string;
  expectedCandidates?: string[];
}): void {
  if (!isProxySignatureDebugEnabled()) {
    return;
  }

  const shop = normalizeShopDomain(args.request.nextUrl.searchParams.get("shop"));
  console.warn("Widget proxy signature verification failed", {
    reason: args.reason,
    shop,
    path: args.request.nextUrl.pathname,
    timestamp_raw: args.timestampRaw,
    now_seconds: args.nowSeconds,
    provided_hmac_prefix: toPrefix((args.providedHmac || "").toLowerCase()),
    provided_signature_prefix: toPrefix((args.providedSignature || "").toLowerCase()),
    expected_prefixes: (args.expectedCandidates ?? []).map((value) =>
      toPrefix((value || "").toLowerCase()),
    ),
  });
}

function normalizeShopDomain(value: string | null): string {
  return (value ?? "")
    .trim()
    .toLowerCase()
    .replace(/^https?:\/\//, "")
    .replace(/\/.*$/, "");
}

function canonicalizeAppProxyParams(
  searchParams: URLSearchParams,
  excludedKeys: ReadonlySet<string>,
): string {
  const grouped = new Map<string, string[]>();

  searchParams.forEach((value, key) => {
    if (excludedKeys.has(key)) {
      return;
    }

    const existing = grouped.get(key);
    if (existing) {
      existing.push(value);
      return;
    }
    grouped.set(key, [value]);
  });

  // Shopify app-proxy signatures are built from unencoded key=value parts,
  // sorted and concatenated without separators.
  return Array.from(grouped.entries())
    .map(([key, values]) => `${key}=${values.join(",")}`)
    .sort()
    .join("");
}

function canonicalizeOauthStyleParams(searchParams: URLSearchParams): string {
  const entries: Array<[string, string]> = [];
  searchParams.forEach((value, key) => {
    if (key === "hmac" || key === "signature") {
      return;
    }
    entries.push([key, value]);
  });

  entries.sort((a, b) => {
    const keyCmp = a[0].localeCompare(b[0]);
    if (keyCmp !== 0) {
      return keyCmp;
    }
    return a[1].localeCompare(b[1]);
  });

  return entries
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`)
    .join("&");
}

function computeExpectedProxyDigests(secret: string, searchParams: URLSearchParams): string[] {
  const candidates = new Set<string>();

  // Shopify app-proxy format: remove `signature`, keep any other params, sort, concat.
  const appProxyCanonical = canonicalizeAppProxyParams(
    searchParams,
    new Set(["signature"]),
  );
  candidates.add(createHmac("sha256", secret).update(appProxyCanonical, "utf8").digest("hex"));

  // Back-compat with previous proxy implementations that removed both keys.
  const appProxyLegacyCanonical = canonicalizeAppProxyParams(
    searchParams,
    new Set(["signature", "hmac"]),
  );
  candidates.add(
    createHmac("sha256", secret).update(appProxyLegacyCanonical, "utf8").digest("hex"),
  );

  // Compatibility with OAuth-style HMAC canonicalization when `hmac` is present.
  const oauthCanonical = canonicalizeOauthStyleParams(searchParams);
  if (oauthCanonical) {
    candidates.add(createHmac("sha256", secret).update(oauthCanonical, "utf8").digest("hex"));
  }

  return Array.from(candidates);
}

function timingSafeHexEqual(expectedHex: string, providedHex: string): boolean {
  if (!expectedHex || !providedHex) {
    return false;
  }

  const expectedBuffer = Buffer.from(expectedHex, "hex");
  const providedBuffer = Buffer.from(providedHex, "hex");
  if (expectedBuffer.length !== providedBuffer.length || expectedBuffer.length === 0) {
    return false;
  }
  return timingSafeEqual(expectedBuffer, providedBuffer);
}

function verifyShopifyAppProxySignature(request: NextRequest): { ok: true } | { ok: false; reason: string } {
  const secret = getShopifyApiSecret();
  const nowSeconds = Math.floor(Date.now() / 1000);
  const timestampRaw = request.nextUrl.searchParams.get("timestamp")?.trim() ?? "";
  const providedHmac = request.nextUrl.searchParams.get("hmac")?.trim().toLowerCase() ?? "";
  const providedSignature = request.nextUrl.searchParams.get("signature")?.trim().toLowerCase() ?? "";

  if (!secret) {
    logProxySignatureFailure({
      reason: "invalid",
      request,
      timestampRaw,
      nowSeconds,
      providedHmac,
      providedSignature,
    });
    return { ok: false, reason: "SHOPIFY_API_SECRET is not configured." };
  }

  const timestamp = Number(timestampRaw);
  if (!Number.isFinite(timestamp) || timestamp <= 0) {
    logProxySignatureFailure({
      reason: "missing",
      request,
      timestampRaw,
      nowSeconds,
      providedHmac,
      providedSignature,
    });
    return { ok: false, reason: "Missing or invalid proxy timestamp." };
  }

  const skewLimit = getMaxProxySkewSeconds();
  if (Math.abs(nowSeconds - Math.floor(timestamp)) > skewLimit) {
    logProxySignatureFailure({
      reason: "stale",
      request,
      timestampRaw,
      nowSeconds,
      providedHmac,
      providedSignature,
    });
    return { ok: false, reason: "Proxy request timestamp is stale." };
  }

  if (!providedHmac && !providedSignature) {
    logProxySignatureFailure({
      reason: "missing",
      request,
      timestampRaw,
      nowSeconds,
      providedHmac,
      providedSignature,
    });
    return { ok: false, reason: "Missing proxy signature." };
  }

  const expectedCandidates = computeExpectedProxyDigests(secret, request.nextUrl.searchParams);
  const hmacValid = providedHmac
    ? expectedCandidates.some((expected) => timingSafeHexEqual(expected, providedHmac))
    : false;
  const signatureValid = providedSignature
    ? expectedCandidates.some((expected) => timingSafeHexEqual(expected, providedSignature))
    : false;
  if (!hmacValid && !signatureValid) {
    logProxySignatureFailure({
      reason: "invalid",
      request,
      timestampRaw,
      nowSeconds,
      providedHmac,
      providedSignature,
      expectedCandidates,
    });
    return { ok: false, reason: "Invalid proxy signature." };
  }

  return { ok: true };
}

function signAnonIdentifier(secret: string, anonId: string): string {
  return createHmac("sha256", secret).update(anonId, "utf8").digest("hex");
}

function parseSignedAnonCookie(secret: string, cookieValue: string): string {
  const [anonId, providedSignature] = cookieValue.split(".", 2);
  if (!anonId || !providedSignature) {
    return "";
  }

  const normalizedAnonId = anonId.trim().toLowerCase();
  if (!/^[a-f0-9-]{20,80}$/.test(normalizedAnonId)) {
    return "";
  }

  const expected = signAnonIdentifier(secret, normalizedAnonId);
  if (!timingSafeHexEqual(expected, providedSignature.trim().toLowerCase())) {
    return "";
  }

  return normalizedAnonId;
}

function resolveAnonymousIdentifier(request: NextRequest, secret: string): {
  anonId: string;
  setCookie: boolean;
  cookieValue: string;
} {
  const existingCookie = request.cookies.get(ANON_COOKIE_NAME)?.value ?? "";
  const parsedExisting = existingCookie ? parseSignedAnonCookie(secret, existingCookie) : "";
  if (parsedExisting) {
    return {
      anonId: parsedExisting,
      setCookie: false,
      cookieValue: existingCookie,
    };
  }

  const anonId = randomUUID().toLowerCase();
  const signedValue = `${anonId}.${signAnonIdentifier(secret, anonId)}`;
  return {
    anonId,
    setCookie: true,
    cookieValue: signedValue,
  };
}

function buildBackendPath(path: string[]): string {
  return `/api/v1/${path.join("/")}`;
}

function buildUpstreamUrl(request: NextRequest, path: string[], upstreamBaseUrl: string): string {
  const search = new URLSearchParams(request.nextUrl.searchParams);

  SHOPIFY_PROXY_QUERY_KEYS.forEach((key) => {
    search.delete(key);
  });

  const query = search.toString();
  return `${upstreamBaseUrl}${buildBackendPath(path)}${query ? `?${query}` : ""}`;
}

function buildProxySignaturePayload(args: {
  ts: string;
  method: string;
  backendPath: string;
  shopDomain: string;
  loggedInCustomerId: string;
  anonId: string;
}): string {
  return [
    args.ts,
    args.method.toUpperCase(),
    args.backendPath,
    args.shopDomain,
    args.loggedInCustomerId,
    args.anonId,
  ].join("\n");
}

function signProxyPayload(secret: string, payload: string): string {
  return createHmac("sha256", secret).update(payload, "utf8").digest("hex");
}

async function proxyRequest(request: NextRequest, path: string[]): Promise<NextResponse> {
  const verifiedProxy = verifyShopifyAppProxySignature(request);
  if (!verifiedProxy.ok) {
    return NextResponse.json(
      { error: verifiedProxy.reason },
      { status: 401 },
    );
  }

  const upstreamBaseUrl = getUpstreamBaseUrl();
  if (!upstreamBaseUrl) {
    return NextResponse.json(
      {
        error: "API_BASE_URL is not configured."
      },
      {
        status: 500
      }
    );
  }

  const proxyShop = normalizeShopDomain(request.nextUrl.searchParams.get("shop"));
  const proxySessionId = request.nextUrl.searchParams.get("session_id")?.trim() ?? "";
  const loggedInCustomerId = request.nextUrl.searchParams.get("logged_in_customer_id")?.trim() ?? "";
  const sharedSecret = getProxySharedSecret();
  if (!sharedSecret) {
    return NextResponse.json(
      { error: "WIDGET_PROXY_SHARED_SECRET is not configured." },
      { status: 500 },
    );
  }
  const { anonId, setCookie, cookieValue } = resolveAnonymousIdentifier(request, sharedSecret);

  const backendPath = buildBackendPath(path);
  const proxyTs = String(Math.floor(Date.now() / 1000));
  const payload = buildProxySignaturePayload({
    ts: proxyTs,
    method: request.method,
    backendPath,
    shopDomain: proxyShop,
    loggedInCustomerId,
    anonId,
  });
  const proxySignature = signProxyPayload(sharedSecret, payload);
  const requestHeaders = new Headers();

  FORWARDED_REQUEST_HEADERS.forEach((headerName) => {
    const value = request.headers.get(headerName);
    if (value) {
      requestHeaders.set(headerName, value);
    }
  });

  if (proxyShop) {
    requestHeaders.set("X-Shop-Domain", proxyShop);
    requestHeaders.set("X-Shopify-Shop-Domain", proxyShop);
  }

  if (proxySessionId && !requestHeaders.has("X-Session-ID")) {
    requestHeaders.set("X-Session-ID", proxySessionId);
  }

  if (loggedInCustomerId) {
    requestHeaders.set("X-Logged-In-Customer-Id", loggedInCustomerId);
  }
  requestHeaders.set("X-Optimo-Anon-Id", anonId);
  requestHeaders.set("X-Optimo-Proxy-Ts", proxyTs);
  requestHeaders.set("X-Optimo-Proxy-Sig", proxySignature);

  const init: RequestInit = {
    method: request.method,
    headers: requestHeaders,
    redirect: "manual"
  };

  if (!["GET", "HEAD"].includes(request.method)) {
    init.body = Buffer.from(await request.arrayBuffer());
  }

  let upstreamResponse: Response;

  try {
    upstreamResponse = await fetch(buildUpstreamUrl(request, path, upstreamBaseUrl), init);
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Unknown upstream fetch error";
    return NextResponse.json(
      {
        error: `Failed to reach upstream API: ${message}`
      },
      {
        status: 502
      }
    );
  }

  const responseHeaders = new Headers();

  FORWARDED_RESPONSE_HEADERS.forEach((headerName) => {
    const value = upstreamResponse.headers.get(headerName);
    if (value) {
      responseHeaders.set(headerName, value);
    }
  });

  const nextResponse = new NextResponse(upstreamResponse.body, {
    status: upstreamResponse.status,
    headers: responseHeaders
  });

  if (setCookie) {
    nextResponse.cookies.set({
      name: ANON_COOKIE_NAME,
      value: cookieValue,
      httpOnly: true,
      secure: true,
      sameSite: "lax",
      path: "/apps/optimo-vts",
      maxAge: ANON_COOKIE_MAX_AGE_SECONDS,
    });
  }

  return nextResponse;
}

type RouteContext = {
  params: {
    path: string[];
  };
};

export async function GET(request: NextRequest, context: RouteContext): Promise<NextResponse> {
  return proxyRequest(request, context.params.path);
}

export async function POST(request: NextRequest, context: RouteContext): Promise<NextResponse> {
  return proxyRequest(request, context.params.path);
}

export async function PATCH(request: NextRequest, context: RouteContext): Promise<NextResponse> {
  return proxyRequest(request, context.params.path);
}

export async function PUT(request: NextRequest, context: RouteContext): Promise<NextResponse> {
  return proxyRequest(request, context.params.path);
}

export async function DELETE(request: NextRequest, context: RouteContext): Promise<NextResponse> {
  return proxyRequest(request, context.params.path);
}
