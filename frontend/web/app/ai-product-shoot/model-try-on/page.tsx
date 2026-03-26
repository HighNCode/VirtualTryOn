"use client";

import { useEffect, useMemo, useState, type CSSProperties } from "react";
import PortalSidebar from "../../_components/PortalSidebar";
import {
  buildJobResultUrl,
  getDefaultProductGid,
  getDefaultProductImageUrl,
  getDefaultStoreId,
  isFailureStatus,
  listPhotoshootModels,
  pollPhotoshootJob,
  resolveBackendUrl,
  startTryOnModelJob,
  type PhotoshootModelResponse
} from "../../../lib/photoshootApi";

type ResultCard = {
  id: string;
  title: string;
  enhanced: boolean;
  variant: "original" | "enhanced-a" | "enhanced-b";
  imageUrl?: string | null;
};

function modelTileStyle(imageUrl: string): CSSProperties {
  return {
    backgroundImage: `url(${resolveBackendUrl(imageUrl)})`,
    backgroundSize: "cover",
    backgroundPosition: "center"
  };
}

export default function ModelTryOnPage() {
  const [tryOnArea, setTryOnArea] = useState("Auto");
  const storeId = useMemo(() => getDefaultStoreId(), []);
  const [productGid, setProductGid] = useState(getDefaultProductGid());
  const [productImageUrl, setProductImageUrl] = useState(getDefaultProductImageUrl());

  const [modelGender, setModelGender] = useState("unisex");
  const [modelAge, setModelAge] = useState("");
  const [modelBodyType, setModelBodyType] = useState("");

  const [models, setModels] = useState<PhotoshootModelResponse[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);

  const [selectedModelId, setSelectedModelId] = useState<string | null>(null);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [generated, setGenerated] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);

  const [statusMessage, setStatusMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [resultImageUrl, setResultImageUrl] = useState<string | null>(null);

  const selectedModel = useMemo(
    () => models.find((model) => model.id === selectedModelId) ?? null,
    [models, selectedModelId]
  );

  const resultCards: ResultCard[] = [
    { id: "original", title: "Original", enhanced: false, variant: "original", imageUrl: productImageUrl || null },
    { id: "enhanced-1", title: "Generated - OptimoVTS", enhanced: true, variant: "enhanced-a", imageUrl: resultImageUrl },
    { id: "enhanced-2", title: "Generated Variant", enhanced: true, variant: "enhanced-b", imageUrl: resultImageUrl }
  ];

  useEffect(() => {
    if (!pickerOpen || !storeId.trim()) {
      return;
    }

    const controller = new AbortController();
    let active = true;

    setLoadingModels(true);

    listPhotoshootModels({
      storeId: storeId.trim(),
      gender: modelGender,
      age: modelAge || null,
      bodyType: modelBodyType || null,
      signal: controller.signal
    })
      .then((data) => {
        if (!active) {
          return;
        }

        setModels(data);
        setSelectedModelId((current) => {
          if (data.length === 0) {
            return null;
          }

          if (current && data.some((item) => item.id === current)) {
            return current;
          }

          return data[0].id;
        });
      })
      .catch((error: unknown) => {
        if (!active || controller.signal.aborted) {
          return;
        }

        const message = error instanceof Error ? error.message : "Failed to load model library.";
        setErrorMessage(message);
        setModels([]);
      })
      .finally(() => {
        if (active) {
          setLoadingModels(false);
        }
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [pickerOpen, storeId, modelGender, modelAge, modelBodyType]);

  const openPicker = () => {
    setGenerated(false);
    setErrorMessage("");
    setPickerOpen(true);
  };

  const closePicker = () => {
    setPickerOpen(false);
  };

  const selectModel = (modelId: string) => {
    setSelectedModelId(modelId);
    setGenerated(false);
    setPickerOpen(false);
  };

  const generateResults = async () => {
    if (!storeId.trim()) {
      setErrorMessage("Open the app from Shopify Admin to connect this tool with the active store.");
      return;
    }

    if (!productGid.trim()) {
      setErrorMessage("Enter Shopify Product GID.");
      return;
    }

    if (!productImageUrl.trim()) {
      setErrorMessage("Enter product image URL.");
      return;
    }

    if (!selectedModelId) {
      setPickerOpen(true);
      setErrorMessage("Select a model before generating.");
      return;
    }

    setIsGenerating(true);
    setGenerated(false);
    setErrorMessage("");
    setResultImageUrl(null);
    setStatusMessage("Starting try-on job...");

    try {
      const startedJob = await startTryOnModelJob({
        storeId: storeId.trim(),
        shopifyProductGid: productGid.trim(),
        productImageUrl: productImageUrl.trim(),
        modelLibraryId: selectedModelId
      });

      setStatusMessage(`Job ${startedJob.job_id} started. Processing...`);

      const finishedJob = await pollPhotoshootJob(storeId.trim(), startedJob.job_id, {
        onUpdate: (job) => {
          const progressText = typeof job.progress === "number" ? ` (${job.progress}%)` : "";
          setStatusMessage(`${job.status}${progressText}${job.message ? ` - ${job.message}` : ""}`);
        }
      });

      if (isFailureStatus(finishedJob.status)) {
        throw new Error(finishedJob.error || finishedJob.message || "Generation failed.");
      }

      const imageUrl = finishedJob.result_image_url
        ? resolveBackendUrl(finishedJob.result_image_url)
        : buildJobResultUrl(startedJob.job_id);

      setResultImageUrl(imageUrl);
      setGenerated(true);
      setPickerOpen(false);
      setStatusMessage("Generation complete.");
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Failed to generate try-on image.";
      setErrorMessage(message);
      setStatusMessage("");
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <main className="portal-shell">
      <PortalSidebar activeMain="ai" activeAi="model-try-on" />

      <section className="portal-main">
        <header className="portal-main-header">
          <h2>AI Product Shoots</h2>
          <p>Generate professional studio shoots in seconds</p>
        </header>

        <section className="ai-stage-model-tryon">
          <aside className="ai-tryon-panel">
            <h3>Try On</h3>
            <p>Product Image</p>

            <h4>Store context</h4>
            <p className="ai-status-note">
              {storeId ? "Connected to the current Shopify store." : "Open the app from Shopify Admin to load store context."}
            </p>

            <h4>Shopify Product GID</h4>
            <label className="ai-text-field">
              <input
                aria-label="Shopify Product GID"
                value={productGid}
                onChange={(event) => setProductGid(event.target.value)}
                placeholder="gid://shopify/Product/1234567890"
                autoComplete="off"
              />
            </label>

            <h4>Product image URL</h4>
            <label className="ai-text-field">
              <input
                aria-label="Product image URL"
                value={productImageUrl}
                onChange={(event) => setProductImageUrl(event.target.value)}
                placeholder="https://cdn.shopify.com/..."
                autoComplete="off"
              />
            </label>

            <h4>Try on area</h4>
            <label className="ai-select-wrap">
              <select aria-label="Try on area" value={tryOnArea} onChange={(event) => setTryOnArea(event.target.value)}>
                <option>Auto</option>
                <option>Upper Body</option>
                <option>Full Body</option>
              </select>
            </label>

            <h4>Try on model</h4>
            <button type="button" className="ai-tryon-model-trigger" onClick={openPicker}>
              {selectedModel ? (
                <span className="ai-tryon-model-thumb" style={modelTileStyle(selectedModel.image_url)} aria-hidden />
              ) : (
                <span className="ai-tryon-model-icon" aria-hidden>
                  <svg viewBox="0 0 24 24" role="img">
                    <rect x="3" y="4" width="18" height="16" rx="2" fill="none" stroke="currentColor" strokeWidth="1.8" />
                    <circle cx="8.2" cy="9" r="1.6" fill="none" stroke="currentColor" strokeWidth="1.8" />
                    <path d="M5.5 17L10.4 12.2L13.3 14.9L16.2 12L18.5 14.4V17" fill="none" stroke="currentColor" strokeWidth="1.8" />
                  </svg>
                </span>
              )}
              <span className="ai-tryon-model-copy">
                <strong>{selectedModel ? "Selected model" : "Select try on model"}</strong>
                <span>{selectedModel ? "Click to edit selection" : "Choose model, pose, and background style"}</span>
              </span>
              <span className="ai-tryon-chevron" aria-hidden>
                ›
              </span>
            </button>

            <button type="button" className="ai-primary-btn ai-tryon-generate-btn" onClick={generateResults} disabled={isGenerating}>
              {isGenerating ? "Generating..." : "Generate"}
            </button>

            {statusMessage ? <p className="ai-status-note">{statusMessage}</p> : null}
            {errorMessage ? <p className="ai-error-note">{errorMessage}</p> : null}
          </aside>

          <section className="ai-tryon-right">
            {pickerOpen ? (
              <section className="ai-tryon-picker">
                <header className="ai-tryon-picker-head">
                  <button type="button" className="ai-tryon-picker-back" onClick={closePicker} aria-label="Back">
                    ‹
                  </button>
                  <div>
                    <h3>Select Try on model</h3>
                    <p>Optimo model library</p>
                  </div>
                </header>

                <div className="ai-tryon-filters">
                  <label className="ai-tryon-filter">
                    <select aria-label="Gender" value={modelGender} onChange={(event) => setModelGender(event.target.value)}>
                      <option value="unisex">All</option>
                      <option value="female">Women</option>
                      <option value="male">Men</option>
                    </select>
                  </label>
                  <label className="ai-tryon-filter">
                    <select aria-label="Age" value={modelAge} onChange={(event) => setModelAge(event.target.value)}>
                      <option value="">Age</option>
                      <option value="18-25">18-25</option>
                      <option value="26-35">26-35</option>
                      <option value="36-45">36-45</option>
                      <option value="45+">45+</option>
                    </select>
                  </label>
                  <label className="ai-tryon-filter">
                    <select aria-label="Body Type" value={modelBodyType} onChange={(event) => setModelBodyType(event.target.value)}>
                      <option value="">Body Type</option>
                      <option value="slim">Slim</option>
                      <option value="athletic">Athletic</option>
                      <option value="regular">Regular</option>
                      <option value="plus">Plus</option>
                    </select>
                  </label>
                  <label className="ai-tryon-filter">
                    <select aria-label="Try on area (preview)" value={tryOnArea} onChange={(event) => setTryOnArea(event.target.value)}>
                      <option>Auto</option>
                      <option>Upper Body</option>
                      <option>Full Body</option>
                    </select>
                  </label>
                </div>

                <div className="ai-tryon-model-list">
                  <div className="ai-tryon-model-grid">
                    {loadingModels ? <p className="ai-inline-note">Loading models...</p> : null}
                    {!loadingModels && models.length === 0 ? <p className="ai-inline-note">No models returned for current filters.</p> : null}

                    {models.map((model) => (
                      <button
                        key={model.id}
                        type="button"
                        className={`ai-tryon-model-tile${selectedModelId === model.id ? " is-selected" : ""}`}
                        onClick={() => selectModel(model.id)}
                        aria-label={model.id}
                      >
                        <span style={modelTileStyle(model.image_url)} />
                      </button>
                    ))}
                  </div>
                </div>
              </section>
            ) : generated ? (
              <div className="ai-results-grid ai-tryon-results-grid">
                {resultCards.map((card) => (
                  <article key={card.id} className="ai-result-card">
                    <header>
                      <p>{card.title}</p>
                      {card.enhanced ? (
                        <div className="ai-result-actions" aria-hidden>
                          <button type="button">↓</button>
                          <button type="button">↻</button>
                        </div>
                      ) : null}
                    </header>

                    <div className={`ai-result-image ai-result-image-${card.variant}`} aria-hidden>
                      {card.imageUrl ? (
                        <span className="ai-result-photo" style={modelTileStyle(card.imageUrl)} />
                      ) : (
                        <span className="ai-model-figure">
                          <span className="ai-model-head" />
                          <span className="ai-model-torso" />
                          <span className="ai-model-leg-left" />
                          <span className="ai-model-leg-right" />
                        </span>
                      )}
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <div className="ai-tryon-placeholder-grid">
                <article className="ai-result-card">
                  <header>
                    <p>Original</p>
                  </header>
                  <div className="ai-result-image ai-result-image-original" aria-hidden>
                    {productImageUrl ? (
                      <span className="ai-result-photo" style={modelTileStyle(productImageUrl)} />
                    ) : (
                      <span className="ai-model-figure">
                        <span className="ai-model-head" />
                        <span className="ai-model-torso" />
                        <span className="ai-model-leg-left" />
                        <span className="ai-model-leg-right" />
                      </span>
                    )}
                  </div>
                </article>
                <div className="ai-tryon-placeholder-card" aria-hidden />
                <div className="ai-tryon-placeholder-card" aria-hidden />
              </div>
            )}
          </section>
        </section>
      </section>
    </main>
  );
}
