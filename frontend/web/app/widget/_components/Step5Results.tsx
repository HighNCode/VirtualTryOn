"use client";

import { CheckCircle2, X, RotateCcw, TrendingUp, Ruler, Sparkles } from "lucide-react";

type Props = { onNext: () => void; confidence?: number };

const measurements = [
  { label: "Height", value: "92.3cm", highlight: true },
  { label: "Bust circumference", value: null },
  { label: "Bust width (shoulder to shoulder)", value: null },
  { label: "Under-bust circumference", value: null },
  { label: "Waist circumference", value: null },
  { label: "Waist width", value: null },
  { label: "Hip circumference", value: null },
  { label: "Hip width", value: null },
  { label: "Shoulder width", value: null },
  { label: "Shoulder circumference", value: null },
  { label: "Arm length", value: null },
  { label: "Arm circumference", value: null },
  { label: "Bicep circumference", value: null },
  { label: "Wrist circumference", value: null },
  { label: "Inseam", value: null },
  { label: "Thigh circumference", value: null },
  { label: "Knee circumference", value: null },
  { label: "Calf circumference", value: null },
  { label: "Ankle circumference", value: null },
  { label: "Back length", value: null }
];

const nextSteps = [
  { icon: TrendingUp, title: "Fit Heatmap", desc: "See exactly where the garment will be loose, snug, or tight on your body" },
  { icon: Ruler, title: "Size Recommendation", desc: "Get AI-powered size suggestions with confidence scores" },
  { icon: Sparkles, title: "Virtual Try-On", desc: "Visualize the product on your body before purchasing" }
];

export function Step5Results({ onNext, confidence = 86 }: Props) {
  const highConfidence = confidence >= 60;
  const lowMeasurements = !highConfidence ? [2, 3, 4, 5] : [];

  return (
    <div className="flex flex-col px-5 py-6 gap-5">
      <div className="flex items-start justify-between gap-3 step-five-head">
        <div className="flex items-start gap-2.5">
          <CheckCircle2 size={28} color="#16a34a" className="flex-shrink-0 mt-0.5" />
          <div>
            <h2 className="text-lg font-bold text-[#1a1a1a]">Measurement Complete!</h2>
            <p className="text-xs text-[#6b7280] mt-0.5">
              We&apos;ve extracted 20+ body dimensions
              <br />
              with high accuracy
            </p>
          </div>
        </div>
        <div className="border border-[#e5e5e5] rounded-[10px] px-3 py-2 text-center flex-shrink-0 mr-9 confidence-chip">
          <span className="text-xs text-[#6b7280]">Confidence Score: </span>
          <span className="text-sm font-bold text-[#E40206]">{confidence}%</span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 step-five-grid">
        <div className="border border-[#e5e5e5] rounded-[14px] p-3 flex flex-col gap-1">
          <div className="flex items-center gap-1.5 mb-2">
            <div className="w-5 h-5 rounded-[5px] bg-[#fff0f0] flex items-center justify-center">
              <Ruler size={11} color="#E40206" />
            </div>
            <span className="text-xs font-bold text-[#1a1a1a]">Your Measurements</span>
          </div>

          <div className="flex flex-col gap-1 overflow-y-auto pr-0.5" style={{ maxHeight: 380 }}>
            {measurements.map((measurement, index) => {
              const failed = lowMeasurements.includes(index);

              return (
                <div key={measurement.label} className="flex items-center justify-between border border-[#f0f0f0] rounded-[6px] px-2 py-1.5">
                  <span className="text-[11px] text-[#1a1a1a]">{measurement.label}</span>
                  {failed ? (
                    <X size={12} color="#E40206" />
                  ) : measurement.highlight ? (
                    <span className="text-[11px] text-[#E40206] font-medium">{measurement.value}</span>
                  ) : null}
                </div>
              );
            })}
          </div>

          {!highConfidence ? (
            <p className="text-[10px] text-[#E40206] mt-1">
              Model couldn&apos;t pick all of the measurements due to image not been taken properly
            </p>
          ) : null}

          <button type="button" className="flex items-center gap-1.5 mt-1 text-[11px] text-[#6b7280] hover:text-[#1a1a1a]">
            <RotateCcw size={11} /> Retake Photo
          </button>
        </div>

        <div className="border border-[#e5e5e5] rounded-[14px] p-3 flex flex-col gap-2">
          <div className="flex items-center gap-1.5 mb-1">
            <TrendingUp size={13} color="#E40206" />
            <div>
              <p className="text-xs font-bold text-[#1a1a1a]">What&apos;s Next?</p>
              <p className="text-[10px] text-[#6b7280]">See Your Perfect Fit</p>
            </div>
          </div>

          {nextSteps.map((nextStep) => (
            <div key={nextStep.title} className="bg-[#fff5f5] rounded-[8px] p-2 flex items-start gap-2">
              <div className="w-6 h-6 rounded-full bg-[#fde8e8] flex items-center justify-center flex-shrink-0">
                <nextStep.icon size={11} color="#E40206" />
              </div>
              <div>
                <p className="text-[11px] font-semibold text-[#1a1a1a]">{nextStep.title}</p>
                <p className="text-[10px] text-[#6b7280]">{nextStep.desc}</p>
              </div>
            </div>
          ))}

          <button
            onClick={onNext}
            className="w-full mt-2 py-2.5 rounded-[10px] text-white text-xs font-bold flex items-center justify-center gap-1"
            style={{ background: "linear-gradient(135deg, #7E0175 0%, #BC174A 55%, #E40206 100%)" }}
          >
            View Your Fit →
          </button>

          <p className="text-[9px] text-[#9ca3af] text-center">Photos stay available for try-on for about 1 hour. With consent, photos and measurement outputs may be retained for research for a limited period.</p>
        </div>
      </div>
    </div>
  );
}

