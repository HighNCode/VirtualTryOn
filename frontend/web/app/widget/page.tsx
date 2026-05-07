"use client";

import { useCallback, useState } from "react";
import { Search, User, ShoppingBag, Minus, Plus } from "lucide-react";
import { WidgetButton } from "./_components/WidgetButton";
import { WidgetShell } from "./_components/WidgetShell";
import { Step1Setup } from "./_components/Step1Setup";
import { Step2FrontPose } from "./_components/Step2FrontPose";
import { Step3SidePose } from "./_components/Step3SidePose";
import { Step4Analyzing } from "./_components/Step4Analyzing";
import { Step5Results } from "./_components/Step5Results";
import { Step6Generating } from "./_components/Step6Generating";
import { Step7TryOn } from "./_components/Step7TryOn";
import { Step8Success } from "./_components/Step8Success";

const TOTAL_STEPS = 8;

export default function WidgetPage() {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState(1);
  const [qty, setQty] = useState(1);

  const goNext = useCallback(() => setStep((value) => Math.min(value + 1, TOTAL_STEPS)), []);
  const goBack = useCallback(() => setStep((value) => Math.max(value - 1, 1)), []);
  const close = () => {
    setOpen(false);
    window.setTimeout(() => setStep(1), 400);
  };

  return (
    <div className="widget-page min-h-screen bg-white flex flex-col">
      <div className="text-center text-xs py-2 border-b border-[#e5e5e5] text-[#6b7280]">Welcome to our store</div>

      <header className="flex items-center justify-between px-8 py-4 border-b border-[#e5e5e5] widget-page-header">
        <div className="flex items-center gap-8">
          <span className="font-bold text-[#1a1a1a]">Komail-Test04</span>
          <nav className="flex gap-6 text-sm text-[#1a1a1a] widget-page-nav">
            <a href="#" className="hover:underline">
              Home
            </a>
            <a href="#" className="hover:underline">
              Catalog
            </a>
            <a href="#" className="hover:underline">
              Contact
            </a>
          </nav>
        </div>
        <div className="flex items-center gap-4 text-[#1a1a1a]">
          <Search size={18} />
          <User size={18} />
          <ShoppingBag size={18} />
        </div>
      </header>

      <main className="flex flex-1 gap-16 px-16 py-12 max-w-6xl mx-auto w-full widget-main">
        <div className="flex-1">
          <div className="w-full aspect-square bg-[#f5f5f5] rounded-[8px] overflow-hidden flex items-center justify-center">
            <img
              src="/widget/product-shirt.jpg"
              alt="Blue Oxford Shirt"
              className="w-full h-full object-contain"
              onError={(event) => {
                event.currentTarget.style.display = "none";
              }}
            />
          </div>
        </div>

        <div className="w-[420px] flex-shrink-0 flex flex-col gap-5 pt-4 widget-detail-panel">
          <div>
            <h1 className="text-2xl font-bold text-[#1a1a1a]">Blue Oxford Shirt</h1>
            <p className="text-base text-[#1a1a1a] mt-2">$0.00</p>
          </div>

          <div className="flex items-center gap-3">
            <div className="flex items-center border border-[#1a1a1a] rounded-full overflow-hidden">
              <button type="button" onClick={() => setQty((value) => Math.max(1, value - 1))} className="px-4 py-2.5 hover:bg-[#f5f5f5]">
                <Minus size={14} />
              </button>
              <span className="px-4 text-sm font-medium">{qty}</span>
              <button type="button" onClick={() => setQty((value) => value + 1)} className="px-4 py-2.5 hover:bg-[#f5f5f5]">
                <Plus size={14} />
              </button>
            </div>
            <button type="button" className="flex-1 py-3 rounded-full bg-[#1a1a1a] text-white text-sm font-medium flex items-center justify-center gap-2">
              <ShoppingBag size={15} /> Add to cart
            </button>
          </div>

          <button type="button" className="w-full py-3 rounded-full bg-[#1a1a1a] text-white text-sm font-medium">
            Buy it now
          </button>

          <WidgetButton onClick={() => setOpen(true)} />
        </div>
      </main>

      {open ? (
        <WidgetShell onClose={close} wide={step === 5 || step === 7}>
          {step === 1 ? <Step1Setup onNext={goNext} /> : null}
          {step === 2 ? <Step2FrontPose onNext={goNext} /> : null}
          {step === 3 ? <Step3SidePose onNext={goNext} /> : null}
          {step === 4 ? <Step4Analyzing onNext={goNext} /> : null}
          {step === 5 ? <Step5Results onNext={goNext} confidence={86} /> : null}
          {step === 6 ? <Step6Generating onNext={goNext} /> : null}
          {step === 7 ? <Step7TryOn onNext={goNext} onBack={goBack} /> : null}
          {step === 8 ? <Step8Success onClose={close} /> : null}
        </WidgetShell>
      ) : null}
    </div>
  );
}

