"use client";

import { useEffect, useMemo, useRef, useState, type CSSProperties, type ChangeEvent } from "react";
import { ChevronRight, Download, PencilLine, RefreshCw, Trash2, Upload, UserRound, X } from "lucide-react";
import AiUploadLanding from "../../_components/AiUploadLanding";
import PortalSidebar from "../../_components/PortalSidebar";
import PortalTopbar from "../../_components/PortalTopbar";
import SubTabNav from "../../_components/SubTabNav";
import {
  approvePhotoshootJob,
  buildJobResultUrl,
  getDefaultStoreId,
  isFailureStatus,
  listPhotoshootModels,
  pollPhotoshootJob,
  resolvePhotoshootImageUrl,
  resolveBackendUrl,
  startTryOnModelJob,
  type PhotoshootModelResponse
} from "../../../lib/photoshootApi";
import { extractProductImageUrls, usePhotoshootProducts } from "../_components/usePhotoshootProducts";

const IMAGE_MAX_BYTES = 10 * 1024 * 1024;
const ALLOWED_IMAGE_MIME = new Set(["image/jpeg", "image/jpg", "image/png", "image/webp"]);

type GeneratedResult = {
  id: string;
  imageUrl: string;
  jobId: string;
  needsProductAtApprove: boolean;
};

function tileStyle(imageUrl: string): CSSProperties {
  const resolvedImageUrl = resolvePhotoshootImageUrl(imageUrl);

  return {
    backgroundImage: `url(${resolvedImageUrl})`,
    backgroundSize: "cover",
    backgroundPosition: "center"
  };
}

function validateImageFile(file: File): string | null {
  if (!ALLOWED_IMAGE_MIME.has(file.type.toLowerCase())) {
    return "Only jpg, png, and webp files are allowed.";
  }
  if (file.size > IMAGE_MAX_BYTES) {
    return "Each file must be 10MB or smaller.";
  }
  return null;
}

const aiTabs = [
  { href: "/ai-product-shoot", label: "Ghost Mannequin" },
  { href: "/ai-product-shoot/model-try-on", label: "Model Try-on" },
  { href: "/ai-product-shoot/model-swap", label: "Model Swap" }
];

