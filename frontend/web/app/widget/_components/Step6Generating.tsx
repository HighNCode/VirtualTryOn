"use client";

import { useEffect, useRef, useState } from "react";
import { CheckCircle2, Circle } from "./icons";

type Props = { onNext: () => void };

const steps = ["Loading Optimo 4o Virtual Studio", "Fitting to your size", "Enhancing Overlay"];

export function Step6Generating({ onNext }: Props) {
  const [progress, setProgress] = useState(0);
  const [done, setDone] = useState(0);
  const calledRef = useRef(false);

  useEffect(() => {
    const interval = window.setInterval(() => {
      setProgress((value) => {
        if (value >= 100) {
          window.clearInterval(interval);
          if (!calledRef.current) {
            calledRef.current = true;
            window.setTimeout(onNext, 400);
          }
          return 100;
        }
        return value + 1.5;
      });
    }, 60);

    return () => window.clearInterval(interval);
  }, [onNext]);

  useEffect(() => {
    setDone(progress < 40 ? 0 : progress < 78 ? 1 : progress < 100 ? 2 : 3);
  }, [progress]);

  return (
    <div className="flex flex-col items-center px-6 py-12 gap-6">
      <svg width="48" height="48" viewBox="0 0 48 48" className="animate-spin">
        <circle cx="24" cy="24" r="20" fill="none" stroke="#f0f0f0" strokeWidth="4" />
        <path d="M 24 4 A 20 20 0 0 1 44 24" fill="none" stroke="url(#spin-grad2)" strokeWidth="4" strokeLinecap="round" />
        <defs>
          <linearGradient id="spin-grad2" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#7E0175" />
            <stop offset="100%" stopColor="#E40206" />
          </linearGradient>
        </defs>
      </svg>

      <div className="text-center">
        <h2 className="text-xl font-bold text-[#1a1a1a]">Generating your Fit</h2>
        <p className="text-xs text-[#6b7280] mt-1">Our AI is creating virtual try-on for you</p>
      </div>

      <div className="w-full h-2.5 bg-[#f0f0f0] rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all duration-100" style={{ width: `${progress}%`, background: "linear-gradient(90deg, #7E0175, #E40206)" }} />
      </div>

      <div className="w-full flex flex-col gap-2.5">
        {steps.map((step, index) => {
          const completed = index < done;
          const active = index === done;

          return (
            <div key={step} className="flex items-center gap-2.5">
              {completed ? <CheckCircle2 size={17} color="#16a34a" /> : <Circle size={17} color={active ? "#E40206" : "#d1d5db"} />}
              <span className={`text-sm ${completed ? "text-[#6b7280]" : active ? "text-[#E40206] font-medium" : "text-[#9ca3af]"}`}>
                {step}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
