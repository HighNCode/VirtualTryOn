"use client";

import { useEffect, useMemo, useState, type CSSProperties } from "react";
import PortalSidebar from "../../_components/PortalSidebar";
import {
  buildJobResultUrl,
  getDefaultProductGid,
  getDefaultProductImageUrl,
  getDefaultStoreId,
  isFailureStatus,
  listModelFaces,
  pollPhotoshootJob,
  resolveBackendUrl,
  startModelSwapJob,
  type PhotoshootModelFaceResponse
} from "../../../lib/photoshootApi";

type ResultCard = {
  id: string;
  title: string;
  enhanced: boolean;
  variant: "original" | "enhanced-a" | "enhanced-b";
  imageUrl?: string | null;
};

function imageTileStyle(imageUrl: string): CSSProperties {
  return {
    backgroundImage: `url(${resolveBackendUrl(imageUrl)})`,
    backgroundSize: "cover",
    backgroundPosition: "center"
  };
}

export default function ModelSwapPage() {
  const [uploaded, setUploaded] = useState(false);

  const storeId = useMemo(() => getDefaultStoreId(), []);
  const [productGid, setProductGid] = useState(getDefaultProductGid());
  const [originalImageUrl, setOriginalImageUrl] = useState(getDefaultProductImageUrl());

  const [faceGender, setFaceGender] = useState("female");
  const [faceAge, setFaceAge] = useState("");
  const [faceSkinTone, setFaceSkinTone] = useState("");

  const [faceLibrary, setFaceLibrary] = useState<PhotoshootModelFaceResponse[]>([]);
  const [loadingFaces, setLoadingFaces] = useState(false);

  const [selectedFaceId, setSelectedFaceId] = useState<string | null>(null);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [generated, setGenerated] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);

  const [statusMessage, setStatusMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [resultImageUrl, setResultImageUrl] = useState<string | null>(null);

  const selectedFace = useMemo(
    () => faceLibrary.find((face) => face.id === selectedFaceId) ?? null,
    [faceLibrary, selectedFaceId]
  );

  const resultCards: ResultCard[] = [
    { id: "original", title: "Original", enhanced: false, variant: "original", imageUrl: originalImageUrl || null },
    { id: "enhanced-1", title: "Model Swap - OptimoVTS", enhanced: true, variant: "enhanced-a", imageUrl: resultImageUrl },
    { id: "enhanced-2", title: "Model Swap Variant", enhanced: true, variant: "enhanced-b", imageUrl: resultImageUrl }
  ];

  useEffect(() => {
    if (!pickerOpen || !storeId.trim()) {
      return;
    }

    const controller = new AbortController();
    let active = true;

    setLoadingFaces(true);

    listModelFaces({
      storeId: storeId.trim(),
      gender: faceGender,
      age: faceAge || null,
      skinTone: faceSkinTone || null,
      signal: controller.signal
    })
      .then((data) => {
        if (!active) {
          return;
        }

        setFaceLibrary(data);
        setSelectedFaceId((current) => {
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

        const message = error instanceof Error ? error.message : "Failed to load face library.";
        setErrorMessage(message);
        setFaceLibrary([]);
      })
      .finally(() => {
        if (active) {
          setLoadingFaces(false);
        }
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [pickerOpen, storeId, faceGender, faceAge, faceSkinTone]);

  const openPicker = () => {
    setGenerated(false);
    setErrorMessage("");
    setPickerOpen(true);
  };

  const closePicker = () => {
    setPickerOpen(false);
  };

  const selectFace = (faceId: string) => {
    setSelectedFaceId(faceId);
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

    if (!originalImageUrl.trim()) {
      setErrorMessage("Enter original image URL.");
      return;
    }

    if (!selectedFaceId) {
      setPickerOpen(true);
      setErrorMessage("Select a face model before generating.");
      return;
    }

    setIsGenerating(true);
    setGenerated(false);
    setErrorMessage("");
    setResultImageUrl(null);
    setStatusMessage("Starting model swap job...");

    try {
      const startedJob = await startModelSwapJob({
        storeId: storeId.trim(),
        shopifyProductGid: productGid.trim(),
        originalImageUrl: originalImageUrl.trim(),
        faceLibraryId: selectedFaceId
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
      const message = error instanceof Error ? error.message : "Failed to generate model swap image.";
      setErrorMessage(message);
      setStatusMessage("");
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <main className="portal-shell">
      <PortalSidebar activeMain="ai" activeAi="model-swap" />

      <section className="portal-main">
        <header className="portal-main-header">
          <h2>AI Product Shoots</h2>
          <p>Generate professional studio shoots in seconds</p>
        </header>

        {!uploaded ? (
          <section className="ai-stage-upload">
            <article className="ai-upload-copy ai-swap-upload-copy">
              <h3>
                Transform Fashion Photos with
                <br />
                Premium <span>AI Model Swap</span>
              </h3>
              <p>Seamless, diverse, and customized visuals, perfect for any market.</p>
              <div className="ai-upload-preview" aria-hidden />
            </article>

            <aside className="ai-upload-panel">
              <p className="ai-upgrade-banner">✦ Upgrade Your Visuals Now</p>

              <div className="ai-upload-drop" aria-hidden>
                <svg viewBox="0 0 24 24" role="img">
                  <path
                    d="M12 14V7M12 7L9 10M12 7L15 10M7 16.5H6.6C4.6 16.5 3 15 3 13C3 11 4.6 9.4 6.6 9.4C7.1 7 9.2 5.2 11.8 5.2C14.7 5.2 17 7.4 17.2 10.1C19.2 10.2 21 11.8 21 13.9C21 16.1 19.2 17.8 16.9 17.8H7"
                    fill="none"
                    stroke="currentColor"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                  />
                </svg>
                <p>Click or drag image here</p>
              </div>

              <button type="button" className="ai-primary-btn" onClick={() => setUploaded(true)}>
                Continue to model swap
              </button>

              <p className="ai-upload-note">
                Use any product image from Shopify CDN,
                <br />
                then choose a face from the Optimo library
              </p>
            </aside>
          </section>
        ) : (
          <section className="ai-stage-model-swap">
            <aside className="ai-swap-panel">
              <h3>Model Swap</h3>
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

              <h4>Original image URL</h4>
              <label className="ai-text-field">
                <input
                  aria-label="Original image URL"
                  value={originalImageUrl}
                  onChange={(event) => setOriginalImageUrl(event.target.value)}
                  placeholder="https://cdn.shopify.com/..."
                  autoComplete="off"
                />
              </label>

              <h4>Face model</h4>
              <button type="button" className="ai-swap-face-trigger" onClick={openPicker}>
                {selectedFace ? (
                  <span className="ai-swap-face-thumb" style={imageTileStyle(selectedFace.image_url)} aria-hidden />
                ) : (
                  <span className="ai-swap-face-icon" aria-hidden>
                    <svg viewBox="0 0 24 24" role="img">
                      <rect x="3" y="4" width="18" height="16" rx="2" fill="none" stroke="currentColor" strokeWidth="1.8" />
                      <circle cx="8.2" cy="9" r="1.6" fill="none" stroke="currentColor" strokeWidth="1.8" />
                      <path d="M5.5 17L10.4 12.2L13.3 14.9L16.2 12L18.5 14.4V17" fill="none" stroke="currentColor" strokeWidth="1.8" />
                    </svg>
                  </span>
                )}
                <span className="ai-swap-face-copy">
                  <strong>Select face model</strong>
                  <span>Choose from the Optimo face library</span>
                </span>
                <span className="ai-swap-chevron" aria-hidden>
                  ›
                </span>
              </button>

              <button type="button" className="ai-primary-btn ai-swap-generate-btn" onClick={generateResults} disabled={isGenerating}>
                {isGenerating ? "Generating..." : "Generate"}
              </button>

              {statusMessage ? <p className="ai-status-note">{statusMessage}</p> : null}
              {errorMessage ? <p className="ai-error-note">{errorMessage}</p> : null}
            </aside>

            <section className="ai-swap-right">
              {pickerOpen ? (
                <section className="ai-swap-picker">
                  <header className="ai-swap-picker-head">
                    <button type="button" className="ai-swap-picker-back" onClick={closePicker} aria-label="Back">
                    ‹
                  </button>
                  <div>
                    <h3>Select face model</h3>
                    <p>Optimo face library</p>
                  </div>
                </header>

                  <div className="ai-swap-filters">
                    <label className="ai-swap-filter">
                      <select aria-label="Gender" value={faceGender} onChange={(event) => setFaceGender(event.target.value)}>
                        <option value="female">Women</option>
                        <option value="male">Men</option>
                      </select>
                    </label>
                    <label className="ai-swap-filter">
                      <select aria-label="Age" value={faceAge} onChange={(event) => setFaceAge(event.target.value)}>
                        <option value="">Age</option>
                        <option value="18-25">18-25</option>
                        <option value="26-35">26-35</option>
                        <option value="36-45">36-45</option>
                        <option value="45+">45+</option>
                      </select>
                    </label>
                    <label className="ai-swap-filter">
                      <select aria-label="Skin" value={faceSkinTone} onChange={(event) => setFaceSkinTone(event.target.value)}>
                        <option value="">Skin</option>
                        <option value="fair">Fair</option>
                        <option value="light">Light</option>
                        <option value="medium">Medium</option>
                        <option value="tan">Tan</option>
                        <option value="dark">Dark</option>
                      </select>
                    </label>
                  </div>

                  <div className="ai-swap-face-list">
                    <div className="ai-swap-face-grid">
                      {loadingFaces ? <p className="ai-inline-note">Loading faces...</p> : null}
                      {!loadingFaces && faceLibrary.length === 0 ? <p className="ai-inline-note">No faces returned for current filters.</p> : null}

                      {faceLibrary.map((face) => (
                        <button
                          key={face.id}
                          type="button"
                          className={`ai-swap-face-tile${selectedFaceId === face.id ? " is-selected" : ""}`}
                          onClick={() => selectFace(face.id)}
                          aria-label={face.id}
                        >
                          <span style={imageTileStyle(face.image_url)} />
                          {selectedFaceId === face.id ? <i className="ai-swap-face-check" aria-hidden>✓</i> : null}
                        </button>
                      ))}
                    </div>
                  </div>
                </section>
              ) : generated ? (
                <div className="ai-results-grid ai-swap-results-grid">
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
                          <span className="ai-result-photo" style={imageTileStyle(card.imageUrl)} />
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
                <div className="ai-swap-placeholder-grid">
                  <article className="ai-result-card">
                    <header>
                      <p>Original</p>
                    </header>
                    <div className="ai-result-image ai-result-image-original" aria-hidden>
                      {originalImageUrl ? (
                        <span className="ai-result-photo" style={imageTileStyle(originalImageUrl)} />
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
                  <div className="ai-swap-placeholder-card" aria-hidden />
                  <div className="ai-swap-placeholder-card" aria-hidden />
                </div>
              )}
            </section>
          </section>
        )}
      </section>
    </main>
  );
}
