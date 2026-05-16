"use client";

import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type ChangeEvent
} from "react";
import { Download, ImagePlus, RefreshCw, Upload, UserRound, X } from "lucide-react";
import AiUploadLanding from "../../_components/AiUploadLanding";
import PortalSidebar from "../../_components/PortalSidebar";
import PortalTopbar from "../../_components/PortalTopbar";
import SubTabNav from "../../_components/SubTabNav";
import {
  approvePhotoshootJob,
  buildJobResultUrl,
  getDefaultStoreId,
  isFailureStatus,
  listPhotoshootJobs,
  listModelFaces,
  pollPhotoshootJob,
  resolvePhotoshootImageUrl,
  resolveBackendUrl,
  startModelSwapJob,
  type PhotoshootModelFaceResponse
} from "../../../lib/photoshootApi";
import { extractProductImageUrls, usePhotoshootProducts } from "../_components/usePhotoshootProducts";

const IMAGE_MAX_BYTES = 10 * 1024 * 1024;
const ALLOWED_IMAGE_MIME = new Set(["image/jpeg", "image/jpg", "image/png", "image/webp"]);

type GeneratedResult = {
  id: string;
  imageUrl: string;
  jobId: string;
  needsProductAtApprove: boolean;
  originalImageUrl?: string | null;
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
    loadMoreProducts
  } = usePhotoshootProducts(storeId);

  const [started, setStarted] = useState(false);
  const [storePickerOpen, setStorePickerOpen] = useState(false);
  const [facePickerOpen, setFacePickerOpen] = useState(false);
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
        setSelectedFaceId((current) => (current && payload.some((item) => item.id === current) ? current : null));
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
  const displayOriginalImagePreview = originalImagePreview || generatedResults[0]?.originalImageUrl || null;

  useEffect(() => {
    if (!storeId.trim()) {
      return;
    }

    const controller = new AbortController();
    listPhotoshootJobs({
      storeId: storeId.trim(),
      jobType: "model_swap",
      limit: 24,
      signal: controller.signal
    })
      .then((jobs) => {
        if (controller.signal.aborted) {
          return;
        }
        const results = jobs
          .filter((job) => job.result_image_url)
          .map((job) => ({
            id: job.job_id,
            imageUrl: resolveBackendUrl(job.result_image_url || `/api/v1/merchant/photoshoot/jobs/${job.job_id}/result`),
            jobId: job.job_id,
            needsProductAtApprove: !job.shopify_product_gid && !job.approved_at,
            originalImageUrl: job.input_image_url ? resolveBackendUrl(job.input_image_url) : null
          }));
        setGeneratedResults(results);
        if (results.length > 0) {
          setStarted(true);
        }
      })
      .catch(() => undefined);

    return () => controller.abort();
  }, [storeId]);

  const applyOriginalUploadFile = (file: File) => {
    const validation = validateImageFile(file);
    if (validation) {
      setErrorMessage(validation);
      return;
    }

    const preview = URL.createObjectURL(file);
    previewUrlsRef.current.push(preview);
    setOriginalImageFile(file);
    setOriginalImageUrl(null);
    setOriginalImagePreview(preview);
    setStarted(true);
    setStorePickerOpen(false);
    setErrorMessage("");
  };

  const onOriginalUpload = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    applyOriginalUploadFile(file);
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
    setFacePickerOpen(false);
    setErrorMessage("");
    event.currentTarget.value = "";
  };

  const chooseStoreOriginalImage = (imageUrl: string) => {
    setOriginalImageUrl(imageUrl);
    setOriginalImageFile(null);
    setOriginalImagePreview(imageUrl);
    setStarted(true);
    setStorePickerOpen(false);
    setErrorMessage("");
  };

  const selectLibraryFace = (faceId: string) => {
    setSelectedFaceId(faceId);
    setFaceSource("library");
    setFaceImageFile(null);
    setFaceImagePreview(null);
    setFacePickerOpen(false);
    setErrorMessage("");
  };

  const clearSelectedFace = () => {
    setSelectedFaceId(null);
    setFaceImageFile(null);
    setFaceImagePreview(null);
    setFaceSource("library");
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
          needsProductAtApprove: !submittedGid,
          originalImageUrl: originalImagePreview
        },
        ...current
      ]);
      setStatusMessage("Generation complete.");
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Failed to generate model swap image.";
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
              onFileSelected={applyOriginalUploadFile}
              onSelectStore={() => setStorePickerOpen(true)}
            />
          </div>
        ) : (
          <section className="ai-simple-workspace ai-model-swap-workspace">
            <aside className="ai-simple-setup-card">
              <h3>Model Swap</h3>
              <p>Replace the model face while preserving the product, pose, and background.</p>

              <article className="ai-simple-source-card">
                <header>
                  <strong>Original image</strong>
                  <span>{displayOriginalImagePreview ? "Ready" : "Required"}</span>
                </header>
                <div className="ai-simple-preview ai-simple-preview-tall">
                  {displayOriginalImagePreview ? (
                    <span style={tileStyle(displayOriginalImagePreview)} />
                  ) : (
                    <ImagePlus size={28} />
                  )}
                </div>
                <div className="ai-simple-actions">
                  <label className="ai-outline-btn">
                    <input type="file" accept="image/jpeg,image/png,image/webp" onChange={onOriginalUpload} />
                    Upload
                  </label>
                  <button type="button" className="ai-outline-btn" onClick={() => setStorePickerOpen(true)}>
                    Store
                  </button>
                </div>
              </article>

              <article className="ai-simple-choice-card">
                <div className="ai-simple-choice-thumb">
                  {faceSource === "library" && selectedFace ? (
                    <span style={tileStyle(selectedFace.image_url)} />
                  ) : faceSource === "upload" && faceImagePreview ? (
                    <span style={tileStyle(faceImagePreview)} />
                  ) : (
                    <UserRound size={24} aria-hidden />
                  )}
                </div>
                <div>
                  <strong>Replacement face</strong>
                  <span>
                    {faceSource === "library" && selectedFace
                      ? "Selected from face library"
                      : faceSource === "upload" && faceImagePreview
                        ? "Uploaded face selected"
                        : "No face selected"}
                  </span>
                  <div className="ai-simple-actions">
                    <button type="button" className="ai-outline-btn" onClick={() => setFacePickerOpen(true)}>
                      Select face
                    </button>
                    {selectedFace || faceImagePreview ? (
                      <button type="button" className="ai-outline-btn" onClick={clearSelectedFace}>
                        Clear
                      </button>
                    ) : null}
                  </div>
                </div>
              </article>

              <button type="button" className="ai-primary-btn ai-swap-generate-btn" onClick={generateResults} disabled={isGenerating}>
                {isGenerating ? "Generating..." : "Generate"}
              </button>

              {statusMessage ? <p className="ai-status-note">{statusMessage}</p> : null}
              {errorMessage ? <p className="ai-error-note">{errorMessage}</p> : null}
            </aside>

            <section className="ai-swap-right">
              <div className="ai-clean-results-grid ai-swap-clean-results" aria-label="Model swap results">
                <article className="ai-clean-result-card is-original">
                  <p className="ai-clean-result-title">
                    <strong>Original</strong>
                    <span> - Image</span>
                  </p>
                  <div className="ai-clean-result-frame" aria-hidden>
                    {displayOriginalImagePreview ? (
                      <span className="ai-result-photo" style={tileStyle(displayOriginalImagePreview)} />
                    ) : null}
                  </div>
                </article>

                {generatedResults.length > 0 ? (
                  generatedResults.map((result, index) => (
                    <article key={result.id} className="ai-clean-result-card is-enhanced">
                      <p className="ai-clean-result-title">
                        <strong>Enhanced</strong>
                        <span>{index === 0 ? " - OptimoVTS" : ` - OptimoVTS (${index})`}</span>
                      </p>
                      <div className="ai-clean-result-frame" aria-hidden>
                        <div className="ai-result-actions">
                          <a href={result.imageUrl} download="model-swap-result.jpg">
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
                  ))
                ) : (
                  <article className="ai-clean-result-card is-enhanced is-empty">
                    <p className="ai-clean-result-title">
                      <strong>Enhanced</strong>
                      <span> - OptimoVTS</span>
                    </p>
                    <div className="ai-clean-result-frame" aria-hidden />
                  </article>
                )}
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

        {storePickerOpen ? (
          <div className="ai-picker-backdrop" role="presentation">
            <section className="ai-picker-modal" role="dialog" aria-modal="true" aria-label="Select original image">
              <header className="ai-picker-head">
                <div>
                  <h3>Select original image</h3>
                  <p>From your store or upload</p>
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
              {isLoading ? <p className="ai-inline-note">Loading products...</p> : null}
              {isSyncing ? <p className="ai-inline-note">Syncing products...</p> : null}
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
                  <input type="file" accept="image/jpeg,image/png,image/webp" onChange={onOriginalUpload} />
                  <Upload size={18} />
                  <strong>Upload</strong>
                  <span>Original image</span>
                </label>
                {productImages.map((imageUrl) => (
                  <button
                    key={imageUrl}
                    type="button"
                    className={`ai-picker-tile${originalImagePreview === imageUrl ? " is-selected" : ""}`}
                    onClick={() => chooseStoreOriginalImage(imageUrl)}
                    aria-label="Use store product image"
                  >
                    <span style={tileStyle(imageUrl)} />
                  </button>
                ))}
              </div>

              {canLoadMore ? (
                <div className="ai-inline-actions">
                  <button type="button" className="ai-outline-btn" onClick={loadMoreProducts} disabled={isLoadingMore}>
                    {isLoadingMore ? "Loading..." : "Load more"}
                  </button>
                </div>
              ) : null}
            </section>
          </div>
        ) : null}

        {facePickerOpen ? (
          <div className="ai-picker-backdrop" role="presentation">
            <section className="ai-picker-modal" role="dialog" aria-modal="true" aria-label="Select replacement face">
              <header className="ai-picker-head">
                <div>
                  <h3>Select replacement face</h3>
                  <p>Face library</p>
                </div>
                <button type="button" onClick={() => setFacePickerOpen(false)} aria-label="Close picker">
                  <X size={15} />
                </button>
              </header>

              <div className="ai-picker-filters">
                <label>
                  <select value={faceGender} onChange={(event) => setFaceGender(event.target.value)} aria-label="Gender">
                    <option value="female">Women</option>
                    <option value="male">Men</option>
                  </select>
                </label>
                <label>
                  <select value={faceAge} onChange={(event) => setFaceAge(event.target.value)} aria-label="Age">
                    <option value="">Age</option>
                    <option value="18-25">18-25</option>
                    <option value="26-35">26-35</option>
                    <option value="36-45">36-45</option>
                    <option value="45+">45+</option>
                  </select>
                </label>
                <label>
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

              <div className="ai-picker-grid">
                <label className="ai-picker-upload-tile">
                  <input type="file" accept="image/jpeg,image/png,image/webp" onChange={onFaceUpload} />
                  <Upload size={18} />
                  <strong>Upload</strong>
                  <span>Face image</span>
                </label>
                {isLoadingFaces ? <p className="ai-inline-note">Loading faces...</p> : null}
                {!isLoadingFaces && faceLibrary.length === 0 ? <p className="ai-inline-note">No faces returned for current filters.</p> : null}
                {faceLibrary.map((face) => (
                  <button
                    key={face.id}
                    type="button"
                    className={`ai-picker-tile${faceSource === "library" && selectedFaceId === face.id ? " is-selected" : ""}`}
                    onClick={() => selectLibraryFace(face.id)}
                    aria-label={face.id}
                  >
                    <span style={tileStyle(face.image_url)} />
                  </button>
                ))}
              </div>
            </section>
          </div>
        ) : null}
      </section>
    </main>
  );
}
