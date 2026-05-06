"use client";

import type { ReactNode } from "react";
import { X } from "./icons";

type Props = { children: ReactNode; onClose: () => void; wide?: boolean };

export function WidgetShell({ children, onClose, wide }: Props) {
  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4" style={{ background: "rgba(0,0,0,0.45)" }}>
      <div
        className="bg-white rounded-[20px] w-full flex flex-col relative overflow-hidden"
        style={{ maxWidth: wide ? 800 : 480, maxHeight: "92vh", boxShadow: "0 20px 60px rgba(0,0,0,0.25)" }}
      >
        <button
          onClick={onClose}
          className="absolute top-3.5 right-3.5 z-10 w-8 h-8 rounded-full bg-[#f3f4f6] flex items-center justify-center hover:bg-[#e5e7eb] transition-colors"
        >
          <X size={15} color="#6b7280" />
        </button>
        <div className="overflow-y-auto flex-1">{children}</div>
      </div>
    </div>
  );
}
