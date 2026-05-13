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
  listModelFaces,
  pollPhotoshootJob,
  resolveBackendUrl,
  startModelSwapJob,
  type PhotoshootModelFaceResponse
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

export default function ModelSwapPage() {
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
  const [originalImageUrl, setOriginalImageUrl] = useState<string | null>(null);
  const [originalImageFile, setOriginalImageFile] = useState<File | null>(null);
  const [originalImagePreview, setOriginalImagePreview] = useState<string | null>(null);

  const [faceSource, setFaceSource] = useState<"library" | "upload">("library");
  const [faceGender, setFaceGender] = useState("female");
  const [faceAge, setFaceAge] = useState("");
  const [faceSkinTone, setFaceSkinTone] = useState("");
  const [faceLibrary, setFaceLibrary] = useState<PhotoshootModelFaceResponse[]>([]);
  const [selectedFaceId, setSelectedFaceId] = useState<string | null>(null);
  const [faceImageFile, setFaceImageFile] = useState<File | null>(null);
  const [faceImagePreview, setFaceImagePreview] = useState<string | null>(null);
  const [isLoadingFaces, setIsLoadingFaces] = useState(false);

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
    if (!storeId.trim() || faceSource !== "library") {
      return;
    }
    const controller = new AbortController();
    setIsLoadingFaces(true);
    listModelFaces({
      storeId: storeId.trim(),
      gender: faceGender,
      age: faceAge || null,
      skinTone: faceSkinTone || null,
      signal: controller.signal
    })
      .then((payload) => {
        setFaceLibrary(payload);
        setSelectedFaceId((current) => {
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
        const message = error instanceof Error ? error.message : "Failed to load face library.";
        setErrorMessage(message);
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsLoadingFaces(false);
        }
      });
    return () => controller.abort();
  }, [faceAge, faceGender, faceSkinTone, faceSource, storeId]);

  const productImages = useMemo(() => extractProductImageUrls(selectedProduct), [selectedProduct]);
  const selectedFace = useMemo(
    () => faceLibrary.find((item) => item.id === selectedFaceId) ?? null,
    [faceLibrary, selectedFaceId]
  );

  const onOriginalUpload = (event: ChangeEvent<HTMLInputElement>) => {
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
    setOriginalImageFile(file);
    setOriginalImageUrl(null);
    setOriginalImagePreview(preview);
    setErrorMessage("");
    event.currentTarget.value = "";
  };

  const onFaceUpload = (event: ChangeEvent<HTMLInputElement>) => {
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
    setFaceImageFile(file);
    setFaceImagePreview(preview);
    setFaceSource("upload");
    setErrorMessage("");
    event.currentTarget.value = "";
  };

  const chooseStoreOriginalImage = (imageUrl: string) => {
    setOriginalImageUrl(imageUrl);
    setOriginalImageFile(null);
    setOriginalImagePreview(imageUrl);
    setErrorMessage("");
  };

  const generateResults = async () => {
    if (!storeId.trim()) {
      setErrorMessage("Open the app from Shopify Admin to connect this tool with the active store.");
      return;
    }
    if (!originalImageUrl && !originalImageFile) {
      setErrorMessage("Select original image from store or upload one.");
      return;
    }
    if (faceSource === "library" && !selectedFaceId) {
      setErrorMessage("Select a replacement face from library.");
      return;
    }
    if (faceSource === "upload" && !faceImageFile) {
      setErrorMessage("Upload a replacement face image.");
      return;
    }

    setIsGenerating(true);
    setResultImageUrl(null);
    setStatusMessage("Starting model swap job...");
    setErrorMessage("");

    try {
      const submittedGid = selectedProductGid.trim() || null;
      const startedJob = await startModelSwapJob({
        storeId: storeId.trim(),
        shopifyProductGid: submittedGid,
        originalImageUrl,
        originalImageFile,
        faceLibraryId: faceSource === "library" ? selectedFaceId : null,
        faceImage: faceSource === "upload" ? faceImageFile : null
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
      const message = error instanceof Error ? error.message : "Failed to generate model swap image.";
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
      <PortalSidebar activeMain="ai" activeAi="model-swap" />

      <section className="portal-main">
        <PortalTopbar title="AI Product Shoot" subtitle="Swap the model in your existing product images" />
        <SubTabNav tabs={aiTabs} />

        {!started ? (
          <div style={{ padding: 24 }}>
            <AiUploadLanding
              headline={
                <>
                  Transform Fashion Photos with Premium{" "}
                  <span
                    style={{
                      background: "linear-gradient(135deg, #7E0175 0%, #BC174A 55%, #E40206 100%)",
                      WebkitBackgroundClip: "text",
                      WebkitTextFillColor: "transparent",
                      backgroundClip: "text",
                    }}
                  >
                    AI Model Swap
                  </span>
                </>
              }
              subtitle="Seamless, diverse, and customized visuals, perfect for any market."
              videoSrc="/Model Swap.mp4"
              onUpload={() => setStarted(true)}
            />
          </div>
        ) : (
          <section className="ai-stage-model-swap">
            <aside className="ai-swap-panel">
              <h3>Model Swap</h3>
              <p>Original Product Image</p>

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
                  <button key={imageUrl} type="button" className="ai-template-item is-selected" onClick={() => chooseStoreOriginalImage(imageUrl)}>
                    <span style={tileStyle(imageUrl)} />
                    <strong>Use image</strong>
                  </button>
                ))}
              </div>

              <label className="ai-outline-btn">
                <input type="file" accept="image/jpeg,image/png,image/webp" onChange={onOriginalUpload} />
                Upload Original Image
              </label>

              <h4>Replacement Face</h4>
              <div className="ai-inline-actions">
                <button
                  type="button"
                  className={`ai-outline-btn${faceSource === "library" ? " is-selected" : ""}`}
                  onClick={() => setFaceSource("library")}
                >
                  Face Library
                </button>
                <button
                  type="button"
                  className={`ai-outline-btn${faceSource === "upload" ? " is-selected" : ""}`}
                  onClick={() => setFaceSource("upload")}
                >
                  Upload Face
                </button>
              </div>

              {faceSource === "library" ? (
                <>
                  <div className="ai-inline-actions">
                    <label className="ai-select-wrap">
                      <select value={faceGender} onChange={(event) => setFaceGender(event.target.value)} aria-label="Gender">
                        <option value="female">Women</option>
                        <option value="male">Men</option>
                      </select>
                    </label>
                    <label className="ai-select-wrap">
                      <select value={faceAge} onChange={(event) => setFaceAge(event.target.value)} aria-label="Age">
                        <option value="">Age</option>
                        <option value="18-25">18-25</option>
                        <option value="26-35">26-35</option>
                        <option value="36-45">36-45</option>
                        <option value="45+">45+</option>
                      </select>
                    </label>
                    <label className="ai-select-wrap">
                      <select value={faceSkinTone} onChange={(event) => setFaceSkinTone(event.target.value)} aria-label="Skin tone">
                        <option value="">Skin</option>
                        <option value="fair">Fair</option>
                        <option value="light">Light</option>
                        <option value="medium">Medium</option>
                        <option value="tan">Tan</option>
                        <option value="dark">Dark</option>
                      </select>
                    </label>
                  </div>
                  {isLoadingFaces ? <p className="ai-status-note">Loading faces...</p> : null}
                  <div className="ai-template-grid">
                    {faceLibrary.map((face) => (
                      <button
                        key={face.id}
                        type="button"
                        className={`ai-template-item ${selectedFaceId === face.id ? "is-selected" : ""}`}
                        onClick={() => setSelectedFaceId(face.id)}
                      >
                        <span style={tileStyle(face.image_url)} />
                      </button>
                    ))}
                  </div>
                </>
              ) : (
                <label className="ai-outline-btn">
                  <input type="file" accept="image/jpeg,image/png,image/webp" onChange={onFaceUpload} />
                  Upload Face Image
                </label>
              )}

              <p className="ai-status-note">Only the face will be swapped while keeping body, clothing, and background aligned.</p>

              <button type="button" className="ai-primary-btn ai-swap-generate-btn" onClick={generateResults} disabled={isGenerating}>
                {isGenerating ? "Generating..." : "Generate"}
              </button>

              {statusMessage ? <p className="ai-status-note">{statusMessage}</p> : null}
              {errorMessage ? <p className="ai-error-note">{errorMessage}</p> : null}
            </aside>

            <section className="ai-swap-right">
              <div className="ai-results-grid ai-swap-results-grid">
                <article className="ai-result-card">
                  <header>
                    <p>Original</p>
                  </header>
                  <div className="ai-result-image ai-result-image-original" aria-hidden>
                    {originalImagePreview ? <span className="ai-result-photo" style={tileStyle(originalImagePreview)} /> : null}
                  </div>
                </article>

                <article className="ai-result-card">
                  <header>
                    <p>Generated</p>
                    {resultImageUrl ? (
                      <div className="ai-result-actions">
                        <a href={resultImageUrl} download="model-swap-result.jpg">
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
              {faceSource === "library" && selectedFace ? (
                <p className="ai-status-note">Selected face from library is ready for generation.</p>
              ) : null}
              {faceSource === "upload" && faceImagePreview ? (
                <p className="ai-status-note">Uploaded face image is ready for generation.</p>
              ) : null}
            </section>
          </section>
        )}
      </section>
    </main>
  );
}
