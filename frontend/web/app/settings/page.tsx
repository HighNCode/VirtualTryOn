"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import PortalSidebar from "../_components/PortalSidebar";
import {
  getDefaultStoreId,
  getWidgetConfig,
  updateWidgetConfig
} from "../../lib/photoshootApi";

const DEFAULT_WIDGET_COLOR_HEX = "#FF0000";
const DEFAULT_WIDGET_BACKGROUND = "linear-gradient(90deg, #a50070 0%, #f1001f 100%)";
const HEX_COLOR_RE = /^#[0-9A-Fa-f]{6}$/;

function normalizeWidgetColor(value: string | null | undefined): string {
  const candidate = String(value || "").trim();
  if (!HEX_COLOR_RE.test(candidate)) {
    return "";
  }
  return candidate.toUpperCase();
}

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
    if (!storeId) {
      return;
    }

    const controller = new AbortController();
    let active = true;

    setIsLoading(true);

    getWidgetConfig({ storeId, signal: controller.signal })
      .then((config) => {
        if (active) {
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
        }
      })
      .catch((error: unknown) => {
        if (!active || controller.signal.aborted) {
          return;
        }

        const message = error instanceof Error ? error.message : "Failed to load widget config.";
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
        setErrorMessage("Primary color must be a valid hex code like #FF0000.");
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
          weekly_tryon_limit: parsedLimit
        }
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
    if (!input) {
      return;
    }
    try {
      if (typeof input.showPicker === "function") {
        input.showPicker();
        return;
      }
    } catch {
      // Fallback to click below when showPicker is unavailable or blocked.
    }
    input.click();
  };

  const handleColorInputChange = (value: string) => {
    setWidgetColorInput(value);
    const trimmed = value.trim();
    if (!trimmed) {
      setUseDefaultWidgetColor(true);
      return;
    }
    setUseDefaultWidgetColor(false);
    if (HEX_COLOR_RE.test(trimmed)) {
      const normalized = normalizeWidgetColor(value);
      setAppliedWidgetColor(normalized);
    }
  };

  const handleUseDefaultColor = () => {
    setWidgetColorInput("");
    setAppliedWidgetColor(DEFAULT_WIDGET_COLOR_HEX);
    setUseDefaultWidgetColor(true);
  };

  const previewBackground = useDefaultWidgetColor ? DEFAULT_WIDGET_BACKGROUND : appliedWidgetColor;

  return (
    <main className="portal-shell">
      <PortalSidebar activeMain="settings" activeSettings="custom" />

      <section className="portal-main">
        <header className="portal-main-header">
          <h2>Settings</h2>
          <p>Manage your Virtual Try-on Studio preferences</p>
        </header>

        {!storeId ? <p className="ai-error-note">Open the app from Shopify Admin to load settings.</p> : null}
        {isLoading ? <p className="ai-status-note">Loading widget settings...</p> : null}
        {errorMessage ? <p className="ai-error-note">{errorMessage}</p> : null}
        {statusMessage ? <p className="ai-status-note">{statusMessage}</p> : null}

        <section className="settings-card">
          <h3>Primary Color</h3>
          <div className="settings-color-controls">
            <div className="settings-color-field">
              <button
                type="button"
                className="settings-color-dot-button"
                onClick={openColorPicker}
                aria-label="Open color picker"
                title="Open color picker"
              >
                <span className="settings-color-dot" aria-hidden style={{ background: previewBackground }} />
              </button>
              <input
                type="text"
                className="settings-color-code"
                value={widgetColorInput}
                onChange={(event) => handleColorInputChange(event.target.value)}
                placeholder="#FF0000"
                aria-label="Primary color hex code"
                autoCapitalize="characters"
                spellCheck={false}
              />
              <button
                type="button"
                className="settings-default-color-button"
                onClick={handleUseDefaultColor}
                disabled={useDefaultWidgetColor}
              >
                Use default
              </button>
            </div>

            <div className="settings-preview-button" style={{ background: previewBackground }}>
              Try It On
            </div>
          </div>
          <input
            ref={colorInputRef}
            type="color"
            className="settings-color-picker-hidden"
            value={appliedWidgetColor}
            onInput={(event) => {
              const normalized = normalizeWidgetColor((event.target as HTMLInputElement).value);
              setWidgetColorInput(normalized);
              setAppliedWidgetColor(normalized);
              setUseDefaultWidgetColor(false);
            }}
            onChange={(event) => {
              const normalized = normalizeWidgetColor((event.target as HTMLInputElement).value);
              setWidgetColorInput(normalized);
              setAppliedWidgetColor(normalized);
              setUseDefaultWidgetColor(false);
            }}
            aria-label="Primary color"
          />
          <p className="settings-help-text">Click the color circle to pick a color, type a hex code, or use default gradient.</p>

          <h3>Generation Limits</h3>
          <p className="settings-subtext">Max Weekly Generations Per User</p>
          <input
            type="number"
            className="settings-limit-input"
            value={generationLimit}
            min={5}
            max={100}
            step={1}
            onChange={(event) => setGenerationLimit(event.target.value)}
            aria-label="Generation limit"
          />
          <p className="settings-help-text settings-help-text-small">
            This limit applies per logged-in customer from Monday to Sunday in the store timezone.
          </p>

          <button type="button" className="settings-save-button" onClick={handleSave} disabled={isSaving}>
            {isSaving ? "Saving..." : "Save Changes"}
          </button>
        </section>
      </section>
    </main>
  );
}
