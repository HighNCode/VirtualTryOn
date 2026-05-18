export function getPhotoshootStartingMessage() {
  return "Preparing your image. This can take a few moments.";
}

export function getPhotoshootProgressMessage(progress?: number | null) {
  if (typeof progress !== "number" || !Number.isFinite(progress)) {
    return "Creating your AI photoshoot image. Please keep this page open.";
  }

  const safeProgress = Math.max(0, Math.min(100, Math.round(progress)));
  let stage = "Creating your AI photoshoot image";

  if (safeProgress < 20) {
    stage = "Preparing your image";
  } else if (safeProgress < 55) {
    stage = "Creating your AI photoshoot image";
  } else if (safeProgress < 85) {
    stage = "Refining the result";
  } else if (safeProgress < 100) {
    stage = "Adding the final details";
  } else {
    stage = "Finalizing your image";
  }

  return `${stage}… ${safeProgress}% complete.`;
}
