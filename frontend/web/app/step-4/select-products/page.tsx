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

type ProductOption = {
  id: string;
  name: string;
  available: number;
  price: number;
};

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
    if (!storeId) {
      return;
    }

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

        if (!active) {
          return;
        }

        setSelectedIds(scope.enabled_product_ids);
        setEnabledCollectionIds(scope.enabled_collection_ids);

        let products = initialProducts;
        if (products.length === 0 && !hasAttemptedAutoSync.current) {
          hasAttemptedAutoSync.current = true;
          setIsSyncing(true);

          try {
            await syncProducts({ storeId });
            if (!active) {
              return;
            }

            products = await listProducts({ storeId, limit: 250, signal: controller.signal });
          } catch (error: unknown) {
            if (!active || controller.signal.aborted) {
              return;
            }
            const message = error instanceof Error ? error.message : "Failed to sync products.";
            setErrorMessage(message);
          } finally {
            if (active) {
              setIsSyncing(false);
            }
          }
        }

        setProductOptions(products.map(toProductOption));
      } catch (error: unknown) {
        if (!active || controller.signal.aborted) {
          return;
        }
        const message = error instanceof Error ? error.message : "Failed to load products.";
        setErrorMessage(message);
      } finally {
        if (active) {
          setIsLoading(false);
        }
      }
    })();

    return () => {
      active = false;
      controller.abort();
    };
  }, [storeId]);

  const visibleProducts = useMemo(() => {
    const normalizedQuery = searchQuery.trim().toLowerCase();

    if (!normalizedQuery) {
      return productOptions;
    }

    return productOptions.filter((product) => {
      const availabilityValue = String(product.available).toLowerCase();
      const priceValue = product.price.toFixed(2).toLowerCase();

      if (searchScope === "name") {
        return product.name.toLowerCase().includes(normalizedQuery);
      }

      if (searchScope === "availability") {
        return availabilityValue.includes(normalizedQuery);
      }

      if (searchScope === "price") {
        return priceValue.includes(normalizedQuery);
      }

      return (
        product.name.toLowerCase().includes(normalizedQuery) ||
        availabilityValue.includes(normalizedQuery) ||
        priceValue.includes(normalizedQuery)
      );
    });
  }, [productOptions, searchQuery, searchScope]);

  const selectedSet = useMemo(() => new Set(selectedIds), [selectedIds]);

  const toggleProduct = (id: string) => {
    setSelectedIds((current) =>
      current.includes(id) ? current.filter((itemId) => itemId !== id) : [...current, id]
    );
  };

  const handleSave = async () => {
    if (!storeId) {
      router.push("/step-4/configured");
      return;
    }

    setIsSaving(true);
    setErrorMessage("");

    try {
      await saveWidgetScope({
        storeId,
        scopeType: "selected_products",
        enabledCollectionIds,
        enabledProductIds: selectedIds
      });
      router.push("/step-4/configured");
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Failed to save selected products.";
      setErrorMessage(message);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <main className="picker-shell">
      <section className="picker-modal" aria-label="Add Products">
        <div className="picker-header-row">
          <EmbeddedLink href="/step-4" className="picker-icon-button" aria-label="Back to previous screen">
            <svg viewBox="0 0 24 24" role="img">
              <path
                d="M14.6 5.5L8.2 12L14.6 18.5"
                fill="none"
                stroke="currentColor"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2.8"
              />
            </svg>
          </EmbeddedLink>
          <EmbeddedLink href="/step-4" className="picker-close-button" aria-label="Close">
            x
          </EmbeddedLink>
        </div>

        <h1 className="picker-title">Add Products</h1>

        {!storeId ? <p className="ai-error-note">Open the app from Shopify Admin to load and save products.</p> : null}
        {isLoading ? <p className="ai-status-note">Loading products...</p> : null}
        {isSyncing ? <p className="ai-status-note">Syncing products from Shopify...</p> : null}
        {errorMessage ? <p className="ai-error-note">{errorMessage}</p> : null}

        <div className="picker-controls picker-controls-products">
          <label className="picker-search-field picker-search-field-accent">
            <svg viewBox="0 0 24 24" role="img" aria-hidden>
              <circle cx="11.2" cy="11.2" r="6.2" fill="none" stroke="currentColor" strokeWidth="1.8" />
              <path d="M16 16L20 20" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" />
            </svg>
            <input
              type="search"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder="Search products"
              aria-label="Search products"
            />
          </label>

          <label className="picker-select-wrap">
            <span className="sr-only">Search scope</span>
            <select
              className="picker-filter-select"
              value={searchScope}
              onChange={(event) => setSearchScope(event.target.value as SearchScope)}
            >
              <option value="all">Search by All</option>
              <option value="name">Search by Name</option>
              <option value="availability">Search by Availability</option>
              <option value="price">Search by Price</option>
            </select>
          </label>
        </div>

        <ul className="picker-list picker-list-products">
          {visibleProducts.map((product) => {
            const isSelected = selectedSet.has(product.id);

            return (
              <li key={product.id}>
                <button
                  type="button"
                  className="product-row"
                  onClick={() => toggleProduct(product.id)}
                  aria-pressed={isSelected}
                >
                  <span className={`picker-mark picker-mark-square product-mark${isSelected ? " is-active" : ""}`} />
                  <span className="product-name">{product.name}</span>
                  <span className="product-stock">{product.available} Variant{product.available === 1 ? "" : "s"}</span>
                  <span className="product-price">{formatPrice(product.price)}</span>
                </button>
              </li>
            );
          })}

          {!isLoading && visibleProducts.length === 0 ? (
            <li className="picker-empty">No products match your search.</li>
          ) : null}
        </ul>

        <div className="picker-footer">
          <p>
            <strong>{selectedIds.length}</strong> Products Selected
          </p>
          <button type="button" className="picker-add-button" onClick={handleSave} disabled={isSaving}>
            <span aria-hidden>+</span> {isSaving ? "Saving..." : "Save"}
          </button>
        </div>
      </section>
    </main>
  );
}
