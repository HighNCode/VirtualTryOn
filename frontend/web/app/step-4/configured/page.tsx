"use client";

import { useEffect, useMemo, useState } from "react";
import { EmbeddedLink } from "../../_components/EmbeddedNavigation";
import {
  listCollections,
  getDefaultStoreId,
  getWidgetScope,
  listProducts,
  type CollectionResponse,
  type ProductResponse
} from "../../../lib/photoshootApi";

export default function StepFourConfiguredPage() {
  const storeId = useMemo(() => getDefaultStoreId(), []);

  const [scopeType, setScopeType] = useState("all");
  const [collectionIds, setCollectionIds] = useState<string[]>([]);
  const [productIds, setProductIds] = useState<string[]>([]);
  const [products, setProducts] = useState<ProductResponse[]>([]);
  const [collections, setCollections] = useState<CollectionResponse[]>([]);

  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    if (!storeId) return;
    const controller = new AbortController();
    let active = true;
    setIsLoading(true);

    Promise.all([
      getWidgetScope({ storeId, signal: controller.signal }),
      listProducts({ storeId, limit: 250, signal: controller.signal }),
      listCollections({ storeId, limit: 250, signal: controller.signal })
    ])
      .then(([scope, productList, collectionList]) => {
        if (!active) return;
        setScopeType(scope.scope_type);
        setCollectionIds(scope.enabled_collection_ids);
        setProductIds(scope.enabled_product_ids);
        setProducts(productList);
        setCollections(collectionList);
      })
      .catch((error: unknown) => {
        if (!active || controller.signal.aborted) return;
        setErrorMessage(error instanceof Error ? error.message : "Failed to load configured scope.");
      })
      .finally(() => { if (active) setIsLoading(false); });

    return () => { active = false; controller.abort(); };
  }, [storeId]);

  const productTitleById = useMemo(() => {
    const lookup = new Map<string, string>();
    products.forEach((product) => lookup.set(product.shopify_product_id, product.title));
    return lookup;
  }, [products]);

  const selectedCollections = useMemo(() => {
    const lookup = new Map(collections.map((c) => [c.id, c]));
    return collectionIds.map((id) => {
      const c = lookup.get(id);
      return { id, name: c?.title ?? id, subtitle: c?.handle ? `Handle: ${c.handle}` : "Collection ID" };
    });
  }, [collectionIds, collections]);

  const selectedProducts = useMemo(
    () => productIds.map((id) => ({ id, name: productTitleById.get(id) ?? id })),
    [productIds, productTitleById]
  );

  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "flex-start", justifyContent: "center", padding: "24px 16px", background: "#f6f4f4" }}>
      <div style={{ width: "100%", maxWidth: 680, background: "#fff", borderRadius: 14, overflow: "hidden", boxShadow: "0 4px 24px rgba(0,0,0,0.08)", border: "1px solid rgba(0,0,0,0.05)" }}>

        {/* Top bar */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 24px", borderBottom: "1px solid #f0f0f0" }}>
          <p style={{ margin: 0, fontSize: 13, fontWeight: 600, color: "#6b7280" }}>Welcome to Optimo VTS</p>
          <p style={{ margin: 0, fontSize: 13, color: "#9ca3af" }}>Step 4 of 6</p>
        </div>

        {/* Progress bar */}
        <div style={{ width: "100%", height: 4, background: "#f3f4f6" }}>
          <div style={{ width: "66.67%", height: "100%", background: "linear-gradient(90deg, #7E0175, #E40206)" }} />
        </div>

        {/* Content */}
        <div style={{ padding: "24px 24px 16px" }}>
          <div style={{ display: "flex", alignItems: "flex-start", gap: 12, marginBottom: 20 }}>
            <EmbeddedLink
              href="/step-4"
              style={{ width: 32, height: 32, borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, marginTop: 2, background: "#f3f4f6", color: "#6b7280" }}
              aria-label="Go to previous screen"
            >
              <svg viewBox="0 0 24 24" width={16} height={16}>
                <path d="M14.6 5.5L8.2 12L14.6 18.5" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.8" />
              </svg>
            </EmbeddedLink>
            <div>
              <h1 style={{ margin: 0, fontSize: 20, fontWeight: 800, color: "#1a1a1a" }}>Enable the Try-On Button</h1>
              <p style={{ margin: "4px 0 0", fontSize: 14, color: "#6b7280" }}>Choose where you want the virtual try-on button to appear on your storefront.</p>
            </div>
          </div>

          {!storeId && <p style={{ fontSize: 13, marginBottom: 16, padding: "8px 12px", borderRadius: 8, background: "#fff1f1", color: "#dc2626" }}>Open the app from Shopify Admin to load widget scope.</p>}
          {isLoading && <p style={{ fontSize: 13, marginBottom: 16, padding: "8px 12px", borderRadius: 8, background: "rgba(126,1,117,0.06)", color: "#7E0175" }}>Loading configured scope...</p>}
          {errorMessage && <p style={{ fontSize: 13, marginBottom: 16, padding: "8px 12px", borderRadius: 8, background: "#fff1f1", color: "#dc2626" }}>{errorMessage}</p>}

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }}>
            {/* Collections card */}
            <div style={{ borderRadius: 12, padding: 16, border: "1px solid rgba(0,0,0,0.07)", background: "#fafafa" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                <span style={{ width: 28, height: 28, borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center", background: "rgba(126,1,117,0.08)" }}>
                  <svg viewBox="0 0 24 24" width={14} height={14} style={{ color: "#7E0175" }}>
                    <rect x="3.5" y="4.5" width="17" height="14" rx="2.4" fill="none" stroke="currentColor" strokeWidth="1.8" />
                    <circle cx="12" cy="9.4" r="2.4" fill="none" stroke="currentColor" strokeWidth="1.8" />
                    <path d="M7 15H17" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
                  </svg>
                </span>
                <h2 style={{ margin: 0, fontSize: 13, fontWeight: 700, color: "#1a1a1a" }}>By Collection</h2>
              </div>
              <p style={{ margin: "0 0 8px", fontSize: 11, color: "#9ca3af" }}>Scope: {scopeType}</p>
              <EmbeddedLink href="/step-4/select-collections" style={{ fontSize: 12, fontWeight: 600, color: "#7E0175", textDecoration: "underline" }}>
                Edit Collections
              </EmbeddedLink>
              <p style={{ margin: "12px 0 6px", fontSize: 11, fontWeight: 600, color: "#6b7280" }}>Selected ({selectedCollections.length})</p>
              <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 6 }}>
                {selectedCollections.length === 0 && (
                  <li style={{ fontSize: 12, color: "#9ca3af" }}>No collections selected.</li>
                )}
                {selectedCollections.map((c) => (
                  <li key={c.id} style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
                    <span style={{ width: 6, height: 6, borderRadius: "50%", marginTop: 6, flexShrink: 0, background: "#7E0175" }} />
                    <span>
                      <span style={{ fontSize: 12, fontWeight: 500, display: "block", color: "#1a1a1a" }}>{c.name}</span>
                      <span style={{ fontSize: 11, color: "#9ca3af" }}>{c.subtitle}</span>
                    </span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Products card */}
            <div style={{ borderRadius: 12, padding: 16, border: "1px solid rgba(0,0,0,0.07)", background: "#fafafa" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                <span style={{ width: 28, height: 28, borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center", background: "rgba(126,1,117,0.08)" }}>
                  <svg viewBox="0 0 24 24" width={14} height={14} style={{ color: "#7E0175" }}>
                    <path d="M12 5.5L8 9.3C7 10.2 5.7 10.7 4.3 10.7H3V12.6H21V10.7H19.7C18.3 10.7 17 10.2 16 9.3L12 5.5Z" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
                  </svg>
                </span>
                <h2 style={{ margin: 0, fontSize: 13, fontWeight: 700, color: "#1a1a1a" }}>By Product</h2>
              </div>
              <p style={{ margin: "0 0 8px", fontSize: 11, color: "#9ca3af" }}>Enable only selected products from your synced catalog.</p>
              <EmbeddedLink href="/step-4/select-products" style={{ fontSize: 12, fontWeight: 600, color: "#7E0175", textDecoration: "underline" }}>
                Edit Products
              </EmbeddedLink>
              <p style={{ margin: "12px 0 6px", fontSize: 11, fontWeight: 600, color: "#6b7280" }}>Selected ({selectedProducts.length})</p>
              <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 6 }}>
                {selectedProducts.length === 0 && (
                  <li style={{ fontSize: 12, color: "#9ca3af" }}>No products selected.</li>
                )}
                {selectedProducts.map((p) => (
                  <li key={p.id} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ width: 6, height: 6, borderRadius: "50%", flexShrink: 0, background: "#7E0175" }} />
                    <span style={{ fontSize: 12, fontWeight: 500, color: "#1a1a1a" }}>{p.name}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* Success banner */}
          <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 16px", borderRadius: 10, background: "#dcfce7", border: "1px solid #bbf7d0" }}>
            <span style={{ width: 24, height: 24, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, background: "#15803d" }}>
              <svg viewBox="0 0 24 24" width={12} height={12}>
                <path d="M20 7L10 17L5 12" fill="none" stroke="white" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.6" />
              </svg>
            </span>
            <div>
              <p style={{ margin: 0, fontSize: 13, fontWeight: 600, color: "#15803d" }}>Button Scope Saved</p>
              <p style={{ margin: 0, fontSize: 12, color: "#166534" }}>
                The virtual try-on button scope is active for {selectedProducts.length} product(s) and {selectedCollections.length} collection(s).
              </p>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 24px", borderTop: "1px solid #f0f0f0" }}>
          <EmbeddedLink href="/settings/support" style={{ fontSize: 13, color: "#7E0175", textDecoration: "underline" }}>
            Need help? Contact our support team
          </EmbeddedLink>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <EmbeddedLink
              href="/step-6"
              style={{ padding: "9px 20px", borderRadius: 10, fontSize: 13, fontWeight: 600, border: "1.5px solid #e5e5e5", color: "#6b7280", textDecoration: "none" }}
            >
              Skip for now
            </EmbeddedLink>
            <EmbeddedLink
              href="/step-5/not-detected"
              style={{ padding: "9px 22px", borderRadius: 10, fontSize: 13, fontWeight: 600, color: "#fff", background: "linear-gradient(135deg, #7E0175 0%, #BC174A 55%, #E40206 100%)", textDecoration: "none" }}
            >
              Enable Try-on
            </EmbeddedLink>
          </div>
        </div>

      </div>
    </div>
  );
}
