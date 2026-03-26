"use client";

import { useState } from "react";
import PortalSidebar from "../_components/PortalSidebar";

const styleTemplates = [
  { id: "white-sweater", label: "White Sweater", tone: "template-tone-light" },
  { id: "black-jacket", label: "Black Jacket", tone: "template-tone-dark" },
  { id: "dark-bomber", label: "Dark Bomber", tone: "template-tone-charcoal" },
  { id: "jeans", label: "Blue Jeans", tone: "template-tone-jeans" },
  { id: "yellow-dress", label: "Yellow Dress", tone: "template-tone-gold" },
  { id: "green-jacket", label: "Green Jacket", tone: "template-tone-olive" }
];

const resultCards = [
  { id: "original", title: "Original Upload", enhanced: false, variant: "original" },
  { id: "enhanced-1", title: "Enhanced - OptimoVTS", enhanced: true, variant: "enhanced-a" },
  { id: "enhanced-2", title: "Enhanced - OptimoVTS (1)", enhanced: true, variant: "enhanced-b" }
] as const;

export default function AiProductShootPage() {
  const [generated, setGenerated] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState(styleTemplates[0].id);

  return (
    <main className="portal-shell">
      <PortalSidebar activeMain="ai" activeAi="ghost" />

      <section className="portal-main">
        <header className="portal-main-header">
          <h2>AI Product Shoots</h2>
          <p>Generate professional studio shoots in seconds</p>
        </header>

        {!generated ? (
          <section className="ai-stage-upload">
            <article className="ai-upload-copy">
              <h3>
                AI <span>Ghost Mannequin</span>
                <br />
                Generator for Product
                <br />
                Photography
              </h3>
              <p>Professional results in seconds, without studios or mannequins.</p>
              <div className="ai-upload-preview" aria-hidden />
            </article>

            <aside className="ai-upload-panel">
              <p className="ai-upgrade-banner">✦ Upgrade Your Visuals Now</p>

              <div className="ai-upload-drop" aria-hidden>
                <svg viewBox="0 0 24 24" role="img">
                  <path
                    d="M12 14V7M12 7L9 10M12 7L15 10M7 16.5H6.6C4.6 16.5 3 15 3 13C3 11 4.6 9.4 6.6 9.4C7.1 7 9.2 5.2 11.8 5.2C14.7 5.2 17 7.4 17.2 10.1C19.2 10.2 21 11.8 21 13.9C21 16.1 19.2 17.8 16.9 17.8H7"
                    fill="none"
                    stroke="currentColor"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                  />
                </svg>
                <p>Click or drag image here</p>
              </div>

              <button type="button" className="ai-primary-btn" onClick={() => setGenerated(true)}>
                Upload Image
              </button>
              <button type="button" className="ai-outline-btn">
                Select from your store
              </button>

              <p className="ai-upload-note">
                Any flat-lay or hanging photo works,
                <br />
                no professional setup needed
              </p>
            </aside>
          </section>
        ) : (
          <section className="ai-stage-result">
            <aside className="ai-generator-card">
              <h3>Ghost Mannequin</h3>
              <p>Original Image</p>

              <h4>Clothing Type</h4>
              <label className="ai-select-wrap">
                <select aria-label="Clothing Type">
                  <option>Select</option>
                  <option>Tops</option>
                  <option>Bottoms</option>
                  <option>Outerwear</option>
                </select>
              </label>

              <h4>Style Templates</h4>
              <div className="ai-template-grid">
                {styleTemplates.map((template) => (
                  <button
                    key={template.id}
                    type="button"
                    className={`ai-template-item ${template.tone}${selectedTemplate === template.id ? " is-selected" : ""}`}
                    onClick={() => setSelectedTemplate(template.id)}
                    aria-label={template.label}
                  >
                    <span />
                  </button>
                ))}
              </div>

              <button type="button" className="ai-primary-btn ai-generate-btn">
                Generate
              </button>
            </aside>

            <div className="ai-results-grid">
              {resultCards.map((card) => (
                <article key={card.id} className="ai-result-card">
                  <header>
                    <p>{card.title}</p>
                    {card.enhanced ? (
                      <div className="ai-result-actions" aria-hidden>
                        <button type="button">↓</button>
                        <button type="button">↻</button>
                      </div>
                    ) : null}
                  </header>

                  <div className={`ai-result-image ai-result-image-${card.variant}`} aria-hidden>
                    <span className="ai-model-figure">
                      <span className="ai-model-head" />
                      <span className="ai-model-torso" />
                      <span className="ai-model-leg-left" />
                      <span className="ai-model-leg-right" />
                    </span>
                  </div>
                </article>
              ))}
            </div>
          </section>
        )}
      </section>
    </main>
  );
}
