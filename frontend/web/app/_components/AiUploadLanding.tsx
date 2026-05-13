"use client";

import { useRef, type ReactNode } from "react";
import { motion } from "framer-motion";
import { CloudUpload, Sparkles } from "lucide-react";

type AiUploadLandingProps = {
  headline: ReactNode;
  subtitle: string;
  videoSrc: string;
  onUpload: () => void;
};

export default function AiUploadLanding({ headline, subtitle, videoSrc, onUpload }: AiUploadLandingProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);

  return (
    <div style={{ display: "flex", alignItems: "stretch", gap: 28 }}>
      <div style={{ width: 605, flexShrink: 0, display: "flex", flexDirection: "column", gap: 16 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 28, lineHeight: 1.15, fontWeight: 900, color: "#1a1a1a" }}>
            {headline}
          </h2>
          <p style={{ margin: "12px 0 0", fontSize: 14, color: "#6b7280" }}>
            {subtitle}
          </p>
        </div>

        <div style={{ width: "100%", height: 317, borderRadius: 14, overflow: "hidden", background: "#e8e8e8" }}>
          <video
            src={videoSrc}
            autoPlay
            loop
            muted
            playsInline
            style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
          />
        </div>
      </div>

      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: "easeOut" }}
        style={{
          flex: 1,
          minHeight: 405,
          background: "#fff",
          borderRadius: 18,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: 28,
          padding: "40px 40px",
          boxShadow: "0 4px 24px rgba(0,0,0,0.08), 0 1px 4px rgba(0,0,0,0.04)",
          border: "1px solid rgba(0,0,0,0.04)",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            padding: "7px 13px",
            borderRadius: 999,
            fontSize: 12,
            fontWeight: 700,
            color: "#7E0175",
            background: "rgba(126,1,117,0.08)",
          }}
        >
          <Sparkles size={11} />
          Upgrade Your Visuals Now
        </div>

        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 14 }}>
          <CloudUpload size={58} color="#7E0175" strokeWidth={1.5} />
          <p style={{ margin: 0, fontSize: 14, color: "#6b7280", textAlign: "center" }}>
            Click or drag image here
          </p>
        </div>

        <div style={{ width: 220, display: "flex", flexDirection: "column", gap: 12 }}>
          <button
            type="button"
            onClick={() => {
              inputRef.current?.click();
              onUpload();
            }}
            style={{
              width: "100%",
              padding: "13px 16px",
              borderRadius: 10,
              border: "none",
              color: "#fff",
              fontSize: 14,
              fontWeight: 800,
              cursor: "pointer",
              background: "linear-gradient(135deg, #7E0175 0%, #BC174A 55%, #E40206 100%)",
            }}
          >
            Upload Image
          </button>
          <button
            type="button"
            onClick={onUpload}
            style={{
              width: "100%",
              padding: "12px 16px",
              borderRadius: 10,
              border: "1.5px solid #7E0175",
              color: "#7E0175",
              background: "#fff",
              fontSize: 14,
              fontWeight: 700,
              cursor: "pointer",
            }}
          >
            Select from your store
          </button>
        </div>

        <p style={{ margin: 0, fontSize: 11, lineHeight: 1.65, color: "#9ca3af", textAlign: "center" }}>
          Any flat-lay or hanging photo works,
          <br />
          no professional setup needed
        </p>

        <input ref={inputRef} type="file" accept="image/*" style={{ display: "none" }} />
      </motion.div>
    </div>
  );
}
