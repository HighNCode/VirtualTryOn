"use client";

import { useEffect, useMemo, useState, type CSSProperties } from "react";
import { Check, ChevronLeft, ChevronRight, Download, RefreshCw, Sparkles, Upload } from "lucide-react";
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

const aiTabs = [
  { href: "/ai-product-shoot", label: "Ghost Mannequin" },
  { href: "/ai-product-shoot/model-try-on", label: "Model Try-on" },
  { href: "/ai-product-shoot/model-swap", label: "Model Swap" }
];

const selectStyle = {
  border: "1.5px solid #e5e5e5",
  color: "#1a1a1a",
  fontFamily: "inherit",
  outline: "none",
  background: "#fff",
} as CSSProperties;

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
        if (!active) return;
        setFaceLibrary(data);
        setSelectedFaceId((current) => {
          if (data.length === 0) return null;
          if (current && data.some((item) => item.id === current)) return current;
          return data[0].id;
        });
      })
      .catch((error: unknown) => {
        if (!active || controller.signal.aborted) return;
        const message = error instanceof Error ? error.message : "Failed to load face library.";
        setErrorMessage(message);
        setFaceLibrary([]);
      })
      .finally(() => {
        if (active) setLoadingFaces(false);
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
    <div style={{ display: "flex", height: "100vh", overflow: "hidden", background: "#f6f4f4" }}>
      <PortalSidebar activeMain="ai" activeAi="model-swap" />

      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "auto" }}>
        <PortalTopbar title="AI Product Shoot" subtitle="Swap the model in your existing product images" />
        <SubTabNav tabs={aiTabs} />

        <div style={{ flex: 1, overflow: "auto" }}>
          {!uploaded ? (
            <div style={{ padding: 24 }}>
              <AiUploadLanding
                headline={
                  <>
                    Transform Fashion Photos with Premium{" "}
                    <span style={{ background: "linear-gradient(135deg, #7E0175 0%, #BC174A 55%, #E40206 100%)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent", backgroundClip: "text" }}>
                      AI Model Swap
                    </span>
                  </>
                }
                subtitle="Seamless, diverse, and customized visuals, perfect for any market."
                videoSrc="/Model Swap.mp4"
                onUpload={() => setUploaded(true)}
              />
            </div>
          ) : !uploaded ? (
            /* Upload landing */
            <div className="flex gap-6 p-6 h-full">
              {/* Left copy */}
              <div className="flex-1 flex flex-col justify-center">
                <span
                  className="text-[11px] font-semibold px-2.5 py-1 rounded-full mb-4 inline-block w-fit"
                  style={{ background: "rgba(126,1,117,0.08)", color: "#7E0175" }}
                >
                  ✦ AI-Powered
                </span>
                <h3 className="text-[28px] font-extrabold leading-tight mb-3" style={{ color: "#1a1a1a" }}>
                  Transform Fashion Photos
                  <br />
                  with Premium
                  <br />
                  <span style={{ background: "linear-gradient(135deg, #7E0175 0%, #BC174A 55%, #E40206 100%)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent", backgroundClip: "text" }}>
                    AI Model Swap
                  </span>
                </h3>
                <p className="text-[15px]" style={{ color: "#6b7280" }}>
                  Seamless, diverse, and customized visuals, perfect for any market.
                </p>
              </div>

              {/* Right upload panel */}
              <div
                className="w-[320px] flex-shrink-0 bg-white rounded-[14px] p-5 flex flex-col gap-3"
                style={{ boxShadow: "0 4px 24px rgba(0,0,0,0.08)", border: "1px solid rgba(0,0,0,0.05)" }}
              >
                <div
                  className="text-[11px] font-semibold px-3 py-1.5 rounded-full text-center"
                  style={{ background: "linear-gradient(135deg, #7E0175 0%, #BC174A 55%, #E40206 100%)", color: "#fff" }}
                >
                  ✦ Upgrade Your Visuals Now
                </div>

                {/* Drop zone */}
                <motion.div
                  whileHover={{ y: -2, borderColor: "#7E0175" }}
                  className="flex flex-col items-center justify-center gap-2 rounded-[14px] py-8 cursor-pointer"
                  style={{
                    border: "1.5px dashed rgba(126,1,117,0.25)",
                    background: "rgba(126,1,117,0.02)",
                    transition: "border-color 150ms",
                  }}
                >
                  <div
                    className="w-10 h-10 rounded-[10px] flex items-center justify-center"
                    style={{ background: "rgba(126,1,117,0.08)" }}
                  >
                    <Upload size={18} style={{ color: "#7E0175" }} />
                  </div>
                  <p className="text-sm font-medium" style={{ color: "#6b7280" }}>
                    Click or drag image here
                  </p>
                </motion.div>

                <motion.button
                  type="button"
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={() => setUploaded(true)}
                  className="w-full py-2.5 rounded-[10px] text-sm font-semibold text-white"
                  style={{ background: "linear-gradient(135deg, #7E0175 0%, #BC174A 55%, #E40206 100%)", border: "none", cursor: "pointer" }}
                >
                  Continue to model swap
                </motion.button>

                <p className="text-xs text-center leading-relaxed" style={{ color: "#9ca3af" }}>
                  Use any product image from Shopify CDN,
                  <br />
                  then choose a face from the Optimo library
                </p>
              </div>
            </div>
          ) : (
            /* Working state */
            <div className="flex gap-0 h-full">
              {/* Left control panel */}
              <div
                className="w-[260px] flex-shrink-0 flex flex-col gap-4 p-5 overflow-auto"
                style={{ borderRight: "1px solid #f0f0f0", background: "#ffffff" }}
              >
                <div>
                  <h3 className="text-[15px] font-bold mb-0.5" style={{ color: "#1a1a1a" }}>Model Swap</h3>
                  <p className="text-xs" style={{ color: "#9ca3af" }}>Product Image</p>
                </div>

                {/* Store context */}
                <div>
                  <h4 className="text-[12px] font-semibold mb-1" style={{ color: "#6b7280" }}>Store context</h4>
                  <p className="text-[11px] px-2.5 py-2 rounded-[8px]" style={{
                    background: storeId ? "rgba(21,128,61,0.06)" : "rgba(220,38,38,0.06)",
                    color: storeId ? "#15803d" : "#dc2626",
                  }}>
                    {storeId ? "Connected to the current Shopify store." : "Open the app from Shopify Admin to load store context."}
                  </p>
                </div>

                {/* Product GID */}
                <div>
                  <h4 className="text-[12px] font-semibold mb-1.5" style={{ color: "#6b7280" }}>Shopify Product GID</h4>
                  <input
                    aria-label="Shopify Product GID"
                    value={productGid}
                    onChange={(e) => setProductGid(e.target.value)}
                    placeholder="gid://shopify/Product/..."
                    autoComplete="off"
                    className="w-full text-xs px-3 py-2 rounded-[10px]"
                    style={selectStyle}
                    onFocus={(e) => {
                      e.currentTarget.style.borderColor = "#7E0175";
                      e.currentTarget.style.boxShadow = "0 0 0 3px rgba(126,1,117,0.1)";
                    }}
                    onBlur={(e) => {
                      e.currentTarget.style.borderColor = "#e5e5e5";
                      e.currentTarget.style.boxShadow = "none";
                    }}
                  />
                </div>

                {/* Original image URL */}
                <div>
                  <h4 className="text-[12px] font-semibold mb-1.5" style={{ color: "#6b7280" }}>Original image URL</h4>
                  <input
                    aria-label="Original image URL"
                    value={originalImageUrl}
                    onChange={(e) => setOriginalImageUrl(e.target.value)}
                    placeholder="https://cdn.shopify.com/..."
                    autoComplete="off"
                    className="w-full text-xs px-3 py-2 rounded-[10px]"
                    style={selectStyle}
                    onFocus={(e) => {
                      e.currentTarget.style.borderColor = "#7E0175";
                      e.currentTarget.style.boxShadow = "0 0 0 3px rgba(126,1,117,0.1)";
                    }}
                    onBlur={(e) => {
                      e.currentTarget.style.borderColor = "#e5e5e5";
                      e.currentTarget.style.boxShadow = "none";
                    }}
                  />
                </div>

                {/* Face model trigger */}
                <div>
                  <h4 className="text-[12px] font-semibold mb-1.5" style={{ color: "#6b7280" }}>Face model</h4>
                  <button
                    type="button"
                    onClick={openPicker}
                    className="w-full flex items-center gap-3 px-3 py-2.5 rounded-[10px]"
                    style={{
                      border: "1.5px solid #e5e5e5",
                      background: "#fafafa",
                      cursor: "pointer",
                      textAlign: "left",
                    }}
                  >
                    {selectedFace ? (
                      <span
                        className="w-9 h-9 rounded-[8px] flex-shrink-0"
                        style={imageTileStyle(selectedFace.image_url)}
                        aria-hidden
                      />
                    ) : (
                      <span
                        className="w-9 h-9 rounded-[8px] flex-shrink-0 flex items-center justify-center"
                        style={{ background: "rgba(126,1,117,0.08)" }}
                        aria-hidden
                      >
                        <svg viewBox="0 0 24 24" width={18} height={18} style={{ color: "#7E0175" }}>
                          <rect x="3" y="4" width="18" height="16" rx="2" fill="none" stroke="currentColor" strokeWidth="1.8" />
                          <circle cx="8.2" cy="9" r="1.6" fill="none" stroke="currentColor" strokeWidth="1.8" />
                          <path d="M5.5 17L10.4 12.2L13.3 14.9L16.2 12L18.5 14.4V17" fill="none" stroke="currentColor" strokeWidth="1.8" />
                        </svg>
                      </span>
                    )}
                    <span className="flex-1 min-w-0">
                      <span className="block text-[12px] font-semibold" style={{ color: "#1a1a1a" }}>Select face model</span>
                      <span className="block text-[11px] truncate" style={{ color: "#9ca3af" }}>Choose from the Optimo face library</span>
                    </span>
                    <ChevronRight size={14} style={{ color: "#9ca3af", flexShrink: 0 }} />
                  </button>
                </div>

                {/* Status / error */}
                {statusMessage && (
                  <p className="text-[11px] px-2.5 py-2 rounded-[8px]" style={{ background: "rgba(126,1,117,0.06)", color: "#7E0175" }}>
                    {statusMessage}
                  </p>
                )}
                {errorMessage && (
                  <p className="text-[11px] px-2.5 py-2 rounded-[8px]" style={{ background: "#fff1f1", color: "#dc2626" }}>
                    {errorMessage}
                  </p>
                )}

                {/* Generate button */}
                <motion.button
                  type="button"
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={generateResults}
                  disabled={isGenerating}
                  className="w-full py-2.5 rounded-[10px] text-sm font-semibold text-white mt-auto"
                  style={{
                    background: "linear-gradient(135deg, #7E0175 0%, #BC174A 55%, #E40206 100%)",
                    border: "none",
                    cursor: isGenerating ? "not-allowed" : "pointer",
                    opacity: isGenerating ? 0.7 : 1,
                  }}
                >
                  <Sparkles size={14} style={{ display: "inline", marginRight: 6 }} />
                  {isGenerating ? "Generating..." : "Generate"}
                </motion.button>
              </div>

              {/* Right area */}
              <div className="flex-1 overflow-auto" style={{ background: "#f6f4f4" }}>
                {pickerOpen ? (
                  /* Face picker */
                  <div className="flex flex-col h-full bg-white" style={{ maxWidth: "100%" }}>
                    {/* Picker header */}
                    <div
                      className="flex items-center gap-3 px-5 py-4 flex-shrink-0"
                      style={{ borderBottom: "1px solid #f0f0f0" }}
                    >
                      <button
                        type="button"
                        onClick={closePicker}
                        aria-label="Back"
                        className="w-8 h-8 rounded-[8px] flex items-center justify-center"
                        style={{ background: "#f3f4f6", border: "none", cursor: "pointer" }}
                      >
                        <ChevronLeft size={16} style={{ color: "#6b7280" }} />
                      </button>
                      <div>
                        <h3 className="text-[15px] font-bold" style={{ color: "#1a1a1a" }}>Select face model</h3>
                        <p className="text-xs" style={{ color: "#9ca3af" }}>Optimo face library</p>
                      </div>
                    </div>

                    {/* Filters */}
                    <div className="flex gap-3 px-5 py-3 flex-shrink-0" style={{ borderBottom: "1px solid #f0f0f0" }}>
                      {[
                        {
                          label: "Gender",
                          value: faceGender,
                          onChange: setFaceGender,
                          options: [
                            { value: "female", label: "Women" },
                            { value: "male", label: "Men" },
                          ],
                        },
                        {
                          label: "Age",
                          value: faceAge,
                          onChange: setFaceAge,
                          options: [
                            { value: "", label: "Age" },
                            { value: "18-25", label: "18-25" },
                            { value: "26-35", label: "26-35" },
                            { value: "36-45", label: "36-45" },
                            { value: "45+", label: "45+" },
                          ],
                        },
                        {
                          label: "Skin",
                          value: faceSkinTone,
                          onChange: setFaceSkinTone,
                          options: [
                            { value: "", label: "Skin" },
                            { value: "fair", label: "Fair" },
                            { value: "light", label: "Light" },
                            { value: "medium", label: "Medium" },
                            { value: "tan", label: "Tan" },
                            { value: "dark", label: "Dark" },
                          ],
                        },
                      ].map((filter) => (
                        <select
                          key={filter.label}
                          aria-label={filter.label}
                          value={filter.value}
                          onChange={(e) => filter.onChange(e.target.value)}
                          className="text-sm px-3 py-2 rounded-[10px]"
                          style={selectStyle}
                        >
                          {filter.options.map((opt) => (
                            <option key={opt.value} value={opt.value}>{opt.label}</option>
                          ))}
                        </select>
                      ))}
                    </div>

                    {/* Face grid */}
                    <div className="flex-1 overflow-auto p-5">
                      {loadingFaces && (
                        <p className="text-sm" style={{ color: "#9ca3af" }}>Loading faces...</p>
                      )}
                      {!loadingFaces && faceLibrary.length === 0 && (
                        <p className="text-sm" style={{ color: "#9ca3af" }}>No faces returned for current filters.</p>
                      )}
                      <div className="grid grid-cols-4 gap-3">
                        {faceLibrary.map((face) => {
                          const isSelected = selectedFaceId === face.id;
                          return (
                            <button
                              key={face.id}
                              type="button"
                              onClick={() => selectFace(face.id)}
                              aria-label={face.id}
                              className="relative aspect-square rounded-[10px] overflow-hidden"
                              style={{
                                border: isSelected ? "2px solid transparent" : "1.5px solid #e5e5e5",
                                background: isSelected
                                  ? "linear-gradient(135deg, #7E0175, #E40206)"
                                  : "#f3f4f6",
                                padding: isSelected ? 2 : 0,
                                cursor: "pointer",
                              }}
                            >
                              <span
                                className="block w-full h-full rounded-[8px]"
                                style={imageTileStyle(face.image_url)}
                              />
                              {isSelected && (
                                <span
                                  className="absolute top-1.5 right-1.5 w-5 h-5 rounded-full flex items-center justify-center"
                                  style={{ background: "linear-gradient(135deg, #7E0175, #E40206)" }}
                                  aria-hidden
                                >
                                  <Check size={10} color="white" />
                                </span>
                              )}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                ) : generated ? (
                  /* Results grid */
                  <div className="p-5">
                    <div className="grid grid-cols-3 gap-4">
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
                                <button
                                  type="button"
                                  className="w-6 h-6 rounded-[6px] flex items-center justify-center"
                                  style={{ background: "rgba(126,1,117,0.08)", border: "none", cursor: "pointer" }}
                                >
                                  <Download size={11} style={{ color: "#7E0175" }} />
                                </button>
                                <button
                                  type="button"
                                  className="w-6 h-6 rounded-[6px] flex items-center justify-center"
                                  style={{ background: "rgba(126,1,117,0.08)", border: "none", cursor: "pointer" }}
                                >
                                  <RefreshCw size={11} style={{ color: "#7E0175" }} />
                                </button>
                              </div>
                            )}
                          </div>
                          <div
                            className={`ai-result-image ai-result-image-${card.variant}`}
                            aria-hidden
                            style={{ minHeight: 200 }}
                          >
                            {card.imageUrl ? (
                              <span
                                className="block w-full h-full"
                                style={{ ...imageTileStyle(card.imageUrl), minHeight: 200 }}
                              />
                            ) : (
                              <span className="ai-model-figure">
                                <span className="ai-model-head" />
                                <span className="ai-model-torso" />
                                <span className="ai-model-leg-left" />
                                <span className="ai-model-leg-right" />
                              </span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  /* Placeholder grid */
                  <div className="p-5">
                    <div className="grid grid-cols-3 gap-4">
                      {/* Original card */}
                      <div
                        className="bg-white rounded-[14px] overflow-hidden"
                        style={{ boxShadow: "0 1px 3px rgba(0,0,0,0.04)", border: "1px solid rgba(0,0,0,0.05)" }}
                      >
                        <div className="px-4 py-3" style={{ borderBottom: "1px solid #f3f4f6" }}>
                          <p className="text-[13px] font-medium" style={{ color: "#1a1a1a" }}>Original</p>
                        </div>
                        <div
                          className="ai-result-image ai-result-image-original"
                          aria-hidden
                          style={{ minHeight: 200 }}
                        >
                          {originalImageUrl ? (
                            <span
                              className="block w-full h-full"
                              style={{ ...imageTileStyle(originalImageUrl), minHeight: 200 }}
                            />
                          ) : (
                            <span className="ai-model-figure">
                              <span className="ai-model-head" />
                              <span className="ai-model-torso" />
                              <span className="ai-model-leg-left" />
                              <span className="ai-model-leg-right" />
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Placeholder cards */}
                      {[1, 2].map((i) => (
                        <div
                          key={i}
                          className="bg-white rounded-[14px] overflow-hidden flex flex-col items-center justify-center"
                          style={{
                            boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
                            border: "1.5px dashed rgba(126,1,117,0.2)",
                            minHeight: 260,
                          }}
                          aria-hidden
                        >
                          <div
                            className="w-10 h-10 rounded-[10px] flex items-center justify-center mb-2"
                            style={{ background: "rgba(126,1,117,0.06)" }}
                          >
                            <Sparkles size={18} style={{ color: "#7E0175", opacity: 0.5 }} />
                          </div>
                          <p className="text-xs" style={{ color: "#d1d5db" }}>Awaiting generation</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
