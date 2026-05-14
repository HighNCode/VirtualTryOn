"use client";

import { useEffect } from "react";
import { useEmbeddedRouter } from "../../_components/EmbeddedNavigation";

export default function StepFourConfiguredAliasPage() {
  const router = useEmbeddedRouter();

  useEffect(() => {
    router.replace("/step-4");
  }, [router]);

  return null;
}
