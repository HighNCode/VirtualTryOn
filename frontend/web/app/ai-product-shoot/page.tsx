"use client";

import { useState } from "react";
import { Sparkles, Download, RefreshCw } from "lucide-react";
import { motion } from "framer-motion";
import AiUploadLanding from "../_components/AiUploadLanding";
import PortalSidebar from "../_components/PortalSidebar";
import PortalTopbar from "../_components/PortalTopbar";
import SubTabNav from "../_components/SubTabNav";

const styleTemplates = [
  { id: "white-sweater", label: "White Sweater", tone: "template-tone-light" },
  { id: "black-jacket", label: "Black Jacket", tone: "template-tone-dark" },
  { id: "dark-bomber", label: "Dark Bomber", tone: "template-tone-charcoal" },
  { id: "jeans", label: "Blue Jeans", tone: "template-tone-jeans" },
  { id: "yellow-dress", label: "Yellow Dress", tone: "template-tone-gold" },
  { id: "green-jacket", label: "Green Jacket", tone: "template-tone-olive" },
];

const resultCards = [
  { id: "original", title: "Original Upload", enhanced: false, variant: "original" },
  { id: "enhanced-1", title: "Enhanced - OptimoVTS", enhanced: true, variant: "enhanced-a" },
  { id: "enhanced-2", title: "Enhanced - OptimoVTS (1)", enhanced: true, variant: "enhanced-b" },
] as const;

const aiTabs = [
  { href: "/ai-product-shoot", label: "Ghost Mannequin" },
  { href: "/ai-product-shoot/model-try-on", label: "Model Try-on" },
  { href: "/ai-product-shoot/model-swap", label: "Model Swap" },
];

export default function AiProductShootPage() {
  const [generated, setGenerated] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState(styleTemplates[0].id);

  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden", background: "#f6f4f4" }}>
      <PortalSidebar activeMain="ai" activeAi="ghost" />

      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "auto" }}>
        <PortalTopbar title="AI Product Shoot" subtitle="Remove mannequin and enhance your product images" />
        <SubTabNav tabs={aiTabs} />

        <div style={{ flex: 1, overflow: "auto", padding: 24 }}>
          {!generated ? (
            <AiUploadLanding
              headline={
                <>
                  AI{" "}
                  <span style={{ background: "linear-gradient(135deg, #7E0175 0%, #BC174A 55%, #E40206 100%)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent", backgroundClip: "text" }}>
                    Ghost Mannequin
                  </span>{" "}
                  Generator for Product Photography
                </>
              }
              subtitle="Professional results in seconds, without studios or mannequins."
              videoSrc="/Ghost Mannequin.mp4"
              onUpload={() => setGenerated(true)}
            />
          ) : (
            /* Working state */
            <div className="flex gap-0 h-full" style={{ margin: -24 }}>
              {/* Left control panel */}
              <div
                className="w-[260px] flex-shrink-0 flex flex-col gap-4 p-5 overflow-auto"
                style={{ borderRight: "1px solid #f0f0f0", background: "#ffffff" }}
              >
                <div>
                  <h3 className="text-[15px] font-bold mb-0.5" style={{ color: "#1a1a1a" }}>Ghost Mannequin</h3>
                  <p className="text-xs" style={{ color: "#9ca3af" }}>Original Image</p>
                </div>

                <div>
                  <h4 className="text-[12px] font-semibold mb-1.5" style={{ color: "#6b7280" }}>Clothing Type</h4>
                  <select
                    aria-label="Clothing Type"
                    className="w-full text-sm px-3 py-2 rounded-[10px]"
                    style={{ border: "1.5px solid #e5e5e5", color: "#1a1a1a", fontFamily: "inherit", outline: "none" }}
                  >
                    <option>Select</option>
                    <option>Tops</option>
                    <option>Bottoms</option>
                    <option>Outerwear</option>
                  </select>
                </div>

                <div>
                  <h4 className="text-[12px] font-semibold mb-2" style={{ color: "#6b7280" }}>Style Templates</h4>
                  <div className="grid grid-cols-3 gap-2">
                    {styleTemplates.map((template) => {
                      const isSelected = selectedTemplate === template.id;
                      return (
                        <button
                          key={template.id}
                          type="button"
                          onClick={() => setSelectedTemplate(template.id)}
                          aria-label={template.label}
                          className="aspect-square rounded-[8px] relative overflow-hidden"
                          style={{
                            border: isSelected ? "2px solid transparent" : "1.5px solid #e5e5e5",
                            background: isSelected
                              ? "linear-gradient(135deg, #7E0175, #E40206)"
                              : "#f3f4f6",
                            cursor: "pointer",
                            padding: 0,
                          }}
                        >
                          {isSelected && (
                            <div
                              className="absolute inset-0.5 rounded-[6px]"
                              style={{ background: "#e5e5e5" }}
                            />
                          )}
                          <span className={`ai-template-item ${template.tone}`} style={{ display: "block", width: "100%", height: "100%", position: "relative" }} />
                        </button>
                      );
                    })}
                  </div>
                </div>

                <motion.button
                  type="button"
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  className="w-full py-2.5 rounded-[10px] text-sm font-semibold text-white mt-auto"
                  style={{ background: "linear-gradient(135deg, #7E0175 0%, #BC174A 55%, #E40206 100%)", border: "none", cursor: "pointer" }}
                >
                  <Sparkles size={14} style={{ display: "inline", marginRight: 6 }} />
                  Generate
                </motion.button>
              </div>

              {/* Results grid */}
              <div className="flex-1 p-5 overflow-auto" style={{ background: "#f6f4f4" }}>
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
                        <span className="ai-model-figure">
                          <span className="ai-model-head" />
                          <span className="ai-model-torso" />
                          <span className="ai-model-leg-left" />
                          <span className="ai-model-leg-right" />
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
