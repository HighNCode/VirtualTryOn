"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo } from "react";
import type { ComponentProps } from "react";

const EMBEDDED_QUERY_KEYS = ["embedded", "host", "locale", "shop"] as const;
const STORAGE_KEY = "optimo-shopify-embedded-params";

function isExternalHref(href: string): boolean {
  return /^(?:[a-z][a-z\d+.-]*:|\/\/|#)/i.test(href);
}

function extractEmbeddedParams(params: URLSearchParams): URLSearchParams {
  const extracted = new URLSearchParams();

  EMBEDDED_QUERY_KEYS.forEach((key) => {
    const value = params.get(key);
    if (value) {
      extracted.set(key, value);
    }
  });

  return extracted;
}

function readPersistedEmbeddedParams(): URLSearchParams {
  if (typeof window === "undefined") {
    return new URLSearchParams();
  }

  const raw = window.sessionStorage.getItem(STORAGE_KEY) ?? window.localStorage.getItem(STORAGE_KEY);
  return raw ? new URLSearchParams(raw) : new URLSearchParams();
}

function persistEmbeddedParams(params: URLSearchParams): void {
  if (typeof window === "undefined") {
    return;
  }

  const embeddedParams = extractEmbeddedParams(params);
  const serialized = embeddedParams.toString();

  if (!serialized) {
    return;
  }

  window.sessionStorage.setItem(STORAGE_KEY, serialized);
  window.localStorage.setItem(STORAGE_KEY, serialized);
}

function mergeEmbeddedParams(target: URLSearchParams, fallback: URLSearchParams): void {
  EMBEDDED_QUERY_KEYS.forEach((key) => {
    if (!target.has(key)) {
      const value = fallback.get(key);
      if (value) {
        target.set(key, value);
      }
    }
  });
}

function buildEmbeddedHref(href: string, currentSearch: string): string {
  if (!href || isExternalHref(href)) {
    return href;
  }

  const baseUrl = typeof window !== "undefined" ? window.location.origin : "https://shopify.com";
  const url = new URL(href, baseUrl);
  const currentParams = new URLSearchParams(currentSearch);

  mergeEmbeddedParams(url.searchParams, extractEmbeddedParams(currentParams));
  mergeEmbeddedParams(url.searchParams, readPersistedEmbeddedParams());

  return `${url.pathname}${url.search}${url.hash}`;
}

export function EmbeddedNavigationBootstrap() {
  const pathname = usePathname();

  useEffect(() => {
    const search = window.location.search.replace(/^\?/, "");
    const currentParams = new URLSearchParams(search);
    const currentEmbeddedParams = extractEmbeddedParams(currentParams);

    if (currentEmbeddedParams.toString()) {
      persistEmbeddedParams(currentParams);
      return;
    }

    const persistedParams = readPersistedEmbeddedParams();
    if (!persistedParams.toString()) {
      return;
    }

    mergeEmbeddedParams(currentParams, persistedParams);
    const nextSearch = currentParams.toString();

    if (nextSearch === search) {
      return;
    }

    const nextUrl = `${pathname}${nextSearch ? `?${nextSearch}` : ""}${window.location.hash}`;
    window.history.replaceState(null, "", nextUrl);
  }, [pathname]);

  return null;
}

type EmbeddedLinkProps = Omit<ComponentProps<typeof Link>, "href"> & {
  href: string;
};

export function EmbeddedLink({ href, ...props }: EmbeddedLinkProps) {
  const resolvedHref = buildEmbeddedHref(
    href,
    typeof window !== "undefined" ? window.location.search.replace(/^\?/, "") : ""
  );

  return <Link href={resolvedHref} {...props} />;
}

export function useEmbeddedRouter() {
  const router = useRouter();

  return useMemo(
    () => ({
      ...router,
      push: (href: string, options?: Parameters<typeof router.push>[1]) =>
        router.push(buildEmbeddedHref(href, typeof window !== "undefined" ? window.location.search.replace(/^\?/, "") : ""), options),
      replace: (href: string, options?: Parameters<typeof router.replace>[1]) =>
        router.replace(
          buildEmbeddedHref(href, typeof window !== "undefined" ? window.location.search.replace(/^\?/, "") : ""),
          options
        )
    }),
    [router]
  );
}
