"use client";

import { useState } from "react";
import { Camera, Square, PersonStanding, Maximize2, Sun } from "lucide-react";

type Props = { onNext: () => void };

const tips = [
  { icon: Square, title: "Plain Background", desc: "Position yourself in front of a plain wall" },
  { icon: PersonStanding, title: "Stand 1.5m Away", desc: "Step back so your full body is visible in frame" },
  { icon: Maximize2, title: "Fitted Clothing", desc: "Wear fitting clothes (not baggy) for best accuracy" },
  { icon: Sun, title: "Good Lighting", desc: "Stand in a well-lit area, facing the light source" }
];

export function Step1Setup({ onNext }: Props) {
  const [height, setHeight] = useState("");
  const [weight, setWeight] = useState("");
  const [gender, setGender] = useState("");
  const [researchConsent, setResearchConsent] = useState(false);

  return (
    <div className="flex flex-col items-center px-6 py-8 gap-5">
      <Camera size={32} color="#E40206" strokeWidth={1.5} />

      <div className="text-center">
        <h2 className="text-xl font-bold text-[#1a1a1a]">
          Quick Setup <span className="text-[#E40206]">Guide</span>
        </h2>
        <p className="text-xs text-[#6b7280] mt-1">Follow these simple steps for the best results</p>
      </div>

      <div className="w-full border border-[#e5e5e5] rounded-[14px] p-4 flex flex-col gap-4">
        <p className="text-sm font-semibold text-[#1a1a1a]">Add your details</p>

        <div className="flex flex-col gap-1">
          <label className="text-xs text-[#6b7280]">Height</label>
          <div className="relative">
            <input
              type="number"
              value={height}
              onChange={(event) => setHeight(event.target.value)}
              className="w-full border border-[#e5e5e5] rounded-[8px] px-3 py-2.5 text-sm outline-none pr-12"
              placeholder=""
            />
            <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-[#9ca3af] flex items-center gap-1">
              cm <span className="text-[10px]">▾</span>
            </span>
          </div>
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-xs text-[#6b7280]">Weight</label>
          <div className="relative">
            <input
              type="number"
              value={weight}
              onChange={(event) => setWeight(event.target.value)}
              className="w-full border border-[#e5e5e5] rounded-[8px] px-3 py-2.5 text-sm outline-none pr-12"
              placeholder=""
            />
            <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-[#9ca3af] flex items-center gap-1">
              kg <span className="text-[10px]">▾</span>
            </span>
          </div>
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-xs text-[#6b7280]">Gender</label>
          <select
            value={gender}
            onChange={(event) => setGender(event.target.value)}
            className="w-full border border-[#e5e5e5] rounded-[8px] px-3 py-2.5 text-sm outline-none appearance-none bg-white"
          >
            <option value="" />
            <option value="male">Male</option>
            <option value="female">Female</option>
            <option value="other">Other</option>
          </select>
        </div>
      </div>

      <div className="w-full flex flex-col gap-3">
        {tips.map((tip) => (
          <div key={tip.title} className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-[8px] border border-[#fbd5d5] bg-[#fff5f5] flex items-center justify-center flex-shrink-0">
              <tip.icon size={15} color="#E40206" />
            </div>
            <div>
              <p className="text-sm font-semibold text-[#1a1a1a]">{tip.title}</p>
              <p className="text-xs text-[#6b7280]">{tip.desc}</p>
            </div>
          </div>
        ))}
      </div>

      <button
        disabled={!researchConsent}
        onClick={onNext}
        className="w-full py-3.5 rounded-[12px] text-white text-sm font-bold"
        style={{ background: "linear-gradient(135deg, #7E0175 0%, #BC174A 55%, #E40206 100%)" }}
      >
        Continue
      </button>

      <label className="w-full flex items-start gap-2 text-[11px] text-[#5f6368]">
        <input
          type="checkbox"
          checked={researchConsent}
          onChange={(event) => setResearchConsent(event.target.checked)}
          className="mt-0.5"
        />
        <span>I agree to research retention of my photos and measurement outputs as described in the privacy notice.</span>
      </label>

      <div className="w-full bg-[#f9f9f9] rounded-[10px] px-4 py-3 text-center">
        <p className="text-[11px] font-semibold text-[#1a1a1a]">Your Privacy Matters</p>
        <p className="text-[10px] text-[#9ca3af] mt-0.5">
          Your photos stay available for try-on for about 1 hour.
          <br />
          With your consent, photos and measurement outputs are retained for research for a limited period.
        </p>
      </div>
    </div>
  );
}

