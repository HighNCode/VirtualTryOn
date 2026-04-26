(function () {
  const STORAGE_KEY = "optimo-vts-user-id";
  const FLOW_SNAPSHOT_TTL_MS = 60 * 60 * 1000;
  const FLOW_SNAPSHOT_PREFIX = "optimo-vts-flow";
  const FLOW_POINTER_PREFIX = "optimo-vts-flow-pointer";
  const ACTIVE_PROGRESS_COLOR = "linear-gradient(90deg, #a4006e 0%, #f3001f 100%)";
  const IDLE_PROGRESS_COLOR = "#d7d5d8";
  const HEATMAP_VIEWBOX = "0 0 300 620";
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

  const FIT_LABEL_ORDER = ["tight", "snug", "perfect", "loose", "very_loose"];
  const FIT_LABEL_TITLES = {
    tight: "Tight",
    snug: "Snug",
    perfect: "Perfect",
    loose: "Loose",
    very_loose: "Very loose"
  };
  const FIT_COLOR_ANCHORS = [
    { delta: -6, color: "#C04020", label: "tight" },
    { delta: -2, color: "#E87040", label: "snug" },
    { delta: 0, color: "#2D9E5A", label: "perfect" },
    { delta: 2, color: "#4A8FD4", label: "loose" },
    { delta: 6, color: "#1A5FAA", label: "very_loose" }
  ];

  const HEATMAP_MEASUREMENT_LABELS = {
    height: "Height",
    shoulder_width: "Shoulder width",
    arm_length: "Arm length",
    torso_length: "Torso length",
    inseam: "Inseam",
    chest: "Chest",
    waist: "Waist",
    hip: "Hip",
    neck: "Neck",
    thigh: "Thigh",
    upper_arm: "Upper arm",
    wrist: "Wrist",
    calf: "Calf",
    ankle: "Ankle",
    bicep: "Bicep"
  };

  const HEATMAP_CATEGORY_MEASUREMENTS = {
    tops: ["neck", "shoulder_width", "chest", "torso_length", "waist", "arm_length", "upper_arm", "bicep", "wrist"],
    outerwear: ["neck", "shoulder_width", "chest", "torso_length", "waist", "arm_length", "upper_arm", "bicep", "wrist"],
    bottoms: ["waist", "hip", "thigh", "calf", "ankle", "inseam"],
    dresses: ["neck", "shoulder_width", "chest", "torso_length", "waist", "hip", "upper_arm", "bicep", "wrist", "thigh", "calf", "ankle"],
    unknown: ["height", "shoulder_width", "arm_length", "torso_length", "inseam", "chest", "waist", "hip", "neck", "thigh", "upper_arm", "wrist", "calf", "ankle", "bicep"]
  };

  const HEATMAP_SEGMENTS = [
    { id: "neck", measurementKey: "neck", label: "Neck", d: "M130 78 L170 78 L176 104 L124 104 Z" },
    { id: "shoulders", measurementKey: "shoulder_width", label: "Shoulder width", d: "M60 106 L240 106 L256 140 L44 140 Z" },
    { id: "chest", measurementKey: "chest", label: "Chest", d: "M74 140 L226 140 L216 204 L84 204 Z" },
    { id: "torso", measurementKey: "torso_length", label: "Torso length", d: "M98 204 L202 204 L194 318 L106 318 Z" },
    { id: "waist", measurementKey: "waist", label: "Waist", d: "M82 254 L218 254 L210 318 L90 318 Z" },
    { id: "hips", measurementKey: "hip", label: "Hip", d: "M70 318 L230 318 L220 378 L80 378 Z" },

    { id: "arm_length_left", measurementKey: "arm_length", label: "Arm length", d: "M50 138 L86 146 L34 334 L2 324 Z" },
    { id: "arm_length_right", measurementKey: "arm_length", label: "Arm length", d: "M250 138 L214 146 L266 334 L298 324 Z" },
    { id: "upper_arm_left", measurementKey: "upper_arm", label: "Upper arm", d: "M56 144 L92 152 L64 254 L30 242 Z" },
    { id: "upper_arm_right", measurementKey: "upper_arm", label: "Upper arm", d: "M244 144 L208 152 L236 254 L270 242 Z" },
    { id: "bicep_left", measurementKey: "bicep", label: "Bicep", d: "M50 186 L80 194 L74 230 L44 220 Z" },
    { id: "bicep_right", measurementKey: "bicep", label: "Bicep", d: "M250 186 L220 194 L226 230 L256 220 Z" },
    { id: "wrist_left", measurementKey: "wrist", label: "Wrist", d: "M10 312 L42 320 L36 352 L6 344 Z" },
    { id: "wrist_right", measurementKey: "wrist", label: "Wrist", d: "M290 312 L258 320 L264 352 L294 344 Z" },

    { id: "thigh_left", measurementKey: "thigh", label: "Thigh", d: "M88 378 L140 378 L138 486 L94 486 Z" },
    { id: "thigh_right", measurementKey: "thigh", label: "Thigh", d: "M160 378 L212 378 L206 486 L162 486 Z" },
    { id: "inseam_left", measurementKey: "inseam", label: "Inseam", d: "M140 380 L148 380 L146 486 L138 486 Z" },
    { id: "inseam_right", measurementKey: "inseam", label: "Inseam", d: "M152 380 L160 380 L162 486 L154 486 Z" },
    { id: "calf_left", measurementKey: "calf", label: "Calf", d: "M96 486 L130 486 L126 574 L100 574 Z" },
    { id: "calf_right", measurementKey: "calf", label: "Calf", d: "M170 486 L204 486 L200 574 L174 574 Z" },
    { id: "ankle_left", measurementKey: "ankle", label: "Ankle", d: "M100 574 L126 574 L124 606 L104 606 Z" },
    { id: "ankle_right", measurementKey: "ankle", label: "Ankle", d: "M174 574 L200 574 L196 606 L176 606 Z" }
  ];

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

  function getSessionStorage() {
    try {
      return window.sessionStorage;
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

  function isThemeEditorDesignMode() {
    return Boolean(window.Shopify && window.Shopify.designMode);
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
        fitGeneratedAt: 0,
        tryOnError: "",
        limitCode: "",
        limitResetAt: "",
        limitTimezone: "",
        limitMessage: "",
        activeImageUrl: "",
        lastGoodImageUrl: "",
        imageLoadError: "",
        failedImageUrl: "",
        lastImageErrorUrl: "",
        studioBackgrounds: [],
        studioBackgroundsError: false,
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
        returningUser: false,
        activeHeatmapZone: "",
        customerLoginRequired: false,
        customerLoggedIn: false,
        loginMessage: "",
        widgetColor: "",
        productViewTracked: false,
        themeDetectionBackfillSent: false
      };

      this.handleHostClick = this.handleHostClick.bind(this);
      this.handleOverlayClick = this.handleOverlayClick.bind(this);
      this.handleOverlayChange = this.handleOverlayChange.bind(this);
      this.handleOverlaySubmit = this.handleOverlaySubmit.bind(this);
      this.handleOverlayInput = this.handleOverlayInput.bind(this);
      this.handleOverlayMouseOver = this.handleOverlayMouseOver.bind(this);
      this.handleOverlayMouseOut = this.handleOverlayMouseOut.bind(this);
      this.handleOverlayAssetError = this.handleOverlayAssetError.bind(this);
      this.handleOverlayAssetLoad = this.handleOverlayAssetLoad.bind(this);
    }

    async init() {
      this.renderHost();
      if (isThemeEditorDesignMode()) {
        // In Shopify theme editor we always render the trigger so merchants can
        // place and preview the block even when runtime scope rules would hide it.
        this.state.isVisible = true;
        this.state.isChecking = false;
        const button = this.host.querySelector("[data-ovts-trigger]");
        if (button) {
          button.hidden = false;
        }
        this.notifyThemeDetected();
        return;
      }
      await this.checkEnabled();
    }

    notifyThemeDetected() {
      if (this.state.themeDetectionBackfillSent) {
        return;
      }
      this.state.themeDetectionBackfillSent = true;
      this.request("/widget/theme-detected", {
        method: "POST",
        withSession: false
      }).catch(function () {
        this.state.themeDetectionBackfillSent = false;
        return null;
      }.bind(this));
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
      this.applyTriggerColor(this.state.widgetColor);
    }

    normalizeHexColor(value) {
      const candidate = String(value || "").trim();
      if (!/^#[0-9A-Fa-f]{6}$/.test(candidate)) {
        return "";
      }
      return candidate.toUpperCase();
    }

    applyTriggerColor(color) {
      const normalized = this.normalizeHexColor(color);
      if (!normalized) {
        this.host.style.removeProperty("--ovts-trigger-background");
        this.state.widgetColor = "";
        return;
      }
      this.host.style.setProperty("--ovts-trigger-background", normalized);
      this.state.widgetColor = normalized;
    }

    async checkEnabled() {
      try {
        const response = await this.request(this.buildCheckEnabledPath(), { withSession: false });
        this.applyEligibilityResponse(response);
        this.state.isVisible = Boolean(response && response.enabled);
        this.notifyThemeDetected();
      } catch (error) {
        this.state.isVisible = false;
      } finally {
        this.state.isChecking = false;
        const button = this.host.querySelector("[data-ovts-trigger]");
        if (button) {
          button.hidden = !this.state.isVisible;
        }
        if (!this.state.productViewTracked) {
          this.state.productViewTracked = true;
          this.trackEvent(
            "product_viewed",
            { product_id: this.config.product.id },
            { allowWithoutSession: true }
          );
        }
      }
    }

    applyEligibilityResponse(response) {
      if (!response || typeof response !== "object") {
        return;
      }

      this.state.customerLoginRequired = Boolean(response.customer_login_required);
      this.state.customerLoggedIn = Boolean(response.customer_logged_in);
      this.state.loginMessage =
        typeof response.login_message === "string" ? response.login_message : "";
      if (typeof response.widget_color === "string") {
        this.applyTriggerColor(response.widget_color);
      }
    }

    getCustomerLoginMessage() {
      return (
        this.state.loginMessage ||
        "Please log in to your store account to continue virtual try-on. After logging in, reopen this widget and continue."
      );
    }

    isCustomerLoginBlocked() {
      return this.state.customerLoginRequired && !this.state.customerLoggedIn;
    }

    async refreshCustomerEligibility() {
      try {
        const response = await this.request(this.buildCheckEnabledPath(), { withSession: false });
        this.applyEligibilityResponse(response);
      } catch (error) {
        return;
      }
    }

    buildCheckEnabledPath() {
      const params = new URLSearchParams();
      params.set("shopify_product_gid", this.config.product.gid);

      const hasCollectionArray = Array.isArray(this.config.product.collectionIds);
      const collectionIds = hasCollectionArray
        ? this.config.product.collectionIds
            .map(function (value) {
              return String(value || "").trim();
            })
            .filter(Boolean)
        : [];

      if (hasCollectionArray) {
        params.set("shopify_collection_ids", collectionIds.join(","));
      }

      return "/widget/check-enabled?" + params.toString();
    }

    async ensureCustomerLoginBeforeAction() {
      await this.refreshCustomerEligibility();
      if (!this.isCustomerLoginBlocked()) {
        return true;
      }

      this.state.error = this.getCustomerLoginMessage();
      this.state.notice = "";
      this.state.stage = "setup";
      this.renderOverlay();
      return false;
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
      this.overlay.addEventListener("mouseover", this.handleOverlayMouseOver);
      this.overlay.addEventListener("mouseout", this.handleOverlayMouseOut);
      this.overlay.addEventListener("error", this.handleOverlayAssetError, true);
      this.overlay.addEventListener("load", this.handleOverlayAssetLoad, true);
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

    getFlowSnapshotKey(sessionId, productId) {
      return FLOW_SNAPSHOT_PREFIX + ":" + String(sessionId || "") + ":" + String(productId || "");
    }

    getFlowSnapshotPointerKey(productId) {
      return FLOW_POINTER_PREFIX + ":" + this.userIdentifier + ":" + String(productId || "");
    }

    hasFreshFitState(referenceTs) {
      if (!referenceTs) {
        return false;
      }
      return Date.now() - Number(referenceTs) <= FLOW_SNAPSHOT_TTL_MS;
    }

    saveFlowSnapshot() {
      if (!this.state.session || !this.state.session.session_id || !this.state.session.product_id) {
        return;
      }
      if (!this.state.recommendation || !this.state.tryOnImageUrl) {
        return;
      }
      const storage = getSessionStorage();
      if (!storage) {
        return;
      }

      const createdAt = this.state.fitGeneratedAt || Date.now();
      const payload = {
        createdAt: createdAt,
        stage: this.state.stage,
        measurement_id: this.state.measurement ? this.state.measurement.measurement_id : null,
        measurements: this.state.measurement ? this.state.measurement.measurements || {} : {},
        recommendation: this.state.recommendation,
        selectedSize: this.state.selectedSize,
        heatmapBySize: this.state.heatmapBySize || {},
        fitScores: this.state.fitScores || {},
        tryOnId: this.state.tryOnId || "",
        tryOnImageUrl: this.state.tryOnImageUrl || "",
        activeImageUrl: this.state.activeImageUrl || "",
        studioResults: this.state.studioResults || {},
        currentStudioBackgroundId: this.state.currentStudioBackgroundId || "",
        selectedStudioImageUrl: this.state.selectedStudioImageUrl || "",
        form: this.state.form
      };

      const snapshotKey = this.getFlowSnapshotKey(this.state.session.session_id, this.state.session.product_id);
      const pointerKey = this.getFlowSnapshotPointerKey(this.state.session.product_id);
      storage.setItem(snapshotKey, JSON.stringify(payload));
      storage.setItem(pointerKey, snapshotKey);
    }

    clearFlowSnapshotForCurrentSession() {
      if (!this.state.session || !this.state.session.session_id || !this.state.session.product_id) {
        return;
      }
      const storage = getSessionStorage();
      if (!storage) {
        return;
      }
      const snapshotKey = this.getFlowSnapshotKey(this.state.session.session_id, this.state.session.product_id);
      storage.removeItem(snapshotKey);
    }

    tryRestoreFlowSnapshot(session) {
      const storage = getSessionStorage();
      if (!storage || !session || !session.session_id || !session.product_id) {
        return false;
      }

      const directKey = this.getFlowSnapshotKey(session.session_id, session.product_id);
      const pointerKey = this.getFlowSnapshotPointerKey(session.product_id);
      const candidateKeys = [];
      const pointerValue = storage.getItem(pointerKey);
      if (pointerValue) {
        candidateKeys.push(pointerValue);
      }
      candidateKeys.push(directKey);

      for (let i = 0; i < candidateKeys.length; i += 1) {
        const key = candidateKeys[i];
        if (!key) {
          continue;
        }
        const raw = storage.getItem(key);
        if (!raw) {
          continue;
        }
        try {
          const snapshot = JSON.parse(raw);
          if (!snapshot || !this.hasFreshFitState(snapshot.createdAt)) {
            storage.removeItem(key);
            continue;
          }
          if (!snapshot.recommendation || !snapshot.tryOnImageUrl) {
            storage.removeItem(key);
            continue;
          }

          this.state.measurement = {
            measurement_id: session.measurement_id || snapshot.measurement_id,
            measurements: session.measurements || snapshot.measurements || {},
            confidence_score: null,
            cached: true
          };
          this.state.recommendation = snapshot.recommendation;
          this.state.selectedSize = snapshot.selectedSize || snapshot.recommendation.recommended_size;
          this.state.heatmapBySize = snapshot.heatmapBySize || {};
          this.state.fitScores = snapshot.fitScores || this.buildFitScoreMap(snapshot.recommendation);
          this.state.tryOnId = snapshot.tryOnId || "";
          this.state.tryOnImageUrl = snapshot.tryOnImageUrl || "";
          this.state.activeImageUrl = snapshot.activeImageUrl || snapshot.tryOnImageUrl || "";
          this.state.studioResults = snapshot.studioResults || {};
          this.state.currentStudioBackgroundId = snapshot.currentStudioBackgroundId || "";
          this.state.selectedStudioImageUrl = snapshot.selectedStudioImageUrl || "";
          this.state.fitGeneratedAt = snapshot.createdAt;
          if (snapshot.form && typeof snapshot.form === "object") {
            this.state.form = Object.assign({}, this.state.form, snapshot.form);
          }
          this.state.stage = snapshot.stage === "measurements" ? "measurements" : "results";
          this.state.notice = "Restored your recent fit from the last hour.";
          this.state.returningUser = true;
          return true;
        } catch (error) {
          storage.removeItem(key);
        }
      }
      return false;
    }

    async startSession() {
      this.state.returningUser = false;
      this.state.activeHeatmapZone = "";
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
        this.state.fitGeneratedAt = 0;
        this.state.tryOnError = "";
        this.state.limitCode = "";
        this.state.limitResetAt = "";
        this.state.limitTimezone = "";
        this.state.limitMessage = "";
        this.state.activeImageUrl = "";
        this.state.lastGoodImageUrl = "";
        this.state.imageLoadError = "";
        this.state.failedImageUrl = "";
        this.state.lastImageErrorUrl = "";
        this.state.studioBackgrounds = [];
        this.state.studioBackgroundsError = false;
        this.state.studioResults = {};
        this.state.currentStudioBackgroundId = "";
        this.state.studioLoadingId = "";
        this.state.selectedStudioImageUrl = "";
        this.state.activeHeatmapZone = "";

        if (session.has_existing_measurements) {
          if (session.height_cm != null && Number.isFinite(Number(session.height_cm))) {
            this.state.form.height = String(session.height_cm);
          }
          if (session.weight_kg != null && Number.isFinite(Number(session.weight_kg))) {
            this.state.form.weight = String(session.weight_kg);
          }
          if (typeof session.gender === "string" && ["male", "female", "unisex"].includes(session.gender)) {
            this.state.form.gender = session.gender;
          }
        }

        const restored = this.tryRestoreFlowSnapshot(session);
        if (restored) {
          // Keep restored stage/results and avoid forcing setup flow.
        } else if (session.has_existing_measurements && session.measurement_id && session.photos_available) {
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

        if (this.isCustomerLoginBlocked()) {
          this.state.error = this.getCustomerLoginMessage();
          this.state.stage = "setup";
          this.state.notice = "";
        }

        this.trackEvent("widget_opened", {
          product_id: this.config.product.id
        });
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

      const zoneTarget = event.target && event.target.closest ? event.target.closest("path[data-zone]") : null;
      if (zoneTarget) {
        event.preventDefault();
        this.setActiveHeatmapZone(zoneTarget.getAttribute("data-zone") || "");
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
        this.state.imageLoadError = "";
        this.showToast("Studio look applied.");
        this.saveFlowSnapshot();
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
        this.shareLook();
      } else if (action === "download-look") {
        this.downloadActiveImage();
      }
    }

    handleOverlayMouseOver(event) {
      if (!this.overlay || this.state.stage !== "results") {
        return;
      }

      const zoneTarget = event.target && event.target.closest ? event.target.closest("path[data-zone]") : null;
      if (!zoneTarget) {
        return;
      }

      this.setActiveHeatmapZone(zoneTarget.getAttribute("data-zone") || "");
    }

    handleOverlayMouseOut(event) {
      if (!this.overlay || this.state.stage !== "results") {
        return;
      }

      const fromZone = event.target && event.target.closest ? event.target.closest("path[data-zone]") : null;
      if (!fromZone) {
        return;
      }

      const toZone = event.relatedTarget && event.relatedTarget.closest ? event.relatedTarget.closest("path[data-zone]") : null;
      if (toZone) {
        return;
      }

      this.setActiveHeatmapZone("");
    }

    handleOverlayAssetLoad(event) {
      const target = event.target;
      if (!(target instanceof HTMLImageElement)) {
        return;
      }
      if (target.getAttribute("data-role") !== "result-image") {
        return;
      }

      this.state.lastGoodImageUrl = target.currentSrc || target.src || this.state.lastGoodImageUrl;
      this.state.imageLoadError = "";
    }

    handleOverlayAssetError(event) {
      const target = event.target;
      if (!(target instanceof HTMLImageElement)) {
        return;
      }
      if (target.getAttribute("data-role") !== "result-image") {
        return;
      }

      const src = target.currentSrc || target.src || "";
      this.trackEvent("result_image_load_failed", {
        image_url: src
      });
      this.resolveResultImageFailure(src);
    }

    async resolveResultImageFailure(src) {
      if (src && this.state.lastImageErrorUrl === src) {
        return;
      }
      this.state.lastImageErrorUrl = src || "";
      const fallback = this.state.lastGoodImageUrl || this.state.tryOnImageUrl || "";
      if (fallback && this.state.activeImageUrl === src) {
        this.state.activeImageUrl = fallback;
      }

      if (!fallback || fallback === src) {
        this.state.failedImageUrl = src || this.state.tryOnImageUrl || this.state.activeImageUrl || "";
        if (this.state.activeImageUrl === src) {
          this.state.activeImageUrl = "";
        }
      }

      let message = "Couldn't load the generated image. Please retry.";
      if (src) {
        const reason = await this.probeImageFailureReason(src);
        if (reason === "expired") {
          message = "Your generated image expired from cache. Please generate again.";
        } else if (reason === "mime") {
          message = "Image format issue detected. Please retry generation.";
        } else if (reason === "proxy") {
          message = "Image proxy couldn't reach the result. Please retry.";
        }
      }

      this.state.imageLoadError = message;
      this.state.notice = message;
      this.clearFlowSnapshotForCurrentSession();
      this.renderOverlay();
    }

    async probeImageFailureReason(url) {
      if (!url) {
        return "unknown";
      }
      try {
        const response = await window.fetch(url, {
          method: "GET",
          credentials: "same-origin"
        });
        if (response.status === 410) {
          return "expired";
        }
        if (response.status >= 500 || response.status === 404) {
          return "proxy";
        }
        const contentType = (response.headers.get("content-type") || "").toLowerCase();
        if (contentType && contentType.indexOf("image/") !== 0) {
          return "mime";
        }
      } catch (error) {
        return "proxy";
      }
      return "unknown";
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

    async goToFrontPose() {
      const loginAllowed = await this.ensureCustomerLoginBeforeAction();
      if (!loginAllowed) {
        return;
      }

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
      this.clearFlowSnapshotForCurrentSession();
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
      this.state.notice = "";
      this.state.returningUser = false;
      this.state.recommendation = null;
      this.state.selectedSize = "";
      this.state.heatmapBySize = {};
      this.state.fitScores = {};
      this.state.tryOnId = "";
      this.state.tryOnImageUrl = "";
      this.state.activeImageUrl = "";
      this.state.studioResults = {};
      this.state.currentStudioBackgroundId = "";
      this.state.selectedStudioImageUrl = "";
      this.state.fitGeneratedAt = 0;
      this.state.stage = "front-pose";
      this.renderOverlay();
    }

    async handlePoseFile(pose, file) {
      const currentPoseLabel = pose === "front" ? "front" : "side";
      let followupNotice = "";
      this.state.error = "";
      this.state.notice = "Checking your " + currentPoseLabel + " pose...";
      this.renderOverlay();

      try {
        const validation = await this.validatePose(file, pose);
        followupNotice = this.getPoseValidationWarningNotice(validation, currentPoseLabel);

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
        followupNotice = "";
      }

      this.state.notice = followupNotice;
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

      if (!response) {
        return;
      }

      const status = typeof response.status === "string" ? response.status : "";
      if (status === "accepted" || status === "accepted_with_warnings") {
        return response;
      }

      if (status === "rejected" || response.valid === false) {
        const hardFailures = Array.isArray(response.hard_failures) ? response.hard_failures : [];
        const hardMessages = hardFailures
          .map((item) => {
            if (!item || !item.message) {
              return "";
            }
            const base = String(item.message).trim();
            const suggestion = item.suggestion ? String(item.suggestion).trim() : "";
            return suggestion ? base + " " + suggestion : base;
          })
          .filter(Boolean);
        if (hardMessages.length) {
          throw new Error(hardMessages.join(" "));
        }

        const issues = Array.isArray(response.issues) ? response.issues.filter(Boolean) : [];
        throw new Error(issues.length ? issues.join(" ") : "We couldn't verify that pose. Try another photo.");
      }

      if (response.valid === true) {
        return response;
      }

      const issues = Array.isArray(response.issues) ? response.issues.filter(Boolean) : [];
      throw new Error(issues.length ? issues.join(" ") : "We couldn't verify that pose. Try another photo.");
    }

    getPoseValidationWarningNotice(response, poseLabel) {
      if (!response || response.status !== "accepted_with_warnings") {
        return "";
      }

      const warnings = Array.isArray(response.warnings) ? response.warnings : [];
      const warningMessages = warnings
        .map((item) => (item && item.message ? String(item.message).trim() : ""))
        .filter(Boolean);

      if (!warningMessages.length) {
        return (
          "Your " +
          poseLabel +
          " photo was accepted, but image quality may slightly affect fit precision."
        );
      }

      const top = warningMessages.slice(0, 2).join(" ");
      return (
        "Your " +
        poseLabel +
        " photo was accepted with caution: " +
        top +
        " Fit accuracy may be slightly reduced."
      );
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

    clearFailedImageState() {
      this.state.imageLoadError = "";
      this.state.failedImageUrl = "";
      this.state.lastImageErrorUrl = "";
    }

    async isImageUrlUsable(url) {
      if (!url) {
        return false;
      }
      try {
        const response = await window.fetch(url, {
          method: "GET",
          credentials: "same-origin"
        });
        if (!response.ok) {
          return false;
        }
        const contentType = (response.headers.get("content-type") || "").toLowerCase();
        return contentType.indexOf("image/") === 0;
      } catch (error) {
        return false;
      }
    }

    resetFitArtifactsForRegeneration() {
      this.state.recommendation = null;
      this.state.selectedSize = "";
      this.state.heatmapBySize = {};
      this.state.fitScores = {};
      this.state.tryOnId = "";
      this.state.tryOnImageUrl = "";
      this.state.activeImageUrl = "";
      this.state.lastGoodImageUrl = "";
      this.state.studioResults = {};
      this.state.currentStudioBackgroundId = "";
      this.state.selectedStudioImageUrl = "";
      this.state.fitGeneratedAt = 0;
      this.clearFailedImageState();
      this.clearFlowSnapshotForCurrentSession();
    }

    async extractMeasurements() {
      if (!this.state.frontFile || !this.state.sideFile || !this.state.session) {
        return;
      }

      const validationError = this.validateSetupForm();
      if (validationError) {
        this.state.error = validationError + " Please complete setup details before extracting measurements.";
        this.state.notice = "";
        this.state.stage = "setup";
        this.renderOverlay();
        return;
      }

      this.state.stage = "analyzing";
      this.state.error = "";
      this.state.notice = "";
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
        this.state.recommendation = null;
        this.state.selectedSize = "";
        this.state.heatmapBySize = {};
        this.state.fitScores = {};
        this.state.tryOnId = "";
        this.state.tryOnImageUrl = "";
        this.state.activeImageUrl = "";
        this.state.studioResults = {};
        this.state.currentStudioBackgroundId = "";
        this.state.selectedStudioImageUrl = "";
        this.state.fitGeneratedAt = 0;
        this.clearFailedImageState();
        this.state.notice = "";
        this.state.stage = "measurements";
        this.trackEvent("measurement_completed");
        this.clearFlowSnapshotForCurrentSession();
      } catch (error) {
        this.clearAnalysisTicker();
        this.state.error = error.message || "Measurement extraction failed.";
        this.state.notice = "";
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

      if (
        this.state.recommendation &&
        this.state.tryOnImageUrl &&
        this.hasFreshFitState(this.state.fitGeneratedAt)
      ) {
        const stillUsable = await this.isImageUrlUsable(this.state.activeImageUrl || this.state.tryOnImageUrl);
        if (!stillUsable) {
          this.resetFitArtifactsForRegeneration();
        } else {
          this.state.error = "";
          this.state.notice = "Showing your recent fit from the last hour.";
          this.state.stage = "results";
          this.renderOverlay();
          if (!this.state.studioBackgrounds.length) {
            this.loadStudioBackgrounds().then(() => {
              this.renderOverlay();
            });
          }
          return;
        }
      }

      const loginAllowed = await this.ensureCustomerLoginBeforeAction();
      if (!loginAllowed) {
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

        let tryOnStatus = null;
        if (tryOnStart.status === "completed" && tryOnStart.result_image_url) {
          tryOnStatus = tryOnStart;
        } else {
          tryOnStatus = await this.pollTryOn(tryOnStart.try_on_id);
        }
        this.state.tryOnId = tryOnStatus.try_on_id;
        this.state.tryOnImageUrl = this.toProxyUrl(tryOnStatus.result_image_url);
        this.state.activeImageUrl = this.state.tryOnImageUrl;
        this.clearFailedImageState();
        this.state.fitGeneratedAt = Date.now();
        this.trackEvent("try_on_generated", {
          try_on_id: tryOnStatus.try_on_id,
          reused: Boolean(tryOnStart.reused)
        });

        await backgroundPromise;
        this.clearAnalysisTicker();
        this.state.generatingStep = 3;
        this.state.stage = "results";
        this.saveFlowSnapshot();
      } catch (error) {
        this.clearAnalysisTicker();
        if (!this.handleGenerationError(error, "tryon")) {
          this.state.error = error.message || "We couldn't generate your try-on.";
          this.state.stage = "measurements";
        }
      }

      this.renderOverlay();
    }

    buildFitScoreMap(recommendation) {
      const map = {};
      if (!recommendation) {
        return map;
      }

      if (recommendation.size_scores && typeof recommendation.size_scores === "object") {
        Object.keys(recommendation.size_scores).forEach(function (sizeKey) {
          const raw = recommendation.size_scores[sizeKey];
          if (raw == null) {
            map[sizeKey] = null;
            return;
          }
          const numeric = Number(raw);
          map[sizeKey] = Number.isFinite(numeric) ? numeric : null;
        });
      } else {
        map[recommendation.recommended_size] = recommendation.fit_score;
        if (Array.isArray(recommendation.alternative_sizes)) {
          recommendation.alternative_sizes.forEach(function (entry) {
            if (entry && entry.size) {
              map[entry.size] = entry.fit_score;
            }
          });
        }
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
        this.saveFlowSnapshot();
        return heatmap;
      } finally {
        this.state.isHeatmapLoading = false;
        this.renderOverlay();
      }
    }

    getSelectedFitScore() {
      if (!this.state.selectedSize) {
        return null;
      }
      if (Object.prototype.hasOwnProperty.call(this.state.fitScores || {}, this.state.selectedSize)) {
        const raw = this.state.fitScores[this.state.selectedSize];
        return raw == null ? null : Number(raw);
      }
      if (this.state.recommendation && this.state.selectedSize === this.state.recommendation.recommended_size) {
        const fallback = Number(this.state.recommendation.fit_score);
        return Number.isFinite(fallback) ? fallback : null;
      }
      return null;
    }

    getCoverageForSize(size) {
      if (!this.state.recommendation || !this.state.recommendation.coverage_by_size) {
        return null;
      }
      const coverage = this.state.recommendation.coverage_by_size[size];
      if (!coverage || typeof coverage !== "object") {
        return null;
      }
      return coverage;
    }

    getCoverageNote(size) {
      const coverage = this.getCoverageForSize(size);
      if (!coverage) {
        return "";
      }
      const expected = Number(coverage.expected_measurements || 0);
      const used = Number(coverage.used_measurements || 0);
      const totalWeight = Number(coverage.total_weight || 0);
      const usedWeight = Number(coverage.used_weight || 0);
      const ratio = totalWeight > 0 ? usedWeight / totalWeight : 0;
      if (expected <= 0 || used <= 0) {
        return "Insufficient size-chart data for this size.";
      }
      if (ratio < 0.55 || used < Math.ceil(expected * 0.5)) {
        return "Lower confidence due to limited size data.";
      }
      return "";
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

        this.state.studioBackgroundsError = false;
        this.state.studioBackgrounds = Array.isArray(list)
          ? list.slice(0, 5).map((entry) => {
              return {
                id: entry.id,
                image_url: this.toProxyUrl(entry.image_url)
              };
            })
          : [];
      } catch (error) {
        this.state.studioBackgroundsError = true;
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

      const loginAllowed = await this.ensureCustomerLoginBeforeAction();
      if (!loginAllowed) {
        this.state.studioLoadingId = "";
        this.renderOverlay();
        return;
      }

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
        this.state.imageLoadError = "";
        this.saveFlowSnapshot();
        this.showToast("Studio look ready.");
      } catch (error) {
        if (!this.handleGenerationError(error, "studio")) {
          this.state.error = error.message || "Studio generation failed.";
        }
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
      this.state.activeHeatmapZone = "";
      this.trackEvent("size_selected", { size: size });
      this.renderOverlay();

      try {
        await this.fetchHeatmap(size);
      } catch (error) {
        this.state.error = error.message || "Unable to load fit heatmap for that size.";
        this.renderOverlay();
        return;
      }
      this.saveFlowSnapshot();
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

    isLikelyMobileDevice() {
      const userAgent = (navigator.userAgent || "").toLowerCase();
      const mobileUa = /android|iphone|ipad|ipod|mobile|silk/.test(userAgent);
      const narrowViewport = window.matchMedia && window.matchMedia("(max-width: 820px)").matches;
      return mobileUa || narrowViewport || (navigator.maxTouchPoints || 0) > 1;
    }

    shouldUseNativeShare() {
      return typeof navigator.share === "function" && this.isLikelyMobileDevice();
    }

    async fetchResultBlob(url) {
      const response = await window.fetch(url, {
        method: "GET",
        credentials: "same-origin"
      });
      if (!response.ok) {
        throw new Error("Image is no longer available.");
      }
      return response.blob();
    }

    getShareText() {
      return "I just tried this look with Optimo VTS. Try it on your store.";
    }

    async shareLook() {
      const shareUrl = window.location.href;
      const shareText = this.getShareText();
      if (!this.shouldUseNativeShare()) {
        await this.downloadActiveImage();
        return;
      }

      const activeUrl = this.state.activeImageUrl || this.state.tryOnImageUrl;
      try {
        if (activeUrl) {
          const blob = await this.fetchResultBlob(activeUrl);
          const extension = blob.type && blob.type.indexOf("png") !== -1 ? "png" : "jpg";
          const file = new File([blob], "optimo-vts-look." + extension, {
            type: blob.type || "image/jpeg"
          });
          if (typeof navigator.canShare === "function" && navigator.canShare({ files: [file] })) {
            await navigator.share({
              title: document.title,
              text: shareText,
              url: shareUrl,
              files: [file]
            });
            return;
          }
        }

        await navigator.share({
          title: document.title,
          text: shareText,
          url: shareUrl
        });
      } catch (error) {
        if (error && error.name === "AbortError") {
          return;
        }
        this.state.error = error.message || "Unable to open share options right now.";
        this.renderOverlay();
      }
    }

    async downloadActiveImage() {
      const activeUrl = this.state.activeImageUrl || this.state.tryOnImageUrl;
      if (!activeUrl) {
        this.state.error = "No image available to download yet.";
        this.renderOverlay();
        return;
      }
      try {
        const blob = await this.fetchResultBlob(activeUrl);
        const objectUrl = URL.createObjectURL(blob);
        const extension = blob.type && blob.type.indexOf("png") !== -1 ? "png" : "jpg";
        const link = document.createElement("a");
        link.href = objectUrl;
        link.download = "optimo-vts-look." + extension;
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(objectUrl);
        this.showToast("Image downloaded.");
        this.renderOverlay();
      } catch (error) {
        this.state.error = error.message || "Unable to download image.";
        this.renderOverlay();
      }
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

    setActiveHeatmapZone(zone) {
      const next = String(zone || "");
      if (next === String(this.state.activeHeatmapZone || "")) {
        return;
      }
      this.state.activeHeatmapZone = next;
      if (!this.updateHeatmapTooltip()) {
        this.renderOverlay();
      }
    }

    updateHeatmapTooltip() {
      if (!this.overlay || this.state.stage !== "results") {
        return false;
      }

      const tooltipNode = this.overlay.querySelector(".ovts-heatmap-tooltip");
      if (!tooltipNode) {
        return false;
      }

      const heatmap = this.getSelectedHeatmap();
      tooltipNode.outerHTML = this.renderHeatmapTooltip(heatmap);
      return true;
    }

    getHeatmapLegend(heatmap) {
      const legend = heatmap && heatmap.legend && typeof heatmap.legend === "object" ? heatmap.legend : null;
      if (!legend) {
        return {};
      }
      return legend;
    }

    getZonePayload(heatmap, zone) {
      if (!heatmap || !heatmap.zones || typeof heatmap.zones !== "object") {
        return null;
      }
      return heatmap.zones[zone] || null;
    }

    getZoneDelta(heatmap, zone) {
      if (!heatmap || typeof heatmap !== "object") {
        return null;
      }
      if (heatmap.zone_deltas && typeof heatmap.zone_deltas === "object" && heatmap.zone_deltas[zone] != null) {
        const delta = Number(heatmap.zone_deltas[zone]);
        return Number.isFinite(delta) ? delta : null;
      }
      const payload = this.getZonePayload(heatmap, zone);
      if (!payload) {
        return null;
      }
      const delta = Number(payload.delta_cm);
      return Number.isFinite(delta) ? delta : null;
    }

    getHeatmapCategory(heatmap) {
      const incoming = heatmap && typeof heatmap.category === "string" ? heatmap.category.toLowerCase() : "";
      if (HEATMAP_CATEGORY_MEASUREMENTS[incoming]) {
        return incoming;
      }
      if (!heatmap || !heatmap.zones || typeof heatmap.zones !== "object") {
        return "unknown";
      }
      const keys = Object.keys(heatmap.zones);
      const hasLower = keys.includes("thigh") || keys.includes("calf") || keys.includes("ankle") || keys.includes("inseam");
      const hasUpper = keys.includes("chest") || keys.includes("shoulder_width") || keys.includes("arm_length") || keys.includes("neck");
      if (hasLower && hasUpper) {
        return "dresses";
      }
      if (hasLower) {
        return "bottoms";
      }
      if (keys.includes("arm_length")) {
        return "outerwear";
      }
      if (keys.includes("chest") || keys.includes("shoulder_width")) {
        return "tops";
      }
      return "unknown";
    }

    getHeatmapSegment(segmentId) {
      for (let i = 0; i < HEATMAP_SEGMENTS.length; i += 1) {
        if (HEATMAP_SEGMENTS[i].id === segmentId) {
          return HEATMAP_SEGMENTS[i];
        }
      }
      return null;
    }

    getSegmentPayload(heatmap, segment) {
      if (!segment || !segment.measurementKey) {
        return null;
      }
      return this.getZonePayload(heatmap, segment.measurementKey);
    }

    getSegmentDelta(heatmap, segment) {
      if (!segment || !segment.measurementKey) {
        return null;
      }
      return this.getZoneDelta(heatmap, segment.measurementKey);
    }

    isSegmentRelevant(segment, category) {
      const measurements = HEATMAP_CATEGORY_MEASUREMENTS[category] || HEATMAP_CATEGORY_MEASUREMENTS.unknown;
      return measurements.indexOf(segment.measurementKey) !== -1;
    }

    getMeasurementLabel(key) {
      return HEATMAP_MEASUREMENT_LABELS[key] || String(key || "").replace(/_/g, " ");
    }

    hexToRgb(hex) {
      const value = String(hex || "").replace("#", "");
      if (value.length !== 6) {
        return { r: 128, g: 128, b: 128 };
      }
      return {
        r: parseInt(value.slice(0, 2), 16),
        g: parseInt(value.slice(2, 4), 16),
        b: parseInt(value.slice(4, 6), 16)
      };
    }

    interpolateColor(colorA, colorB, t) {
      const a = this.hexToRgb(colorA);
      const b = this.hexToRgb(colorB);
      const clampT = Math.max(0, Math.min(1, t));
      const r = Math.round(a.r + (b.r - a.r) * clampT);
      const g = Math.round(a.g + (b.g - a.g) * clampT);
      const bCh = Math.round(a.b + (b.b - a.b) * clampT);
      return "rgb(" + r + "," + g + "," + bCh + ")";
    }

    colorForDelta(delta) {
      if (!Number.isFinite(delta)) {
        return "rgba(255,255,255,0.08)";
      }
      if (delta <= FIT_COLOR_ANCHORS[0].delta) {
        return FIT_COLOR_ANCHORS[0].color;
      }
      if (delta >= FIT_COLOR_ANCHORS[FIT_COLOR_ANCHORS.length - 1].delta) {
        return FIT_COLOR_ANCHORS[FIT_COLOR_ANCHORS.length - 1].color;
      }
      for (let i = 0; i < FIT_COLOR_ANCHORS.length - 1; i += 1) {
        const left = FIT_COLOR_ANCHORS[i];
        const right = FIT_COLOR_ANCHORS[i + 1];
        if (delta >= left.delta && delta <= right.delta) {
          const fraction = (delta - left.delta) / (right.delta - left.delta);
          return this.interpolateColor(left.color, right.color, fraction);
        }
      }
      return FIT_COLOR_ANCHORS[2].color;
    }

    fitLabelForDelta(delta) {
      if (!Number.isFinite(delta)) {
        return "perfect";
      }
      if (delta < -3.5) {
        return "tight";
      }
      if (delta < -1.0) {
        return "snug";
      }
      if (delta <= 1.5) {
        return "perfect";
      }
      if (delta <= 3.5) {
        return "loose";
      }
      return "very_loose";
    }

    resolvePayloadFill(heatmap, segment) {
      const delta = this.getSegmentDelta(heatmap, segment);
      return this.colorForDelta(delta);
    }

    renderHeatmapSvg(heatmap) {
      const category = this.getHeatmapCategory(heatmap);
      const parts = [
        '<svg viewBox="' + HEATMAP_VIEWBOX + '" preserveAspectRatio="xMidYMid meet" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Fit heatmap">',
        '<g class="ovts-heatmap-zones">'
      ];

      for (let i = 0; i < HEATMAP_SEGMENTS.length; i += 1) {
        const entry = HEATMAP_SEGMENTS[i];
        const payload = this.getSegmentPayload(heatmap, entry);
        const delta = this.getSegmentDelta(heatmap, entry);
        const isRelevant = this.isSegmentRelevant(entry, category);
        const fill = this.resolvePayloadFill(heatmap, entry);
        const fillOpacity = payload ? (isRelevant ? "0.92" : "0.48") : isRelevant ? "0.24" : "0.12";
        const stroke = "#111111";
        const strokeOpacity = payload ? "0.92" : isRelevant ? "0.52" : "0.30";

        const title = payload
          ? entry.label +
            ": " +
            (FIT_LABEL_TITLES[this.fitLabelForDelta(delta)] || this.fitLabelForDelta(delta)) +
            " (" +
            String(Math.round((delta || 0) * 10) / 10) +
            " cm)"
          : entry.label + ": no size data";

        parts.push(
          '<path d="' +
            escapeHtml(entry.d) +
            '" data-zone="' +
            escapeHtml(entry.id) +
            '" fill="' +
            escapeHtml(fill) +
            '" fill-opacity="' +
            fillOpacity +
            '" stroke="' +
            escapeHtml(stroke) +
            '" stroke-opacity="' +
            strokeOpacity +
            '" stroke-width="' +
            (payload ? "2.4" : "1.9") +
            '" vector-effect="non-scaling-stroke">' +
            "<title>" +
            escapeHtml(title) +
            "</title></path>"
        );
      }

      parts.push("</g></svg>");
      return parts.join("");
    }

    renderHeatmapLegend(heatmap) {
      return FIT_LABEL_ORDER.map((key) => {
        const anchor = FIT_COLOR_ANCHORS.find(function (entry) {
          return entry.label === key;
        });
        const color = anchor ? anchor.color : "";
        const title = FIT_LABEL_TITLES[key] || key;
        const style = color ? ' style="background:' + escapeHtml(color) + '"' : "";
        return '<span><i' + style + '></i>' + escapeHtml(title) + "</span>";
      }).join("");
    }

    renderHeatmapCoverage(heatmap) {
      const availableRaw = heatmap && heatmap.coverage_available != null
        ? Number(heatmap.coverage_available)
        : NaN;
      const totalRaw = heatmap && heatmap.coverage_total != null
        ? Number(heatmap.coverage_total)
        : NaN;
      const available = Number.isFinite(availableRaw)
        ? availableRaw
        : Object.keys((heatmap && heatmap.zones) || {}).length;
      const total = Number.isFinite(totalRaw) && totalRaw > 0 ? totalRaw : 15;
      return '<div class="ovts-heatmap-coverage"><strong>Fit coverage:</strong> ' + escapeHtml(String(available)) + "/" + escapeHtml(String(total)) + " measurements</div>";
    }

    renderHeatmapTooltip(heatmap) {
      const segmentId = String(this.state.activeHeatmapZone || "");
      if (!segmentId) {
        return '<div class="ovts-heatmap-tooltip" aria-hidden="true"></div>';
      }
      const segment = this.getHeatmapSegment(segmentId);
      const payload = segment ? this.getSegmentPayload(heatmap, segment) : null;
      const delta = segment ? this.getSegmentDelta(heatmap, segment) : null;
      const measurementKey = segment ? segment.measurementKey : "";
      const measurementLabel = this.getMeasurementLabel(measurementKey);

      if (!payload) {
        return (
          '<div class="ovts-heatmap-tooltip is-visible" role="status" aria-live="polite">' +
          '<div class="ovts-heatmap-tooltip__row"><strong>' +
          escapeHtml(measurementLabel) +
          "</strong><span>No data</span></div>" +
          '<div class="ovts-heatmap-tooltip__meta"><span>No size chart data for this measurement.</span></div>' +
          "</div>"
        );
      }

      const labelKey = this.fitLabelForDelta(delta);
      const label = FIT_LABEL_TITLES[labelKey] || labelKey || "Fit";
      const userText = formatNumber(payload.user_cm);
      const productText = formatNumber(payload.product_cm);

      return (
        '<div class="ovts-heatmap-tooltip is-visible" role="status" aria-live="polite">' +
        '<div class="ovts-heatmap-tooltip__row"><strong>' +
        escapeHtml(measurementLabel) +
        "</strong><span>" +
        escapeHtml(label) +
        "</span></div>" +
        '<div class="ovts-heatmap-tooltip__meta">' +
        '<span>You: <strong>' +
        escapeHtml(userText != null ? userText + " cm" : "--") +
        "</strong></span>" +
        '<span>Garment: <strong>' +
        escapeHtml(productText != null ? productText + " cm" : "--") +
        "</strong></span>" +
        "</div></div>"
      );
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

    formatWeeklyReset(resetAt, timezone) {
      if (!resetAt) {
        return "";
      }

      try {
        const date = new Date(resetAt);
        if (Number.isNaN(date.getTime())) {
          return resetAt;
        }

        const options = {
          dateStyle: "full",
          timeStyle: "short"
        };
        if (timezone) {
          options.timeZone = timezone;
        }

        const label = new Intl.DateTimeFormat(undefined, options).format(date);
        return timezone ? label + " (" + timezone + ")" : label;
      } catch (error) {
        return resetAt;
      }
    }

    handleGenerationError(error, context) {
      const code = error && typeof error.code === "string" ? error.code : "";
      const detail = error && error.detail && typeof error.detail === "object" ? error.detail : {};
      const message = (error && error.message) || "Request failed.";

      if (code === "WEEKLY_LIMIT_REACHED") {
        const resetAt = typeof detail.reset_at === "string" ? detail.reset_at : "";
        const timezone = typeof detail.timezone === "string" ? detail.timezone : "";

        this.state.limitCode = code;
        this.state.limitResetAt = resetAt;
        this.state.limitTimezone = timezone;
        this.state.limitMessage = message;
        this.state.notice = "";

        const resetText = this.formatWeeklyReset(resetAt, timezone);
        if (context === "studio") {
          this.state.error = resetText
            ? "Weekly limit reached. Resets at " + resetText + "."
            : "Weekly limit reached. Contact the store to request more attempts.";
          return true;
        }

        this.state.error = "";
        this.state.stage = "weekly-limit";
        return true;
      }

      if (code === "CUSTOMER_LOGIN_REQUIRED") {
        this.state.customerLoginRequired = true;
        this.state.customerLoggedIn = false;
        this.state.error = message || this.getCustomerLoginMessage();
        this.state.stage = "setup";
        return true;
      }

      if (
        code === "SUBSCRIPTION_INACTIVE" ||
        code === "PLAN_REQUIRED" ||
        code === "TRIAL_EXPIRED" ||
        code === "LEGACY_SUBSCRIPTION_UPGRADE_REQUIRED" ||
        code === "OVERAGE_BLOCKED"
      ) {
        this.state.error = message || "Store billing is unavailable. Please contact the store.";
        if (context !== "studio") {
          this.state.stage = "measurements";
        }
        return true;
      }

      return false;
    }

    trackEvent(eventType, eventData, options) {
      const trackOptions = options || {};
      const hasSession = Boolean(this.state.session && this.state.session.session_id);
      if (!hasSession && !trackOptions.allowWithoutSession) {
        return;
      }

      const payload = {
        event_type: eventType,
        event_data: eventData || {}
      };

      if (hasSession) {
        payload.session_id = this.state.session.session_id;
      }

      this.request("/analytics/events", {
        method: "POST",
        withSession: hasSession,
        json: payload
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
        let code = "";
        let detailPayload = null;
        try {
          const payload = await response.json();
          if (payload && payload.detail && typeof payload.detail === "object") {
            detailPayload = payload.detail;
            if (typeof payload.detail.code === "string") {
              code = payload.detail.code;
            }
            if (typeof payload.detail.message === "string" && payload.detail.message) {
              message = payload.detail.message;
            } else {
              message = payload.error || payload.message || message;
            }
          } else if (Array.isArray(payload && payload.detail)) {
            const detailList = payload.detail
              .map(function (item) {
                if (!item || typeof item !== "object") {
                  return "";
                }
                if (typeof item.msg === "string" && item.msg) {
                  return item.msg;
                }
                return "";
              })
              .filter(Boolean);
            if (detailList.length) {
              message = detailList.join(" ");
            } else {
              message = payload.error || payload.message || message;
            }
          } else {
            message = payload.detail || payload.error || payload.message || message;
          }
        } catch (error) {
          try {
            message = await response.text();
          } catch (innerError) {
            message = "Request failed.";
          }
        }

        const err = new Error(message);
        if (code) {
          err.code = code;
        }
        if (detailPayload) {
          err.detail = detailPayload;
        }
        throw err;
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
      const previousModal = this.overlay.querySelector(".ovts-modal");
      const previousScrollTop = previousModal ? previousModal.scrollTop : 0;

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

      const nextModal = this.overlay.querySelector(".ovts-modal");
      if (nextModal && previousScrollTop > 0) {
        nextModal.scrollTop = previousScrollTop;
      }
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
        case "weekly-limit":
          return this.renderWeeklyLimitReached();
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

    renderWeeklyLimitReached() {
      const resetText = this.formatWeeklyReset(this.state.limitResetAt, this.state.limitTimezone);
      const subtitle = this.state.limitMessage || "Weekly try-on limit reached.";

      return (
        '<div class="ovts-stage ovts-stage--center">' +
        '<div class="ovts-complete-head"><span class="ovts-check">' +
        svgIcon("plain") +
        '</span><div><h2>Weekly Limit Reached</h2><p>' +
        escapeHtml(subtitle) +
        "</p></div></div>" +
        '<div class="ovts-feature-stack">' +
        '<div class="ovts-feature-tile"><strong>Reset time</strong><p>' +
        escapeHtml(resetText || "At the start of next week in store timezone.") +
        "</p></div>" +
        '<div class="ovts-feature-tile"><strong>Need more attempts?</strong><p>Contact the store to request additional weekly try-ons.</p></div>' +
        "</div>" +
        '<button type="button" class="ovts-primary ovts-primary--wide" data-action="close">Close</button>' +
        "</div>"
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
        '</span></button><div class="ovts-subtle-note">Measurements are cached for faster reuse. Photos are deleted in 1 hour.</div></section></div></div>'
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
      const requestedImage = this.state.activeImageUrl || this.state.tryOnImageUrl;
      const blocked = this.state.failedImageUrl && requestedImage === this.state.failedImageUrl;
      const mainImage =
        (this.state.imageLoadError && this.state.lastGoodImageUrl) ||
        (blocked ? "" : requestedImage) ||
        this.state.lastGoodImageUrl ||
        this.config.product.featuredImage;
      const selectedVariant = this.resolveVariantForSize(this.state.selectedSize) || this.getCurrentVariant();
      const price = selectedVariant && selectedVariant.price ? selectedVariant.price : this.config.product.price;
      const heatmapSvg = this.renderHeatmapSvg(heatmap);
      const heatmapLegend = this.renderHeatmapLegend(heatmap);
      const heatmapCoverage = this.renderHeatmapCoverage(heatmap);
      const heatmapTooltip = this.renderHeatmapTooltip(heatmap);
      const shimmerClass = this.state.isHeatmapLoading ? " is-active" : "";
      const selectedScore = this.getSelectedFitScore();
      const selectedScoreText = selectedScore == null ? "--" : String(selectedScore);
      const coverageNote = this.getCoverageNote(this.state.selectedSize);

      return (
        '<div class="ovts-stage ovts-stage--results"><button type="button" class="ovts-inline-back is-top" data-action="back-to-measurements">' +
        svgIcon("back") +
        'Back to measurements</button><div class="ovts-results-grid"><section class="ovts-hero-panel"><div class="ovts-panel-head"><div><h3>Virtual Try-On</h3><span class="ovts-powered">Powered by Optimo 4o</span></div></div><div class="ovts-tryon-preview">' +
        (mainImage
          ? '<img src="' + escapeHtml(mainImage) + '" alt="Virtual try-on result" loading="lazy" data-role="result-image">'
          : '<div class="ovts-image-placeholder">Generating your look...</div>') +
        (this.state.imageLoadError ? '<p class="ovts-image-issue">' + escapeHtml(this.state.imageLoadError) + "</p>" : "") +
        '</div></section><section class="ovts-side-panel"><div class="ovts-studio-box"><div class="ovts-panel-head"><h4>Studio Shoots</h4></div><div class="ovts-studio-grid">' +
        this.renderStudioTiles() +
        '</div><div class="ovts-studio-actions"><button type="button" class="ovts-primary ovts-primary--small" data-action="submit-studio"' +
        (this.state.selectedStudioImageUrl ? "" : " disabled") +
        '>Submit</button><button type="button" class="ovts-secondary ovts-secondary--small" data-action="retry-studio"' +
        (this.state.currentStudioBackgroundId ? "" : " disabled") +
        '>Retry</button></div><div class="ovts-share-box"><span>Share your look</span>' +
        this.renderShareActionButton() +
        '<div class="ovts-share-icons" aria-hidden="true">' +
        this.renderShareIcon("Instagram", "#E4405F") +
        this.renderShareIcon("Facebook", "#1877F2") +
        this.renderShareIcon("WhatsApp", "#25D366") +
        this.renderShareIcon("TikTok", "#111111") +
        "</div></div></div></section><section class=\"ovts-heatmap-panel\"><div class=\"ovts-panel-head\"><div><h3>Heat Map</h3><span class=\"ovts-powered\">Powered by Optimo 4o</span></div></div><div class=\"ovts-heatmap-visual\"><div class=\"ovts-heatmap-body\"><div class=\"ovts-heatmap-overlay\">" +
        heatmapSvg +
        "</div>" +
        heatmapTooltip +
        '<span class="ovts-heatmap-shimmer' +
        shimmerClass +
        '" aria-hidden="true"></span>' +
        '</div><div class="ovts-heatmap-legend">' +
        heatmapLegend +
        "</div>" +
        heatmapCoverage +
        '<p>Tap a zone to see details.</p></div></section><section class="ovts-fit-panel"><div class="ovts-panel-head"><h3>Select Your Size</h3></div><div class="ovts-size-grid">' +
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
        escapeHtml(selectedScoreText) +
        '%</strong></div><div class="ovts-fit-bar"><span style="width:' +
        escapeHtml(selectedScore == null ? "0" : String(selectedScore)) +
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
        '</p></div>' +
        (coverageNote ? '<p class="ovts-coverage-note">' + escapeHtml(coverageNote) + "</p>" : "") +
        "</section></div></div>"
      );
    }

    renderStudioTiles() {
      if (!this.state.studioBackgrounds.length) {
        if (this.state.studioBackgroundsError) {
          return '<div class="ovts-empty-copy">Unable to load studio templates right now. Please retry in a moment.</div>';
        }
        return '<div class="ovts-empty-copy">No studio templates configured yet for this store.</div>';
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
              ? '<img src="' + escapeHtml(image) + '" alt="Studio look option" loading="lazy" data-role="studio-image">'
              : '<span class="ovts-studio-plus">+</span>') +
            (isLoading ? '<span class="ovts-studio-loading">Generating...</span>' : "") +
            "</button>"
          );
        })
        .join("");
    }

    renderShareActionButton() {
      if (this.shouldUseNativeShare()) {
        return '<button type="button" class="ovts-share-primary" data-action="share-look">Share</button>';
      }
      return '<button type="button" class="ovts-share-primary" data-action="download-look">Download Image</button>';
    }

    renderShareIcon(label, color) {
      return (
        '<span class="ovts-share-icon" style="--share-color:' +
        escapeHtml(color) +
        '">' +
        escapeHtml(label.slice(0, 2).toUpperCase()) +
        "</span>"
      );
    }

    renderSuccess() {
      const score = this.getSelectedFitScore();
      return (
        '<div class="ovts-stage ovts-stage--center ovts-stage--success"><span class="ovts-check is-large">' +
        svgIcon("success") +
        "</span><h2>Perfect Fit Added</h2><p>Size " +
        escapeHtml(this.state.selectedSize) +
        " added to your cart with " +
        escapeHtml(score == null ? "--" : String(score)) +
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
        if (isThemeEditorDesignMode()) {
          host.innerHTML =
            '<div class="optimo-vts-editor-placeholder">' +
            "<strong>Optimo VTS Widget failed to initialize</strong>" +
            "<span>" +
            escapeHtml(error && error.message ? error.message : "Unknown initialization error") +
            "</span>" +
            "</div>";
        } else {
          host.innerHTML = "";
        }
      }
    });
  }

  let _initScheduled = false;
  function scheduleInitWidgets() {
    if (_initScheduled) {
      return;
    }
    _initScheduled = true;
    window.requestAnimationFrame(function () {
      _initScheduled = false;
      initWidgets();
    });
  }

  function setupEditorLifecycleHooks() {
    // Shopify Theme Editor often reloads sections dynamically after block add/remove.
    // Re-run widget discovery so new app-block instances mount reliably.
    document.addEventListener("shopify:section:load", scheduleInitWidgets);
    document.addEventListener("shopify:section:reorder", scheduleInitWidgets);
    document.addEventListener("shopify:block:select", scheduleInitWidgets);

    if (!window.MutationObserver) {
      return;
    }

    const observer = new MutationObserver(function (mutations) {
      for (let i = 0; i < mutations.length; i += 1) {
        const mutation = mutations[i];
        for (let j = 0; j < mutation.addedNodes.length; j += 1) {
          const node = mutation.addedNodes[j];
          if (!(node instanceof Element)) {
            continue;
          }

          if (
            node.matches("script[data-optimo-vts-config]") ||
            node.querySelector("script[data-optimo-vts-config]")
          ) {
            scheduleInitWidgets();
            return;
          }
        }
      }
    });

    observer.observe(document.documentElement, {
      childList: true,
      subtree: true
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      initWidgets();
      setupEditorLifecycleHooks();
    });
  } else {
    initWidgets();
    setupEditorLifecycleHooks();
  }
})();
