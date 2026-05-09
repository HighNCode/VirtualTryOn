"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";
import PortalSidebar from "../_components/PortalSidebar";
import PortalTopbar from "../_components/PortalTopbar";
import SubTabNav from "../_components/SubTabNav";
import {
  getDefaultStoreId,
  getWidgetConfig,
  updateWidgetConfig,
} from "../../lib/photoshootApi";

const DEFAULT_WIDGET_COLOR_HEX = "#7E0175";
const DEFAULT_WIDGET_BACKGROUND = "linear-gradient(90deg, #8d017f 0%, #a33396 100%)";
const HEX_COLOR_RE = /^#[0-9A-Fa-f]{6}$/;

function normalizeWidgetColor(value: string | null | undefined): string {
  const candidate = String(value || "").trim();
  if (!HEX_COLOR_RE.test(candidate)) return "";
  return candidate.toUpperCase();
}

const settingsTabs = [
  { href: "/settings", label: "Custom" },
  { href: "/settings/privacy", label: "Privacy" },
  { href: "/settings/billing", label: "Billing" },
  { href: "/settings/support", label: "Support" },
];

export default function SettingsPage() {
  const storeId = useMemo(() => getDefaultStoreId(), []);
  const colorInputRef = useRef<HTMLInputElement | null>(null);

  const [widgetColorInput, setWidgetColorInput] = useState("");
  const [appliedWidgetColor, setAppliedWidgetColor] = useState(DEFAULT_WIDGET_COLOR_HEX);
  const [useDefaultWidgetColor, setUseDefaultWidgetColor] = useState(true);
  const [generationLimit, setGenerationLimit] = useState("10");

  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [statusMessage, setStatusMessage] = useState("");

  useEffect(() => {
    if (!storeId) return;

    const controller = new AbortController();
    let active = true;
    setIsLoading(true);

    getWidgetConfig({ storeId, signal: controller.signal })
      .then((config) => {
        if (!active) return;
        const normalized = normalizeWidgetColor(config.widget_color);
        if (normalized) {
          setWidgetColorInput(normalized);
          setAppliedWidgetColor(normalized);
          setUseDefaultWidgetColor(false);
        } else {
          setWidgetColorInput("");
          setAppliedWidgetColor(DEFAULT_WIDGET_COLOR_HEX);
          setUseDefaultWidgetColor(true);
        }
        setGenerationLimit(String(config.weekly_tryon_limit ?? 10));
      })
      .catch((error: unknown) => {
        if (!active || controller.signal.aborted) return;
        const message = error instanceof Error ? error.message : "Failed to load widget config.";
        setErrorMessage(message);
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [storeId]);

  const handleSave = async () => {
    if (!storeId) {
      setErrorMessage("Open the app from Shopify Admin before saving widget settings.");
      return;
    }

    setIsSaving(true);
    setErrorMessage("");
    setStatusMessage("");

    const parsedLimit = Number.parseInt(generationLimit, 10);
    if (!Number.isFinite(parsedLimit) || parsedLimit < 5 || parsedLimit > 100) {
      setErrorMessage("Weekly generation limit must be a whole number between 5 and 100.");
      setIsSaving(false);
      return;
    }

    let normalizedColor = "";
    if (!useDefaultWidgetColor) {
      if (!HEX_COLOR_RE.test(widgetColorInput.trim())) {
        setErrorMessage("Primary color must be a valid hex code like #7E0175.");
        setIsSaving(false);
        return;
      }
      normalizedColor = normalizeWidgetColor(widgetColorInput);
    }

    try {
      await updateWidgetConfig({
        storeId,
        payload: {
          widget_color: useDefaultWidgetColor ? "" : normalizedColor,
          weekly_tryon_limit: parsedLimit,
        },
      });
      if (useDefaultWidgetColor) {
        setWidgetColorInput("");
        setAppliedWidgetColor(DEFAULT_WIDGET_COLOR_HEX);
      } else {
        setWidgetColorInput(normalizedColor);
        setAppliedWidgetColor(normalizedColor);
      }
      setStatusMessage("Widget settings saved.");
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Failed to save widget config.";
      setErrorMessage(message);
    } finally {
      setIsSaving(false);
    }
  };

  const openColorPicker = () => {
    const input = colorInputRef.current;
    if (!input) return;
    try {
      if (typeof input.showPicker === "function") {
        input.showPicker();
        return;
      }
    } catch {
      // Browser fallback below.
    }
    input.click();
  };

  const handleColorInputChange = (value: string) => {
    const normalizedInput = value.startsWith("#") ? value : `#${value}`;
    setWidgetColorInput(normalizedInput);
    const trimmed = normalizedInput.trim();
    if (!trimmed || trimmed === "#") {
      setUseDefaultWidgetColor(true);
      setAppliedWidgetColor(DEFAULT_WIDGET_COLOR_HEX);
      return;
    }
    setUseDefaultWidgetColor(false);
    if (HEX_COLOR_RE.test(trimmed)) {
      setAppliedWidgetColor(normalizeWidgetColor(trimmed));
    }
  };

  const previewBackground = useDefaultWidgetColor ? DEFAULT_WIDGET_BACKGROUND : appliedWidgetColor;
  const visibleWidgetColor = (useDefaultWidgetColor ? DEFAULT_WIDGET_COLOR_HEX : widgetColorInput).replace(/^#/, "");

  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden", background: "#f6f4f4" }}>
      <PortalSidebar activeMain="settings" activeSettings="custom" />

      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "auto" }}>
        <PortalTopbar title="Settings" subtitle="Manage your Virtual Fit Studio configuration" />
        <SubTabNav tabs={settingsTabs} />

        <div style={{ flex: 1, padding: "24px 28px", display: "flex", flexDirection: "column", gap: 20 }}>
          {!storeId && (
            <p style={{ margin: 0, fontSize: 13, padding: "8px 16px", borderRadius: 10, background: "#fff1f1", color: "#dc2626" }}>
              Open the app from Shopify Admin to load settings.
            </p>
          )}
          {isLoading && (
            <p style={{ margin: 0, fontSize: 13, padding: "8px 16px", borderRadius: 10, background: "rgba(126,1,117,0.05)", color: "#7E0175" }}>
              Loading widget settings...
            </p>
          )}
          {errorMessage && (
            <p style={{ margin: 0, fontSize: 13, padding: "8px 16px", borderRadius: 10, background: "#fff1f1", color: "#dc2626" }}>
              {errorMessage}
            </p>
          )}
          {statusMessage && (
            <p style={{ margin: 0, fontSize: 13, padding: "8px 16px", borderRadius: 10, background: "#dcfce7", color: "#15803d" }}>
              {statusMessage}
            </p>
          )}

          <motion.section
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
            style={{ background: "#fff", borderRadius: 12, padding: "22px 20px 24px", boxShadow: "0 1px 3px rgba(0,0,0,0.06)", border: "1px solid rgba(0,0,0,0.05)" }}
          >
            <h3 style={{ margin: "0 0 8px", fontSize: 14, fontWeight: 700, color: "#111111" }}>Primary Color</h3>
            <p style={{ margin: "0 0 20px", fontSize: 13, color: "#4b5f7c" }}>
              This color will be used only for Try on button on theme
            </p>

            <div style={{ display: "flex", alignItems: "center", minHeight: 62, width: "100%", borderRadius: 10, border: "1px solid #dddddd", background: "#ffffff", padding: "0 16px", boxSizing: "border-box", marginBottom: 18 }}>
              <button
                type="button"
                onClick={openColorPicker}
                aria-label="Open color picker"
                style={{ width: 34, height: 34, borderRadius: 6, border: "none", cursor: "pointer", flexShrink: 0, background: appliedWidgetColor, padding: 0, marginRight: 14 }}
              />
              <span style={{ fontSize: 13, color: "#6b7280", marginRight: 8 }}>#</span>
              <input
                type="text"
                value={visibleWidgetColor}
                onChange={(e) => handleColorInputChange(e.target.value)}
                placeholder="7E0175"
                aria-label="Primary color hex code"
                autoCapitalize="characters"
                spellCheck={false}
                style={{ border: "none", outline: "none", background: "transparent", color: "#4b5563", fontFamily: "inherit", fontSize: 13, width: "100%" }}
              />
            </div>

            <p style={{ margin: "0 0 12px", fontSize: 13, fontWeight: 700, color: "#111111" }}>Preview</p>
            <div style={{ width: 326, maxWidth: "100%", padding: "10px 20px", borderRadius: 8, fontSize: 14, fontWeight: 700, textAlign: "center", color: "#fff", background: previewBackground }}>
              Try It On
            </div>

            <input
              ref={colorInputRef}
              type="color"
              value={appliedWidgetColor}
              onInput={(e) => {
                const normalized = normalizeWidgetColor((e.target as HTMLInputElement).value);
                setWidgetColorInput(normalized);
                setAppliedWidgetColor(normalized);
                setUseDefaultWidgetColor(false);
              }}
              onChange={(e) => {
                const normalized = normalizeWidgetColor((e.target as HTMLInputElement).value);
                setWidgetColorInput(normalized);
                setAppliedWidgetColor(normalized);
                setUseDefaultWidgetColor(false);
              }}
              aria-label="Primary color"
              style={{ position: "absolute", opacity: 0, pointerEvents: "none", width: 0, height: 0 }}
            />
          </motion.section>

          <motion.section
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: 0.08 }}
            style={{ background: "#fff", borderRadius: 12, padding: "22px 20px", boxShadow: "0 1px 3px rgba(0,0,0,0.06)", border: "1px solid rgba(0,0,0,0.05)" }}
          >
            <h3 style={{ margin: "0 0 8px", fontSize: 14, fontWeight: 700, color: "#111111" }}>Generation Limits</h3>
            <p style={{ margin: "0 0 20px", fontSize: 13, color: "#4b5f7c" }}>Max Weekly Generations Per User</p>

            <input
              type="number"
              value={generationLimit}
              min={5}
              max={100}
              step={1}
              onChange={(e) => setGenerationLimit(e.target.value)}
              aria-label="Generation limit"
              style={{ fontSize: 13, width: "100%", padding: "11px 12px", borderRadius: 10, border: "1px solid #dddddd", outline: "none", color: "#111111", fontFamily: "inherit", boxSizing: "border-box", marginBottom: 10 }}
              onFocus={(e) => {
                e.currentTarget.style.borderColor = "#7E0175";
                e.currentTarget.style.boxShadow = "0 0 0 3px rgba(126,1,117,0.1)";
              }}
              onBlur={(e) => {
                e.currentTarget.style.borderColor = "#dddddd";
                e.currentTarget.style.boxShadow = "none";
              }}
            />
            <p style={{ margin: 0, fontSize: 12, color: "#4b5f7c" }}>
              Set the maximum number of try-ons your one customer can generate. Default is 6, This limit resets weekly for each customer.
            </p>
          </motion.section>

          <div>
            <motion.button
              type="button"
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={handleSave}
              disabled={isSaving}
              style={{
                padding: "12px 18px",
                borderRadius: 8,
                fontSize: 14,
                fontWeight: 700,
                color: "#fff",
                background: "linear-gradient(135deg, #7E0175 0%, #BC174A 55%, #E40206 100%)",
                border: "none",
                cursor: isSaving ? "not-allowed" : "pointer",
                opacity: isSaving ? 0.7 : 1,
              }}
            >
              {isSaving ? "Saving..." : "Save Changes"}
            </motion.button>
          </div>
        </div>
      </div>
    </div>
  );
}
