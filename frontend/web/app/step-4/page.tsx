"use client";

import { useEffect, useMemo, useState } from "react";
import { EmbeddedLink, useEmbeddedRouter } from "../_components/EmbeddedNavigation";
import {
  getDefaultStoreId,
  getOnboardingStatus,
  getWidgetScope,
  listCollections,
  listProducts,
  saveWidgetScope,
  type CollectionResponse,
  type OnboardingStatusResponse,
  type ProductResponse,
  type WidgetScopeResponse
} from "../../lib/photoshootApi";

const placementChoices = [
  {
    id: "collections",
    description: "Enable on entire collections. This is the easiest way to manage the button.",
    actionLabel: "Select Collections",
    href: "/step-4/select-collections",
    accent: true,
  },
  {
    id: "products",
    description: "Enable on specific products. Good for testing or limited drops.",
    actionLabel: "Select Products",
    href: "/step-4/select-products",
    accent: false,
  }
];

export default function StepFourPage() {
  const router = useEmbeddedRouter();
  const storeId = useMemo(() => getDefaultStoreId(), []);
  const [onboardingStatus, setOnboardingStatus] = useState<OnboardingStatusResponse | null>(null);
  const [widgetScope, setWidgetScope] = useState<WidgetScopeResponse | null>(null);
  const [products, setProducts] = useState<ProductResponse[]>([]);
  const [collections, setCollections] = useState<CollectionResponse[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSelectingAll, setIsSelectingAll] = useState(false);
  const [isSkipping, setIsSkipping] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    if (!storeId) return;
    const controller = new AbortController();
    let active = true;
    setIsLoading(true);
    setErrorMessage("");

    (async () => {
      try {
        const [status, scope] = await Promise.all([
          getOnboardingStatus({ storeId, signal: controller.signal }),
          getWidgetScope({ storeId, signal: controller.signal })
        ]);
        if (!active) return;

        setOnboardingStatus(status);
        setWidgetScope(scope);

        const stepOrder: Record<string, number> = {
          welcome: 0,
          goals: 1,
          referral: 2,
          widget_scope: 3,
          theme_setup: 4,
          plan: 5,
          complete: 6
        };
        const hasAdvancedPastWidgetScope = (stepOrder[status.onboarding_step] ?? -1) > stepOrder.widget_scope;
        const hasExplicitScopedSelections =
          (scope.enabled_collection_ids?.length ?? 0) > 0 || (scope.enabled_product_ids?.length ?? 0) > 0;
        const hasSavedAllScope = scope.scope_type === "all" && hasAdvancedPastWidgetScope;
        const shouldShowSummary = hasExplicitScopedSelections || hasSavedAllScope;

        if (!shouldShowSummary) {
          setProducts([]);
          setCollections([]);
          return;
        }

        const [productList, collectionList] = await Promise.all([
          listProducts({ storeId, limit: 250, signal: controller.signal }),
          listCollections({ storeId, limit: 250, signal: controller.signal })
        ]);
        if (!active) return;
        setProducts(productList);
        setCollections(collectionList);
      } catch (error: unknown) {
        if (!active || controller.signal.aborted) return;
        setErrorMessage(error instanceof Error ? error.message : "Failed to load widget scope.");
      } finally {
        if (active) setIsLoading(false);
      }
    })();

    return () => {
      active = false;
      controller.abort();
    };
  }, [storeId]);

  const scopeType = widgetScope?.scope_type ?? "all";
  const enabledCollectionIds = widgetScope?.enabled_collection_ids ?? [];
  const enabledProductIds = widgetScope?.enabled_product_ids ?? [];

  const hasExplicitScopedSelections = enabledCollectionIds.length > 0 || enabledProductIds.length > 0;

  const currentStep = onboardingStatus?.onboarding_step ?? "";
  const stepOrder: Record<string, number> = {
    welcome: 0,
    goals: 1,
    referral: 2,
    widget_scope: 3,
    theme_setup: 4,
    plan: 5,
    complete: 6
  };
  const hasAdvancedPastWidgetScope = (stepOrder[currentStep] ?? -1) > stepOrder.widget_scope;
  const hasSavedAllScope = scopeType === "all" && hasAdvancedPastWidgetScope;

  const showSummary = hasExplicitScopedSelections || hasSavedAllScope;

  const productTitleById = useMemo(() => {
    const lookup = new Map<string, string>();
    products.forEach((product) => lookup.set(product.shopify_product_id, product.title));
    return lookup;
  }, [products]);

  const selectedCollections = useMemo(() => {
    const lookup = new Map(collections.map((collection) => [collection.id, collection]));
    return enabledCollectionIds.map((id) => {
      const collection = lookup.get(id);
      return {
        id,
        name: collection?.title ?? id,
        subtitle: collection?.handle ? `Handle: ${collection.handle}` : "Collection ID"
      };
    });
  }, [collections, enabledCollectionIds]);

  const selectedProducts = useMemo(
    () => enabledProductIds.map((id) => ({ id, name: productTitleById.get(id) ?? id })),
    [enabledProductIds, productTitleById]
  );

  const handleSelectAll = async () => {
    if (!storeId) {
      setErrorMessage("Open the app from Shopify Admin to save widget scope.");
      return;
    }
    setIsSelectingAll(true);
    setErrorMessage("");
    try {
      await saveWidgetScope({
        storeId,
        scopeType: "all",
        enabledCollectionIds: [],
        enabledProductIds: []
      });
      setWidgetScope({
        scope_type: "all",
        enabled_collection_ids: [],
        enabled_product_ids: []
      });
      setOnboardingStatus((current) => {
        if (!current) {
          return {
            store_id: storeId,
            onboarding_step: "theme_setup",
            onboarding_completed: false,
            plan_name: "free"
          };
        }
        if (current.onboarding_step !== "widget_scope") return current;
        return { ...current, onboarding_step: "theme_setup" };
      });
      router.replace("/step-4");
    } catch (error: unknown) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to save widget scope.");
    } finally {
      setIsSelectingAll(false);
    }
  };

  const handleSkip = async () => {
    if (!storeId) {
      router.push("/step-5");
      return;
    }
    setIsSkipping(true);
    setErrorMessage("");
    try {
      await saveWidgetScope({
        storeId,
        scopeType: "selected_products",
        enabledCollectionIds: [],
        enabledProductIds: []
      });
      router.push("/step-5");
    } catch (error: unknown) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to save widget scope.");
    } finally {
      setIsSkipping(false);
    }
  };

  if (showSummary) {
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
                href="/step-3"
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
                  {selectedCollections.map((collection) => (
                    <li key={collection.id} style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
                      <span style={{ width: 6, height: 6, borderRadius: "50%", marginTop: 6, flexShrink: 0, background: "#7E0175" }} />
                      <span>
                        <span style={{ fontSize: 12, fontWeight: 500, display: "block", color: "#1a1a1a" }}>{collection.name}</span>
                        <span style={{ fontSize: 11, color: "#9ca3af" }}>{collection.subtitle}</span>
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
                  {selectedProducts.map((product) => (
                    <li key={product.id} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ width: 6, height: 6, borderRadius: "50%", flexShrink: 0, background: "#7E0175" }} />
                      <span style={{ fontSize: 12, fontWeight: 500, color: "#1a1a1a" }}>{product.name}</span>
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
              <button
                type="button"
                onClick={handleSkip}
                disabled={isSkipping}
                style={{
                  padding: "9px 20px",
                  borderRadius: 10,
                  fontSize: 13,
                  fontWeight: 600,
                  border: "1.5px solid #e5e5e5",
                  color: "#6b7280",
                  background: "#fff",
                  cursor: isSkipping ? "not-allowed" : "pointer",
                  opacity: isSkipping ? 0.7 : 1
                }}
              >
                {isSkipping ? "Saving..." : "Skip for now"}
              </button>
              <EmbeddedLink
                href="/step-5"
                style={{ padding: "9px 22px", borderRadius: 10, fontSize: 13, fontWeight: 600, color: "#fff", background: "linear-gradient(135deg, #7E0175 0%, #BC174A 55%, #E40206 100%)", textDecoration: "none" }}
              >
                Continue
              </EmbeddedLink>
            </div>
          </div>

        </div>
      </div>
    );
  }

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
              href="/step-3"
              style={{ width: 32, height: 32, borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, marginTop: 2, background: "#f3f4f6", color: "#6b7280" }}
              aria-label="Go to previous step"
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

          {isLoading && <p style={{ fontSize: 13, marginBottom: 16, padding: "8px 12px", borderRadius: 8, background: "rgba(126,1,117,0.06)", color: "#7E0175" }}>Loading widget scope...</p>}
          {!storeId && <p style={{ fontSize: 13, marginBottom: 16, padding: "8px 12px", borderRadius: 8, background: "#fff1f1", color: "#dc2626" }}>Open the app from Shopify Admin to save widget scope.</p>}
          {errorMessage && <p style={{ fontSize: 13, marginBottom: 16, padding: "8px 12px", borderRadius: 8, background: "#fff1f1", color: "#dc2626" }}>{errorMessage}</p>}

          <ul style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, listStyle: "none", margin: 0, padding: 0 }}>
            {placementChoices.map((choice) => (
              <li
                key={choice.id}
                style={{ borderRadius: 12, padding: 20, display: "flex", flexDirection: "column", gap: 16, border: "1px solid rgba(0,0,0,0.07)", background: "#fafafa" }}
              >
                <p style={{ margin: 0, fontSize: 14, lineHeight: 1.6, color: "#6b7280" }}>{choice.description}</p>
                <EmbeddedLink
                  href={choice.href}
                  style={
                    choice.accent
                      ? { display: "block", textAlign: "center", padding: "10px 16px", borderRadius: 10, fontSize: 13, fontWeight: 600, background: "linear-gradient(135deg, #7E0175 0%, #BC174A 55%, #E40206 100%)", color: "#fff", textDecoration: "none" }
                      : { display: "block", textAlign: "center", padding: "10px 16px", borderRadius: 10, fontSize: 13, fontWeight: 600, background: "#fff", border: "1.5px solid #7E0175", color: "#7E0175", textDecoration: "none" }
                  }
                >
                  {choice.actionLabel}
                </EmbeddedLink>
              </li>
            ))}
          </ul>
        </div>

        {/* Footer */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 24px", borderTop: "1px solid #f0f0f0" }}>
          <EmbeddedLink href="/settings/support" style={{ fontSize: 13, color: "#7E0175", textDecoration: "underline" }}>
            Need help? Contact our support team
          </EmbeddedLink>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <button
              type="button"
              onClick={handleSkip}
              disabled={isSkipping || isSelectingAll}
              style={{
                padding: "9px 20px",
                borderRadius: 10,
                fontSize: 13,
                fontWeight: 600,
                border: "1.5px solid #e5e5e5",
                color: "#6b7280",
                background: "#fff",
                cursor: isSkipping || isSelectingAll ? "not-allowed" : "pointer",
                opacity: isSkipping || isSelectingAll ? 0.7 : 1
              }}
            >
              {isSkipping ? "Saving..." : "Skip"}
            </button>
            <button
              type="button"
              onClick={handleSelectAll}
              disabled={isSelectingAll || isSkipping}
              style={{
                padding: "9px 22px", borderRadius: 10, fontSize: 13, fontWeight: 600, color: "#fff",
                background: "linear-gradient(135deg, #7E0175 0%, #BC174A 55%, #E40206 100%)",
                border: "none",
                cursor: isSelectingAll || isSkipping ? "not-allowed" : "pointer",
                opacity: isSelectingAll || isSkipping ? 0.7 : 1,
              }}
            >
              {isSelectingAll ? "Saving..." : "Select all"}
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}
