import { NextRequest, NextResponse } from "next/server";
import { getResolvedBillingCatalog } from "../../../../../lib/shopify/billing-config";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(request: NextRequest): Promise<NextResponse> {
  const currencyCode = request.nextUrl.searchParams.get("currency");
  const payload = getResolvedBillingCatalog(currencyCode);

  return NextResponse.json(payload, {
    headers: {
      "Cache-Control": "no-store"
    }
  });
}
