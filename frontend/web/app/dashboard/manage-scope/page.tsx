"use client";

import { useEffect, useMemo, useState } from "react";
import { EmbeddedLink } from "../../_components/EmbeddedNavigation";
import PortalSidebar from "../../_components/PortalSidebar";
import {
  getDefaultStoreId,
  getWidgetConfig,
  listCollections,
  listProducts,
  updateWidgetConfig,
  type CollectionResponse,
  type ProductResponse
} from "../../../lib/photoshootApi";

export default function DashboardManageScopePage() {
  const storeId = useMemo(() => getDefaultStoreId(), []);

  const [scopeType, setScopeType] = useState("all");
  const [collectionIds, setCollectionIds] = useState<string[]>([]);
  const [productIds, setProductIds] = useState<string[]>([]);
  const [products, setProducts] = useState<ProductResponse[]>([]);
  const [collections, setCollections] = useState<CollectionResponse[]>([]);

  const [isLoading, setIsLoading] = useState(false);
  const [isUpdatingAll, setIsUpdatingAll] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const isAllScope = scopeType === "all";

  useEffect(() => {
    if (!storeId) {
      return;
    }

    const controller = new AbortController();
    let active = true;

    setIsLoading(true);
    setErrorMessage("");

    Promise.all([
      getWidgetConfig({ storeId, signal: controller.signal }),
      listProducts({ storeId, limit: 250, signal: controller.signal }),
      listCollections({ storeId, limit: 250, signal: controller.signal })
    ])
      .then(([config, productList, collectionList]) => {
        if (!active) {
          return;
        }
        setScopeType(config.scope_type);
        setCollectionIds(config.enabled_collection_ids);
        setProductIds(config.enabled_product_ids);
        setProducts(productList);
        setCollections(collectionList);
      })
      .catch((error: unknown) => {
        if (!active || controller.signal.aborted) {
          return;
        }
        const message = error instanceof Error ? error.message : "Failed to load widget scope.";
        setErrorMessage(message);
      })
      .finally(() => {
        if (active) {
          setIsLoading(false);
        }
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [storeId]);

  const handleEnableEverywhere = async () => {
    if (!storeId) {
      return;
    }

    setIsUpdatingAll(true);
    setErrorMessage("");

    try {
      await updateWidgetConfig({
        storeId,
        payload: {
          scope_type: "all",
          enabled_collection_ids: [],
          enabled_product_ids: []
        }
      });
      setScopeType("all");
      setCollectionIds([]);
      setProductIds([]);
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Failed to update scope.";
      setErrorMessage(message);
    } finally {
      setIsUpdatingAll(false);
    }
  };

  const productTitleById = useMemo(() => {
    const lookup = new Map<string, string>();
    products.forEach((product) => {
      lookup.set(product.shopify_product_id, product.title);
    });
    return lookup;
  }, [products]);

  const selectedCollections = useMemo(() => {
    const lookup = new Map(collections.map((collection) => [collection.id, collection]));
    return collectionIds.map((id) => {
      const collection = lookup.get(id);
      return {
        id,
        name: collection?.title ?? id,
        subtitle: collection?.handle ? `Handle: ${collection.handle}` : "Collection ID"
      };
    });
  }, [collectionIds, collections]);

  const selectedProducts = useMemo(
    () =>
      productIds.map((id) => ({
        id,
        name: productTitleById.get(id) ?? id
      })),
    [productIds, productTitleById]
  );

  return (
    <main className="portal-shell">
      <PortalSidebar activeMain="overview" />

      <section className="portal-main">
        <header className="portal-main-header">
          <h2>Manage Enabled Products &amp; Collections</h2>
          <p>Control where your storefront try-on widget appears.</p>
        </header>

        <section className="welcome-card">
          <div className="step4-heading-row step4-heading-row-configured">
            <EmbeddedLink href="/dashboard" className="back-button" aria-label="Back to overview">
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

            <div className="step4-heading-copy step4-heading-copy-configured">
              <h1>Enable the Try-On Button</h1>
              <p>Control where your storefront try-on widget appears.</p>
            </div>
          </div>

          {!storeId ? <p className="ai-error-note">Open the app from Shopify Admin to load widget scope.</p> : null}
          {isLoading ? <p className="ai-status-note">Loading configured scope...</p> : null}
          {errorMessage ? <p className="ai-error-note">{errorMessage}</p> : null}

          <div className="configured-grid">
            <article className="configured-card">
              <header className="configured-card-head">
                <span className="configured-card-icon" aria-hidden>
                  <svg viewBox="0 0 24 24" role="img">
                    <rect x="3.5" y="4.5" width="17" height="14" rx="2.4" fill="none" stroke="currentColor" strokeWidth="1.8" />
                    <circle cx="12" cy="9.4" r="2.4" fill="none" stroke="currentColor" strokeWidth="1.8" />
                    <path d="M7 15H17" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
                  </svg>
                </span>
                <h2>By Collection</h2>
              </header>

              <p className="configured-card-description">Enable by selecting collections from your synced catalog.</p>

              <EmbeddedLink href="/dashboard/manage-scope/select-collections" className="configured-edit-link">
                Edit Collections
              </EmbeddedLink>

              <p className="configured-selected-label">Selected ({isAllScope ? "All" : selectedCollections.length})</p>

              <ul className="configured-item-list">
                {isAllScope ? <li className="picker-empty">All collections enabled.</li> : null}
                {!isAllScope && selectedCollections.length === 0 ? <li className="picker-empty">No collections selected.</li> : null}
                {selectedCollections.map((collection) => (
                  <li key={collection.id} className="configured-item">
                    <span className="configured-thumb" aria-hidden>
                      <svg viewBox="0 0 24 24" role="img">
                        <path d="M3 18H21L15.5 10.5L11 15.5L8 12L3 18Z" fill="currentColor" opacity="0.85" />
                        <circle cx="8" cy="8" r="2.1" fill="currentColor" opacity="0.85" />
                      </svg>
                    </span>
                    <span className="configured-item-copy">
                      <strong>{collection.name}</strong>
                      <span>{collection.subtitle}</span>
                    </span>
                  </li>
                ))}
              </ul>
            </article>

            <article className="configured-card">
              <header className="configured-card-head">
                <span className="configured-card-icon" aria-hidden>
                  <svg viewBox="0 0 24 24" role="img">
                    <path
                      d="M12 5.5L8 9.3C7 10.2 5.7 10.7 4.3 10.7H3V12.6H21V10.7H19.7C18.3 10.7 17 10.2 16 9.3L12 5.5Z"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.8"
                      strokeLinejoin="round"
                    />
                    <path d="M12 4.3V2.6" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
                  </svg>
                </span>
                <h2>By Product</h2>
              </header>

              <p className="configured-card-description">Enable only selected products from your synced catalog.</p>

              <EmbeddedLink href="/dashboard/manage-scope/select-products" className="configured-edit-link">
                Edit Products
              </EmbeddedLink>

              <p className="configured-selected-label">Selected ({isAllScope ? "All" : selectedProducts.length})</p>

              <ul className="configured-item-list">
                {isAllScope ? <li className="picker-empty">All products enabled.</li> : null}
                {!isAllScope && selectedProducts.length === 0 ? <li className="picker-empty">No products selected.</li> : null}
                {selectedProducts.map((product) => (
                  <li key={product.id} className="configured-item configured-item-singleline">
                    <span className="configured-thumb" aria-hidden>
                      <svg viewBox="0 0 24 24" role="img">
                        <path d="M3 18H21L15.5 10.5L11 15.5L8 12L3 18Z" fill="currentColor" opacity="0.85" />
                        <circle cx="8" cy="8" r="2.1" fill="currentColor" opacity="0.85" />
                      </svg>
                    </span>
                    <span className="configured-item-copy configured-item-copy-singleline">
                      <strong>{product.name}</strong>
                    </span>
                  </li>
                ))}
              </ul>
            </article>
          </div>

          <section className="configured-success">
            <header>
              <svg viewBox="0 0 24 24" role="img" aria-hidden>
                <path d="M20 7L10 17L5 12" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.6" />
              </svg>
              <h3>Button Scope Saved</h3>
            </header>
            {isAllScope ? (
              <p>The virtual try-on button is enabled for all products and collections.</p>
            ) : (
              <p>
                The virtual try-on button scope is active for {selectedProducts.length} product(s) and {selectedCollections.length} collection(s).
              </p>
            )}
          </section>

          <div className="configured-actions">
            <button type="button" className="secondary-action" onClick={handleEnableEverywhere} disabled={isUpdatingAll || isAllScope}>
              {isUpdatingAll ? "Saving..." : isAllScope ? "Enabled On All Products" : "Enable On All Products"}
            </button>
          </div>
        </section>
      </section>
    </main>
  );
}
