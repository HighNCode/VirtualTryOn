"use client";

import { useEffect, useMemo, useState, type CSSProperties } from "react";
import { ChevronLeft, ChevronRight, Download, RefreshCw, Sparkles } from "lucide-react";
import { motion } from "framer-motion";
import AiUploadLanding from "../../_components/AiUploadLanding";
import PortalSidebar from "../../_components/PortalSidebar";
import PortalTopbar from "../../_components/PortalTopbar";
import SubTabNav from "../../_components/SubTabNav";
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
  type PhotoshootModelResponse,
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
    backgroundPosition: "center",
  };
}

const aiTabs = [
  { href: "/ai-product-shoot", label: "Ghost Mannequin" },
  { href: "/ai-product-shoot/model-try-on", label: "Model Try-on" },
  { href: "/ai-product-shoot/model-swap", label: "Model Swap" },
];

export default function ModelTryOnPage() {
  const [uploaded, setUploaded] = useState(false);
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
    { id: "enhanced-2", title: "Generated Variant", enhanced: true, variant: "enhanced-b", imageUrl: resultImageUrl },
  ];

  useEffect(() => {
    if (!pickerOpen || !storeId.trim()) return;

    const controller = new AbortController();
    let active = true;
    setLoadingModels(true);

    listPhotoshootModels({
      storeId: storeId.trim(),
      gender: modelGender,
      age: modelAge || null,
      bodyType: modelBodyType || null,
      signal: controller.signal,
    })
      .then((data) => {
        if (!active) return;
        setModels(data);
        setSelectedModelId((current) => {
          if (data.length === 0) return null;
          if (current && data.some((item) => item.id === current)) return current;
          return data[0].id;
        });
      })
      .catch((error: unknown) => {
        if (!active || controller.signal.aborted) return;
        const message = error instanceof Error ? error.message : "Failed to load model library.";
        setErrorMessage(message);
        setModels([]);
      })
      .finally(() => {
        if (active) setLoadingModels(false);
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [pickerOpen, storeId, modelGender, modelAge, modelBodyType]);

  const openPicker = () => { setGenerated(false); setErrorMessage(""); setPickerOpen(true); };
  const closePicker = () => setPickerOpen(false);
  const selectModel = (modelId: string) => { setSelectedModelId(modelId); setGenerated(false); setPickerOpen(false); };

  const generateResults = async () => {
    if (!storeId.trim()) { setErrorMessage("Open the app from Shopify Admin to connect this tool with the active store."); return; }
    if (!productGid.trim()) { setErrorMessage("Enter Shopify Product GID."); return; }
    if (!productImageUrl.trim()) { setErrorMessage("Enter product image URL."); return; }
    if (!selectedModelId) { setPickerOpen(true); setErrorMessage("Select a model before generating."); return; }

    setIsGenerating(true); setGenerated(false); setErrorMessage(""); setResultImageUrl(null);
    setStatusMessage("Starting try-on job...");

    try {
      const startedJob = await startTryOnModelJob({
        storeId: storeId.trim(),
        shopifyProductGid: productGid.trim(),
        productImageUrl: productImageUrl.trim(),
        modelLibraryId: selectedModelId,
      });
      setStatusMessage(`Job ${startedJob.job_id} started. Processing...`);

      const finishedJob = await pollPhotoshootJob(storeId.trim(), startedJob.job_id, {
        onUpdate: (job) => {
          const progressText = typeof job.progress === "number" ? ` (${job.progress}%)` : "";
          setStatusMessage(`${job.status}${progressText}${job.message ? ` - ${job.message}` : ""}`);
        },
      });

      if (isFailureStatus(finishedJob.status)) throw new Error(finishedJob.error || finishedJob.message || "Generation failed.");

      const imageUrl = finishedJob.result_image_url
        ? resolveBackendUrl(finishedJob.result_image_url)
        : buildJobResultUrl(startedJob.job_id);

      setResultImageUrl(imageUrl); setGenerated(true); setPickerOpen(false); setStatusMessage("Generation complete.");
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Failed to generate try-on image.";
      setErrorMessage(message); setStatusMessage("");
    } finally {
      setIsGenerating(false);
    }
  };

  const inputStyle: CSSProperties = {
    border: "1.5px solid #e5e5e5",
    borderRadius: 10,
    padding: "8px 12px",
    fontSize: 13,
    color: "#1a1a1a",
    fontFamily: "inherit",
    outline: "none",
    width: "100%",
    boxSizing: "border-box",
  };

  const selectStyle: CSSProperties = { ...inputStyle, cursor: "pointer" };

  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden", background: "#f6f4f4" }}>
      <PortalSidebar activeMain="ai" activeAi="model-try-on" />

      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "auto" }}>
        <PortalTopbar title="AI Product Shoot" subtitle="Place your product on a real model" />
        <SubTabNav tabs={aiTabs} />

        {!uploaded ? (
          <div style={{ flex: 1, overflow: "auto", padding: 24 }}>
            <AiUploadLanding
              headline={
                <>
                  Turn Garments Into Best-Selling{" "}
                  <span style={{ background: "linear-gradient(135deg, #7E0175 0%, #BC174A 55%, #E40206 100%)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent", backgroundClip: "text" }}>
                    Virtual Try-On Images
                  </span>
                </>
              }
              subtitle="AI On-Model Photos Generator, accurate, realistic, and built to convert."
              videoSrc="/Try-on.mp4"
              onUpload={() => setUploaded(true)}
            />
          </div>
        ) : (
        <div className="flex gap-0 flex-1 overflow-hidden">
          {/* Left control panel */}
          <div
            className="w-[260px] flex-shrink-0 flex flex-col gap-4 p-5 overflow-auto"
            style={{ borderRight: "1px solid #f0f0f0", background: "#ffffff" }}
          >
            <div>
              <h3 className="text-[15px] font-bold mb-0.5" style={{ color: "#1a1a1a" }}>Try On</h3>
              <p className="text-xs" style={{ color: "#9ca3af" }}>Product Image</p>
            </div>

            <div>
              <h4 className="text-[12px] font-semibold mb-1" style={{ color: "#6b7280" }}>Store context</h4>
              <p className="text-xs px-3 py-2 rounded-[8px]" style={{ background: storeId ? "#dcfce7" : "#fff1f1", color: storeId ? "#15803d" : "#dc2626" }}>
                {storeId ? "Connected to the current Shopify store." : "Open the app from Shopify Admin to load store context."}
              </p>
            </div>

            <div>
              <h4 className="text-[12px] font-semibold mb-1" style={{ color: "#6b7280" }}>Shopify Product GID</h4>
              <input
                aria-label="Shopify Product GID"
                value={productGid}
                onChange={(e) => setProductGid(e.target.value)}
                placeholder="gid://shopify/Product/1234567890"
                autoComplete="off"
                style={inputStyle}
              />
            </div>

            <div>
              <h4 className="text-[12px] font-semibold mb-1" style={{ color: "#6b7280" }}>Product image URL</h4>
              <input
                aria-label="Product image URL"
                value={productImageUrl}
                onChange={(e) => setProductImageUrl(e.target.value)}
                placeholder="https://cdn.shopify.com/..."
                autoComplete="off"
                style={inputStyle}
              />
            </div>

            <div>
              <h4 className="text-[12px] font-semibold mb-1" style={{ color: "#6b7280" }}>Try on area</h4>
              <select
                aria-label="Try on area"
                value={tryOnArea}
                onChange={(e) => setTryOnArea(e.target.value)}
                style={selectStyle}
              >
                <option>Auto</option>
                <option>Upper Body</option>
                <option>Full Body</option>
              </select>
            </div>

            <div>
              <h4 className="text-[12px] font-semibold mb-1" style={{ color: "#6b7280" }}>Try on model</h4>
              <button
                type="button"
                onClick={openPicker}
                className="w-full flex items-center gap-3 px-3 py-2.5 rounded-[10px] text-left"
                style={{ border: "1.5px solid #e5e5e5", background: "#fafafa", cursor: "pointer" }}
              >
                {selectedModel ? (
                  <span
                    className="w-8 h-8 rounded-[6px] flex-shrink-0"
                    style={{ ...modelTileStyle(selectedModel.image_url), display: "block" }}
                  />
                ) : (
                  <span
                    className="w-8 h-8 rounded-[6px] flex-shrink-0 flex items-center justify-center"
                    style={{ background: "rgba(126,1,117,0.08)" }}
                  >
                    <svg viewBox="0 0 24 24" width="16" height="16" role="img">
                      <rect x="3" y="4" width="18" height="16" rx="2" fill="none" stroke="#7E0175" strokeWidth="1.8" />
                      <circle cx="8.2" cy="9" r="1.6" fill="none" stroke="#7E0175" strokeWidth="1.8" />
                      <path d="M5.5 17L10.4 12.2L13.3 14.9L16.2 12L18.5 14.4V17" fill="none" stroke="#7E0175" strokeWidth="1.8" />
                    </svg>
                  </span>
                )}
                <span className="flex-1">
                  <strong className="block text-[12px]" style={{ color: "#1a1a1a" }}>{selectedModel ? "Selected model" : "Select try on model"}</strong>
                  <span className="text-[11px]" style={{ color: "#9ca3af" }}>{selectedModel ? "Click to edit" : "Choose model, pose, background"}</span>
                </span>
                <ChevronRight size={14} style={{ color: "#9ca3af" }} />
              </button>
            </div>

            <motion.button
              type="button"
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={generateResults}
              disabled={isGenerating}
              className="w-full py-2.5 rounded-[10px] text-sm font-semibold text-white flex items-center justify-center gap-2"
              style={{
                background: "linear-gradient(135deg, #7E0175 0%, #BC174A 55%, #E40206 100%)",
                border: "none",
                cursor: isGenerating ? "not-allowed" : "pointer",
                opacity: isGenerating ? 0.7 : 1,
              }}
            >
              <Sparkles size={14} />
              {isGenerating ? "Generating..." : "Generate"}
            </motion.button>

            {statusMessage && (
              <p className="text-xs px-3 py-2 rounded-[8px]" style={{ background: "rgba(126,1,117,0.05)", color: "#7E0175" }}>
                {statusMessage}
              </p>
            )}
            {errorMessage && (
              <p className="text-xs px-3 py-2 rounded-[8px]" style={{ background: "#fff1f1", color: "#dc2626" }}>
                {errorMessage}
              </p>
            )}
          </div>

          {/* Right panel */}
          <div className="flex-1 overflow-auto" style={{ background: "#f6f4f4" }}>
            {pickerOpen ? (
              /* Model picker */
              <div className="h-full flex flex-col bg-white">
                <div className="flex items-center gap-3 px-5 py-4" style={{ borderBottom: "1px solid #f0f0f0" }}>
                  <button
                    type="button"
                    onClick={closePicker}
                    className="w-8 h-8 rounded-full flex items-center justify-center"
                    style={{ background: "#f3f4f6", border: "none", cursor: "pointer" }}
                  >
                    <ChevronLeft size={16} style={{ color: "#6b7280" }} />
                  </button>
                  <div>
                    <h3 className="text-[14px] font-bold" style={{ color: "#1a1a1a" }}>Select Try on model</h3>
                    <p className="text-xs" style={{ color: "#9ca3af" }}>Optimo model library</p>
                  </div>
                </div>

                <div className="flex gap-2 px-5 py-3" style={{ borderBottom: "1px solid #f0f0f0" }}>
                  {[
                    { label: "Gender", value: modelGender, onChange: setModelGender, options: [{ value: "unisex", label: "All" }, { value: "female", label: "Women" }, { value: "male", label: "Men" }] },
                    { label: "Age", value: modelAge, onChange: setModelAge, options: [{ value: "", label: "Age" }, { value: "18-25", label: "18-25" }, { value: "26-35", label: "26-35" }, { value: "36-45", label: "36-45" }, { value: "45+", label: "45+" }] },
                    { label: "Body Type", value: modelBodyType, onChange: setModelBodyType, options: [{ value: "", label: "Body Type" }, { value: "slim", label: "Slim" }, { value: "athletic", label: "Athletic" }, { value: "regular", label: "Regular" }, { value: "plus", label: "Plus" }] },
                    { label: "Try on area", value: tryOnArea, onChange: setTryOnArea, options: [{ value: "Auto", label: "Auto" }, { value: "Upper Body", label: "Upper Body" }, { value: "Full Body", label: "Full Body" }] },
                  ].map((filter) => (
                    <select
                      key={filter.label}
                      aria-label={filter.label}
                      value={filter.value}
                      onChange={(e) => filter.onChange(e.target.value)}
                      className="text-xs px-2 py-1.5 rounded-[8px]"
                      style={{ border: "1.5px solid #e5e5e5", color: "#1a1a1a", fontFamily: "inherit", outline: "none" }}
                    >
                      {filter.options.map((opt) => (
                        <option key={opt.value} value={opt.value}>{opt.label}</option>
                      ))}
                    </select>
                  ))}
                </div>

                <div className="flex-1 overflow-auto p-5">
                  {loadingModels && <p className="text-sm" style={{ color: "#9ca3af" }}>Loading models...</p>}
                  {!loadingModels && models.length === 0 && (
                    <p className="text-sm" style={{ color: "#9ca3af" }}>No models returned for current filters.</p>
                  )}
                  <div className="grid grid-cols-4 gap-3">
                    {models.map((model) => (
                      <button
                        key={model.id}
                        type="button"
                        onClick={() => selectModel(model.id)}
                        aria-label={model.id}
                        className="aspect-square rounded-[10px] overflow-hidden relative"
                        style={{
                          border: selectedModelId === model.id
                            ? "2.5px solid #7E0175"
                            : "1.5px solid #e5e5e5",
                          cursor: "pointer",
                          padding: 0,
                        }}
                      >
                        <span
                          style={{
                            display: "block",
                            width: "100%",
                            height: "100%",
                            ...modelTileStyle(model.image_url),
                          }}
                        />
                        {selectedModelId === model.id && (
                          <span
                            className="absolute top-1.5 right-1.5 w-5 h-5 rounded-full flex items-center justify-center text-white text-[10px]"
                            style={{ background: "linear-gradient(135deg, #7E0175, #E40206)" }}
                          >
                            ✓
                          </span>
                        )}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            ) : generated ? (
              /* Results */
              <div className="p-5 grid grid-cols-3 gap-4">
                {resultCards.map((card) => (
                  <div
                    key={card.id}
                    className="bg-white rounded-[14px] overflow-hidden"
                    style={{ boxShadow: "0 1px 3px rgba(0,0,0,0.04)", border: "1px solid rgba(0,0,0,0.05)" }}
                  >
                    <div className="flex items-center justify-between px-4 py-3" style={{ borderBottom: "1px solid #f3f4f6" }}>
                      <p className="text-[13px] font-medium" style={{ color: "#1a1a1a" }}>{card.title}</p>
                      {card.enhanced && (
                        <div className="flex gap-1">
                          <button type="button" className="w-6 h-6 rounded-[6px] flex items-center justify-center" style={{ background: "rgba(126,1,117,0.08)", border: "none", cursor: "pointer" }}>
                            <Download size={11} style={{ color: "#7E0175" }} />
                          </button>
                          <button type="button" className="w-6 h-6 rounded-[6px] flex items-center justify-center" style={{ background: "rgba(126,1,117,0.08)", border: "none", cursor: "pointer" }}>
                            <RefreshCw size={11} style={{ color: "#7E0175" }} />
                          </button>
                        </div>
                      )}
                    </div>
                    <div className={`ai-result-image ai-result-image-${card.variant}`} aria-hidden style={{ minHeight: 200 }}>
                      {card.imageUrl ? (
                        <span className="ai-result-photo" style={modelTileStyle(card.imageUrl)} />
                      ) : (
                        <span className="ai-model-figure">
                          <span className="ai-model-head" /><span className="ai-model-torso" /><span className="ai-model-leg-left" /><span className="ai-model-leg-right" />
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              /* Placeholder */
              <div className="p-5 grid grid-cols-3 gap-4">
                <div
                  className="bg-white rounded-[14px] overflow-hidden"
                  style={{ boxShadow: "0 1px 3px rgba(0,0,0,0.04)", border: "1px solid rgba(0,0,0,0.05)" }}
                >
                  <div className="px-4 py-3" style={{ borderBottom: "1px solid #f3f4f6" }}>
                    <p className="text-[13px] font-medium" style={{ color: "#1a1a1a" }}>Original</p>
                  </div>
                  <div className="ai-result-image ai-result-image-original" aria-hidden style={{ minHeight: 200 }}>
                    {productImageUrl ? (
                      <span className="ai-result-photo" style={modelTileStyle(productImageUrl)} />
                    ) : (
                      <span className="ai-model-figure">
                        <span className="ai-model-head" /><span className="ai-model-torso" /><span className="ai-model-leg-left" /><span className="ai-model-leg-right" />
                      </span>
                    )}
                  </div>
                </div>
                {[1, 2].map((i) => (
                  <div
                    key={i}
                    className="rounded-[14px]"
                    style={{ border: "1.5px dashed rgba(126,1,117,0.15)", background: "rgba(126,1,117,0.02)", minHeight: 200 }}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
        )}
      </div>
    </div>
  );
}
