import { createHmac, timingSafeEqual } from "node:crypto";
import { NextRequest, NextResponse } from "next/server";

const HMAC_HEADER = "x-shopify-hmac-sha256";
const TOPIC_HEADER = "x-shopify-topic";
const SHOP_HEADER = "x-shopify-shop-domain";
const WEBHOOK_ID_HEADER = "x-shopify-webhook-id";
const TRIGGERED_AT_HEADER = "x-shopify-triggered-at";

const TOPIC_TO_FORWARD_PATH: Record<string, string> = {
  "app/uninstalled": "/app/uninstalled",
  "shop/update": "/shop/update",
  "app_subscriptions/update": "/app_subscriptions/update",
  "customers/data_request": "/gdpr/customers/data_request",
  "customers/redact": "/gdpr/customers/redact",
  "shop/redact": "/gdpr/shop/redact"
};

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

function buildHmac(secret: string, payload: string): string {
  return createHmac("sha256", secret).update(payload, "utf8").digest("base64");
}

function isValidWebhookSignature(secret: string, payload: string, providedHmac: string): boolean {
  const expectedHmac = buildHmac(secret, payload);
  const expectedBuffer = Buffer.from(expectedHmac);
  const providedBuffer = Buffer.from(providedHmac);

  if (expectedBuffer.length !== providedBuffer.length) {
    return false;
  }

  return timingSafeEqual(expectedBuffer, providedBuffer);
}

function buildForwardUrl(base: string, path: string): string | null {
  try {
    const url = new URL(base);
    const normalizedPath = `${url.pathname.replace(/\/+$/, "")}/${path.replace(/^\/+/, "")}`;
    url.pathname = normalizedPath;
    return url.toString();
  } catch {
    return null;
  }
}

async function forwardWebhook(rawBody: string, request: NextRequest): Promise<void> {
  const forwardBaseUrl = process.env.SHOPIFY_WEBHOOK_FORWARD_URL?.trim();
  if (!forwardBaseUrl) {
    return;
  }

  const topic = request.headers.get(TOPIC_HEADER)?.trim().toLowerCase() ?? "";
  const forwardPath = TOPIC_TO_FORWARD_PATH[topic];
  if (!forwardPath) {
    console.info("Shopify webhook topic ignored (no forward mapping)", { topic });
    return;
  }

  const forwardUrl = buildForwardUrl(forwardBaseUrl, forwardPath);
  if (!forwardUrl) {
    console.error("Shopify webhook forwarding skipped: invalid SHOPIFY_WEBHOOK_FORWARD_URL", {
      topic,
      configuredBaseUrl: forwardBaseUrl
    });
    return;
  }

  const headers = new Headers();
  const contentType = request.headers.get("content-type");

  if (contentType) {
    headers.set("content-type", contentType);
  }

  [
    TOPIC_HEADER,
    SHOP_HEADER,
    HMAC_HEADER,
    WEBHOOK_ID_HEADER,
    TRIGGERED_AT_HEADER,
    "x-shopify-api-version",
    "x-shopify-event-id"
  ].forEach((headerName) => {
    const value = request.headers.get(headerName);
    if (value) {
      headers.set(headerName, value);
    }
  });

  const forwardToken = process.env.SHOPIFY_WEBHOOK_FORWARD_TOKEN?.trim();
  if (forwardToken) {
    headers.set("authorization", `Bearer ${forwardToken}`);
  }

  const response = await fetch(forwardUrl, {
    method: "POST",
    headers,
    body: rawBody
  });

  if (!response.ok) {
    console.error("Shopify webhook forward target responded non-2xx", {
      topic,
      forwardPath,
      status: response.status
    });
  }
}

export async function POST(request: NextRequest): Promise<NextResponse> {
  const secret = process.env.SHOPIFY_API_SECRET?.trim() ?? process.env.SHOPIFY_API_SECRET_KEY?.trim() ?? "";
  if (!secret) {
    return NextResponse.json(
      {
        error: "SHOPIFY_API_SECRET is not configured."
      },
      {
        status: 500
      }
    );
  }

  const providedHmac = request.headers.get(HMAC_HEADER) ?? "";
  const topic = request.headers.get(TOPIC_HEADER) ?? "unknown";
  const shopDomain = request.headers.get(SHOP_HEADER) ?? "unknown";
  const rawBody = await request.text();

  if (!providedHmac || !isValidWebhookSignature(secret, rawBody, providedHmac)) {
    return NextResponse.json(
      {
        error: "Invalid webhook signature."
      },
      {
        status: 401
      }
    );
  }

  try {
    await forwardWebhook(rawBody, request);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Webhook forwarding failed.";
    console.error("Shopify webhook forwarding error", {
      topic,
      shopDomain,
      webhookId: request.headers.get(WEBHOOK_ID_HEADER) ?? "",
      message
    });
  }

  console.info("Shopify webhook received", {
    topic,
    shopDomain,
    webhookId: request.headers.get(WEBHOOK_ID_HEADER) ?? ""
  });

  return new NextResponse(null, {
    status: 200
  });
}
