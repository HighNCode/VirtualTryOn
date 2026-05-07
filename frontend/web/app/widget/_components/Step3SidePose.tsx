"use client";

import { useRef } from "react";
import { Camera, Upload } from "lucide-react";

type Props = { onNext: () => void };

export function Step3SidePose({ onNext }: Props) {
  const uploadRef = useRef<HTMLInputElement>(null);

  return (
    <div className="flex flex-col items-center px-6 py-8 gap-5">
      <h2 className="text-xl font-bold text-[#1a1a1a] self-start">
        Position: <span className="text-[#E40206]">Side Pose</span>
      </h2>

      <div className="grid grid-cols-2 gap-4 w-full">
        {[
          { label: "Good Example", good: true },
          { label: "Bad Example", good: false }
        ].map((example) => (
          <div key={example.label} className="flex flex-col gap-2">
            <p className="text-xs text-[#6b7280] text-center">{example.label}</p>
            <div className="w-full aspect-[3/4] rounded-[14px] border border-[#e5e5e5] bg-[#f0f0f0] flex items-center justify-center overflow-hidden">
              <img
                src={example.good ? "/widget/side-good.jpg" : "/widget/side-bad.jpg"}
                alt={example.label}
                className="w-full h-full object-cover"
                onError={(event) => {
                  event.currentTarget.style.display = "none";
                }}
              />
            </div>
          </div>
        ))}
      </div>

      <div className="flex flex-col gap-3 w-full">
        <button
          onClick={onNext}
          className="w-full py-3.5 rounded-[12px] text-white text-sm font-bold flex items-center justify-center gap-2"
          style={{ background: "linear-gradient(135deg, #7E0175 0%, #BC174A 55%, #E40206 100%)" }}
        >
          <Camera size={18} />
          Take Photo
        </button>

        <input ref={uploadRef} type="file" accept="image/*" className="hidden" onChange={onNext} />
        <button
          onClick={() => uploadRef.current?.click()}
          className="w-full py-3.5 rounded-[12px] text-sm font-bold border-2 border-[#e5e5e5] text-[#1a1a1a] flex items-center justify-center gap-2 hover:bg-[#f9f9f9] transition-colors"
        >
          <Upload size={17} />
          Upload <span className="text-[#E40206]">Side Pose</span>
        </button>
      </div>
    </div>
  );
}

