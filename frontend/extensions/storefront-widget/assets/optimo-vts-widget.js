(function () {
  const STORAGE_KEY = "optimo-vts-user-id";
  const ACTIVE_PROGRESS_COLOR = "linear-gradient(90deg, #a4006e 0%, #f3001f 100%)";
  const IDLE_PROGRESS_COLOR = "#d7d5d8";
  const MEASUREMENT_ROWS = [
    ["height", "Height"],
    ["chest", "Chest circumference"],
    ["shoulder_width", "Shoulder width"],
    ["waist", "Waist circumference"],
    ["hip", "Hip circumference"],
    ["neck", "Neck circumference"],
    ["arm_length", "Arm length"],
    ["thigh", "Thigh circumference"],
    ["inseam", "Inseam"]
  ];
  const FALLBACK_HEATMAP =
    '<svg viewBox="0 0 200 500" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">' +
    '<rect x="58" y="48" width="84" height="40" rx="20" fill="rgba(255,255,255,0.18)"></rect>' +
    '<rect x="44" y="104" width="112" height="108" rx="52" fill="rgba(255,181,45,0.68)"></rect>' +
    '<rect x="56" y="216" width="88" height="72" rx="26" fill="rgba(255,181,45,0.72)"></rect>' +
    '<rect x="62" y="292" width="32" height="142" rx="16" fill="rgba(45,196,170,0.78)"></rect>' +
    '<rect x="106" y="292" width="32" height="142" rx="16" fill="rgba(45,196,170,0.78)"></rect>' +
    "</svg>";

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function formatNumber(value) {
    const num = Number(value);
    if (!Number.isFinite(num)) {
      return null;
    }
    return num % 1 === 0 ? String(num) : num.toFixed(1);
  }

  function getLocalStorage() {
    try {
      return window.localStorage;
    } catch (error) {
      return null;
    }
  }

  function getUserIdentifier() {
    const storage = getLocalStorage();
    if (!storage) {
      return `ovts-${Math.random().toString(36).slice(2)}${Date.now().toString(36)}`;
    }

    let existing = storage.getItem(STORAGE_KEY);
    if (!existing) {
      existing =
        window.crypto && typeof window.crypto.randomUUID === "function"
          ? window.crypto.randomUUID()
          : `ovts-${Math.random().toString(36).slice(2)}${Date.now().toString(36)}`;
      storage.setItem(STORAGE_KEY, existing);
    }
    return existing;
  }

  function delay(ms) {
    return new Promise(function (resolve) {
      window.setTimeout(resolve, ms);
    });
  }

  function getRootUrl() {
    if (window.Shopify && window.Shopify.routes && window.Shopify.routes.root) {
      return window.Shopify.routes.root;
    }
    return "/";
  }

  function svgIcon(name) {
    const icons = {
      camera:
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 7h2.1l1.3-2h3.2l1.3 2H17a3 3 0 0 1 3 3v7a3 3 0 0 1-3 3H7a3 3 0 0 1-3-3v-7a3 3 0 0 1 3-3Zm5 10.2a3.7 3.7 0 1 0 0-7.4 3.7 3.7 0 0 0 0 7.4Z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"></path></svg>',
      upload:
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 15V6m0 0 3.5 3.5M12 6 8.5 9.5M5 17.5v1A1.5 1.5 0 0 0 6.5 20h11a1.5 1.5 0 0 0 1.5-1.5v-1" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"></path></svg>',
      close:
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m7 7 10 10M17 7 7 17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"></path></svg>',
      back:
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15 18 9 12l6-6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path></svg>',
      success:
        '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="2"></circle><path d="m8 12.5 2.4 2.4L16.5 9" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path></svg>',
      refresh:
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 12a9 9 0 0 1 15.3-6.4L21 8M21 4v4h-4M21 12a9 9 0 0 1-15.3 6.4L3 16M3 20v-4h4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"></path></svg>',
      sparkle:
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m12 3 1.5 4.5L18 9l-4.5 1.5L12 15l-1.5-4.5L6 9l4.5-1.5L12 3Zm7.5 10.5.8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8.8-2.2ZM5 15l1 2.8L8.8 19 6 20l-1 2.8L4 20l-2.8-1L4 17.8 5 15Z" fill="currentColor"></path></svg>',
      fit:
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 18 12-12M14 6h4v4M6 10v8h8" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"></path></svg>',
      privacy:
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 10V8a5 5 0 1 1 10 0v2m-8 0h6a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2v-6a2 2 0 0 1 2-2Z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"></path></svg>',
      plain:
        '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="5" width="14" height="14" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.8"></rect></svg>',
      distance:
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 4v16m8-16v16M4 8h4m8 0h4M4 16h4m8 0h4" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"></path></svg>',
      clothing:
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 5 3 2 3-2 4 4-2.4 2.1-1.6-1.2V20H8V9.9L6.4 11 4 9l5-4Z" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"></path></svg>',
      light:
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2v3m0 14v3M4.9 4.9l2.1 2.1m10 10 2.1 2.1M2 12h3m14 0h3M4.9 19.1 7 17m10-10 2.1-2.1M12 8a4 4 0 1 1 0 8 4 4 0 0 1 0-8Z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"></path></svg>',
      cart:
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 6h15l-1.3 7H8.2L7 4H4m5 13.5a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3Zm8 0a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3Z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"></path></svg>',
      arrow:
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14m-5-5 5 5-5 5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"></path></svg>'
    };
    return icons[name] || "";
  }

  function poseFigure(pose, quality) {
    const className = quality === "good" ? "ovts-pose-card is-good" : "ovts-pose-card is-bad";
    const poseClass = pose === "front" ? "is-front" : "is-side";
    return (
      '<div class="' +
      className +
      '">' +
      '<span class="ovts-pose-label">' +
      escapeHtml(quality === "good" ? "Good Example" : "Bad Example") +
      "</span>" +
      '<div class="ovts-pose-figure ' +
      poseClass +
      '">' +
      '<span class="ovts-pose-head"></span>' +
      '<span class="ovts-pose-body"></span>' +
      '<span class="ovts-pose-arm is-left"></span>' +
      '<span class="ovts-pose-arm is-right"></span>' +
      '<span class="ovts-pose-leg is-left"></span>' +
      '<span class="ovts-pose-leg is-right"></span>' +
      (quality === "bad" ? '<span class="ovts-pose-slash"></span>' : "") +
      "</div>" +
      "</div>"
    );
  }

  class OptimoVTSWidget {
    constructor(host, config) {
      this.host = host;
      this.config = config;
      this.userIdentifier = getUserIdentifier();
      this.bodyOverflow = "";
      this.overlay = null;
      this.toastTimer = null;
      this.analysisTicker = null;
      this.state = {
        isVisible: false,
        isOpen: false,
        stage: "idle",
        isChecking: true,
        error: "",
        notice: "",
        toast: "",
        form: {
          height: "",
          weight: "",
          gender: "male"
        },
        session: null,
        measurement: null,
        recommendation: null,
        selectedSize: "",
        heatmapBySize: {},
        fitScores: {},
        tryOnId: "",
        tryOnImageUrl: "",
        tryOnError: "",
        activeImageUrl: "",
        studioBackgrounds: [],
        studioResults: {},
        currentStudioBackgroundId: "",
        studioLoadingId: "",
        frontFile: null,
        sideFile: null,
        frontPreviewUrl: "",
        sidePreviewUrl: "",
        analysisStep: 0,
        generatingStep: 0,
        isHeatmapLoading: false,
        selectedStudioImageUrl: "",
        returningUser: false
      };

      this.handleHostClick = this.handleHostClick.bind(this);
      this.handleOverlayClick = this.handleOverlayClick.bind(this);
      this.handleOverlayChange = this.handleOverlayChange.bind(this);
      this.handleOverlaySubmit = this.handleOverlaySubmit.bind(this);
      this.handleOverlayInput = this.handleOverlayInput.bind(this);
    }

    async init() {
      this.renderHost();
      await this.checkEnabled();
    }

    renderHost() {
      this.host.innerHTML =
        '<button type="button" class="ovts-trigger" data-ovts-trigger hidden>' +
        '<span class="ovts-trigger__icon">' +
        svgIcon("camera") +
        "</span>" +
        '<span class="ovts-trigger__text">' +
        escapeHtml(this.config.buttonLabel || "Try it on virtually") +
        "</span>" +
        '<span class="ovts-trigger__arrow">' +
        svgIcon("arrow") +
        "</span>" +
        "</button>";

      const button = this.host.querySelector("[data-ovts-trigger]");
      if (button) {
        button.addEventListener("click", this.handleHostClick);
      }
    }

    async checkEnabled() {
      try {
        const response = await this.request(
          "/widget/check-enabled?shopify_product_gid=" + encodeURIComponent(this.config.product.gid),
          { withSession: false }
        );
        this.state.isVisible = Boolean(response && response.enabled);
      } catch (error) {
        this.state.isVisible = false;
      } finally {
        this.state.isChecking = false;
        const button = this.host.querySelector("[data-ovts-trigger]");
        if (button) {
          button.hidden = !this.state.isVisible;
        }
      }
    }

    ensureOverlay() {
      if (this.overlay) {
        return;
      }

      this.overlay = document.createElement("div");
      this.overlay.className = "ovts-overlay";
      this.overlay.hidden = true;
      this.overlay.addEventListener("click", this.handleOverlayClick);
      this.overlay.addEventListener("change", this.handleOverlayChange);
      this.overlay.addEventListener("submit", this.handleOverlaySubmit);
      this.overlay.addEventListener("input", this.handleOverlayInput);
      document.body.appendChild(this.overlay);
    }

    async open() {
      this.ensureOverlay();
      this.state.isOpen = true;
      this.state.stage = "booting";
      this.state.error = "";
      this.state.notice = "";
      this.renderOverlay();

      this.overlay.hidden = false;
      this.bodyOverflow = document.body.style.overflow;
      document.body.style.overflow = "hidden";

      await this.startSession();
    }

    close() {
      if (!this.overlay) {
        return;
      }
      this.state.isOpen = false;
      this.overlay.hidden = true;
      document.body.style.overflow = this.bodyOverflow;
      this.clearAnalysisTicker();
      this.clearToast();
    }

    async startSession() {
      this.state.returningUser = false;
      this.renderOverlay();

      try {
        const session = await this.request("/widget/sessions", {
          method: "POST",
          json: {
            shopify_product_gid: this.config.product.gid,
            user_identifier: this.userIdentifier
          },
          withSession: false
        });

        this.state.session = session;
        this.state.measurement = null;
        this.state.recommendation = null;
        this.state.selectedSize = "";
        this.state.heatmapBySize = {};
        this.state.fitScores = {};
        this.state.tryOnId = "";
        this.state.tryOnImageUrl = "";
        this.state.tryOnError = "";
        this.state.activeImageUrl = "";
        this.state.studioBackgrounds = [];
        this.state.studioResults = {};
        this.state.currentStudioBackgroundId = "";
        this.state.studioLoadingId = "";
        this.state.selectedStudioImageUrl = "";

        if (session.has_existing_measurements && session.measurement_id && session.photos_available) {
          this.state.returningUser = true;
          this.state.measurement = {
            measurement_id: session.measurement_id,
            measurements: session.measurements || {},
            confidence_score: null,
            cached: true
          };
          this.state.notice = "Using your saved measurements from the last 24 hours.";
          this.state.stage = "measurements";
        } else {
          this.state.notice = session.has_existing_measurements
            ? "Your saved measurements were found, but we need fresh photos to generate a new try-on."
            : "";
          this.state.stage = "setup";
        }

        this.trackEvent("widget_opened");
      } catch (error) {
        this.state.error = error.message || "Unable to start the Optimo VTS flow.";
        this.state.stage = "setup";
      }

      this.renderOverlay();
    }

    handleHostClick(event) {
      event.preventDefault();
      this.open();
    }

    handleOverlayInput(event) {
      const target = event.target;
      if (!(target instanceof HTMLInputElement || target instanceof HTMLSelectElement)) {
        return;
      }

      if (!target.name || !this.state.form.hasOwnProperty(target.name)) {
        return;
      }

      this.state.form[target.name] = target.value;
    }

    handleOverlayClick(event) {
      if (event.target === this.overlay) {
        this.close();
        return;
      }

      const backgroundTarget = event.target.closest("[data-background-id]");
      if (backgroundTarget) {
        event.preventDefault();
        this.generateStudio(backgroundTarget.getAttribute("data-background-id"), false);
        return;
      }

      const actionTarget = event.target.closest("[data-action]");
      if (!actionTarget) {
        return;
      }

      const action = actionTarget.getAttribute("data-action");
      if (!action) {
        return;
      }

      event.preventDefault();

      if (action === "close") {
        this.close();
      } else if (action === "back-to-setup") {
        this.state.stage = "setup";
        this.state.error = "";
        this.renderOverlay();
      } else if (action === "back-to-measurements") {
        this.state.stage = "measurements";
        this.state.error = "";
        this.renderOverlay();
      } else if (action === "camera-front") {
        this.triggerFileInput("front", "camera");
      } else if (action === "upload-front") {
        this.triggerFileInput("front", "upload");
      } else if (action === "camera-side") {
        this.triggerFileInput("side", "camera");
      } else if (action === "upload-side") {
        this.triggerFileInput("side", "upload");
      } else if (action === "retake-photos") {
        this.resetPhotoCapture();
      } else if (action === "continue-to-front") {
        this.goToFrontPose();
      } else if (action === "view-fit") {
        this.generateFit();
      } else if (action === "submit-studio" && this.state.selectedStudioImageUrl) {
        this.state.activeImageUrl = this.state.selectedStudioImageUrl;
        this.showToast("Studio look applied.");
        this.renderOverlay();
      } else if (action === "retry-studio" && this.state.currentStudioBackgroundId) {
        this.generateStudio(this.state.currentStudioBackgroundId, true);
      } else if (action === "add-to-cart") {
        this.addToCart();
      } else if (action === "view-cart") {
        window.location.href = getRootUrl() + "cart";
      } else if (action === "continue-shopping") {
        this.close();
      } else if (action === "select-size") {
        this.selectSize(actionTarget.getAttribute("data-size"));
      } else if (action === "share-look") {
        this.shareLook(actionTarget.getAttribute("data-network") || "share");
      }
    }

    handleOverlayChange(event) {
      const target = event.target;
      if (!(target instanceof HTMLInputElement) || target.type !== "file") {
        return;
      }

      const pose = target.getAttribute("data-pose");
      if (!pose || !target.files || !target.files[0]) {
        return;
      }

      this.handlePoseFile(pose, target.files[0]);
      target.value = "";
    }

    handleOverlaySubmit(event) {
      const form = event.target;
      if (!(form instanceof HTMLFormElement) || form.getAttribute("data-role") !== "setup-form") {
        return;
      }

      event.preventDefault();
      this.goToFrontPose();
    }

    triggerFileInput(pose, source) {
      const input = this.overlay.querySelector(
        'input[type="file"][data-pose="' + pose + '"][data-source="' + source + '"]'
      );
      if (input) {
        input.click();
      }
    }

    goToFrontPose() {
      const validationError = this.validateSetupForm();
      if (validationError) {
        this.state.error = validationError;
        this.state.stage = "setup";
        this.renderOverlay();
        return;
      }

      this.state.error = "";
      this.state.notice = "";
      this.state.stage = "front-pose";
      this.renderOverlay();
    }

    validateSetupForm() {
      const height = Number(this.state.form.height);
      const weight = Number(this.state.form.weight);

      if (!Number.isFinite(height) || height < 100 || height > 250) {
        return "Enter a height between 100 and 250 cm.";
      }

      if (!Number.isFinite(weight) || weight < 30 || weight > 300) {
        return "Enter a weight between 30 and 300 kg.";
      }

      if (!["male", "female", "unisex"].includes(this.state.form.gender)) {
        return "Select a valid gender option.";
      }

      return "";
    }

    setPreviewUrl(key, file) {
      const currentKey = key === "front" ? "frontPreviewUrl" : "sidePreviewUrl";
      const currentValue = this.state[currentKey];
      if (currentValue) {
        URL.revokeObjectURL(currentValue);
      }
      this.state[currentKey] = URL.createObjectURL(file);
    }

    resetPhotoCapture() {
      this.state.frontFile = null;
      this.state.sideFile = null;
      if (this.state.frontPreviewUrl) {
        URL.revokeObjectURL(this.state.frontPreviewUrl);
      }
      if (this.state.sidePreviewUrl) {
        URL.revokeObjectURL(this.state.sidePreviewUrl);
      }
      this.state.frontPreviewUrl = "";
      this.state.sidePreviewUrl = "";
      this.state.error = "";
      this.state.stage = "front-pose";
      this.renderOverlay();
    }

    async handlePoseFile(pose, file) {
      const currentPoseLabel = pose === "front" ? "front" : "side";
      this.state.error = "";
      this.state.notice = "Checking your " + currentPoseLabel + " pose...";
      this.renderOverlay();

      try {
        await this.validatePose(file, pose);

        if (pose === "front") {
          this.state.frontFile = file;
          this.setPreviewUrl("front", file);
          this.state.stage = "side-pose";
        } else {
          this.state.sideFile = file;
          this.setPreviewUrl("side", file);
        }

        this.trackEvent("photo_captured", { pose: pose });
      } catch (error) {
        this.state.error = error.message || "We could not use that image. Try another photo.";
      }

      this.state.notice = "";
      this.renderOverlay();

      if (pose === "side" && this.state.sideFile) {
        await this.extractMeasurements();
      }
    }

    async validatePose(file, pose) {
      const formData = new FormData();
      formData.append("image", file);
      formData.append("pose_type", pose);

      const response = await this.request("/measurements/validate", {
        method: "POST",
        formData: formData
      });

      if (!response || response.valid) {
        return;
      }

      const issues = Array.isArray(response.issues) ? response.issues.filter(Boolean) : [];
      throw new Error(issues.length ? issues.join(" ") : "We couldn't verify that pose. Try again.");
    }

    clearAnalysisTicker() {
      if (this.analysisTicker) {
        window.clearInterval(this.analysisTicker);
        this.analysisTicker = null;
      }
    }

    startAnalysisTicker(type) {
      this.clearAnalysisTicker();
      this.state.analysisStep = 0;
      this.state.generatingStep = 0;

      const steps = type === "analyzing" ? 2 : 3;
      this.analysisTicker = window.setInterval(() => {
        if (type === "analyzing") {
          this.state.analysisStep = Math.min(this.state.analysisStep + 1, steps);
        } else {
          this.state.generatingStep = Math.min(this.state.generatingStep + 1, steps);
        }
        this.renderOverlay();
      }, 1100);
    }

    async extractMeasurements() {
      if (!this.state.frontFile || !this.state.sideFile || !this.state.session) {
        return;
      }

      this.state.stage = "analyzing";
      this.state.error = "";
      this.startAnalysisTicker("analyzing");
      this.renderOverlay();

      try {
        const formData = new FormData();
        formData.append("front_image", this.state.frontFile);
        formData.append("side_image", this.state.sideFile);
        formData.append("height_cm", String(this.state.form.height));
        formData.append("weight_kg", String(this.state.form.weight));
        formData.append("gender", this.state.form.gender);

        const measurement = await this.request("/measurements/extract", {
          method: "POST",
          formData: formData
        });

        this.clearAnalysisTicker();
        this.state.measurement = measurement;
        this.state.notice = "";
        this.state.stage = "measurements";
        this.trackEvent("measurement_completed");
      } catch (error) {
        this.clearAnalysisTicker();
        this.state.error = error.message || "Measurement extraction failed.";
        this.state.stage = "side-pose";
      }

      this.renderOverlay();
    }

    async generateFit() {
      if (!this.state.session || !this.state.measurement) {
        this.state.error = "Measurement data is missing. Please retake your photos.";
        this.state.stage = "setup";
        this.renderOverlay();
        return;
      }

      this.state.stage = "generating";
      this.state.error = "";
      this.state.tryOnError = "";
      this.state.isHeatmapLoading = false;
      this.startAnalysisTicker("generating");
      this.renderOverlay();

      try {
        const recommendation = await this.request("/recommendations/size", {
          method: "POST",
          json: {
            measurement_id: this.state.measurement.measurement_id,
            product_id: this.state.session.product_id
          }
        });

        this.state.recommendation = recommendation;
        this.state.selectedSize = recommendation.recommended_size;
        this.state.fitScores = this.buildFitScoreMap(recommendation);
        this.trackEvent("size_recommended", {
          size: recommendation.recommended_size,
          fit_score: recommendation.fit_score
        });
        this.state.generatingStep = 1;
        this.renderOverlay();

        const heatmapPromise = this.fetchHeatmap(recommendation.recommended_size);
        const backgroundPromise = this.loadStudioBackgrounds();

        const tryOnStart = await this.request("/tryon/generate", {
          method: "POST",
          json: {
            product_id: this.state.session.product_id
          }
        });

        this.state.tryOnId = tryOnStart.try_on_id;
        await heatmapPromise;
        this.state.generatingStep = 2;
        this.renderOverlay();

        const tryOnStatus = await this.pollTryOn(tryOnStart.try_on_id);
        this.state.tryOnId = tryOnStatus.try_on_id;
        this.state.tryOnImageUrl = this.toProxyUrl(tryOnStatus.result_image_url);
        this.state.activeImageUrl = this.state.tryOnImageUrl;
        this.trackEvent("try_on_generated", {
          try_on_id: tryOnStatus.try_on_id
        });

        await backgroundPromise;
        this.clearAnalysisTicker();
        this.state.generatingStep = 3;
        this.state.stage = "results";
      } catch (error) {
        this.clearAnalysisTicker();
        this.state.error = error.message || "We couldn't generate your try-on.";
        this.state.stage = "measurements";
      }

      this.renderOverlay();
    }

    buildFitScoreMap(recommendation) {
      const map = {};
      if (!recommendation) {
        return map;
      }

      map[recommendation.recommended_size] = recommendation.fit_score;
      if (Array.isArray(recommendation.alternative_sizes)) {
        recommendation.alternative_sizes.forEach(function (entry) {
          if (entry && entry.size) {
            map[entry.size] = entry.fit_score;
          }
        });
      }

      return map;
    }

    async fetchHeatmap(size) {
      if (this.state.heatmapBySize[size]) {
        return this.state.heatmapBySize[size];
      }

      this.state.isHeatmapLoading = true;
      this.renderOverlay();

      try {
        const heatmap = await this.request("/heatmap/generate", {
          method: "POST",
          json: {
            measurement_id: this.state.measurement.measurement_id,
            product_id: this.state.session.product_id,
            size: size
          }
        });

        this.state.heatmapBySize[size] = heatmap;
        this.state.fitScores[size] = heatmap.overall_fit_score;
        return heatmap;
      } finally {
        this.state.isHeatmapLoading = false;
        this.renderOverlay();
      }
    }

    async pollTryOn(tryOnId) {
      for (let attempt = 0; attempt < 40; attempt += 1) {
        const status = await this.request("/tryon/" + encodeURIComponent(tryOnId) + "/status", {
          withSession: false
        });

        if (status.status === "completed" && status.result_image_url) {
          return status;
        }

        if (status.status === "failed") {
          throw new Error(status.error || status.message || "Try-on generation failed.");
        }

        await delay(2500);
      }

      throw new Error("Try-on generation timed out. Please try again.");
    }

    async loadStudioBackgrounds() {
      try {
        const list = await this.request(
          "/tryon/studio-backgrounds?gender=" + encodeURIComponent(this.state.form.gender || "unisex"),
          { withSession: false }
        );

        this.state.studioBackgrounds = Array.isArray(list)
          ? list.slice(0, 5).map((entry) => {
              return {
                id: entry.id,
                image_url: this.toProxyUrl(entry.image_url)
              };
            })
          : [];
      } catch (error) {
        this.state.studioBackgrounds = [];
      }
    }

    async generateStudio(backgroundId, forceRetry) {
      if (!this.state.tryOnId) {
        return;
      }

      if (!forceRetry && this.state.studioResults[backgroundId]) {
        this.state.currentStudioBackgroundId = backgroundId;
        this.state.selectedStudioImageUrl = this.state.studioResults[backgroundId];
        this.renderOverlay();
        return;
      }

      this.state.currentStudioBackgroundId = backgroundId;
      this.state.studioLoadingId = backgroundId;
      this.state.error = "";
      this.renderOverlay();

      try {
        const start = await this.request("/tryon/studio", {
          method: "POST",
          json: {
            try_on_id: this.state.tryOnId,
            studio_background_id: backgroundId
          },
          withSession: false
        });

        let imageUrl = start.result_image_url ? this.toProxyUrl(start.result_image_url) : "";

        if (!imageUrl) {
          const status = await this.pollTryOn(start.try_on_id);
          imageUrl = this.toProxyUrl(status.result_image_url);
        }

        this.state.studioResults[backgroundId] = imageUrl;
        this.state.selectedStudioImageUrl = imageUrl;
        this.showToast("Studio look ready.");
      } catch (error) {
        this.state.error = error.message || "Studio generation failed.";
      } finally {
        this.state.studioLoadingId = "";
        this.renderOverlay();
      }
    }

    async selectSize(size) {
      if (!size || size === this.state.selectedSize) {
        return;
      }

      this.state.selectedSize = size;
      this.trackEvent("size_selected", { size: size });
      this.renderOverlay();

      try {
        await this.fetchHeatmap(size);
      } catch (error) {
        this.state.error = error.message || "Unable to load fit heatmap for that size.";
        this.renderOverlay();
      }
    }

    resolveVariantForSize(size) {
      const variants = Array.isArray(this.config.product.variants) ? this.config.product.variants : [];
      if (!variants.length) {
        return null;
      }

      const sizeIndex = this.findSizeOptionIndex();
      if (sizeIndex === -1) {
        return variants.find((variant) => String(variant.id) === String(this.getCurrentVariantId())) || variants[0];
      }

      const currentVariant = this.getCurrentVariant();
      const currentOptions = currentVariant && Array.isArray(currentVariant.options) ? currentVariant.options : [];

      const exactMatch = variants.find(function (variant) {
        if (!Array.isArray(variant.options) || variant.options[sizeIndex] !== size) {
          return false;
        }

        return currentOptions.every(function (value, index) {
          if (index === sizeIndex) {
            return true;
          }
          return variant.options[index] === value;
        });
      });

      if (exactMatch && exactMatch.available) {
        return exactMatch;
      }

      const looseMatch = variants.find(function (variant) {
        return Array.isArray(variant.options) && variant.options[sizeIndex] === size;
      });

      return looseMatch || exactMatch || currentVariant || variants[0];
    }

    findSizeOptionIndex() {
      const options = Array.isArray(this.config.product.options) ? this.config.product.options : [];
      return options.findIndex(function (option) {
        return /size/i.test(option.name || "");
      });
    }

    getCurrentVariantId() {
      const cartForm =
        document.querySelector('form[action*="/cart/add"] [name="id"]') ||
        document.querySelector('input[name="id"][form]');

      if (cartForm && cartForm.value) {
        return cartForm.value;
      }

      const url = new URL(window.location.href);
      const variantParam = url.searchParams.get("variant");
      return variantParam || this.config.product.selectedVariantId;
    }

    getCurrentVariant() {
      const currentVariantId = String(this.getCurrentVariantId() || "");
      const variants = Array.isArray(this.config.product.variants) ? this.config.product.variants : [];
      return (
        variants.find(function (variant) {
          return String(variant.id) === currentVariantId;
        }) ||
        variants[0] ||
        null
      );
    }

    async addToCart() {
      const variant = this.resolveVariantForSize(this.state.selectedSize);
      if (!variant) {
        this.state.error = "We couldn't match that size to a product variant.";
        this.renderOverlay();
        return;
      }

      if (!variant.available) {
        this.state.error = "That size is currently sold out.";
        this.renderOverlay();
        return;
      }

      try {
        const response = await window.fetch(getRootUrl() + "cart/add.js", {
          method: "POST",
          headers: {
            Accept: "application/json",
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            id: variant.id,
            quantity: 1
          })
        });

        if (!response.ok) {
          const errorBody = await response.json().catch(function () {
            return null;
          });
          throw new Error((errorBody && errorBody.description) || "Unable to add the selected size to cart.");
        }

        this.trackEvent("added_to_cart", {
          product_id: this.config.product.id,
          variant_id: variant.id,
          size: this.state.selectedSize
        });

        this.state.stage = "success";
        this.state.error = "";
      } catch (error) {
        this.state.error = error.message || "Unable to add that size to your cart.";
      }

      this.renderOverlay();
    }

    async shareLook(network) {
      const shareUrl = window.location.href;
      const shareText = "See how this fit looks with Optimo VTS.";

      if (navigator.share) {
        try {
          await navigator.share({
            title: document.title,
            text: shareText,
            url: shareUrl
          });
          return;
        } catch (error) {
          /* no-op */
        }
      }

      if (navigator.clipboard && navigator.clipboard.writeText) {
        try {
          await navigator.clipboard.writeText(shareUrl);
          this.showToast(network + " share link copied.");
          this.renderOverlay();
          return;
        } catch (error) {
          /* no-op */
        }
      }

      window.open(shareUrl, "_blank", "noopener,noreferrer");
    }

    toProxyUrl(path) {
      if (!path) {
        return "";
      }
      if (/^https?:\/\//i.test(path)) {
        return path;
      }
      if (path.startsWith("/api/v1/")) {
        return this.config.proxyBase + path.replace(/^\/api\/v1/, "");
      }
      if (path.startsWith("/")) {
        return this.config.proxyBase + path;
      }
      return this.config.proxyBase + "/" + path.replace(/^\/+/, "");
    }

    getSelectedHeatmap() {
      return this.state.heatmapBySize[this.state.selectedSize] || null;
    }

    getVisibleSizes() {
      if (!this.state.recommendation || !Array.isArray(this.state.recommendation.all_sizes)) {
        return [];
      }
      return this.state.recommendation.all_sizes.slice(0, 5);
    }

    getMeasurementMarkup() {
      if (!this.state.measurement || !this.state.measurement.measurements) {
        return '<p class="ovts-empty-copy">Measurements will appear here after analysis.</p>';
      }

      const measurements = this.state.measurement.measurements;
      const rows = MEASUREMENT_ROWS.map(function (entry) {
        const key = entry[0];
        const label = entry[1];
        const value = formatNumber(measurements[key]);
        if (value == null) {
          return "";
        }
        return (
          '<div class="ovts-measure-row">' +
          '<span>' +
          escapeHtml(label) +
          "</span>" +
          '<strong>' +
          escapeHtml(value) +
          " cm</strong>" +
          "</div>"
        );
      }).join("");

      return rows || '<p class="ovts-empty-copy">We found only partial measurement data.</p>';
    }

    getSizeReasoning() {
      if (!this.state.recommendation) {
        return "We compare your measurements against this product's fit profile to surface the closest match.";
      }

      const size = this.state.selectedSize || this.state.recommendation.recommended_size;
      const alternative = Array.isArray(this.state.recommendation.alternative_sizes)
        ? this.state.recommendation.alternative_sizes.find(function (entry) {
            return entry.size === size;
          })
        : null;

      if (size === this.state.recommendation.recommended_size) {
        const fitAnalysis = this.state.recommendation.fit_analysis || {};
        const strongAreas = Object.keys(fitAnalysis)
          .filter(function (key) {
            return fitAnalysis[key] && fitAnalysis[key].status === "perfect_fit";
          })
          .slice(0, 2)
          .map(function (key) {
            return key.replace(/_/g, " ");
          });

        if (strongAreas.length) {
          return (
            "Based on your key measurements, size " +
            size +
            " stays balanced through the " +
            strongAreas.join(" and ") +
            " for the cleanest fit."
          );
        }
      }

      if (alternative && alternative.note) {
        return "Size " + size + " is available too: " + alternative.note + ".";
      }

      return (
        "Size " +
        size +
        " remains the closest match for this garment based on your measurements and the product size chart."
      );
    }

    showToast(message) {
      this.clearToast();
      this.state.toast = message;
      this.toastTimer = window.setTimeout(() => {
        this.state.toast = "";
        this.renderOverlay();
      }, 2200);
    }

    clearToast() {
      if (this.toastTimer) {
        window.clearTimeout(this.toastTimer);
        this.toastTimer = null;
      }
      this.state.toast = "";
    }

    trackEvent(eventType, eventData) {
      if (!this.state.session) {
        return;
      }

      this.request("/analytics/events", {
        method: "POST",
        json: {
          event_type: eventType,
          session_id: this.state.session.session_id,
          event_data: eventData || {}
        }
      }).catch(function () {
        return null;
      });
    }

    async request(path, options) {
      const requestOptions = options || {};
      const method = requestOptions.method || "GET";
      const headers = new Headers({
        Accept: "application/json"
      });

      if (requestOptions.headers) {
        Object.keys(requestOptions.headers).forEach(function (key) {
          headers.set(key, requestOptions.headers[key]);
        });
      }

      if (requestOptions.withSession !== false && this.state.session && this.state.session.session_id) {
        headers.set("X-Session-ID", this.state.session.session_id);
      }

      let body = undefined;

      if (requestOptions.json) {
        headers.set("Content-Type", "application/json");
        body = JSON.stringify(requestOptions.json);
      } else if (requestOptions.formData) {
        body = requestOptions.formData;
      }

      const requestUrl = new URL(this.config.proxyBase + path, window.location.origin);

      if (requestOptions.withSession !== false && this.state.session && this.state.session.session_id) {
        requestUrl.searchParams.set("session_id", this.state.session.session_id);
      }

      const response = await window.fetch(requestUrl.toString(), {
        method: method,
        headers: headers,
        body: body
      });

      if (!response.ok) {
        let message = "Request failed.";
        try {
          const payload = await response.json();
          message = payload.detail || payload.error || payload.message || message;
        } catch (error) {
          try {
            message = await response.text();
          } catch (innerError) {
            message = "Request failed.";
          }
        }
        throw new Error(message);
      }

      if (response.status === 204) {
        return null;
      }

      const contentType = response.headers.get("content-type") || "";
      if (contentType.indexOf("application/json") !== -1) {
        return response.json();
      }

      return response.text();
    }

    renderOverlay() {
      if (!this.overlay) {
        return;
      }

      const toastMarkup = this.state.toast
        ? '<div class="ovts-toast">' + escapeHtml(this.state.toast) + "</div>"
        : "";
      const errorMarkup = this.state.error
        ? '<div class="ovts-banner is-error">' + escapeHtml(this.state.error) + "</div>"
        : "";
      const noticeMarkup = this.state.notice
        ? '<div class="ovts-banner is-note">' + escapeHtml(this.state.notice) + "</div>"
        : "";

      this.overlay.innerHTML =
        '<div class="ovts-modal" role="dialog" aria-modal="true" aria-label="Optimo VTS virtual try-on">' +
        '<button type="button" class="ovts-close" data-action="close" aria-label="Close">' +
        svgIcon("close") +
        "</button>" +
        toastMarkup +
        errorMarkup +
        noticeMarkup +
        this.renderStage() +
        "</div>";
    }

    renderStage() {
      switch (this.state.stage) {
        case "booting":
          return this.renderBooting();
        case "setup":
          return this.renderSetup();
        case "front-pose":
          return this.renderPoseStep("front");
        case "side-pose":
          return this.renderPoseStep("side");
        case "analyzing":
          return this.renderAnalyzing();
        case "measurements":
          return this.renderMeasurements();
        case "generating":
          return this.renderGenerating();
        case "results":
          return this.renderResults();
        case "success":
          return this.renderSuccess();
        default:
          return this.renderBooting();
      }
    }

    renderBooting() {
      return (
        '<div class="ovts-stage ovts-stage--center">' +
        '<div class="ovts-spinner"></div>' +
        "<h2>Preparing your virtual try-on</h2>" +
        "<p>Loading the Optimo VTS flow for " +
        escapeHtml(this.config.product.title) +
        ".</p></div>"
      );
    }

    renderSetup() {
      return (
        '<div class="ovts-stage">' +
        '<div class="ovts-stage-head"><h2>Quick Setup <span>Guide</span></h2><p>Follow these simple steps for the best results.</p></div>' +
        '<form class="ovts-card ovts-setup-form" data-role="setup-form">' +
        "<h3>Add your details</h3>" +
        '<label class="ovts-field"><span>Height</span><div class="ovts-input-wrap"><input type="number" name="height" min="100" max="250" step="0.1" value="' +
        escapeHtml(this.state.form.height) +
        '" placeholder="175" required><em>cm</em></div></label>' +
        '<label class="ovts-field"><span>Weight</span><div class="ovts-input-wrap"><input type="number" name="weight" min="30" max="300" step="0.1" value="' +
        escapeHtml(this.state.form.weight) +
        '" placeholder="70" required><em>kg</em></div></label>' +
        '<label class="ovts-field"><span>Gender</span><div class="ovts-select-wrap"><select name="gender">' +
        '<option value="male"' +
        (this.state.form.gender === "male" ? " selected" : "") +
        ">Male</option>" +
        '<option value="female"' +
        (this.state.form.gender === "female" ? " selected" : "") +
        ">Female</option>" +
        '<option value="unisex"' +
        (this.state.form.gender === "unisex" ? " selected" : "") +
        ">Prefer not to say</option></select></div></label></form>" +
        '<div class="ovts-guides">' +
        this.renderGuideRow("plain", "Plain Background", "Position yourself in front of a plain wall.") +
        this.renderGuideRow("distance", "Stand 1.5m Away", "Step back so your full body is visible in frame.") +
        this.renderGuideRow("clothing", "Fitted Clothing", "Wear fitting clothes for the cleanest measurement read.") +
        this.renderGuideRow("light", "Good Lighting", "Stand in a well-lit area facing the light source.") +
        '</div><button type="button" class="ovts-primary" data-action="continue-to-front">Continue</button>' +
        '<div class="ovts-privacy-note"><strong>Your Privacy Matters</strong><span>Your photo is processed instantly and deleted within 1 hour. We never store or share your image. GDPR compliant.</span></div></div>'
      );
    }

    renderGuideRow(icon, title, text) {
      return (
        '<div class="ovts-guide-row"><span class="ovts-guide-icon">' +
        svgIcon(icon) +
        "</span><div><strong>" +
        escapeHtml(title) +
        "</strong><p>" +
        escapeHtml(text) +
        "</p></div></div>"
      );
    }

    renderPoseStep(pose) {
      const isFront = pose === "front";
      return (
        '<div class="ovts-stage">' +
        '<div class="ovts-pose-headline">' +
        (isFront
          ? ""
          : '<button type="button" class="ovts-inline-back" data-action="back-to-setup">' + svgIcon("back") + "Back</button>") +
        "<h2>Position: <span>" +
        escapeHtml(isFront ? "Front Pose" : "Side Pose") +
        "</span></h2></div>" +
        '<div class="ovts-pose-grid">' +
        poseFigure(pose, "good") +
        poseFigure(pose, "bad") +
        "</div>" +
        '<div class="ovts-pose-actions">' +
        '<button type="button" class="ovts-primary" data-action="' +
        escapeHtml(isFront ? "camera-front" : "camera-side") +
        '"><span class="ovts-btn-icon">' +
        svgIcon("camera") +
        "</span>Take Photo</button>" +
        '<button type="button" class="ovts-secondary" data-action="' +
        escapeHtml(isFront ? "upload-front" : "upload-side") +
        '"><span class="ovts-btn-icon">' +
        svgIcon("upload") +
        "</span>" +
        escapeHtml(isFront ? "Upload Front Pose" : "Upload Side Pose") +
        '</button></div><input class="ovts-file-input" type="file" accept="image/*" capture="environment" data-pose="' +
        escapeHtml(pose) +
        '" data-source="camera"><input class="ovts-file-input" type="file" accept="image/*" data-pose="' +
        escapeHtml(pose) +
        '" data-source="upload"></div>'
      );
    }

    renderAnalyzing() {
      const progress = [36, 68, 100][this.state.analysisStep] || 24;
      return (
        '<div class="ovts-stage ovts-stage--center"><div class="ovts-spinner is-ring"></div><h2>Analyzing Your Photo</h2><p>Our AI is extracting 20+ body measurements.</p>' +
        this.renderProgressBar(progress) +
        '<div class="ovts-task-list">' +
        this.renderTask("Detecting pose landmarks", this.state.analysisStep >= 0) +
        this.renderTask("Extracting measurements", this.state.analysisStep >= 1) +
        this.renderTask("Calculating confidence", this.state.analysisStep >= 2) +
        "</div></div>"
      );
    }

    renderMeasurements() {
      const confidence =
        this.state.measurement && this.state.measurement.confidence_score != null
          ? Math.round(Number(this.state.measurement.confidence_score) * 100)
          : 86;

      return (
        '<div class="ovts-stage"><div class="ovts-results-top"><div class="ovts-complete-head"><span class="ovts-check">' +
        svgIcon("success") +
        '</span><div><h2>Measurement Complete!</h2><p>' +
        escapeHtml(
          this.state.returningUser
            ? "We found your saved body profile and kept it ready for this product."
            : "We have extracted 20+ body dimensions with high accuracy."
        ) +
        '</p></div></div><div class="ovts-confidence">Confidence Score: <strong>' +
        escapeHtml(String(confidence)) +
        '%</strong></div></div><div class="ovts-measurement-grid"><section class="ovts-card"><h3><span class="ovts-card-icon">' +
        svgIcon("fit") +
        '</span>Your Measurements</h3><div class="ovts-measure-list">' +
        this.getMeasurementMarkup() +
        '</div><button type="button" class="ovts-link-button" data-action="retake-photos">' +
        svgIcon("refresh") +
        'Retake Photo</button></section><section class="ovts-card"><h3><span class="ovts-card-icon">' +
        svgIcon("sparkle") +
        "</span>What's Next?</h3><p class=\"ovts-what-next\">See your perfect fit.</p><div class=\"ovts-feature-stack\">" +
        this.renderFeatureTile("Fit Heatmap", "See exactly where the garment will be loose, snug, or right on your body.") +
        this.renderFeatureTile("Size Recommendation", "Get AI-powered size suggestions with confidence scores.") +
        this.renderFeatureTile("Virtual Try-On", "Visualize the product on your body before purchasing.") +
        '</div><button type="button" class="ovts-primary ovts-primary--wide" data-action="view-fit">View Your Fit <span class="ovts-inline-icon">' +
        svgIcon("arrow") +
        '</span></button><div class="ovts-subtle-note">Your measurements are saved for 1 year. Photo deleted in 1 hour.</div></section></div></div>'
      );
    }

    renderFeatureTile(title, text) {
      return '<div class="ovts-feature-tile"><strong>' + escapeHtml(title) + "</strong><p>" + escapeHtml(text) + "</p></div>";
    }

    renderGenerating() {
      const progress = [24, 58, 84, 100][this.state.generatingStep] || 18;
      return (
        '<div class="ovts-stage ovts-stage--center"><div class="ovts-spinner is-ring"></div><h2>Generating your Fit</h2><p>Our AI is creating virtual try-on for you.</p>' +
        this.renderProgressBar(progress) +
        '<div class="ovts-task-list">' +
        this.renderTask("Loading Optimo 4o Virtual Studio", this.state.generatingStep >= 1) +
        this.renderTask("Fitting to your size", this.state.generatingStep >= 2) +
        this.renderTask("Enhancing overlay", this.state.generatingStep >= 3) +
        "</div></div>"
      );
    }

    renderTask(label, complete) {
      const icon = complete
        ? '<span class="ovts-task-status is-complete">' + svgIcon("success") + "</span>"
        : '<span class="ovts-task-status"></span>';
      return '<div class="ovts-task-row">' + icon + "<span>" + escapeHtml(label) + "</span></div>";
    }

    renderProgressBar(value) {
      return (
        '<div class="ovts-progress"><span style="width:' +
        escapeHtml(String(value)) +
        '%;background:' +
        (value > 0 ? ACTIVE_PROGRESS_COLOR : IDLE_PROGRESS_COLOR) +
        ';"></span></div>'
      );
    }

    renderResults() {
      const heatmap = this.getSelectedHeatmap();
      const visibleSizes = this.getVisibleSizes();
      const mainImage = this.state.activeImageUrl || this.state.tryOnImageUrl || this.config.product.featuredImage;
      const selectedVariant = this.resolveVariantForSize(this.state.selectedSize) || this.getCurrentVariant();
      const price = selectedVariant && selectedVariant.price ? selectedVariant.price : this.config.product.price;

      return (
        '<div class="ovts-stage ovts-stage--results"><button type="button" class="ovts-inline-back is-top" data-action="back-to-measurements">' +
        svgIcon("back") +
        'Back to measurements</button><div class="ovts-results-grid"><section class="ovts-hero-panel"><div class="ovts-panel-head"><div><h3>Virtual Try-On</h3><span class="ovts-powered">Powered by Optimo 4o</span></div></div><div class="ovts-tryon-preview">' +
        (mainImage
          ? '<img src="' + escapeHtml(mainImage) + '" alt="Virtual try-on result" loading="lazy">'
          : '<div class="ovts-image-placeholder">Generating your look...</div>') +
        '</div></section><section class="ovts-side-panel"><div class="ovts-studio-box"><div class="ovts-panel-head"><h4>Studio Shoots</h4></div><div class="ovts-studio-grid">' +
        this.renderStudioTiles() +
        '</div><div class="ovts-studio-actions"><button type="button" class="ovts-primary ovts-primary--small" data-action="submit-studio"' +
        (this.state.selectedStudioImageUrl ? "" : " disabled") +
        '>Submit</button><button type="button" class="ovts-secondary ovts-secondary--small" data-action="retry-studio"' +
        (this.state.currentStudioBackgroundId ? "" : " disabled") +
        '>Retry</button></div><div class="ovts-share-box"><span>Share your look</span><div class="ovts-share-row">' +
        this.renderShareButton("Instagram", "#ff4f75") +
        this.renderShareButton("TikTok", "#111111") +
        this.renderShareButton("Snapchat", "#ffdd00") +
        this.renderShareButton("Facebook", "#4267B2") +
        '</div></div></div></section><section class="ovts-heatmap-panel"><div class="ovts-panel-head"><div><h3>Heat Map</h3><span class="ovts-powered">Powered by Optimo 4o</span></div></div><div class="ovts-heatmap-visual"><div class="ovts-heatmap-body"><span class="ovts-heatmap-silhouette"></span><div class="ovts-heatmap-overlay">' +
        (heatmap && heatmap.svg_overlay ? heatmap.svg_overlay : FALLBACK_HEATMAP) +
        '</div></div><div class="ovts-heatmap-legend"><span><i class="is-loose"></i>Loose</span><span><i class="is-snug"></i>Snug</span><span><i class="is-tight"></i>Tight</span></div><p>Interactive heat map showing fit on your body.</p></div></section><section class="ovts-fit-panel"><div class="ovts-panel-head"><h3>Select Your Size</h3></div><div class="ovts-size-grid">' +
        visibleSizes
          .map(
            (size) =>
              '<button type="button" class="ovts-size-chip' +
              (size === this.state.selectedSize ? " is-active" : "") +
              '" data-action="select-size" data-size="' +
              escapeHtml(size) +
              '"><strong>' +
              escapeHtml(size) +
              "</strong><span>" +
              escapeHtml(this.state.fitScores[size] != null ? String(this.state.fitScores[size]) + "%" : "--") +
              "</span></button>"
          )
          .join("") +
        '</div><div class="ovts-fit-confidence"><div class="ovts-fit-confidence__head"><span>Fit Confidence</span><strong>' +
        escapeHtml(String(this.state.fitScores[this.state.selectedSize] || this.state.recommendation.fit_score || 89)) +
        '%</strong></div><div class="ovts-fit-bar"><span style="width:' +
        escapeHtml(String(this.state.fitScores[this.state.selectedSize] || this.state.recommendation.fit_score || 89)) +
        '%"></span></div></div><div class="ovts-fit-card"><div class="ovts-fit-row"><span>Recommended Size</span><strong>' +
        escapeHtml(this.state.recommendation.recommended_size) +
        '</strong></div><div class="ovts-fit-row"><span>Product</span><strong>' +
        escapeHtml(this.config.product.title) +
        '</strong></div><div class="ovts-fit-row"><span>Selected Size</span><strong>' +
        escapeHtml(this.state.selectedSize) +
        '</strong></div><div class="ovts-fit-row"><span>Price</span><strong>$' +
        escapeHtml(price || "") +
        '</strong></div></div><button type="button" class="ovts-primary ovts-primary--wide" data-action="add-to-cart">Add Size To Cart</button><div class="ovts-size-why"><h4>Why size ' +
        escapeHtml(this.state.selectedSize) +
        '?</h4><p>' +
        escapeHtml(this.getSizeReasoning()) +
        "</p></div></section></div></div>"
      );
    }

    renderStudioTiles() {
      if (!this.state.studioBackgrounds.length) {
        return '<div class="ovts-empty-copy">Studio looks will appear here after your fit is ready.</div>';
      }

      return this.state.studioBackgrounds
        .map((background) => {
          const image = this.state.studioResults[background.id] || background.image_url;
          const isLoading = this.state.studioLoadingId === background.id;
          const isActive = this.state.currentStudioBackgroundId === background.id;
          return (
            '<button type="button" class="ovts-studio-tile' +
            (isActive ? " is-active" : "") +
            '" data-background-id="' +
            escapeHtml(background.id) +
            '">' +
            (image
              ? '<img src="' + escapeHtml(image) + '" alt="Studio look option" loading="lazy">'
              : '<span class="ovts-studio-plus">+</span>') +
            (isLoading ? '<span class="ovts-studio-loading">Generating...</span>' : "") +
            "</button>"
          );
        })
        .join("");
    }

    renderShareButton(label, color) {
      return '<button type="button" class="ovts-share-chip" data-action="share-look" data-network="' + escapeHtml(label) + '" style="--share-color:' + escapeHtml(color) + '"><span>' + escapeHtml(label.slice(0, 2)) + "</span></button>";
    }

    renderSuccess() {
      const score = this.state.fitScores[this.state.selectedSize] || this.state.recommendation.fit_score || 89;
      return (
        '<div class="ovts-stage ovts-stage--center ovts-stage--success"><span class="ovts-check is-large">' +
        svgIcon("success") +
        "</span><h2>Perfect Fit Added</h2><p>Size " +
        escapeHtml(this.state.selectedSize) +
        " added to your cart with " +
        escapeHtml(String(score)) +
        '% confidence match.</p><button type="button" class="ovts-primary ovts-primary--wide" data-action="view-cart"><span class="ovts-btn-icon">' +
        svgIcon("cart") +
        '</span>View Cart</button><button type="button" class="ovts-secondary ovts-secondary--wide" data-action="continue-shopping">Continue Shopping</button><div class="ovts-delete-note">Your photo was deleted. We value your privacy.</div></div>'
      );
    }
  }

  function initWidgets() {
    const configNodes = document.querySelectorAll("script[data-optimo-vts-config]");
    configNodes.forEach(function (node) {
      if (node.dataset.optimoVtsMounted === "true") {
        return;
      }

      const blockId = node.getAttribute("data-optimo-vts-config");
      const host = document.getElementById("optimo-vts-widget-" + blockId);
      if (!host) {
        return;
      }

      try {
        const config = JSON.parse(node.textContent || "{}");
        const widget = new OptimoVTSWidget(host, config);
        node.dataset.optimoVtsMounted = "true";
        widget.init();
      } catch (error) {
        host.innerHTML = "";
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initWidgets);
  } else {
    initWidgets();
  }
})();
