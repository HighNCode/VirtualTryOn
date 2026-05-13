"use client";

import { useEffect, useMemo, useRef, useState, type CSSProperties, type ChangeEvent, type Dispatch, type SetStateAction } from "react";
import { Download, RefreshCw } from "lucide-react";
import AiUploadLanding from "../_components/AiUploadLanding";
import PortalSidebar from "../_components/PortalSidebar";
import PortalTopbar from "../_components/PortalTopbar";
import SubTabNav from "../_components/SubTabNav";
import {
  approvePhotoshootJob,
  buildJobResultUrl,
  getDefaultStoreId,
  isFailureStatus,
  pollPhotoshootJob,
  resolveBackendUrl,
  startGhostMannequinJob
} from "../../lib/photoshootApi";
import { extractProductImageUrls, usePhotoshootProducts } from "./_components/usePhotoshootProducts";

const IMAGE_MAX_BYTES = 10 * 1024 * 1024;
const ALLOWED_IMAGE_MIME = new Set(["image/jpeg", "image/jpg", "image/png", "image/webp"]);

type SourceSlot = {
  url: string | null;
  file: File | null;
  preview: string | null;
};

const EMPTY_SLOT: SourceSlot = { url: null, file: null, preview: null };

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

export default function AiProductShootPage() {
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
  const [clothingType, setClothingType] = useState("tops");
  const [frontSlot, setFrontSlot] = useState<SourceSlot>(EMPTY_SLOT);
  const [sideSlot, setSideSlot] = useState<SourceSlot>(EMPTY_SLOT);

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

  const productImages = useMemo(() => extractProductImageUrls(selectedProduct), [selectedProduct]);
  const originalPreview = frontSlot.preview || sideSlot.preview || null;

  const setStoreImageToFront = (imageUrl: string) => {
    setFrontSlot({ url: imageUrl, file: null, preview: imageUrl });
  };

  const setStoreImageToSide = (imageUrl: string) => {
    setSideSlot({ url: imageUrl, file: null, preview: imageUrl });
  };

  const setUploadedImage = (
    file: File,
    slotSetter: Dispatch<SetStateAction<SourceSlot>>
  ) => {
    const preview = URL.createObjectURL(file);
    previewUrlsRef.current.push(preview);
    slotSetter({ url: null, file, preview });
  };

  const onFileInputChange = async (
    event: ChangeEvent<HTMLInputElement>,
    slotSetter: Dispatch<SetStateAction<SourceSlot>>
  ) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    const validationError = validateImageFile(file);
    if (validationError) {
      setErrorMessage(validationError);
      event.currentTarget.value = "";
      return;
    }
    setErrorMessage("");
    setUploadedImage(file, slotSetter);
    event.currentTarget.value = "";
  };

  const generateResults = async () => {
    if (!storeId.trim()) {
      setErrorMessage("Open the app from Shopify Admin to connect this tool with the active store.");
      return;
    }
    if (!frontSlot.preview || !sideSlot.preview) {
      setErrorMessage("Set both Front image and Side image before generating.");
      return;
    }

    setIsGenerating(true);
    setResultImageUrl(null);
    setStatusMessage("Starting ghost mannequin job...");
    setErrorMessage("");

    try {
      const submittedGid = selectedProductGid.trim() || null;
      const startedJob = await startGhostMannequinJob({
        storeId: storeId.trim(),
        clothingType,
        shopifyProductGid: submittedGid,
        image1Url: frontSlot.url,
        image2Url: sideSlot.url,
        image1File: frontSlot.file,
        image2File: sideSlot.file
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
      const message = error instanceof Error ? error.message : "Failed to generate ghost mannequin image.";
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
      <PortalSidebar activeMain="ai" activeAi="ghost" />

      <section className="portal-main">
        <PortalTopbar title="AI Product Shoot" subtitle="Remove mannequin and enhance your product images" />
        <SubTabNav tabs={aiTabs} />

        {!started ? (
          <div style={{ padding: 24 }}>
            <AiUploadLanding
              headline={
                <>
                  AI{" "}
                  <span
                    style={{
                      background: "linear-gradient(135deg, #7E0175 0%, #BC174A 55%, #E40206 100%)",
                      WebkitBackgroundClip: "text",
                      WebkitTextFillColor: "transparent",
                      backgroundClip: "text",
                    }}
                  >
                    Ghost Mannequin
                  </span>{" "}
                  Generator for Product Photography
                </>
              }
              subtitle="Professional results in seconds, without studios or mannequins."
              videoSrc="/Ghost Mannequin.mp4"
              onUpload={() => setStarted(true)}
            />
          </div>
        ) : (
          <section className="ai-stage-result">
            <aside className="ai-generator-card">
              <h3>Ghost Mannequin</h3>
              <p>Product Source</p>

              <h4>Store context</h4>
              <p className="ai-status-note">
                {storeId ? "Connected to the current Shopify store." : "Open the app from Shopify Admin to load store context."}
              </p>

              <h4>Clothing Type</h4>
              <label className="ai-select-wrap">
                <select
                  aria-label="Clothing Type"
                  value={clothingType}
                  onChange={(event) => setClothingType(event.target.value)}
                >
                  <option value="tops">Tops</option>
                  <option value="bottoms">Bottoms</option>
                  <option value="dresses">Dresses</option>
                  <option value="outerwear">Outerwear</option>
                </select>
              </label>

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

              <h4>Selected Product Images</h4>
              <div className="ai-template-grid">
                {productImages.map((imageUrl) => (
                  <div key={imageUrl} className="ai-template-item is-selected">
                    <span style={tileStyle(imageUrl)} />
                    <button type="button" className="ai-outline-btn" onClick={() => setStoreImageToFront(imageUrl)}>
                      Use as Front
                    </button>
                    <button type="button" className="ai-outline-btn" onClick={() => setStoreImageToSide(imageUrl)}>
                      Use as Side
                    </button>
                  </div>
                ))}
              </div>

              <h4>Front image</h4>
              <label className="ai-outline-btn">
                <input type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => void onFileInputChange(event, setFrontSlot)} />
                Upload Front
              </label>
              {frontSlot.preview ? <p className="ai-status-note">Front image ready.</p> : null}

              <h4>Side image</h4>
              <label className="ai-outline-btn">
                <input type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => void onFileInputChange(event, setSideSlot)} />
                Upload Side
              </label>
              {sideSlot.preview ? <p className="ai-status-note">Side image ready.</p> : null}

              <button type="button" className="ai-primary-btn ai-generate-btn" onClick={generateResults} disabled={isGenerating}>
                {isGenerating ? "Generating..." : "Generate"}
              </button>
              {statusMessage ? <p className="ai-status-note">{statusMessage}</p> : null}
              {errorMessage ? <p className="ai-error-note">{errorMessage}</p> : null}
            </aside>

            <div className="ai-results-grid">
              <article className="ai-result-card">
                <header>
                  <p>Original</p>
                </header>
                <div className="ai-result-image ai-result-image-original" aria-hidden>
                  {originalPreview ? <span className="ai-result-photo" style={tileStyle(originalPreview)} /> : null}
                </div>
              </article>

              <article className="ai-result-card">
                <header>
                  <p>Generated</p>
                  {resultImageUrl ? (
                    <div className="ai-result-actions">
                      <a href={resultImageUrl} download="ghost-mannequin-result.jpg">
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
          </section>
        )}
      </section>
    </main>
  );
}
