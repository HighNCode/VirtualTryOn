"use client";

import { useState } from "react";
import { ArrowLeft, Plus, RotateCcw, HelpCircle } from "./icons";

type Props = { onNext: () => void; onBack: () => void };

const sizes = [
  { label: "XS", pct: 45 },
  { label: "X", pct: 65 },
  { label: "M", pct: 89 },
  { label: "L", pct: 78 },
  { label: "XL", pct: 62 }
];

const socials = [
  { name: "Facebook", src: "/image 78.png" },
  { name: "Snapchat", src: "/image 79.png" },
  { name: "TikTok", src: "/image 80.png" },
  { name: "Instagram", src: "/instagram-vector-logo-icon-social-media-logotype_901408-392 2.png" }
];

export function Step7TryOn({ onNext, onBack }: Props) {
  const [selectedSize, setSelectedSize] = useState("M");
  const confidence = 89;

  return (
    <div className="flex flex-col px-5 py-5 gap-6">
      <button type="button" onClick={onBack} className="flex items-center gap-1.5 text-sm text-[#6b7280] hover:text-[#1a1a1a] self-start">
        <ArrowLeft size={14} /> Back to measurements
      </button>

      <div>
        <div className="flex items-center gap-2 mb-3">
          <span className="text-base font-bold text-[#1a1a1a]">Virtual Try-On</span>
          <span className="text-[10px] border border-[#e5e5e5] rounded-full px-2.5 py-0.5 text-[#6b7280]">Powered By Optimo 4o</span>
        </div>

        <div className="grid gap-4 step-seven-split">
          <div className="rounded-[16px] bg-[#ede8e3] overflow-hidden border border-[#e5e5e5]" style={{ aspectRatio: "3/4" }}>
            <img
              src="/widget/tryon-result.jpg"
              alt="Try-On"
              className="w-full h-full object-cover"
              onError={(event) => {
                event.currentTarget.style.display = "none";
              }}
            />
          </div>

          <div className="flex flex-col gap-3">
            <div className="border border-[#e5e5e5] rounded-[14px] overflow-hidden">
              <div className="bg-[#fdf6f4] px-3 py-2.5 text-center text-sm font-bold text-[#1a1a1a] border-b border-[#f0e8e4]">Studio Shoots</div>
              <div className="p-2.5 grid grid-cols-3 gap-2">
                {[1, 2, 3, 4, 5].map((index) => (
                  <div key={index} className="aspect-square rounded-[8px] bg-[#e8e4e0] overflow-hidden">
                    <img
                      src={`/widget/studio-${index}.jpg`}
                      alt=""
                      className="w-full h-full object-cover"
                      onError={(event) => {
                        event.currentTarget.style.display = "none";
                      }}
                    />
                  </div>
                ))}
                <button type="button" className="aspect-square rounded-[8px] bg-[#fdf0f0] border border-[#fbd5d5] flex items-center justify-center">
                  <Plus size={18} color="#E40206" />
                </button>
              </div>
            </div>

            <div className="flex gap-2">
              <button type="button" className="flex-1 py-2.5 rounded-[10px] text-sm font-bold text-white" style={{ background: "linear-gradient(135deg, #7E0175, #E40206)" }}>
                Submit
              </button>
              <button type="button" className="flex-1 py-2.5 rounded-[10px] text-sm font-bold border-2 border-[#e5e5e5] text-[#1a1a1a] flex items-center justify-center gap-1.5">
                <RotateCcw size={13} /> Retry
              </button>
            </div>

            <div className="border border-[#e5e5e5] rounded-[12px] px-3 py-3 flex flex-col items-center gap-2.5">
              <span className="text-xs text-[#6b7280]">Share your look</span>
              <div className="flex gap-4 items-center justify-center">
                {socials.map((social) => (
                  <button
                    key={social.name}
                    title={social.name}
                    type="button"
                    className="w-10 h-10 hover:scale-110 transition-transform flex-shrink-0"
                    onContextMenu={(event) => event.preventDefault()}
                  >
                    <img src={social.src} alt={social.name} className="w-full h-full object-contain" draggable={false} />
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="grid gap-5 step-seven-split">
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <span className="text-base font-bold text-[#1a1a1a]">Heat Map</span>
            <span className="text-[10px] border border-[#e5e5e5] rounded-full px-2.5 py-0.5 text-[#6b7280]">Powered By Optimo 4o</span>
          </div>
          <div className="rounded-[14px] bg-[#f0f0f0] overflow-hidden border border-[#e5e5e5] relative" style={{ aspectRatio: "3/4" }}>
            <img
              src="/widget/heatmap.jpg"
              alt="Heat Map"
              className="w-full h-full object-cover"
              onError={(event) => {
                event.currentTarget.style.display = "none";
              }}
            />
          </div>
          <p className="text-xs text-[#9ca3af] text-center">Interactive heat map showing fit on your body</p>
          <div className="flex items-center justify-center gap-4">
            {[
              { label: "Loose", color: "#4ade80" },
              { label: "Snug", color: "#facc15" },
              { label: "Tight", color: "#f87171" }
            ].map((legend) => (
              <div key={legend.label} className="flex items-center gap-1.5">
                <div className="w-2.5 h-2.5 rounded-full" style={{ background: legend.color }} />
                <span className="text-xs text-[#6b7280]">{legend.label}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="flex flex-col gap-3">
          <p className="text-base font-bold text-[#1a1a1a]">Select Your Size</p>

          <div className="flex gap-2 flex-wrap">
            {sizes.map((sizeOption) => {
              const isSelected = selectedSize === sizeOption.label;
              return (
                <button
                  key={sizeOption.label}
                  onClick={() => setSelectedSize(sizeOption.label)}
                  className="flex flex-col items-center justify-center rounded-[10px] border-2 transition-all font-bold"
                  style={{
                    width: 52,
                    height: 52,
                    borderColor: isSelected ? "transparent" : "#e5e5e5",
                    background: isSelected ? "linear-gradient(135deg, #7E0175, #E40206)" : "#fff",
                    color: isSelected ? "#fff" : "#1a1a1a"
                  }}
                >
                  <span className="text-sm leading-none">{sizeOption.label}</span>
                  <span className="text-[11px] leading-none mt-0.5" style={{ color: isSelected ? "rgba(255,255,255,0.85)" : "#E40206" }}>
                    {sizeOption.pct}%
                  </span>
                </button>
              );
            })}
          </div>

          <div>
            <div className="flex justify-between text-sm mb-1.5">
              <span className="font-semibold text-[#1a1a1a]">Fit Confidence</span>
              <span className="font-bold text-[#1a1a1a]">{confidence}%</span>
            </div>
            <div className="w-full h-2.5 bg-[#f0f0f0] rounded-full overflow-hidden">
              <div className="h-full rounded-full" style={{ width: `${confidence}%`, background: "linear-gradient(90deg, #7E0175, #E40206)" }} />
            </div>
          </div>

          <div className="bg-[#f5f5f5] rounded-[12px] px-3 py-2.5">
            <p className="text-xs font-bold text-[#1a1a1a]">Recommendation Size</p>
            <p className="text-[11px] text-[#6b7280] mt-0.5">This size provides the best overall fit for your measurements</p>
          </div>

          <div className="flex flex-col gap-2 text-sm">
            <div className="flex justify-between">
              <span className="text-[#6b7280]">Product</span>
              <span className="font-semibold text-[#1a1a1a]">Essential Slim Fit Jeans</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[#6b7280]">Selected Size</span>
              <span className="font-semibold text-[#1a1a1a]">M</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[#6b7280]">Price</span>
              <span className="font-semibold text-[#1a1a1a]">$89.99</span>
            </div>
          </div>

          <button
            type="button"
            onClick={onNext}
            className="w-full py-3.5 rounded-[12px] text-white text-sm font-bold"
            style={{ background: "linear-gradient(135deg, #7E0175 0%, #BC174A 55%, #E40206 100%)" }}
          >
            Add Size M to Cart
          </button>

          <div className="flex items-start gap-2 border border-[#e5e5e5] rounded-[12px] px-3 py-2.5">
            <HelpCircle size={14} color="#6b7280" className="flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-xs font-bold text-[#1a1a1a]">Why Size M?</p>
              <p className="text-[11px] text-[#6b7280] mt-0.5">
                Based on your measurements and this brand&apos;s fit profile, size M provides the optimal balance across all zones. The waist will fit perfectly without being restrictive.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
