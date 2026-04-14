"use client";

import { useEffect, useMemo, useState } from "react";
import { EmbeddedLink, useEmbeddedRouter } from "../_components/EmbeddedNavigation";
import { getDefaultStoreId, getOnboardingStatus, saveOnboardingGoals } from "../../lib/photoshootApi";

type GoalOption = {
  id: string;
  title: string;
  description: string;
  icon: JSX.Element;
};

const goals: GoalOption[] = [
  {
    id: "conversion",
    title: "Improve conversion rates",
    description: "Help customers make faster purchasing decisions",
    icon: (
      <svg viewBox="0 0 24 24" role="img">
        <path d="M14 3L14.8 5.6L17.4 6.4L14.8 7.2L14 9.8L13.2 7.2L10.6 6.4L13.2 5.6L14 3Z" fill="currentColor" />
        <path d="M7 7L7.6 8.9L9.5 9.5L7.6 10.1L7 12L6.4 10.1L4.5 9.5L6.4 8.9L7 7Z" fill="currentColor" />
        <circle cx="9.2" cy="15.2" r="5.4" fill="none" stroke="currentColor" strokeWidth="1.9" />
        <path d="M14.8 19.4L19 15.2" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="1.9" />
      </svg>
    )
  },
  {
    id: "returns",
    title: "Reduce return rates",
    description: "Minimize returns due to sizing or fit issues",
    icon: (
      <svg viewBox="0 0 24 24" role="img">
        <path d="M4 6H10V12" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
        <path d="M5 11L10 6L14 10L20 4" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
        <path d="M14 14H20V20H14Z" fill="currentColor" />
      </svg>
    )
  },
  {
    id: "emails",
    title: "Collect customer emails",
    description: "Build your email list through the try-on button",
    icon: (
      <svg viewBox="0 0 24 24" role="img">
        <path
          d="M17.8 10.4C17.8 6.9 15.1 4.2 11.6 4.2C8.1 4.2 5.4 6.9 5.4 10.4C5.4 13.9 8.1 16.6 11.6 16.6H13.2C15.1 16.6 16.7 18.2 16.7 20.1C16.7 22 15.1 23.6 13.2 23.6H6.2"
          fill="none"
          stroke="currentColor"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="1.9"
          transform="translate(0 -2)"
        />
        <circle cx="9.6" cy="10.7" r="2.4" fill="none" stroke="currentColor" strokeWidth="1.9" />
      </svg>
    )
  },
  {
    id: "content",
    title: "Create marketing content",
    description: "Use AI Studio to generate on-model photos for ads",
    icon: (
      <svg viewBox="0 0 24 24" role="img">
        <path
          d="M6 7.5C6 5.6 7.6 4 9.5 4H15.5C17.4 4 19 5.6 19 7.5V16.5C19 18.4 17.4 20 15.5 20H9.5C7.6 20 6 18.4 6 16.5V7.5Z"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.9"
        />
        <path d="M10 9.5H15M10 12H15M10 14.5H13" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="1.9" />
        <path d="M4 9.5V16.5C4 19.5 6.5 22 9.5 22H15.5" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="1.9" />
      </svg>
    )
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
          <p className="step">Step 2 of 7</p>
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
                    {goal.icon}
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
