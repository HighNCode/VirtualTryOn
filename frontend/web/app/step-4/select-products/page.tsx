"use client";

import { useMemo, useState, useEffect, useRef } from "react";
import { EmbeddedLink, useEmbeddedRouter } from "../../_components/EmbeddedNavigation";
import {
  getDefaultStoreId,
  getWidgetScope,
  listProducts,
  syncProducts,
  saveWidgetScope,
  type ProductResponse
} from "../../../lib/photoshootApi";

type ProductOption = { id: string; name: string; available: number; price: number };
type SearchScope = "all" | "name" | "availability" | "price";

function formatPrice(value: number): string {
  return `$${value.toFixed(2)}`;
}

function toProductOption(product: ProductResponse): ProductOption {
  const firstPrice = Number.parseFloat(product.variants[0]?.price ?? "0");
  return {
    id: product.shopify_product_id,
    name: product.title,
    available: Math.max(product.variants.length, 1),
    price: Number.isFinite(firstPrice) ? firstPrice : 0
  };
}

export default function SelectProductsPage() {
  const router = useEmbeddedRouter();
  const storeId = useMemo(() => getDefaultStoreId(), []);

  const [searchQuery, setSearchQuery] = useState("");
  const [searchScope, setSearchScope] = useState<SearchScope>("all");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [enabledCollectionIds, setEnabledCollectionIds] = useState<string[]>([]);
  const [productOptions, setProductOptions] = useState<ProductOption[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const hasAttemptedAutoSync = useRef(false);

  useEffect(() => {
    if (!storeId) return;
    const controller = new AbortController();
    let active = true;
    setIsLoading(true);
    setErrorMessage("");

    (async () => {
      try {
        const [initialProducts, scope] = await Promise.all([
          listProducts({ storeId, limit: 250, signal: controller.signal }),
          getWidgetScope({ storeId, signal: controller.signal })
        ]);
        if (!active) return;
        setSelectedIds(scope.enabled_product_ids);
        setEnabledCollectionIds(scope.enabled_collection_ids);
        let products = initialProducts;
        if (products.length === 0 && !hasAttemptedAutoSync.current) {
          hasAttemptedAutoSync.current = true;
          setIsSyncing(true);
          try {
            await syncProducts({ storeId });
            if (!active) return;
            products = await listProducts({ storeId, limit: 250, signal: controller.signal });
          } catch (error: unknown) {
            if (!active || controller.signal.aborted) return;
            setErrorMessage(error instanceof Error ? error.message : "Failed to sync products.");
          } finally {
            if (active) setIsSyncing(false);
          }
        }
        setProductOptions(products.map(toProductOption));
      } catch (error: unknown) {
        if (!active || controller.signal.aborted) return;
        setErrorMessage(error instanceof Error ? error.message : "Failed to load products.");
      } finally {
        if (active) setIsLoading(false);
      }
    })();

    return () => { active = false; controller.abort(); };
  }, [storeId]);

  const visibleProducts = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return productOptions;
    return productOptions.filter((product) => {
      if (searchScope === "name") return product.name.toLowerCase().includes(q);
      if (searchScope === "availability") return String(product.available).includes(q);
      if (searchScope === "price") return product.price.toFixed(2).includes(q);
      return product.name.toLowerCase().includes(q) || String(product.available).includes(q) || product.price.toFixed(2).includes(q);
    });
  }, [productOptions, searchQuery, searchScope]);

  const selectedSet = useMemo(() => new Set(selectedIds), [selectedIds]);

  const toggleProduct = (id: string) => {
    setSelectedIds((current) => current.includes(id) ? current.filter((x) => x !== id) : [...current, id]);
  };

  const handleSave = async () => {
    if (!storeId) { router.push("/step-4/configured"); return; }
    setIsSaving(true);
    setErrorMessage("");
    try {
      await saveWidgetScope({ storeId, scopeType: "selected_products", enabledCollectionIds, enabledProductIds: selectedIds });
      router.push("/step-4/configured");
    } catch (error: unknown) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to save selected products.");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "flex-start", justifyContent: "center", padding: "24px 16px", background: "#f6f4f4" }}>
      <div style={{ width: "100%", maxWidth: 640, background: "#fff", borderRadius: 14, overflow: "hidden", display: "flex", flexDirection: "column", maxHeight: "90vh", boxShadow: "0 4px 24px rgba(0,0,0,0.08)", border: "1px solid rgba(0,0,0,0.05)" }}>

        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 20px", borderBottom: "1px solid #f0f0f0", flexShrink: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <EmbeddedLink
              href="/step-4"
              style={{ width: 32, height: 32, borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center", background: "#f3f4f6", color: "#6b7280" }}
              aria-label="Back to previous screen"
            >
              <svg viewBox="0 0 24 24" width={16} height={16}>
                <path d="M14.6 5.5L8.2 12L14.6 18.5" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.8" />
              </svg>
            </EmbeddedLink>
            <h1 style={{ margin: 0, fontSize: 17, fontWeight: 700, color: "#1a1a1a" }}>Add Products</h1>
          </div>
          <EmbeddedLink
            href="/step-4"
            style={{ width: 32, height: 32, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18, fontWeight: 700, background: "#f3f4f6", color: "#6b7280", textDecoration: "none" }}
            aria-label="Close"
          >
            ×
          </EmbeddedLink>
        </div>

        {/* Controls */}
        <div style={{ padding: "16px 20px 12px", display: "flex", flexDirection: "column", gap: 12, flexShrink: 0 }}>
          {!storeId && <p style={{ fontSize: 13, padding: "8px 12px", borderRadius: 8, background: "#fff1f1", color: "#dc2626", margin: 0 }}>Open the app from Shopify Admin to load and save products.</p>}
          {isLoading && <p style={{ fontSize: 13, padding: "8px 12px", borderRadius: 8, background: "rgba(126,1,117,0.06)", color: "#7E0175", margin: 0 }}>Loading products...</p>}
          {isSyncing && <p style={{ fontSize: 13, padding: "8px 12px", borderRadius: 8, background: "rgba(126,1,117,0.06)", color: "#7E0175", margin: 0 }}>Syncing products from Shopify...</p>}
          {errorMessage && <p style={{ fontSize: 13, padding: "8px 12px", borderRadius: 8, background: "#fff1f1", color: "#dc2626", margin: 0 }}>{errorMessage}</p>}

          {/* Search + scope */}
          <div style={{ display: "flex", gap: 8 }}>
            <label style={{ flex: 1, display: "flex", alignItems: "center", gap: 8, padding: "10px 12px", borderRadius: 10, border: "1.5px solid rgba(126,1,117,0.3)", background: "#fafafa" }}>
              <svg viewBox="0 0 24 24" width={15} height={15} aria-hidden style={{ color: "#7E0175", flexShrink: 0 }}>
                <circle cx="11.2" cy="11.2" r="6.2" fill="none" stroke="currentColor" strokeWidth="1.8" />
                <path d="M16 16L20 20" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" />
              </svg>
              <input
                type="search"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search products"
                aria-label="Search products"
                style={{ flex: 1, fontSize: 13, background: "transparent", outline: "none", border: "none", color: "#1a1a1a" }}
              />
            </label>
            <select
              value={searchScope}
              onChange={(e) => setSearchScope(e.target.value as SearchScope)}
              aria-label="Search scope"
              style={{ fontSize: 13, padding: "10px 12px", borderRadius: 10, border: "1.5px solid #e5e5e5", color: "#6b7280", fontFamily: "inherit", outline: "none", background: "#fafafa" }}
            >
              <option value="all">All fields</option>
              <option value="name">Name</option>
              <option value="availability">Availability</option>
              <option value="price">Price</option>
            </select>
          </div>
        </div>

        {/* Product list */}
        <div style={{ flex: 1, overflowY: "auto", minHeight: 0 }}>
          {/* Table header */}
          <div
            style={{ display: "grid", gridTemplateColumns: "2rem 1fr 5rem 5rem", padding: "8px 20px", fontSize: 11, fontWeight: 600, color: "#9ca3af", background: "#fff", borderBottom: "1px solid #f0f0f0", position: "sticky", top: 0 }}
          >
            <span />
            <span>Product</span>
            <span style={{ textAlign: "right" }}>Variants</span>
            <span style={{ textAlign: "right" }}>Price</span>
          </div>

          <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
            {visibleProducts.map((product) => {
              const isSelected = selectedSet.has(product.id);
              return (
                <li key={product.id} style={{ borderBottom: "1px solid #f9fafb" }}>
                  <button
                    type="button"
                    onClick={() => toggleProduct(product.id)}
                    aria-pressed={isSelected}
                    style={{ width: "100%", display: "grid", gridTemplateColumns: "2rem 1fr 5rem 5rem", alignItems: "center", padding: "12px 20px", textAlign: "left", border: "none", background: "transparent", cursor: "pointer" }}
                    onMouseEnter={(e) => { e.currentTarget.style.background = "#fafafa"; }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
                  >
                    <span
                      style={{
                        width: 16, height: 16, borderRadius: 4, display: "flex", alignItems: "center", justifyContent: "center",
                        border: isSelected ? "none" : "1.5px solid #d1d5db",
                        background: isSelected ? "linear-gradient(135deg, #7E0175, #E40206)" : "#fff",
                      }}
                    >
                      {isSelected && (
                        <svg viewBox="0 0 24 24" width={10} height={10}>
                          <path d="M20 7L10 17L5 12" fill="none" stroke="white" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.8" />
                        </svg>
                      )}
                    </span>
                    <span style={{ fontSize: 13, fontWeight: 500, color: "#1a1a1a", paddingRight: 12, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{product.name}</span>
                    <span style={{ fontSize: 12, textAlign: "right", color: "#6b7280" }}>
                      {product.available} Variant{product.available === 1 ? "" : "s"}
                    </span>
                    <span style={{ fontSize: 12, textAlign: "right", fontWeight: 500, color: "#1a1a1a" }}>{formatPrice(product.price)}</span>
                  </button>
                </li>
              );
            })}
            {!isLoading && visibleProducts.length === 0 && (
              <li style={{ fontSize: 13, textAlign: "center", padding: "32px 0", color: "#9ca3af" }}>No products match your search.</li>
            )}
          </ul>
        </div>

        {/* Footer */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 20px", borderTop: "1px solid #f0f0f0", flexShrink: 0 }}>
          <p style={{ margin: 0, fontSize: 13, color: "#6b7280" }}>
            <strong style={{ color: "#1a1a1a" }}>{selectedIds.length}</strong> Product{selectedIds.length === 1 ? "" : "s"} Selected
          </p>
          <button
            type="button"
            onClick={handleSave}
            disabled={isSaving}
            style={{
              padding: "9px 22px", borderRadius: 10, fontSize: 13, fontWeight: 600, color: "#fff",
              background: "linear-gradient(135deg, #7E0175 0%, #BC174A 55%, #E40206 100%)",
              border: "none",
              cursor: isSaving ? "not-allowed" : "pointer",
              opacity: isSaving ? 0.7 : 1,
            }}
          >
            {isSaving ? "Saving..." : "Save"}
          </button>
        </div>

      </div>
    </div>
  );
}
