"use client";

import { CheckCircle2, ShoppingCart, Lock } from "lucide-react";

type Props = { onClose: () => void };

export function Step8Success({ onClose }: Props) {
  return (
    <div className="flex flex-col items-center px-8 py-10 gap-5 text-center">
      <CheckCircle2 size={52} color="#16a34a" strokeWidth={1.5} />

      <div>
        <h2 className="text-xl font-bold text-[#1a1a1a]">Perfect Fit Added</h2>
        <p className="text-sm text-[#6b7280] mt-1">
          Size M added to your cart with
          <br />
          89% confidence match
        </p>
      </div>

      <div className="flex flex-col gap-3 w-full">
        <button
          type="button"
          className="w-full py-3.5 rounded-[12px] text-white text-sm font-bold flex items-center justify-center gap-2"
          style={{ background: "linear-gradient(135deg, #7E0175 0%, #BC174A 55%, #E40206 100%)" }}
        >
          <ShoppingCart size={17} />
          View Cart
        </button>

        <button
          type="button"
          onClick={onClose}
          className="w-full py-3.5 rounded-[12px] text-sm font-bold border-2 border-[#e5e5e5] text-[#1a1a1a] hover:bg-[#f9f9f9] transition-colors"
        >
          Continue Shopping
        </button>
      </div>

      <div className="flex items-center gap-1.5 text-[11px] text-[#9ca3af]">
        <Lock size={11} />
        Your photo was deleted. We value your privacy.
      </div>
    </div>
  );
}

