"use client";

import { useEffect, useMemo, useState } from "react";
import PortalSidebar from "../_components/PortalSidebar";
import {
  getDefaultStoreId,
  getStandardAnalytics,
  type StandardAnalyticsResponse
} from "../../lib/photoshootApi";

function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "-";
  }
  return `${value.toFixed(1)}%`;
}

function formatCurrency(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "-";
  }
  return `$${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "-";
  }
  return value.toLocaleString();
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
    setErrorMessage("");

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

  const trendRows = analytics?.performance_trend ?? [];
  const trendSvg = useMemo(() => {
    if (trendRows.length === 0) {
      return { points: "", labels: [] as string[] };
    }

    const width = 700;
    const height = 260;
    const leftPad = 22;
    const rightPad = 22;
    const topPad = 20;
    const bottomPad = 30;
    const maxValue = Math.max(1, ...trendRows.map((entry) => entry.try_on_sessions));
    const usableW = width - leftPad - rightPad;
    const usableH = height - topPad - bottomPad;

    const points = trendRows
      .map((entry, index) => {
        const x = leftPad + (trendRows.length === 1 ? usableW / 2 : (index / (trendRows.length - 1)) * usableW);
        const y = topPad + usableH - (entry.try_on_sessions / maxValue) * usableH;
        return `${x.toFixed(2)},${y.toFixed(2)}`;
      })
      .join(" ");

    const labels = [
      trendRows[0]?.date ?? "",
      trendRows[Math.floor((trendRows.length - 1) / 2)]?.date ?? "",
      trendRows[trendRows.length - 1]?.date ?? ""
    ];

    return { points, labels };
  }, [trendRows]);

  const topProducts = analytics?.top_performing_products ?? [];

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

        <div className="analytics-v2-toolbar">
          <label className="ai-select-wrap analytics-v2-period">
            <select value={period} onChange={(event) => setPeriod(Number(event.target.value))} aria-label="Analytics period">
              <option value={7}>Last 7 days</option>
              <option value={30}>Last 30 days</option>
              <option value={90}>Last 90 days</option>
            </select>
          </label>
        </div>

        <section className="analytics-v2-kpis">
          <article className="analytics-v2-kpi">
            <h3>Return Reduction</h3>
            <p>{formatPercent(analytics?.return_reduction)}</p>
            <span>vs previous equal period</span>
          </article>

          <article className="analytics-v2-kpi">
            <h3>Conversion Rate</h3>
            <p>{formatPercent(analytics?.conversion_rate)}</p>
            <span>{formatNumber(analytics?.conversions)} attributed orders</span>
          </article>

          <article className="analytics-v2-kpi">
            <h3>Revenue Impact</h3>
            <p>{formatCurrency(analytics?.revenue_impact)}</p>
            <span>Attributed line-item revenue</span>
          </article>

          <article className="analytics-v2-kpi">
            <h3>Active Users</h3>
            <p>{formatNumber(analytics?.active_users)}</p>
            <span>{formatNumber(analytics?.anonymous_users)} anonymous users</span>
          </article>
        </section>

        <section className="analytics-v2-main-grid">
          <article className="analytics-v2-card">
            <div className="analytics-v2-card-head">
              <h3>Performance Trends</h3>
              <p>Daily try-on sessions</p>
            </div>
            <div className="analytics-v2-trend">
              {trendRows.length === 0 ? (
                <p className="ai-inline-note">No trend data yet.</p>
              ) : (
                <>
                  <svg viewBox="0 0 700 260" role="img" aria-label="Try-on session trend">
                    <polyline className="analytics-v2-trend-line" points={trendSvg.points} />
                    <polyline className="analytics-v2-trend-fill" points={`${trendSvg.points} 678,230 22,230`} />
                  </svg>
                  <div className="analytics-v2-trend-labels">
                    {trendSvg.labels.map((label, index) => (
                      <span key={`${label}-${index}`}>{label}</span>
                    ))}
                  </div>
                </>
              )}
            </div>
          </article>

          <article className="analytics-v2-card analytics-v2-quick">
            <div className="analytics-v2-card-head">
              <h3>Quick Stats</h3>
              <p>Current period snapshot</p>
            </div>
            <div className="analytics-v2-quick-list">
              <div>
                <span>Try-on Sessions</span>
                <strong>{formatNumber(analytics?.try_on_sessions)}</strong>
              </div>
              <div>
                <span>Widget Click Rate</span>
                <strong>{formatPercent(analytics?.widget_click_rate)}</strong>
              </div>
              <div>
                <span>Attributed Returns</span>
                <strong>{formatNumber(analytics?.return_count)}</strong>
              </div>
              <div>
                <span>Credits Used</span>
                <strong>{formatNumber(analytics?.credits_used)}</strong>
              </div>
            </div>
          </article>
        </section>

        <section className="analytics-v2-card analytics-v2-table-card">
          <div className="analytics-v2-card-head">
            <h3>Top Performing Products</h3>
            <p>Try-on Sessions, Conversion, Returns, Revenue</p>
          </div>

          {topProducts.length === 0 ? (
            <p className="ai-inline-note">No product analytics yet.</p>
          ) : (
            <div className="analytics-v2-table-wrap">
              <table className="analytics-v2-table">
                <thead>
                  <tr>
                    <th>Product</th>
                    <th>Try-on Sessions</th>
                    <th>Conversion %</th>
                    <th>Return %</th>
                    <th>Revenue</th>
                  </tr>
                </thead>
                <tbody>
                  {topProducts.map((product) => (
                    <tr key={product.shopify_product_id}>
                      <td>{product.title}</td>
                      <td>{formatNumber(product.try_on_sessions)}</td>
                      <td>{formatPercent(product.conversion_rate)}</td>
                      <td>{formatPercent(product.return_rate)}</td>
                      <td>{formatCurrency(product.revenue_impact)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </section>
    </main>
  );
}
