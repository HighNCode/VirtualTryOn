"use client";

import { useRef, type ChangeEvent, type ReactNode } from "react";
import { motion } from "framer-motion";
import { CloudUpload, Sparkles } from "lucide-react";

type AiUploadLandingProps = {
  headline: ReactNode;
  subtitle: string;
  videoSrc: string;
  onUpload?: () => void;
  onFileSelected?: (file: File) => void;
  onSelectStore?: () => void;
};

export default function AiUploadLanding({
  headline,
  subtitle,
  videoSrc,
  onUpload,
  onFileSelected,
  onSelectStore
}: AiUploadLandingProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    if (onFileSelected) {
      onFileSelected(file);
    } else {
      onUpload?.();
    }

    event.currentTarget.value = "";
  };

  return (
    <div className="ai-upload-landing">
      <div className="ai-upload-landing-copy">
        <div>
          <h2>{headline}</h2>
          <p>{subtitle}</p>
        </div>

        <div className="ai-upload-landing-preview">
          <video
            src={videoSrc}
            autoPlay
            loop
            muted
            playsInline
          />
        </div>
      </div>

      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: "easeOut" }}
        className="ai-upload-landing-panel"
      >
        <div className="ai-upload-landing-badge">
          <Sparkles size={11} />
          Upgrade Your Visuals Now
        </div>

        <div className="ai-upload-landing-drop">
          <CloudUpload size={58} color="#7E0175" strokeWidth={1.5} />
          <p>Click or drag image here</p>
        </div>

        <div className="ai-upload-landing-actions">
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            className="ai-upload-landing-primary"
          >
            Upload Image
          </button>
          <button
            type="button"
            onClick={onSelectStore ?? onUpload}
            className="ai-upload-landing-secondary"
          >
            Select from your store
          </button>
        </div>

        <p className="ai-upload-landing-note">
          Any flat-lay or hanging photo works,
          <br />
          no professional setup needed
        </p>

        <input ref={inputRef} type="file" accept="image/*" style={{ display: "none" }} onChange={handleFileChange} />
      </motion.div>
    </div>
  );
}
