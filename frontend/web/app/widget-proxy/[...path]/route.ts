import { NextRequest, NextResponse } from "next/server";

const FORWARDED_REQUEST_HEADERS = [
  "accept",
  "content-type",
  "x-session-id",
  "x-store-id",
  "x-shop-domain",
  "x-shopify-shop-domain",
  "x-logged-in-customer-id"
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

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

function getUpstreamBaseUrl(): string {
  const configuredUrl =
    process.env.API_BASE_URL?.trim() ||
    process.env.BACKEND_URL?.trim() ||
    process.env.NEXT_PUBLIC_API_BASE_URL?.trim() ||
    "";

  return configuredUrl.replace(/\/+$/, "");
}

function normalizeShopDomain(value: string | null): string {
  return (value ?? "")
    .trim()
    .toLowerCase()
    .replace(/^https?:\/\//, "")
    .replace(/\/.*$/, "");
}

function buildUpstreamUrl(request: NextRequest, path: string[], upstreamBaseUrl: string): string {
  const search = new URLSearchParams(request.nextUrl.searchParams);

  SHOPIFY_PROXY_QUERY_KEYS.forEach((key) => {
    search.delete(key);
  });

  const query = search.toString();
  return `${upstreamBaseUrl}/api/v1/${path.join("/")}${query ? `?${query}` : ""}`;
}

async function proxyRequest(request: NextRequest, path: string[]): Promise<NextResponse> {
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

  return new NextResponse(upstreamResponse.body, {
    status: upstreamResponse.status,
    headers: responseHeaders
  });
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
