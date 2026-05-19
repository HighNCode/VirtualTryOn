"use client";

import { useEffect, useMemo, useRef, useState, type CSSProperties, type ChangeEvent } from "react";
import { Download, ImagePlus, RefreshCw, Upload, X } from "lucide-react";
import AiUploadLanding from "../_components/AiUploadLanding";
import PortalSidebar from "../_components/PortalSidebar";
import PortalTopbar from "../_components/PortalTopbar";
import SubTabNav from "../_components/SubTabNav";
import {
  approvePhotoshootJob,
  buildJobResultUrl,
  getDefaultStoreId,
  isFailureStatus,
  listGhostMannequinRefs,
  listPhotoshootJobs,
  pollPhotoshootJob,
  resolvePhotoshootImageUrl,
  resolveBackendUrl,
  startGhostMannequinJob,
  type GhostMannequinRefResponse
} from "../../lib/photoshootApi";
import { getPhotoshootProgressMessage, getPhotoshootStartingMessage } from "./_components/photoshootStatus";
import { extractProductImageUrls, usePhotoshootProducts } from "./_components/usePhotoshootProducts";

const IMAGE_MAX_BYTES = 10 * 1024 * 1024;
const ALLOWED_IMAGE_MIME = new Set(["image/jpeg", "image/jpg", "image/png", "image/webp"]);

type SourceSlot = {
  url: string | null;
  file: File | null;
  preview: string | null;
};

type GeneratedResult = {
  id: string;
  imageUrl: string;
  jobId: string;
  needsProductAtApprove: boolean;
  originalImageUrl?: string | null;
};

const EMPTY_SLOT: SourceSlot = { url: null, file: null, preview: null };

const ghostTemplates = [
  { id: "fallback-front", pose: "front", label: "Front", image: "/templates/white-jacket.jpg", referenceId: null },
  { id: "fallback-side", pose: "side", label: "Side", image: "/templates/hooded-jacket.jpg", referenceId: null },
  { id: "fallback-back", pose: "back", label: "Back", image: "/templates/bomber.jpg", referenceId: null }
] as const;

