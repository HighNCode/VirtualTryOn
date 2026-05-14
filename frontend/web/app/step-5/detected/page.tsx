"use client";

import { useEffect } from "react";
import { useEmbeddedRouter } from "../../_components/EmbeddedNavigation";

export default function StepFiveDetectedAliasPage() {
  const router = useEmbeddedRouter();

  useEffect(() => {
    router.replace("/step-5");
  }, [router]);

  return null;
}
