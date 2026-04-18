"use client";

import { useEffect, useMemo, useState } from "react";
import PortalSidebar from "../_components/PortalSidebar";
import {
  getDefaultStoreId,
  getWidgetConfig,
  updateWidgetConfig
} from "../../lib/photoshootApi";

export default function SettingsPage() {
  const storeId = useMemo(() => getDefaultStoreId(), []);

  const [widgetColor, setWidgetColor] = useState("#FF0000");
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
          setWidgetColor(config.widget_color || "#FF0000");
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
    if (!Number.isFinite(parsedLimit) || parsedLimit < 1 || parsedLimit > 1000) {
      setErrorMessage("Weekly generation limit must be a whole number between 1 and 1000.");
      setIsSaving(false);
      return;
    }

    try {
      await updateWidgetConfig({
        storeId,
        payload: {
          widget_color: widgetColor,
          weekly_tryon_limit: parsedLimit
        }
      });
      setStatusMessage("Widget settings saved.");
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Failed to save widget config.";
      setErrorMessage(message);
    } finally {
      setIsSaving(false);
    }
  };

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
          <label className="settings-color-field">
            <span className="settings-color-dot" aria-hidden style={{ backgroundColor: widgetColor }} />
            <input
              type="text"
              value={widgetColor}
              onChange={(event) => setWidgetColor(event.target.value)}
              aria-label="Primary color code"
            />
          </label>
          <p className="settings-help-text">This color is used for the Try-On button in theme extension.</p>

          <h3>Preview</h3>
          <button type="button" className="settings-preview-button" style={{ backgroundColor: widgetColor }}>
            Try It On
          </button>

          <h3>Generation Limits</h3>
          <p className="settings-subtext">Max Weekly Generations Per User</p>
          <input
            type="number"
            className="settings-limit-input"
            value={generationLimit}
            min={1}
            max={1000}
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
