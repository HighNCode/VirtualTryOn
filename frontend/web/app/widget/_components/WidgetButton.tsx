"use client";

import { Camera, ArrowRight } from "./icons";

type Props = { onClick: () => void };

export function WidgetButton({ onClick }: Props) {
  return (
    <button
      onClick={onClick}
      className="flex items-center justify-center gap-3 w-full py-4 rounded-[14px] text-white text-base font-bold transition-opacity hover:opacity-90"
      style={{ background: "linear-gradient(135deg, #7E0175 0%, #BC174A 55%, #E40206 100%)" }}
    >
      <Camera size={22} strokeWidth={2} />
      Try it on virtually
      <ArrowRight size={18} strokeWidth={2.5} />
    </button>
  );
}
