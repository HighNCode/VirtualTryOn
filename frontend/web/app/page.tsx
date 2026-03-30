"use client";

import { useEffect, useMemo } from "react";
import { EmbeddedLink, useEmbeddedRouter } from "./_components/EmbeddedNavigation";
import { getDefaultStoreId, getOnboardingStatus } from "../lib/photoshootApi";

const features = [
  {
    title: "Virtual Try-On for Customers",
    text: "Allow shoppers to upload their photo and preview products instantly, helping them buy with confidence."
  },
  {
    title: "AI Studio for Marketing",
    text: "Generate model-quality product visuals for landing pages and campaigns without a photoshoot."
  },
  {
    title: "Body Measurement Heat Map",
    text: "Analyze key body points from shopper images to recommend better-fitting sizes and reduce returns."
  },
  {
    title: "Marketing and User Experience",
    text: "Let shoppers share generated looks on social channels to amplify organic reach and engagement."
  }
];

const STEP_ROUTES: Record<string, string> = {
  goals: "/step-2",
  referral: "/step-3",
  widget_scope: "/step-4",
  theme_setup: "/step-5/not-detected",
  plan: "/step-7",
  complete: "/dashboard"
};

export default function Home() {
  const router = useEmbeddedRouter();
  const storeId = useMemo(() => getDefaultStoreId(), []);

  useEffect(() => {
    if (!storeId) return;

    getOnboardingStatus({ storeId })
      .then((status) => {
        const route = STEP_ROUTES[status.onboarding_step];
        if (route) router.replace(route);
      })
      .catch(() => {
        // If status check fails, stay on step 1 — user will continue normally
      });
  }, [router, storeId]);

  return (
    <main className="shell">
      <section className="welcome-card">
        <header className="topline">
          <p className="screen-title">Welcome to Optimo VTS</p>
          <p className="step">Step 1 of 7</p>
        </header>

        <div className="progress-track" aria-hidden>
          <span className="progress-fill" />
        </div>

        <div className="heading-wrap">
          <h1>
            Welcome to <span>Optimo VTS AI</span>
          </h1>
          <p>
            The ultimate AI-powered Virtual Try-On studio
            <br />
            Boost confidence, reduce returns, and drive more sales.
          </p>
        </div>

        <section className="features-panel">
          <h2>
            What you can do with <span>Optimo VTS</span>:
          </h2>

          <ul className="feature-list">
            {features.map((feature) => (
              <li key={feature.title} className="feature-item">
                <span className="tick" aria-hidden>
                  <svg viewBox="0 0 24 24" role="img">
                    <path
                      d="M20 7L10 17L5 12"
                      fill="none"
                      stroke="currentColor"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth="2.75"
                    />
                  </svg>
                </span>
                <div>
                  <h3>{feature.title}:</h3>
                  <p>{feature.text}</p>
                </div>
              </li>
            ))}
          </ul>
        </section>

        <div className="action-wrap">
          <EmbeddedLink href="/step-2" className="primary-action">
            Continue
          </EmbeddedLink>
        </div>

        <p className="support-link">
          <EmbeddedLink href="/settings/support">Need help? Contact our support team</EmbeddedLink>
        </p>
      </section>
    </main>
  );
}
