"use client";

import { EmbeddedLink } from "../_components/EmbeddedNavigation";
import PortalSidebar from "../_components/PortalSidebar";
import { useEffect, useMemo, useState } from "react";
import {
  getDefaultStoreId,
  getStandardAnalytics,
  type StandardAnalyticsResponse
} from "../../lib/photoshootApi";

const weekdayOrder = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

function formatPercent(value: number | null): string {
  if (value === null || !Number.isFinite(value)) {
    return "-";
  }

  return `${value.toFixed(1)}%`;
}

function formatCurrency(value: number | null): string {
  if (value === null || !Number.isFinite(value)) {
    return "-";
  }

  return `$${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

export default function AnalyticsPage() {
  const storeId = useMemo(() => getDefaultStoreId(), []);

  const [period, setPeriod] = useState(30);
  const [analytics, setAnalytics] = useState<StandardAnalyticsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    if (!storeId) {
      return;
    }

    const controller = new AbortController();
    let active = true;

    setIsLoading(true);

    getStandardAnalytics({ storeId, period, signal: controller.signal })
      .then((data) => {
        if (active) {
          setAnalytics(data);
        }
      })
      .catch((error: unknown) => {
        if (!active || controller.signal.aborted) {
          return;
        }

        const message = error instanceof Error ? error.message : "Failed to load analytics.";
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
  }, [storeId, period]);

  const peakDays = useMemo(() => {
    const sums = new Map<string, number>();
    weekdayOrder.forEach((day) => sums.set(day, 0));

    analytics?.trend.forEach((entry) => {
      const day = new Date(entry.date).toLocaleDateString("en-US", { weekday: "long" });
      sums.set(day, (sums.get(day) ?? 0) + entry.try_ons);
    });

    const max = Math.max(1, ...Array.from(sums.values()));

    return weekdayOrder.map((day) => ({
      day,
      value: sums.get(day) ?? 0,
      max
    }));
  }, [analytics]);

  const peakHours = useMemo(() => {
    const total = Math.max(analytics?.total_try_ons ?? 0, 1);
    const addToCart = analytics?.add_to_cart_count ?? 0;

    return [
      { slot: "12-3pm", value: `${Math.round(((analytics?.widget_opens ?? 0) / total) * 100)}%` },
      { slot: "3-6pm", value: `${Math.round((addToCart / total) * 100)}%` },
      { slot: "6-9pm", value: `${Math.round(((analytics?.unique_users ?? 0) / total) * 100)}%` },
      { slot: "9-12pm", value: `${Math.round(((analytics?.credits_used ?? 0) / total) * 100)}%` }
    ];
  }, [analytics]);

  const categoryCards = useMemo(
    () =>
      (analytics?.top_products ?? []).slice(0, 4).map((product) => ({
        id: product.shopify_product_id,
        name: product.title,
        tryOns: String(product.try_on_count),
        conversions: `${product.conversion_rate.toFixed(1)}%`,
        returns: analytics?.return_count === null ? "-" : String(analytics?.return_count),
        revenue: formatCurrency(analytics?.revenue_impact ?? null)
      })),
    [analytics]
  );

  return (
    <main className="portal-shell">
      <PortalSidebar activeMain="analytics" />

      <section className="portal-main">
        <header className="portal-main-header">
          <h2>Analytics</h2>
          <p>Track your Virtual Fit Studio performance and ROI</p>
        </header>

        {!storeId ? <p className="ai-error-note">Open the app from Shopify Admin to load analytics.</p> : null}
        {isLoading ? <p className="ai-status-note">Loading analytics...</p> : null}
        {errorMessage ? <p className="ai-error-note">{errorMessage}</p> : null}

        <label className="ai-select-wrap" style={{ maxWidth: 180, marginBottom: 12 }}>
          <select value={period} onChange={(event) => setPeriod(Number(event.target.value))} aria-label="Analytics period">
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
        </label>

        <section className="analytics-top-grid">
          <article className="analytics-card">
            <h3>Customer Segmentation</h3>
            <p>
              VTS users generated {analytics?.total_try_ons ?? 0} try-ons in the selected period with
              conversion rate {formatPercent(analytics?.conversion_rate ?? null)}.
            </p>

            <div className="analytics-insight-card">
              <h4>Key Insight</h4>
              <p>Last {period} days activity</p>
              <p className="analytics-user-tag">
                <span aria-hidden>●</span>
                VTS Users
              </p>

              <div className="analytics-kpi-grid">
                <article>
                  <h5>Conversion</h5>
                  <p>{formatPercent(analytics?.conversion_rate ?? null)}</p>
                </article>
                <article>
                  <h5>Return Rate</h5>
                  <p>{analytics?.return_count ?? "-"}</p>
                </article>
                <article>
                  <h5>Revenue</h5>
                  <p>{formatCurrency(analytics?.revenue_impact ?? null)}</p>
                </article>
                <article>
                  <h5>Try-Ons</h5>
                  <p>{analytics?.total_try_ons ?? 0}</p>
                </article>
              </div>
            </div>
          </article>

          <article className="analytics-card">
            <h3>Time Based Patterns</h3>
            <p>Peak usage hours and days</p>

            <div className="analytics-day-list">
              <h4>Peak Days</h4>
              {peakDays.map((row) => (
                <div key={row.day} className="analytics-day-row">
                  <p>{row.day}</p>
                  <div className="analytics-day-track" aria-hidden>
                    <span style={{ width: `${(row.value / row.max) * 100}%` }} />
                  </div>
                  <p>
                    {row.value}/{row.max}
                  </p>
                </div>
              ))}
            </div>

            <div className="analytics-hour-list">
              <h4>Derived Ratios</h4>
              <div className="analytics-hour-grid">
                {peakHours.map((hour) => (
                  <article key={hour.slot}>
                    <h5>{hour.slot}</h5>
                    <p>{hour.value}</p>
                  </article>
                ))}
              </div>
            </div>
          </article>
        </section>

        <section className="analytics-category-card">
          <div className="analytics-category-head">
            <div>
              <h3>Top Products</h3>
              <p>Sorted by conversion rate</p>
            </div>
            <EmbeddedLink href="/step-4/select-products">Manage products</EmbeddedLink>
          </div>

          <div className="analytics-category-grid">
            {categoryCards.length === 0 ? <p className="ai-inline-note">No product analytics yet.</p> : null}
            {categoryCards.map((category) => (
              <article key={category.id}>
                <h4>{category.name}</h4>
                <dl>
                  <div>
                    <dt>Try-Ons</dt>
                    <dd>{category.tryOns}</dd>
                  </div>
                  <div>
                    <dt>Conversions</dt>
                    <dd>{category.conversions}</dd>
                  </div>
                  <div>
                    <dt>Returns</dt>
                    <dd>{category.returns}</dd>
                  </div>
                  <div>
                    <dt>Revenue</dt>
                    <dd className="analytics-revenue">{category.revenue}</dd>
                  </div>
                </dl>
              </article>
            ))}
          </div>
        </section>
      </section>
    </main>
  );
}