export default function ModelTryOnPage() {
  const storeId = useMemo(() => getDefaultStoreId(), []);
  const {
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
    errorMessage: productError,
    canLoadMore,
    loadMoreProducts
  } = usePhotoshootProducts(storeId);

  const [started, setStarted] = useState(false);
  const [modelPickerOpen, setModelPickerOpen] = useState(false);
  const [storePickerOpen, setStorePickerOpen] = useState(false);

  const [productImageUrl, setProductImageUrl] = useState<string | null>(null);
  const [productImageFile, setProductImageFile] = useState<File | null>(null);
  const [productImagePreview, setProductImagePreview] = useState<string | null>(null);

  const [modelSource, setModelSource] = useState<"library" | "upload">("library");
  const [modelGender, setModelGender] = useState("unisex");
  const [modelAge, setModelAge] = useState("");
  const [modelBodyType, setModelBodyType] = useState("");
  const [models, setModels] = useState<PhotoshootModelResponse[]>([]);
  const [selectedModelId, setSelectedModelId] = useState<string | null>(null);
  const [modelImageFile, setModelImageFile] = useState<File | null>(null);
  const [modelImagePreview, setModelImagePreview] = useState<string | null>(null);
  const [isLoadingModels, setIsLoadingModels] = useState(false);

  const [isGenerating, setIsGenerating] = useState(false);
  const [isApproving, setIsApproving] = useState(false);
  const [approvingResultId, setApprovingResultId] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [generatedResults, setGeneratedResults] = useState<GeneratedResult[]>([]);
  const previewUrlsRef = useRef<string[]>([]);

  useEffect(() => {
    return () => {
      previewUrlsRef.current.forEach((url) => URL.revokeObjectURL(url));
      previewUrlsRef.current = [];
    };
  }, []);

  useEffect(() => {
    if (!modelPickerOpen || !storeId.trim() || modelSource !== "library") {
      return;
    }

    const controller = new AbortController();
    setIsLoadingModels(true);
    listPhotoshootModels({
      storeId: storeId.trim(),
      gender: modelGender,
      age: modelAge || null,
      bodyType: modelBodyType || null,
      signal: controller.signal
    })
      .then((payload) => {
        setModels(payload);
        setSelectedModelId((current) => {
          if (current && payload.some((item) => item.id === current)) {
            return current;
          }
          return null;
        });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        const message = error instanceof Error ? error.message : "Failed to load model library.";
        setErrorMessage(message);
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsLoadingModels(false);
        }
      });

    return () => controller.abort();
  }, [modelAge, modelBodyType, modelGender, modelPickerOpen, modelSource, storeId]);

  const productImages = useMemo(() => extractProductImageUrls(selectedProduct), [selectedProduct]);
  const selectedModel = useMemo(
    () => models.find((model) => model.id === selectedModelId) ?? null,
    [models, selectedModelId]
  );

  const applyUploadedProductFile = (file: File) => {
    const validation = validateImageFile(file);
    if (validation) {
      setErrorMessage(validation);
      return;
    }

    const preview = URL.createObjectURL(file);
    previewUrlsRef.current.push(preview);
    setProductImageFile(file);
    setProductImageUrl(null);
    setProductImagePreview(preview);
    setStarted(true);
    setStorePickerOpen(false);
    setErrorMessage("");
  };

  const onProductUpload = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    applyUploadedProductFile(file);
    event.currentTarget.value = "";
  };

  const onModelUpload = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    const validation = validateImageFile(file);
    if (validation) {
      setErrorMessage(validation);
      event.currentTarget.value = "";
      return;
    }
    const preview = URL.createObjectURL(file);
    previewUrlsRef.current.push(preview);
    setModelImageFile(file);
    setModelImagePreview(preview);
    setModelSource("upload");
    setModelPickerOpen(false);
    setErrorMessage("");
    event.currentTarget.value = "";
  };

  const chooseStoreProductImage = (imageUrl: string) => {
    setProductImageUrl(imageUrl);
    setProductImageFile(null);
    setProductImagePreview(imageUrl);
    setStarted(true);
    setStorePickerOpen(false);
    setErrorMessage("");
  };

  const selectLibraryModel = (modelId: string) => {
    setSelectedModelId(modelId);
    setModelSource("library");
    setModelImageFile(null);
    setModelImagePreview(null);
    setModelPickerOpen(false);
  };

  const clearSelectedModel = () => {
    setSelectedModelId(null);
    setModelImageFile(null);
    setModelImagePreview(null);
    setModelSource("library");
  };

  const generateResults = async () => {
    if (!storeId.trim()) {
      setErrorMessage("Open the app from Shopify Admin to connect this tool with the active store.");
      return;
    }
    if (!productImageUrl && !productImageFile) {
      setStorePickerOpen(true);
      setErrorMessage("Select a product image from store or upload one.");
      return;
    }
    if (modelSource === "library" && !selectedModelId) {
      setModelPickerOpen(true);
      setErrorMessage("Select a model before generating.");
      return;
    }
    if (modelSource === "upload" && !modelImageFile) {
      setModelPickerOpen(true);
      setErrorMessage("Upload a model image.");
      return;
    }

    setIsGenerating(true);
    setStatusMessage("Starting try-on model job...");
    setErrorMessage("");

    try {
      const submittedGid = selectedProductGid.trim() || null;
      const startedJob = await startTryOnModelJob({
        storeId: storeId.trim(),
        shopifyProductGid: submittedGid,
        productImageUrl,
        productImageFile,
        modelLibraryId: modelSource === "library" ? selectedModelId : null,
        modelImage: modelSource === "upload" ? modelImageFile : null
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

      setGeneratedResults((current) => [
        {
          id: `${startedJob.job_id}-${Date.now()}`,
          imageUrl,
          jobId: startedJob.job_id,
          needsProductAtApprove: !submittedGid
        },
        ...current
      ]);
      setStatusMessage("Generation complete.");
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Failed to generate model try-on image.";
      setErrorMessage(message);
      setStatusMessage("");
    } finally {
      setIsGenerating(false);
    }
  };

  const approveToShopify = async (result: GeneratedResult) => {
    if (!result.jobId || !storeId.trim()) {
      return;
    }
    if (result.needsProductAtApprove && !selectedProductGid) {
      setStorePickerOpen(true);
      setErrorMessage("Select a store product before approving this result.");
      return;
    }

    setIsApproving(true);
    setApprovingResultId(result.id);
    setErrorMessage("");
    try {
      const response = await approvePhotoshootJob({
        storeId: storeId.trim(),
        jobId: result.jobId,
        shopifyProductGid: result.needsProductAtApprove ? selectedProductGid : null
      });
      setStatusMessage(response.message);
      setGeneratedResults((current) =>
        current.map((item) => (item.id === result.id ? { ...item, needsProductAtApprove: false } : item))
      );
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Failed to approve generated image.";
      setErrorMessage(message);
    } finally {
      setIsApproving(false);
      setApprovingResultId(null);
    }
  };

  const openModelPicker = () => {
    setModelPickerOpen(true);
    setErrorMessage("");
  };

  const selectedModelPreview =
    modelSource === "library" ? selectedModel?.image_url ?? null : modelImagePreview;

  return (
    <main className="portal-shell">
      <PortalSidebar activeMain="ai" activeAi="model-try-on" />

      <section className="portal-main">
        <PortalTopbar title="AI Product Shoot" subtitle="Place your product on a real model" />
        <SubTabNav tabs={aiTabs} />

        {!started ? (
          <div style={{ padding: 24 }}>
            <AiUploadLanding
              headline={
                <>
                  Turn Garments Into Best-Selling{" "}
                  <span
                    style={{
                      background: "linear-gradient(135deg, #7E0175 0%, #BC174A 55%, #E40206 100%)",
                      WebkitBackgroundClip: "text",
                      WebkitTextFillColor: "transparent",
                      backgroundClip: "text"
                    }}
                  >
                    Virtual Try-On Images
                  </span>
                </>
              }
              subtitle="AI On-Model Photos Generator, accurate, realistic, and built to convert."
              videoSrc="/Try-on.mp4"
              onFileSelected={applyUploadedProductFile}
              onSelectStore={() => setStorePickerOpen(true)}
            />
          </div>
        ) : (
          <section className={`ai-tryon-workspace${generatedResults.length > 0 ? " has-result" : ""}`}>
            <aside className="ai-tryon-setup-card">
              <h3>Fashion Model</h3>

              <p className="ai-tryon-field-label">Product Image</p>
              <div className="ai-tryon-product-preview">
                {productImagePreview ? <span style={tileStyle(productImagePreview)} /> : null}
              </div>

              <label className="ai-tryon-field">
                <span>Try-on Item</span>
                <select aria-label="Try-on Item" value="auto" onChange={() => undefined}>
                  <option value="auto">Auto</option>
                </select>
              </label>

              <section className="ai-tryon-model-card">
                <div className="ai-tryon-model-thumb-wrap">
                  {selectedModelPreview ? (
                    <span style={tileStyle(selectedModelPreview)} />
                  ) : (
                    <UserRound size={24} aria-hidden />
                  )}
                </div>

                <div className="ai-tryon-model-summary">
                  <strong>Try on model</strong>
                  <span>{selectedModelPreview ? "Selected 1 model" : "No model selected"}</span>

                  <div className="ai-tryon-model-actions">
                    <button type="button" onClick={openModelPicker}>
                      <PencilLine size={15} />
                      {selectedModelPreview ? "Edit selection" : "Select model"}
                    </button>
                    {selectedModelPreview ? (
                      <button type="button" onClick={clearSelectedModel}>
                        <Trash2 size={15} />
                        Clear
                      </button>
                    ) : null}
                  </div>
                </div>

                <button type="button" className="ai-tryon-model-open" onClick={openModelPicker} aria-label="Select model">
                  <ChevronRight size={18} />
                </button>
              </section>

              <button type="button" className="ai-primary-btn ai-tryon-generate-main" onClick={generateResults} disabled={isGenerating}>
                {isGenerating ? "Generating..." : "Generate"}
              </button>

              {statusMessage ? <p className="ai-status-note">{statusMessage}</p> : null}
              {errorMessage ? <p className="ai-error-note">{errorMessage}</p> : null}
            </aside>

            {generatedResults.length > 0 ? (
              <section className="ai-clean-results-grid ai-tryon-clean-results" aria-label="Generated try-on results">
                <article className="ai-clean-result-card is-original">
                  <p className="ai-clean-result-title">
                    <strong>Original</strong>
                    <span> - Image</span>
                  </p>
                  <div className="ai-clean-result-frame" aria-hidden>
                    {productImagePreview ? <span className="ai-result-photo" style={tileStyle(productImagePreview)} /> : null}
                  </div>
                </article>

                {generatedResults.map((result, index) => (
                  <article key={result.id} className="ai-clean-result-card is-enhanced">
                    <p className="ai-clean-result-title">
                      <strong>Enhanced</strong>
                      <span>{index === 0 ? " - OptimoVTS" : ` - OptimoVTS (${index})`}</span>
                    </p>
                    <div className="ai-clean-result-frame" aria-hidden>
                      <div className="ai-result-actions">
                        <a href={result.imageUrl} download="model-try-on-result.jpg">
                          <Download size={11} />
                        </a>
                        {index === 0 ? (
                          <button type="button" onClick={generateResults} disabled={isGenerating}>
                            <RefreshCw size={11} />
                          </button>
                        ) : null}
                      </div>
                      <span className="ai-result-photo" style={tileStyle(result.imageUrl)} />
                      <button
                        type="button"
                        className="ai-clean-store-hover-btn"
                        onClick={() => approveToShopify(result)}
                        disabled={isApproving || (result.needsProductAtApprove && !selectedProductGid)}
                      >
                        {approvingResultId === result.id ? "Uploading..." : "Upload on your store"}
                      </button>
                    </div>
                  </article>
                ))}
              </section>
            ) : null}
          </section>
        )}

        {modelPickerOpen ? (
          <div className="ai-picker-backdrop" role="presentation">
            <section className="ai-picker-modal" role="dialog" aria-modal="true" aria-label="Select try on model">
              <header className="ai-picker-head">
                <div>
                  <h3>Select Try on model</h3>
                  <p>Recommended</p>
                </div>
                <button type="button" onClick={() => setModelPickerOpen(false)} aria-label="Close picker">
                  <X size={15} />
                </button>
              </header>

              <div className="ai-picker-filters">
                <label>
                  <select value={modelGender} onChange={(event) => setModelGender(event.target.value)} aria-label="Gender">
                    <option value="unisex">Gender</option>
                    <option value="female">Women</option>
                    <option value="male">Men</option>
                  </select>
                </label>
                <label>
                  <select value={modelAge} onChange={(event) => setModelAge(event.target.value)} aria-label="Age Range">
                    <option value="">Age Range</option>
                    <option value="18-25">18-25</option>
                    <option value="26-35">26-35</option>
                    <option value="36-45">36-45</option>
                    <option value="45+">45+</option>
                  </select>
                </label>
                <label>
                  <select value={modelBodyType} onChange={(event) => setModelBodyType(event.target.value)} aria-label="Body Type">
                    <option value="">Body Type</option>
                    <option value="slim">Slim</option>
                    <option value="athletic">Athletic</option>
                    <option value="regular">Regular</option>
                    <option value="plus">Plus</option>
                  </select>
                </label>
              </div>

              <div className="ai-picker-grid">
                <label className="ai-picker-upload-tile">
                  <input type="file" accept="image/jpeg,image/png,image/webp" onChange={onModelUpload} />
                  <Upload size={18} />
                  <strong>Upload</strong>
                  <span>Model image</span>
                </label>
                {isLoadingModels ? <p className="ai-inline-note">Loading models...</p> : null}
                {!isLoadingModels && models.length === 0 ? <p className="ai-inline-note">No models returned for current filters.</p> : null}
                {models.map((model) => (
                  <button
                    key={model.id}
                    type="button"
                    className={`ai-picker-tile${modelSource === "library" && selectedModelId === model.id ? " is-selected" : ""}`}
                    onClick={() => selectLibraryModel(model.id)}
                    aria-label={model.id}
                  >
                    <span style={tileStyle(model.image_url)} />
                  </button>
                ))}
              </div>
            </section>
          </div>
        ) : null}

        {storePickerOpen ? (
          <div className="ai-picker-backdrop" role="presentation">
            <section className="ai-picker-modal" role="dialog" aria-modal="true" aria-label="Select product image">
              <header className="ai-picker-head">
                <div>
                  <h3>Select product image</h3>
                  <p>From your store</p>
                </div>
                <button type="button" onClick={() => setStorePickerOpen(false)} aria-label="Close picker">
                  <X size={15} />
                </button>
              </header>

              <label className="ai-picker-search">
                <input
                  value={searchQuery}
                  onChange={(event) => setSearchQuery(event.target.value)}
                  placeholder="Search synced products"
                  autoComplete="off"
                />
              </label>
              {productError ? <p className="ai-error-note">{productError}</p> : null}

              <div className="ai-picker-store-list">
                {visibleProducts.map((product) => (
                  <button
                    key={product.product_id}
                    type="button"
                    className={selectedProductId === product.product_id ? "is-selected" : ""}
                    onClick={() => setSelectedProductId(product.product_id)}
                  >
                    {product.title}
                  </button>
                ))}
              </div>

              <div className="ai-picker-grid ai-picker-store-grid">
                <label className="ai-picker-upload-tile">
                  <input type="file" accept="image/jpeg,image/png,image/webp" onChange={onProductUpload} />
                  <Upload size={18} />
                  <strong>Upload</strong>
                  <span>Product image</span>
                </label>
                {isLoading ? <p className="ai-inline-note">Loading products...</p> : null}
                {productImages.map((imageUrl) => (
                  <button
                    key={imageUrl}
                    type="button"
                    className={`ai-picker-tile${productImagePreview === imageUrl ? " is-selected" : ""}`}
                    onClick={() => chooseStoreProductImage(imageUrl)}
                    aria-label="Use store product image"
                  >
                    <span style={tileStyle(imageUrl)} />
                  </button>
                ))}
              </div>

              {canLoadMore || isSyncing || isLoadingMore ? (
                <div className="ai-inline-actions">
                  {canLoadMore ? (
                    <button type="button" className="ai-outline-btn" onClick={loadMoreProducts} disabled={isLoadingMore}>
                      {isLoadingMore ? "Loading..." : "Load more"}
                    </button>
                  ) : null}
                  {isSyncing ? <span className="ai-inline-note">Syncing products...</span> : null}
                </div>
              ) : null}
            </section>
          </div>
        ) : null}
      </section>
    </main>
  );
}
