import { createHmac, timingSafeEqual } from "node:crypto";
import { NextRequest, NextResponse } from "next/server";

const HMAC_HEADER = "x-shopify-hmac-sha256";
const TOPIC_HEADER = "x-shopify-topic";
const SHOP_HEADER = "x-shopify-shop-domain";

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

async function forwardWebhook(rawBody: string, request: NextRequest): Promise<void> {
  const forwardUrl = process.env.SHOPIFY_WEBHOOK_FORWARD_URL?.trim();
  if (!forwardUrl) {
    return;
  }

  const headers = new Headers();
  const contentType = request.headers.get("content-type");

  if (contentType) {
    headers.set("content-type", contentType);
  }

  [TOPIC_HEADER, SHOP_HEADER, "x-shopify-api-version", "x-shopify-event-id"].forEach((headerName) => {
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
    throw new Error(`Webhook forward failed with status ${response.status}.`);
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
      message
    });

    return NextResponse.json(
      {
        error: message
      },
      {
        status: 500
      }
    );
  }

  console.info("Shopify webhook received", {
    topic,
    shopDomain
  });

  return new NextResponse(null, {
    status: 200
  });
}
