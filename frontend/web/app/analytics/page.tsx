"use client";

import { useEffect, useMemo, useState } from "react";
import { motion, type Variants } from "framer-motion";
import { DollarSign, Lightbulb, PackageCheck, TrendingDown, TrendingUp, Users } from "lucide-react";
import PortalSidebar from "../_components/PortalSidebar";
import PortalTopbar from "../_components/PortalTopbar";
import {
  getDefaultStoreId,
  getStandardAnalytics,
  type StandardAnalyticsResponse,
} from "../../lib/photoshootApi";

function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "-";
  return `${value.toFixed(1)}%`;
}

function formatCurrency(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "-";
  return `$${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "-";
  return value.toLocaleString();
}

const cardVariants: Variants = {
  hidden: { opacity: 0, y: 12 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { duration: 0.35, ease: "easeOut", delay: i * 0.05 },
  }),
};

function formatSignedPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "Awaiting data";
  return `${value >= 0 ? "+" : ""}${value.toFixed(1)}%`;
}

export default function AnalyticsPage() {
  const storeId = useMemo(() => getDefaultStoreId(), []);
  const [period, setPeriod] = useState(30);
  const [analytics, setAnalytics] = useState<StandardAnalyticsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    if (!storeId) return;

    const controller = new AbortController();
    let active = true;
    setIsLoading(true);
    setErrorMessage("");

    getStandardAnalytics({ storeId, period, signal: controller.signal })
      .then((data) => {
        if (active) setAnalytics(data);
      })
      .catch((error: unknown) => {
        if (!active || controller.signal.aborted) return;
        setErrorMessage(error instanceof Error ? error.message : "Failed to load analytics.");
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [storeId, period]);

  const trendRows = analytics?.performance_trend ?? [];
  const chart = useMemo(() => {
    const width = 1200;
    const height = 220;
    const leftPad = 34;
    const rightPad = 18;
    const topPad = 20;
    const bottomPad = 32;
    const maxValue = Math.max(40, ...trendRows.map((row) => row.try_on_sessions));
    const usableW = width - leftPad - rightPad;
    const usableH = height - topPad - bottomPad;

    const points = trendRows
      .map((row, index) => {
        const x = leftPad + (trendRows.length === 1 ? usableW / 2 : (index / (trendRows.length - 1)) * usableW);
        const y = topPad + usableH - (row.try_on_sessions / maxValue) * usableH;
        return `${x.toFixed(2)},${y.toFixed(2)}`;
      })
      .join(" ");

    return { width, height, leftPad, rightPad, topPad, bottomPad, points };
  }, [trendRows]);

  const totalQuickStat = Math.max(
    analytics?.try_on_sessions ?? 0,
    analytics?.widget_opens ?? 0,
    analytics?.add_to_cart_count ?? 0,
    analytics?.credits_used ?? 0,
    1
  );

  const kpis = [
    {
      label: "Active Users",
      value: formatNumber(analytics?.active_users),
      delta: `${formatNumber(analytics?.anonymous_users)} anonymous`,
      icon: Users,
    },
    {
      label: "Return Reduction",
      value: formatPercent(analytics?.return_reduction),
      delta: analytics?.return_reduction === null || analytics?.return_reduction === undefined ? "Shopify orders unavailable" : `${formatSignedPercent(analytics.return_reduction)} vs previous period`,
      icon: TrendingDown,
    },
    {
      label: "Conversion Rate",
      value: formatPercent(analytics?.conversion_rate),
      delta: `${formatNumber(analytics?.conversions)} attributed orders`,
      icon: TrendingUp,
    },
    {
      label: "Revenue Impact",
      value: formatCurrency(analytics?.revenue_impact),
      delta: analytics?.revenue_impact === null || analytics?.revenue_impact === undefined ? "Shopify orders unavailable" : "Attributed revenue",
      icon: DollarSign,
    },
  ];

  const quickStats = [
    { label: "Try-on Sessions", value: analytics?.try_on_sessions ?? 0 },
    { label: "Widget Opens", value: analytics?.widget_opens ?? 0 },
    { label: "Add to Cart", value: analytics?.add_to_cart_count ?? 0 },
    { label: "Credits Used", value: analytics?.credits_used ?? 0 },
  ];

  const products = (analytics?.top_performing_products ?? [])
    .slice(0, 5)
    .map((product) => ({
        title: product.title,
        tryOnSessions: formatNumber(product.try_on_sessions),
        conversion: formatPercent(product.conversion_rate),
        returns: formatPercent(product.return_rate),
        revenue: formatCurrency(product.revenue_impact),
      }));

  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden", background: "#f6f4f4" }}>
      <PortalSidebar activeMain="analytics" />

      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "auto" }}>
        <PortalTopbar title="Analytics" subtitle="Performance insights for your store" />

        <div style={{ flex: 1, padding: "22px 24px", display: "flex", flexDirection: "column", gap: 18 }}>
          {!storeId && (
            <p style={{ margin: 0, fontSize: 13, padding: "8px 16px", borderRadius: 10, background: "#fff1f1", color: "#dc2626" }}>
              Open the app from Shopify Admin to load analytics.
            </p>
          )}
          {isLoading && (
            <p style={{ margin: 0, fontSize: 13, padding: "8px 16px", borderRadius: 10, background: "rgba(126,1,117,0.05)", color: "#7E0175" }}>
              Loading analytics...
            </p>
          )}
          {errorMessage && (
            <p style={{ margin: 0, fontSize: 13, padding: "8px 16px", borderRadius: 10, background: "#fff1f1", color: "#dc2626" }}>
              {errorMessage}
            </p>
          )}

          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))", gap: 18 }}>
            {kpis.map((kpi, index) => {
              const Icon = kpi.icon;
              return (
                <motion.section
                  key={kpi.label}
                  custom={index}
                  variants={cardVariants}
                  initial="hidden"
                  animate="visible"
                  style={{ minHeight: 138, background: "#fff", borderRadius: 12, padding: 18, boxShadow: "0 1px 3px rgba(0,0,0,0.06)", border: "1px solid rgba(0,0,0,0.05)" }}
                >
                  <span style={{ width: 34, height: 34, borderRadius: 9, display: "flex", alignItems: "center", justifyContent: "center", background: "rgba(126,1,117,0.1)", color: "#9a007f" }}>
                    <Icon size={16} />
                  </span>
                  <p style={{ margin: "16px 0 2px", fontSize: 28, lineHeight: 1, fontWeight: 900, color: "#111827" }}>
                    {kpi.value}
                  </p>
                  <p style={{ margin: "0 0 12px", fontSize: 13, color: "#5f6b85" }}>
                    {kpi.label}
                  </p>
                  <span style={{ display: "inline-flex", alignItems: "center", minHeight: 20, borderRadius: 999, padding: "3px 9px", fontSize: 11, fontWeight: 700, color: "#15803d", background: "#dcfce7" }}>
                    {kpi.delta}
                  </span>
                </motion.section>
              );
            })}
          </div>

          <motion.section
            custom={4}
            variants={cardVariants}
            initial="hidden"
            animate="visible"
            style={{ background: "#fff", borderRadius: 12, padding: "20px 20px 16px", boxShadow: "0 1px 3px rgba(0,0,0,0.06)", border: "1px solid rgba(0,0,0,0.05)" }}
          >
            <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 12 }}>
              <div>
                <h3 style={{ margin: "0 0 4px", fontSize: 15, fontWeight: 800, color: "#111827" }}>Performance Trend</h3>
                <p style={{ margin: 0, fontSize: 13, color: "#5f6b85" }}>Try-on activity over the last {period} days</p>
              </div>
              <select
                value={period}
                onChange={(event) => setPeriod(Number(event.target.value))}
                aria-label="Analytics period"
                style={{ padding: "5px 12px", borderRadius: 999, border: "none", background: "rgba(126,1,117,0.08)", color: "#9a007f", fontSize: 12, fontWeight: 700, outline: "none", fontFamily: "inherit" }}
              >
                <option value={7}>Last 7 days</option>
                <option value={30}>Last 30 days</option>
                <option value={90}>Last 90 days</option>
              </select>
            </div>

            <svg viewBox={`0 0 ${chart.width} ${chart.height}`} role="img" aria-label="Performance trend chart" style={{ width: "100%", height: 220, display: "block" }}>
              <defs>
                <linearGradient id="analyticsLine" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#8d007c" />
                  <stop offset="100%" stopColor="#E40206" />
                </linearGradient>
              </defs>
              {[0, 10, 20, 30, 40].map((tick) => {
                const y = chart.height - chart.bottomPad - (tick / 40) * (chart.height - chart.topPad - chart.bottomPad);
                return (
                  <g key={tick}>
                    <text x="0" y={y + 4} fontSize="10" fill="#b6a3c0">{tick}</text>
                    <line x1={chart.leftPad} x2={chart.width - chart.rightPad} y1={y} y2={y} stroke="#ece7ee" strokeDasharray="3 5" />
                  </g>
                );
              })}
              {trendRows.map((row, index) => {
                const x = chart.leftPad + (trendRows.length === 1 ? 0 : (index / (trendRows.length - 1)) * (chart.width - chart.leftPad - chart.rightPad));
                const showLabel = index === 0 || index === trendRows.length - 1 || index % Math.max(1, Math.floor(trendRows.length / 6)) === 0;
                return (
                  <g key={`${row.date}-${index}`}>
                    <line x1={x} x2={x} y1={chart.topPad} y2={chart.height - chart.bottomPad} stroke="#f0edf2" strokeDasharray="3 5" />
                    {showLabel && (
                      <text x={x} y={chart.height - 8} textAnchor="middle" fontSize="10" fill="#9ca3af">
                        {row.date}
                      </text>
                    )}
                  </g>
                );
              })}
              {trendRows.length > 0 && (
                <polyline points={chart.points} fill="none" stroke="url(#analyticsLine)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
              )}
            </svg>
          </motion.section>

          <div style={{ display: "grid", gridTemplateColumns: "0.95fr 1.95fr", gap: 18 }}>
            <motion.section
              custom={5}
              variants={cardVariants}
              initial="hidden"
              animate="visible"
              style={{ background: "#fff", borderRadius: 12, padding: 18, minHeight: 278, boxShadow: "0 1px 3px rgba(0,0,0,0.06)", border: "1px solid rgba(0,0,0,0.05)" }}
            >
              <h3 style={{ margin: "0 0 18px", fontSize: 15, fontWeight: 800, color: "#111827" }}>Quick Stats</h3>
              <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
                {quickStats.map((stat) => (
                  <div key={stat.label}>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
                      <span style={{ fontSize: 13, color: "#5f6b85" }}>{stat.label}</span>
                      <strong style={{ fontSize: 13, color: "#111827" }}>{formatNumber(stat.value)}</strong>
                    </div>
                    <div style={{ height: 5, borderRadius: 999, overflow: "hidden", background: "#eef0f3" }}>
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${Math.min(100, (stat.value / totalQuickStat) * 100)}%` }}
                        transition={{ duration: 0.7, ease: "easeOut" }}
                        style={{ height: "100%", borderRadius: 999, background: "linear-gradient(90deg, #8d007c 0%, #E40206 100%)" }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </motion.section>

            <motion.section
              custom={6}
              variants={cardVariants}
              initial="hidden"
              animate="visible"
              style={{ background: "#fff", borderRadius: 12, padding: 18, minHeight: 278, boxShadow: "0 1px 3px rgba(0,0,0,0.06)", border: "1px solid rgba(0,0,0,0.05)" }}
            >
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
                <h3 style={{ margin: 0, fontSize: 15, fontWeight: 800, color: "#111827" }}>Top Performing Products</h3>
                <button type="button" style={{ border: "none", background: "transparent", color: "#9a007f", fontSize: 13, fontWeight: 700, cursor: "pointer" }}>
                  View all {"->"}
                </button>
              </div>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead>
                  <tr style={{ borderTop: "1px solid #eef0f3", borderBottom: "1px solid #eef0f3" }}>
                    {["#", "Product", "Try-ons", "Conv%", "Returns%", "Revenue"].map((heading) => (
                      <th key={heading} style={{ textAlign: heading === "Product" ? "left" : "right", padding: "10px 12px", color: "#5f6b85", fontSize: 12, fontWeight: 600 }}>
                        {heading}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {products.length > 0 ? (
                    products.map((product, index) => (
                      <tr key={`${product.title}-${index}`} style={{ borderBottom: "1px solid #eef0f3" }}>
                        <td style={{ padding: "11px 12px", width: 44 }}>
                          <span style={{ width: 20, height: 20, borderRadius: "50%", display: "inline-flex", alignItems: "center", justifyContent: "center", color: "#fff", background: "#c70047", fontSize: 11, fontWeight: 800 }}>
                            {index + 1}
                          </span>
                        </td>
                        <td style={{ padding: "11px 12px", color: "#111827", fontWeight: 600 }}>{product.title}</td>
                        <td style={{ padding: "11px 12px", textAlign: "right", color: "#5f6b85" }}>{product.tryOnSessions}</td>
                        <td style={{ padding: "11px 12px", textAlign: "right", color: "#047857", fontWeight: 700 }}>{product.conversion}</td>
                        <td style={{ padding: "11px 12px", textAlign: "right", color: "#5f6b85" }}>{product.returns}</td>
                        <td style={{ padding: "11px 12px", textAlign: "right", color: "#111827", fontWeight: 700 }}>{product.revenue}</td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={6} style={{ padding: "28px 12px", textAlign: "center", color: "#9ca3af" }}>
                        No product analytics yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </motion.section>
          </div>

          {analytics && (
            <motion.section
              custom={7}
              variants={cardVariants}
              initial="hidden"
              animate="visible"
              style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 18, padding: "16px 18px", borderRadius: 12, background: "#f4edf3", border: "1px solid rgba(126,1,117,0.16)" }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 16, minWidth: 0 }}>
                <span style={{ width: 34, height: 34, borderRadius: 9, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, background: "linear-gradient(135deg, #8d007c 0%, #E40206 100%)", color: "#fff" }}>
                  <Lightbulb size={16} />
                </span>
                <div>
                  <h3 style={{ margin: "0 0 4px", fontSize: 14, fontWeight: 800, color: "#111827" }}>Performance Insight</h3>
                  <p style={{ margin: 0, fontSize: 13, lineHeight: 1.45, color: "#5f6b85" }}>
                    This period has <strong style={{ color: "#111827" }}>{formatNumber(analytics.try_on_sessions)} try-on sessions</strong>, <strong style={{ color: "#111827" }}>{formatNumber(analytics.widget_opens)} widget opens</strong>, and <strong style={{ color: "#111827" }}>{formatNumber(analytics.add_to_cart_count)} add-to-cart events</strong>. Commerce metrics show as unavailable when Shopify order attribution cannot be resolved.
                  </p>
                </div>
              </div>
              <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 8, flexShrink: 0 }}>
                <span style={{ padding: "4px 12px", borderRadius: 999, fontSize: 12, fontWeight: 800, background: "#dcfce7", color: "#15803d" }}>
                  {formatPercent(analytics.widget_click_rate)} click rate
                </span>
                <span style={{ padding: "4px 12px", borderRadius: 999, fontSize: 12, fontWeight: 800, background: "rgba(126,1,117,0.08)", color: "#9a007f" }}>
                  {formatNumber(analytics.credits_used)} credits
                </span>
              </div>
            </motion.section>
          )}
        </div>
      </div>
    </div>
  );
}
