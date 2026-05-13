"use client";

import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type ChangeEvent
} from "react";
import { Download, RefreshCw } from "lucide-react";
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
  resolveBackendUrl,
  startTryOnModelJob,
  type PhotoshootModelResponse
} from "../../../lib/photoshootApi";
import { extractProductImageUrls, usePhotoshootProducts } from "../_components/usePhotoshootProducts";

const IMAGE_MAX_BYTES = 10 * 1024 * 1024;
const ALLOWED_IMAGE_MIME = new Set(["image/jpeg", "image/jpg", "image/png", "image/webp"]);

function tileStyle(imageUrl: string): CSSProperties {
  return {
    backgroundImage: `url(${resolveBackendUrl(imageUrl)})`,
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

export default function ModelTryOnPage() {
  const storeId = useMemo(() => getDefaultStoreId(), []);
  const aiTabs = [
    { href: "/ai-product-shoot", label: "Ghost Mannequin" },
    { href: "/ai-product-shoot/model-try-on", label: "Model Try-on" },
    { href: "/ai-product-shoot/model-swap", label: "Model Swap" }
  ];

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
    loadMoreProducts,
    syncNow
  } = usePhotoshootProducts(storeId);

  const [started, setStarted] = useState(false);
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
  const [statusMessage, setStatusMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [resultImageUrl, setResultImageUrl] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobNeedsProductAtApprove, setJobNeedsProductAtApprove] = useState(false);
  const previewUrlsRef = useRef<string[]>([]);

  useEffect(() => {
    return () => {
      previewUrlsRef.current.forEach((url) => URL.revokeObjectURL(url));
      previewUrlsRef.current = [];
    };
  }, []);

  useEffect(() => {
    if (!storeId.trim() || modelSource !== "library") {
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
          return payload[0]?.id ?? null;
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
  }, [modelAge, modelBodyType, modelGender, modelSource, storeId]);

  const productImages = useMemo(() => extractProductImageUrls(selectedProduct), [selectedProduct]);
  const selectedModel = useMemo(
    () => models.find((model) => model.id === selectedModelId) ?? null,
    [models, selectedModelId]
  );

  const onProductUpload = (event: ChangeEvent<HTMLInputElement>) => {
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
    setProductImageFile(file);
    setProductImageUrl(null);
    setProductImagePreview(preview);
    setErrorMessage("");
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
    setErrorMessage("");
    event.currentTarget.value = "";
  };

  const chooseStoreProductImage = (imageUrl: string) => {
    setProductImageUrl(imageUrl);
    setProductImageFile(null);
    setProductImagePreview(imageUrl);
    setErrorMessage("");
  };

  const generateResults = async () => {
    if (!storeId.trim()) {
      setErrorMessage("Open the app from Shopify Admin to connect this tool with the active store.");
      return;
    }
    if (!productImageUrl && !productImageFile) {
      setErrorMessage("Select a product image from store or upload one.");
      return;
    }
    if (modelSource === "library" && !selectedModelId) {
      setErrorMessage("Select a model from library.");
      return;
    }
    if (modelSource === "upload" && !modelImageFile) {
      setErrorMessage("Upload a model image.");
      return;
    }

    setIsGenerating(true);
    setResultImageUrl(null);
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

      setJobId(startedJob.job_id);
      setJobNeedsProductAtApprove(!submittedGid);
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
      setStatusMessage("Generation complete.");
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Failed to generate model try-on image.";
      setErrorMessage(message);
      setStatusMessage("");
    } finally {
      setIsGenerating(false);
    }
  };

  const approveToShopify = async () => {
    if (!jobId || !storeId.trim()) {
      return;
    }
    if (jobNeedsProductAtApprove && !selectedProductGid) {
      setErrorMessage("Select a store product before approving this result.");
      return;
    }

    setIsApproving(true);
    setErrorMessage("");
    try {
      const response = await approvePhotoshootJob({
        storeId: storeId.trim(),
        jobId,
        shopifyProductGid: jobNeedsProductAtApprove ? selectedProductGid : null
      });
      setStatusMessage(response.message);
      setJobNeedsProductAtApprove(false);
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Failed to approve generated image.";
      setErrorMessage(message);
    } finally {
      setIsApproving(false);
    }
  };

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
                      backgroundClip: "text",
                    }}
                  >
                    Virtual Try-On Images
                  </span>
                </>
              }
              subtitle="AI On-Model Photos Generator, accurate, realistic, and built to convert."
              videoSrc="/Try-on.mp4"
              onUpload={() => setStarted(true)}
            />
          </div>
        ) : (
          <section className="ai-stage-model-tryon">
            <aside className="ai-tryon-panel">
              <h3>Model Try-On</h3>
              <p>Product Image</p>

              <h4>Store context</h4>
              <p className="ai-status-note">
                {storeId ? "Connected to the current Shopify store." : "Open the app from Shopify Admin to load store context."}
              </p>

              <h4>Product Search</h4>
              <label className="ai-text-field">
                <input
                  value={searchQuery}
                  onChange={(event) => setSearchQuery(event.target.value)}
                  placeholder="Search synced products"
                  autoComplete="off"
                />
              </label>
              {isLoading ? <p className="ai-status-note">Loading products...</p> : null}
              {isSyncing ? <p className="ai-status-note">Syncing products from Shopify...</p> : null}
              {productError ? <p className="ai-error-note">{productError}</p> : null}

              <div className="ai-product-list">
                {visibleProducts.map((product) => (
                  <button
                    key={product.product_id}
                    type="button"
                    className={`ai-template-item ${selectedProductId === product.product_id ? "is-selected" : ""}`}
                    onClick={() => setSelectedProductId(product.product_id)}
                    aria-label={product.title}
                  >
                    <span>{product.title}</span>
                  </button>
                ))}
              </div>
              <div className="ai-inline-actions">
                <button type="button" className="ai-outline-btn" onClick={syncNow} disabled={isSyncing}>
                  {isSyncing ? "Syncing..." : "Sync products"}
                </button>
                {canLoadMore ? (
                  <button type="button" className="ai-outline-btn" onClick={loadMoreProducts} disabled={isLoadingMore}>
                    {isLoadingMore ? "Loading..." : "Load more"}
                  </button>
                ) : null}
              </div>

              <h4>Store product images</h4>
              <div className="ai-template-grid">
                {productImages.map((imageUrl) => (
                  <button key={imageUrl} type="button" className="ai-template-item is-selected" onClick={() => chooseStoreProductImage(imageUrl)}>
                    <span style={tileStyle(imageUrl)} />
                    <strong>Use image</strong>
                  </button>
                ))}
              </div>

              <label className="ai-outline-btn">
                <input type="file" accept="image/jpeg,image/png,image/webp" onChange={onProductUpload} />
                Upload Product Image
              </label>

              <h4>Model Source</h4>
              <div className="ai-inline-actions">
                <button
                  type="button"
                  className={`ai-outline-btn${modelSource === "library" ? " is-selected" : ""}`}
                  onClick={() => setModelSource("library")}
                >
                  Model Library
                </button>
                <button
                  type="button"
                  className={`ai-outline-btn${modelSource === "upload" ? " is-selected" : ""}`}
                  onClick={() => setModelSource("upload")}
                >
                  Upload Model
                </button>
              </div>

              {modelSource === "library" ? (
                <>
                  <div className="ai-inline-actions">
                    <label className="ai-select-wrap">
                      <select value={modelGender} onChange={(event) => setModelGender(event.target.value)} aria-label="Gender">
                        <option value="unisex">All</option>
                        <option value="female">Women</option>
                        <option value="male">Men</option>
                      </select>
                    </label>
                    <label className="ai-select-wrap">
                      <select value={modelAge} onChange={(event) => setModelAge(event.target.value)} aria-label="Age">
                        <option value="">Age</option>
                        <option value="18-25">18-25</option>
                        <option value="26-35">26-35</option>
                        <option value="36-45">36-45</option>
                        <option value="45+">45+</option>
                      </select>
                    </label>
                    <label className="ai-select-wrap">
                      <select value={modelBodyType} onChange={(event) => setModelBodyType(event.target.value)} aria-label="Body Type">
                        <option value="">Body Type</option>
                        <option value="slim">Slim</option>
                        <option value="athletic">Athletic</option>
                        <option value="regular">Regular</option>
                        <option value="plus">Plus</option>
                      </select>
                    </label>
                  </div>
                  {isLoadingModels ? <p className="ai-status-note">Loading models...</p> : null}
                  <div className="ai-template-grid">
                    {models.map((model) => (
                      <button
                        key={model.id}
                        type="button"
                        className={`ai-template-item ${selectedModelId === model.id ? "is-selected" : ""}`}
                        onClick={() => setSelectedModelId(model.id)}
                      >
                        <span style={tileStyle(model.image_url)} />
                      </button>
                    ))}
                  </div>
                </>
              ) : (
                <label className="ai-outline-btn">
                  <input type="file" accept="image/jpeg,image/png,image/webp" onChange={onModelUpload} />
                  Upload Model Image
                </label>
              )}

              <button type="button" className="ai-primary-btn ai-tryon-generate-btn" onClick={generateResults} disabled={isGenerating}>
                {isGenerating ? "Generating..." : "Generate"}
              </button>

              {statusMessage ? <p className="ai-status-note">{statusMessage}</p> : null}
              {errorMessage ? <p className="ai-error-note">{errorMessage}</p> : null}
            </aside>

            <section className="ai-tryon-right">
              <div className="ai-results-grid ai-tryon-results-grid">
                <article className="ai-result-card">
                  <header>
                    <p>Original</p>
                  </header>
                  <div className="ai-result-image ai-result-image-original" aria-hidden>
                    {productImagePreview ? <span className="ai-result-photo" style={tileStyle(productImagePreview)} /> : null}
                  </div>
                </article>

                <article className="ai-result-card">
                  <header>
                    <p>Generated</p>
                    {resultImageUrl ? (
                      <div className="ai-result-actions">
                        <a href={resultImageUrl} download="model-try-on-result.jpg">
                          <Download size={11} />
                        </a>
                        <button type="button" onClick={generateResults} disabled={isGenerating}>
                          <RefreshCw size={11} />
                        </button>
                      </div>
                    ) : null}
                  </header>
                  <div className="ai-result-image ai-result-image-enhanced-a" aria-hidden>
                    {resultImageUrl ? <span className="ai-result-photo" style={tileStyle(resultImageUrl)} /> : null}
                  </div>
                  <button
                    type="button"
                    className="ai-primary-btn"
                    onClick={approveToShopify}
                    disabled={!jobId || isApproving || (jobNeedsProductAtApprove && !selectedProductGid)}
                  >
                    {isApproving ? "Approving..." : "Approve & Push to Shopify"}
                  </button>
                </article>
              </div>
              {modelSource === "library" && selectedModel ? (
                <p className="ai-status-note">Selected library model is ready for generation.</p>
              ) : null}
              {modelSource === "upload" && modelImagePreview ? (
                <p className="ai-status-note">Uploaded model image is ready for generation.</p>
              ) : null}
            </section>
          </section>
        )}
      </section>
    </main>
  );
}
