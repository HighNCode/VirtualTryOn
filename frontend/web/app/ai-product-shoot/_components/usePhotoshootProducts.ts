"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  listProductsPage,
  syncProducts,
  toShopifyProductGid,
  type ProductResponse
} from "../../../lib/photoshootApi";

const PAGE_SIZE = 30;

export function extractProductImageUrls(product: ProductResponse | null): string[] {
  if (!product) {
    return [];
  }
  return product.images
    .map((image) => (typeof image.src === "string" ? image.src.trim() : ""))
    .filter((url): url is string => url.length > 0);
}

export function usePhotoshootProducts(storeId: string) {
  const [products, setProducts] = useState<ProductResponse[]>([]);
  const [nextOffset, setNextOffset] = useState<number | null>(0);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedProductId, setSelectedProductId] = useState<string | null>(null);

  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  const hasAttemptedAutoSync = useRef(false);

  const refreshProducts = useCallback(
    async (signal?: AbortSignal) => {
      if (!storeId.trim()) {
        setProducts([]);
        setNextOffset(0);
        return;
      }

      setIsLoading(true);
      setErrorMessage("");

      try {
        let firstPage = await listProductsPage({
          storeId: storeId.trim(),
          limit: PAGE_SIZE,
          offset: 0,
          signal
        });

        if (firstPage.products.length === 0 && !hasAttemptedAutoSync.current) {
          hasAttemptedAutoSync.current = true;
          setIsSyncing(true);
          try {
            await syncProducts({ storeId: storeId.trim() });
            firstPage = await listProductsPage({
              storeId: storeId.trim(),
              limit: PAGE_SIZE,
              offset: 0,
              signal
            });
          } finally {
            setIsSyncing(false);
          }
        }

        setProducts(firstPage.products);
        setNextOffset(firstPage.nextOffset);
        setSelectedProductId((current) => {
          if (!current) {
            return firstPage.products[0]?.product_id ?? null;
          }
          return firstPage.products.some((item) => item.product_id === current)
            ? current
            : firstPage.products[0]?.product_id ?? null;
        });
      } catch (error: unknown) {
        const message = error instanceof Error ? error.message : "Failed to load products.";
        setErrorMessage(message);
      } finally {
        setIsLoading(false);
      }
    },
    [storeId]
  );

  useEffect(() => {
    const controller = new AbortController();
    hasAttemptedAutoSync.current = false;
    void refreshProducts(controller.signal);
    return () => controller.abort();
  }, [refreshProducts]);

  const loadMoreProducts = useCallback(async () => {
    if (!storeId.trim() || nextOffset === null || isLoadingMore) {
      return;
    }
    setIsLoadingMore(true);
    setErrorMessage("");
    try {
      const page = await listProductsPage({
        storeId: storeId.trim(),
        limit: PAGE_SIZE,
        offset: nextOffset
      });
      setProducts((current) => {
        const known = new Set(current.map((item) => item.product_id));
        const appended = page.products.filter((item) => !known.has(item.product_id));
        return [...current, ...appended];
      });
      setNextOffset(page.nextOffset);
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Failed to load more products.";
      setErrorMessage(message);
    } finally {
      setIsLoadingMore(false);
    }
  }, [isLoadingMore, nextOffset, storeId]);

  const syncNow = useCallback(async () => {
    if (!storeId.trim()) {
      return;
    }
    setIsSyncing(true);
    setErrorMessage("");
    try {
      await syncProducts({ storeId: storeId.trim() });
      await refreshProducts();
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Failed to sync products.";
      setErrorMessage(message);
    } finally {
      setIsSyncing(false);
    }
  }, [refreshProducts, storeId]);

  const visibleProducts = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    if (!query) {
      return products;
    }
    return products.filter((product) => product.title.toLowerCase().includes(query));
  }, [products, searchQuery]);

  const selectedProduct = useMemo(
    () => products.find((item) => item.product_id === selectedProductId) ?? null,
    [products, selectedProductId]
  );
  const selectedProductGid = selectedProduct ? toShopifyProductGid(selectedProduct) : "";

  return {
    products,
    visibleProducts,
    selectedProduct,
    selectedProductId,
    selectedProductGid,
    searchQuery,
    setSearchQuery,
    setSelectedProductId,
    isLoading,
    isLoadingMore,
    isSyncing,
    errorMessage,
    canLoadMore: nextOffset !== null,
    loadMoreProducts,
    refreshProducts,
    syncNow
  };
}
