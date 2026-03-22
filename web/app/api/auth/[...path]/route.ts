import { NextRequest, NextResponse } from "next/server";

const FORWARDED_REQUEST_HEADERS = [
  "accept",
  "content-type",
  "x-forwarded-for",
  "x-forwarded-host",
  "x-forwarded-proto",
] as const;

const FORWARDED_RESPONSE_HEADERS = [
  "cache-control",
  "content-disposition",
  "content-type",
  "location",
] as const;

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

async function proxyAuthRequest(request: NextRequest, path: string[]): Promise<NextResponse> {
  const upstreamBaseUrl = getUpstreamBaseUrl();
  if (!upstreamBaseUrl) {
    return NextResponse.json(
      {
        error: "API_BASE_URL is not configured.",
      },
      { status: 500 }
    );
  }

  if (path.length === 0) {
    return NextResponse.json({ error: "Missing auth path." }, { status: 400 });
  }

  const headers = new Headers();
  FORWARDED_REQUEST_HEADERS.forEach((headerName) => {
    const value = request.headers.get(headerName);
    if (value) {
      headers.set(headerName, value);
    }
  });

  const init: RequestInit = {
    method: request.method,
    headers,
    redirect: "manual",
  };

  if (!["GET", "HEAD"].includes(request.method)) {
    init.body = Buffer.from(await request.arrayBuffer());
  }

  let upstreamResponse: Response;

  try {
    upstreamResponse = await fetch(
      `${upstreamBaseUrl}/api/v1/auth/${path.join("/")}${request.nextUrl.search}`,
      init
    );
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Unknown upstream fetch error";
    return NextResponse.json(
      {
        error: `Failed to reach upstream API: ${message}`,
      },
      { status: 502 }
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
    headers: responseHeaders,
  });
}

type RouteContext = {
  params: {
    path: string[];
  };
};

export async function GET(request: NextRequest, context: RouteContext): Promise<NextResponse> {
  return proxyAuthRequest(request, context.params.path);
}

export async function POST(request: NextRequest, context: RouteContext): Promise<NextResponse> {
  return proxyAuthRequest(request, context.params.path);
}
