"use client";

import { useEffect, useMemo, useState } from "react";
import { Camera, Mail, TrendingDown, TrendingUp, type LucideIcon } from "lucide-react";
import { EmbeddedLink, useEmbeddedRouter } from "../_components/EmbeddedNavigation";
import { getDefaultStoreId, getOnboardingStatus, saveOnboardingGoals } from "../../lib/photoshootApi";

type GoalOption = {
  id: string;
  title: string;
  description: string;
  icon: LucideIcon;
};

const goals: GoalOption[] = [
  {
    id: "conversion",
    title: "Improve conversion rates",
    description: "Help customers make faster purchasing decisions",
    icon: TrendingUp
  },
  {
    id: "returns",
    title: "Reduce return rates",
    description: "Minimize returns due to sizing or fit issues",
    icon: TrendingDown
  },
  {
    id: "emails",
    title: "Collect customer emails",
    description: "Build your email list through the try-on button",
    icon: Mail
  },
  {
    id: "content",
    title: "Create marketing content",
    description: "Use AI Studio to generate on-model photos for ads",
    icon: Camera
  }
];

export default function StepTwoPage() {
  const router = useEmbeddedRouter();
  const storeId = useMemo(() => getDefaultStoreId(), []);

  const [selectedGoals, setSelectedGoals] = useState<string[]>([]);
  const [isSaving, setIsSaving] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    if (!storeId) {
      return;
    }

    const controller = new AbortController();
    let active = true;

    setIsLoading(true);

    getOnboardingStatus({ storeId, signal: controller.signal })
      .then((status) => {
        if (!active) {
          return;
        }

        setSelectedGoals(status.goals ?? []);
      })
      .catch((error: unknown) => {
        if (!active || controller.signal.aborted) {
          return;
        }

        const message = error instanceof Error ? error.message : "Failed to load onboarding goals.";
        setErrorMessage(message);
      })
      .finally(() => {
        if (active) {
          setIsLoading(false);
        }
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [storeId]);

  const selectedSet = useMemo(() => new Set(selectedGoals), [selectedGoals]);

  const toggleGoal = (goalId: string) => {
    setSelectedGoals((current) =>
      current.includes(goalId) ? current.filter((id) => id !== goalId) : [...current, goalId]
    );
  };

  const handleContinue = async () => {
    if (!storeId) {
      router.push("/step-3");
      return;
    }

    setIsSaving(true);
    setErrorMessage("");

    try {
      await saveOnboardingGoals({ storeId, goals: selectedGoals });
      router.push("/step-3");
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Failed to save goals.";
      setErrorMessage(message);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <main className="shell">
      <section className="welcome-card">
        <header className="topline">
          <p className="screen-title">Welcome to Optimo VTS</p>
          <p className="step">Step 2 of 6</p>
        </header>

        <div className="progress-track" aria-hidden>
          <span className="progress-fill progress-step2" />
        </div>

        <div className="step2-title-row">
          <EmbeddedLink href="/" className="back-button" aria-label="Go to Step 1">
            <svg viewBox="0 0 24 24" role="img">
              <path d="M14.6 5.5L8.2 12L14.6 18.5" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.8" />
            </svg>
          </EmbeddedLink>
          <h1>What do you want to achieve?</h1>
        </div>

        <p className="step2-subtitle">Select all that apply</p>

        {isLoading ? <p className="ai-status-note">Loading current goals...</p> : null}
        {!storeId ? <p className="ai-error-note">Open the app from Shopify Admin to save onboarding progress.</p> : null}
        {errorMessage ? <p className="ai-error-note">{errorMessage}</p> : null}

        <form>
          <ul className="goal-list">
            {goals.map((goal) => (
              <li key={goal.id}>
                <label className="goal-option">
                  <input
                    type="checkbox"
                    name="goals"
                    value={goal.id}
                    checked={selectedSet.has(goal.id)}
                    onChange={() => toggleGoal(goal.id)}
                  />
                  <span className="goal-icon" aria-hidden>
                    <goal.icon size={20} strokeWidth={1.9} />
                  </span>
                  <span className="goal-copy">
                    <strong>{goal.title}:</strong>
                    <span>{goal.description}</span>
                  </span>
                </label>
              </li>
            ))}
          </ul>
        </form>

        <div className="step2-footer">
          <p className="support-link support-inline">
            <EmbeddedLink href="/settings/support">Need help? Contact our support team</EmbeddedLink>
          </p>
          <button type="button" className="primary-action" onClick={handleContinue} disabled={isSaving}>
            {isSaving ? "Saving..." : "Continue"}
          </button>
        </div>
      </section>
    </main>
  );
}