type GhostTemplateOption = {
  id: string;
  pose: string;
  label: string;
  image: string;
  referenceId: string | null;
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
    loadMoreProducts
  } = usePhotoshootProducts(storeId);

  const [started, setStarted] = useState(false);
  const [storePickerOpen, setStorePickerOpen] = useState(false);
  const [clothingType, setClothingType] = useState("tops");
  const [originalSlot, setOriginalSlot] = useState<SourceSlot>(EMPTY_SLOT);
  const [ghostRefs, setGhostRefs] = useState<GhostMannequinRefResponse[]>([]);
  const [isLoadingGhostRefs, setIsLoadingGhostRefs] = useState(false);
  const [ghostRefsError, setGhostRefsError] = useState("");
  const [selectedTemplate, setSelectedTemplate] = useState("fallback-front");

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

  const productImages = useMemo(() => extractProductImageUrls(selectedProduct), [selectedProduct]);
  const originalPreview = originalSlot.preview || null;
  const displayOriginalPreview = originalPreview || generatedResults[0]?.originalImageUrl || null;
  const ghostTemplateOptions = useMemo<GhostTemplateOption[]>(() => {
    const poseOrder: Record<string, number> = { front: 0, side: 1, back: 2 };
    const visiblePoses = new Set(["front", "side", "back"]);
    const libraryTemplates = [...ghostRefs]
      .filter((ref) => visiblePoses.has(ref.pose))
      .sort((a, b) => (poseOrder[a.pose] ?? 99) - (poseOrder[b.pose] ?? 99))
      .map((ref) => ({
        id: ref.id,
        pose: ref.pose,
        label: ref.pose ? ref.pose.charAt(0).toUpperCase() + ref.pose.slice(1) : "Template",
        image: ref.image_url,
        referenceId: ref.id
      }));

    return libraryTemplates.length > 0 ? libraryTemplates : [...ghostTemplates];
  }, [ghostRefs]);

  const selectedTemplateOption = useMemo(
    () => ghostTemplateOptions.find((template) => template.id === selectedTemplate) || ghostTemplateOptions[0],
    [ghostTemplateOptions, selectedTemplate]
  );

  useEffect(() => {
    if (!storeId.trim()) {
      return;
    }

    const controller = new AbortController();
    setIsLoadingGhostRefs(true);
    setGhostRefsError("");

    listGhostMannequinRefs({
      storeId: storeId.trim(),
      clothingType,
      signal: controller.signal
    })
      .then((refs) => {
        setGhostRefs(refs);
        setSelectedTemplate((current) => {
          const visibleRefs = refs.filter((ref) => ["front", "side", "back"].includes(ref.pose));
          if (visibleRefs.some((ref) => ref.id === current) || ghostTemplates.some((template) => template.id === current)) {
            return current;
          }
          return visibleRefs[0]?.id ?? "fallback-front";
        });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        const message = error instanceof Error ? error.message : "Could not load ghost mannequin templates.";
        setGhostRefs([]);
        setGhostRefsError(message);
        setSelectedTemplate((current) =>
          ghostTemplates.some((template) => template.id === current) ? current : "fallback-front"
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsLoadingGhostRefs(false);
        }
      });

    return () => controller.abort();
  }, [clothingType, storeId]);

  useEffect(() => {
    if (!storeId.trim()) {
      return;
    }

    const controller = new AbortController();
    listPhotoshootJobs({
      storeId: storeId.trim(),
      jobType: "ghost_mannequin",
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

  const setStoreImageToOriginal = (imageUrl: string) => {
    setOriginalSlot({ url: imageUrl, file: null, preview: imageUrl });
    setStarted(true);
    setStorePickerOpen(false);
  };

  const setUploadedOriginalImage = (file: File) => {
    const preview = URL.createObjectURL(file);
    previewUrlsRef.current.push(preview);
    setOriginalSlot({ url: null, file, preview });
  };

  const onFileInputChange = async (event: ChangeEvent<HTMLInputElement>) => {
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
    setUploadedOriginalImage(file);
    event.currentTarget.value = "";
  };

  const onLandingUpload = (file: File) => {
    const validationError = validateImageFile(file);
    if (validationError) {
      setErrorMessage(validationError);
      return;
    }

    setErrorMessage("");
    setUploadedOriginalImage(file);
    setStarted(true);
  };

  const openStorePicker = () => {
    setStorePickerOpen(true);
    setErrorMessage("");
  };

  const onStorePickerUpload = async (event: ChangeEvent<HTMLInputElement>) => {
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
    setUploadedOriginalImage(file);
    setStarted(true);
    setStorePickerOpen(false);
    event.currentTarget.value = "";
  };

  const generateResults = async () => {
    if (!storeId.trim()) {
      setErrorMessage("Open the app from Shopify Admin to connect this tool with the active store.");
      return;
    }
    if (!originalSlot.url && !originalSlot.file) {
      setErrorMessage("Upload an original image or select one from your store before generating.");
      return;
    }

    setIsGenerating(true);
    setStatusMessage(getPhotoshootStartingMessage());
    setErrorMessage("");

    try {
      const submittedGid = selectedProductGid.trim() || null;
      const startedJob = await startGhostMannequinJob({
        storeId: storeId.trim(),
        clothingType,
        referenceId: selectedTemplateOption?.referenceId ?? null,
        shopifyProductGid: submittedGid,
        image1Url: originalSlot.url,
        image1File: originalSlot.file,
        // Keep the merchant UI as a single-image flow, but send the same image
        // into the legacy second slot so older backend deployments that still
        // require image2 do not reject the request.
        image2Url: originalSlot.url,
        image2File: originalSlot.file
      });

      setStatusMessage("Your image is now being generated. We’ll show the result here as soon as it’s ready.");

      const finishedJob = await pollPhotoshootJob(storeId.trim(), startedJob.job_id, {
        onUpdate: (job) => {
          setStatusMessage(getPhotoshootProgressMessage(job.progress));
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
          originalImageUrl: originalSlot.preview
        },
        ...current
      ]);
      setStatusMessage("Generation complete.");
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Failed to generate ghost mannequin image.";
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
              onFileSelected={onLandingUpload}
              onSelectStore={openStorePicker}
            />
          </div>
        ) : (
          <section className="ai-simple-workspace ai-ghost-workspace">
            <aside className="ai-simple-setup-card">
              <h3>Ghost Mannequin</h3>
              <p className="ai-ghost-field-title">Original Image</p>

              <div className="ai-ghost-original-preview">
                {displayOriginalPreview ? <span style={tileStyle(displayOriginalPreview)} /> : <ImagePlus size={30} />}
              </div>

              <div className="ai-simple-actions ai-ghost-image-actions">
                <label className="ai-outline-btn">
                  <input type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => void onFileInputChange(event)} />
                  Upload
                </label>
                <button type="button" className="ai-outline-btn" onClick={openStorePicker}>
                  Store
                </button>
              </div>

              <label className="ai-simple-field">
                <span>Clothing Type</span>
                <select
                  aria-label="Clothing Type"
                  value={clothingType}
                  onChange={(event) => setClothingType(event.target.value)}
                >
                  <option value="tops">Top</option>
                  <option value="bottoms">Bottom</option>
                  <option value="dresses">Dress</option>
                  <option value="outerwear">Outerwear</option>
                </select>
              </label>

              <section className="ai-ghost-template-section" aria-label="Style Templates">
                <div className="ai-ghost-template-head">
                  <h4>Style Templates</h4>
                  {isLoadingGhostRefs ? <span>Loading</span> : null}
                </div>
                <div className="ai-ghost-template-grid">
                  {ghostTemplateOptions.map((template) => (
                    <button
                      key={template.id}
                      type="button"
                      className={`ai-ghost-template-tile${selectedTemplate === template.id ? " is-selected" : ""}`}
                      onClick={() => setSelectedTemplate(template.id)}
                    >
                      <span style={tileStyle(template.image)} />
                      <strong>{template.label}</strong>
                    </button>
                  ))}
                </div>
                {ghostRefsError ? (
                  <p className="ai-inline-note ai-ghost-template-note">
                    Showing local template examples. Backend templates could not be loaded.
                  </p>
                ) : null}
              </section>

              <button type="button" className="ai-primary-btn ai-generate-btn" onClick={generateResults} disabled={isGenerating}>
                {isGenerating ? "Generating..." : "Generate"}
              </button>
              {statusMessage ? <p className="ai-status-note">{statusMessage}</p> : null}
              {errorMessage ? <p className="ai-error-note">{errorMessage}</p> : null}
            </aside>

            <div className="ai-ghost-results-grid" aria-label="Ghost mannequin results">
              <article className="ai-ghost-result-card is-original">
                <p className="ai-ghost-result-title">
                  <strong>Original</strong>
                  <span> - Image</span>
                </p>
                <div className="ai-ghost-result-frame" aria-hidden>
                  {displayOriginalPreview ? <span className="ai-result-photo" style={tileStyle(displayOriginalPreview)} /> : null}
                </div>
              </article>

              {generatedResults.length > 0 ? (
                generatedResults.map((result, index) => (
                  <article key={result.id} className="ai-ghost-result-card is-enhanced">
                    <p className="ai-ghost-result-title">
                      <strong>Enhanced</strong>
                      <span>{index === 0 ? " - OptimoVTS" : ` - OptimoVTS (${index})`}</span>
                    </p>
                    <div className="ai-ghost-result-frame" aria-hidden>
                      <div className="ai-result-actions">
                        <a href={result.imageUrl} download="ghost-mannequin-result.jpg">
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
                        className="ai-ghost-store-hover-btn"
                        onClick={() => approveToShopify(result)}
                        disabled={isApproving || (result.needsProductAtApprove && !selectedProductGid)}
                      >
                        {approvingResultId === result.id ? "Uploading..." : "Upload on your store"}
                      </button>
                    </div>
                  </article>
                ))
              ) : (
                <article className="ai-ghost-result-card is-enhanced is-empty">
                  <p className="ai-ghost-result-title">
                    <strong>Enhanced</strong>
                    <span> - OptimoVTS</span>
                  </p>
                  <div className="ai-ghost-result-frame" aria-hidden />
                </article>
              )}
            </div>
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
                  <input type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => void onStorePickerUpload(event)} />
                  <Upload size={18} />
                  <strong>Upload</strong>
                  <span>Original image</span>
                </label>
                {productImages.map((imageUrl) => (
                  <button
                    key={imageUrl}
                    type="button"
                    className="ai-picker-tile"
                    onClick={() => setStoreImageToOriginal(imageUrl)}
                    aria-label="Use as original image"
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
      </section>
    </main>
  );
}
