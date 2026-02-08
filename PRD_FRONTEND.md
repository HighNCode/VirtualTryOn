# Virtual Try-On Shopify App - Frontend PRD (Storefront Widget)

**Version:** 1.0  
**Last Updated:** 2026-02-06  
**Tech Stack:** Vanilla JavaScript (ES6+), HTML5, CSS3  
**Target:** Shopify storefront customer-facing widget  

---

## Table of Contents

1. [Overview](#overview)
2. [User Flow](#user-flow)
3. [Component Specifications](#component-specifications)
4. [UI/UX Guidelines](#uiux-guidelines)
5. [API Integration](#api-integration)
6. [State Management](#state-management)
7. [Error Handling](#error-handling)
8. [Performance](#performance)
9. [Browser Support](#browser-support)
10. [Deployment](#deployment)

---

## Overview

### Purpose
Customer-facing widget embedded in Shopify product pages that enables virtual try-on through AI-powered image generation based on body measurements.

### Key Features
- **Camera Integration:** Native browser camera access with timer
- **Dual Pose Capture:** Front and side pose photos with validation
- **Measurement Display:** Show extracted 15 body measurements
- **Virtual Try-On:** AI-generated try-on image
- **Heatmap Visualization:** Color-coded fit analysis
- **Size Recommendation:** Best size with alternatives
- **Style Selection:** Studio-style photo templates
- **Social Sharing:** Share results to social media
- **Shopify Cart Integration:** Add recommended size to cart

### Technology Stack
```
Language:     Vanilla JavaScript (ES6+)
Bundler:      Webpack 5
Styling:      CSS3 (BEM methodology)
Browser APIs: getUserMedia, Canvas, FileReader
No frameworks: Pure JS for minimal bundle size
Target size:  < 150KB (gzipped)
```

---

## User Flow

### Complete Flow Diagram

```
Product Page
    ↓
[Try On Button] ← Injected by widget
    ↓
┌─────────────────────────────────────────┐
│  STEP 1: BASIC INFO                     │
│  • Height input (cm/inches toggle)      │
│  • Weight input (kg/lbs toggle)         │
│  • Gender select (M/F/Unisex)           │
│  • Photo guidelines (expandable)        │
│  • [Open Camera] [Upload Photo]         │
└────────────┬────────────────────────────┘
             ↓
┌─────────────────────────────────────────┐
│  STEP 2A: CAMERA CAPTURE (if selected)  │
│  • Camera preview with guidelines       │
│  • Front/Back camera toggle             │
│  • Capture button → 3 second countdown  │
│  • Photo preview → [Retake] [Use Photo] │
│  • Repeat for side pose                 │
└────────────┬────────────────────────────┘
             ↓
┌─────────────────────────────────────────┐
│  STEP 2B: UPLOAD (if selected)          │
│  • File picker for front pose           │
│  • Image preview                        │
│  • File picker for side pose            │
│  • Both images preview                  │
└────────────┬────────────────────────────┘
             ↓
     [Image Validation]
     ↓ (if fail) → Show error, allow retake
     ↓ (if pass)
┌─────────────────────────────────────────┐
│  STEP 3: PROCESSING                     │
│  • Loading spinner                      │
│  • Progress bar (0-100%)                │
│  • Status text: "Analyzing images..."   │
└────────────┬────────────────────────────┘
             ↓
┌─────────────────────────────────────────┐
│  STEP 4: MEASUREMENTS DISPLAY           │
│  ┌─────────────┬───────────────────────┐│
│  │ LEFT        │ RIGHT                 ││
│  │ • Height    │ What's Next:          ││
│  │ • Shoulder  │ 1. Review your        ││
│  │ • Chest ✓   │    measurements       ││
│  │ • Waist ✓   │ 2. Generate try-on    ││
│  │ • Hip ✓     │ 3. View results       ││
│  │ • Inseam    │                       ││
│  │ • Arm       │ [View Your Fit] →     ││
│  │ • ...       │                       ││
│  │             │ Confidence: 87%       ││
│  └─────────────┴───────────────────────┘│
│  All measurements read-only             │
└────────────┬────────────────────────────┘
             ↓
     [Click "View Your Fit"]
             ↓
┌─────────────────────────────────────────┐
│  STEP 5: GENERATING RESULTS             │
│  • Loading spinner                      │
│  • "Creating your virtual try-on..."    │
│  • Estimated time: 45 seconds           │
└────────────┬────────────────────────────┘
             ↓
┌─────────────────────────────────────────┐
│  STEP 6: RESULTS VIEW                   │
│  ┌──────────────────┬──────────────────┐│
│  │ TOP LEFT         │ TOP RIGHT        ││
│  │ Virtual Try-On   │ Style Templates  ││
│  │ [Generated Img]  │ ┌──┬──┬──┬──┐   ││
│  │                  │ │🏢│🌆│🌳│💼│   ││
│  │                  │ └──┴──┴──┴──┘   ││
│  │                  │ [Try It][Reset]  ││
│  │                  │                  ││
│  │                  │ [Share Icons]    ││
│  │                  │ FB TW IG CP      ││
│  ├──────────────────┼──────────────────┤│
│  │ BOTTOM LEFT      │ BOTTOM RIGHT     ││
│  │ Fit Heatmap      │ Size Selection   ││
│  │ [Body outline    │ Recommended: M   ││
│  │  with colored    │ ┌───────────┐   ││
│  │  regions]        │ │ XS S [M] L│   ││
│  │                  │ └───────────┘   ││
│  │ Legend:          │                  ││
│  │ 🟢 Perfect       │ Product Name     ││
│  │ 🟡 Loose         │ $49.99           ││
│  │ 🔴 Tight         │ Size: M          ││
│  │                  │                  ││
│  │                  │ [Add to Cart]    ││
│  └──────────────────┴──────────────────┘│
└────────────┬────────────────────────────┘
             ↓
     [Click "Add to Cart"]
             ↓
┌─────────────────────────────────────────┐
│  SUCCESS MODAL                          │
│  ✓ Added to Cart!                       │
│  [View Cart] [Continue Shopping]        │
└─────────────────────────────────────────┘
```

---

## Component Specifications

### 1. Entry Point - Try On Button

**Location:** Below "Add to Cart" button on product page

**HTML Structure:**
```html
<button id="vto-trigger-btn" class="vto-button vto-button--primary">
  <svg class="vto-button__icon" viewBox="0 0 24 24">
    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
  </svg>
  <span class="vto-button__text">Try Me On</span>
</button>
```

**Styling:**
```css
.vto-button {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 12px 24px;
  border: 2px solid #000;
  background: #fff;
  color: #000;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  border-radius: 4px;
  margin-top: 12px;
  width: 100%;
  justify-content: center;
}

.vto-button:hover {
  background: #000;
  color: #fff;
}

.vto-button__icon {
  width: 20px;
  height: 20px;
  fill: currentColor;
}
```

**Behavior:**
- Detects product page using `window.location.pathname.includes('/products/')`
- Injects button after add-to-cart button
- On click: Opens modal with Step 1

**Detection Logic:**
```javascript
function findAddToCartButton() {
  // Try multiple selectors for different themes
  const selectors = [
    'button[name="add"]',
    '.product-form__submit',
    '[data-add-to-cart]',
    '.btn--add-to-cart'
  ];
  
  for (const selector of selectors) {
    const element = document.querySelector(selector);
    if (element) return element;
  }
  
  return null;
}

function injectButton() {
  const addToCartBtn = findAddToCartButton();
  if (!addToCartBtn) {
    console.warn('VTO: Could not find add-to-cart button');
    return;
  }
  
  const container = addToCartBtn.parentNode;
  const button = createTryOnButton();
  
  container.insertBefore(button, addToCartBtn.nextSibling);
}
```

---

### 2. Modal Container

**Base Structure:**
```html
<div id="vto-modal-overlay" class="vto-modal-overlay">
  <div class="vto-modal">
    <button class="vto-modal__close" aria-label="Close">×</button>
    
    <div class="vto-modal__header">
      <h2 class="vto-modal__title">Virtual Try-On</h2>
      <div class="vto-progress-steps">
        <div class="vto-progress-step vto-progress-step--active">Info</div>
        <div class="vto-progress-step">Photos</div>
        <div class="vto-progress-step">Results</div>
      </div>
    </div>
    
    <div class="vto-modal__body">
      <!-- Step content rendered here -->
    </div>
  </div>
</div>
```

**Styling:**
```css
.vto-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.8);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 999999;
  padding: 20px;
  animation: fadeIn 0.3s ease;
}

.vto-modal {
  background: #fff;
  border-radius: 12px;
  max-width: 900px;
  width: 100%;
  max-height: 90vh;
  overflow-y: auto;
  position: relative;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.vto-modal__close {
  position: absolute;
  top: 16px;
  right: 16px;
  background: none;
  border: none;
  font-size: 32px;
  cursor: pointer;
  color: #666;
  z-index: 10;
}

.vto-modal__close:hover {
  color: #000;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}
```

---

### 3. Step 1 - Basic Info Screen

**Component:** `BasicInfoScreen`

**HTML:**
```html
<div class="vto-step vto-step--basic-info">
  <div class="vto-form">
    <div class="vto-form-group">
      <label for="vto-height">Height *</label>
      <div class="vto-input-with-unit">
        <input 
          type="number" 
          id="vto-height" 
          placeholder="175" 
          min="120" 
          max="230"
          step="0.1"
          required
        />
        <select id="vto-height-unit">
          <option value="cm">cm</option>
          <option value="inches">inches</option>
        </select>
      </div>
    </div>
    
    <div class="vto-form-group">
      <label for="vto-weight">Weight (optional)</label>
      <div class="vto-input-with-unit">
        <input 
          type="number" 
          id="vto-weight" 
          placeholder="70"
          min="30"
          max="200"
          step="0.1"
        />
        <select id="vto-weight-unit">
          <option value="kg">kg</option>
          <option value="lbs">lbs</option>
        </select>
      </div>
    </div>
    
    <div class="vto-form-group">
      <label for="vto-gender">Gender</label>
      <select id="vto-gender">
        <option value="male">Male</option>
        <option value="female">Female</option>
        <option value="unisex">Prefer not to say</option>
      </select>
    </div>
    
    <div class="vto-guidelines">
      <button class="vto-guidelines__toggle" id="vto-show-guidelines">
        <svg class="vto-icon"><!-- info icon --></svg>
        Photo Guidelines (Click to view)
      </button>
      
      <div class="vto-guidelines__content" id="vto-guidelines-content" style="display:none;">
        <h4>For Best Results:</h4>
        <ul class="vto-guidelines__list">
          <li>✓ Stand 6-8 feet from camera</li>
          <li>✓ Wear form-fitting clothes (not baggy)</li>
          <li>✓ Stand straight, arms slightly away from body</li>
          <li>✓ Good lighting (bright room, natural light best)</li>
          <li>✓ Plain background (solid color wall)</li>
          <li>✓ Remove jackets/coats</li>
        </ul>
        
        <div class="vto-example-images">
          <div class="vto-example vto-example--good">
            <img src="good-example.jpg" alt="Good example">
            <span class="vto-label vto-label--success">✓ Good</span>
          </div>
          <div class="vto-example vto-example--bad">
            <img src="bad-example.jpg" alt="Bad example">
            <span class="vto-label vto-label--error">✗ Avoid</span>
          </div>
        </div>
      </div>
    </div>
    
    <div class="vto-actions">
      <button class="vto-button vto-button--secondary" id="vto-upload-btn">
        <svg class="vto-icon"><!-- upload icon --></svg>
        Upload Photos
      </button>
      <button class="vto-button vto-button--primary" id="vto-camera-btn">
        <svg class="vto-icon"><!-- camera icon --></svg>
        Open Camera
      </button>
    </div>
  </div>
</div>
```

**Validation:**
```javascript
function validateBasicInfo() {
  const height = parseFloat(document.getElementById('vto-height').value);
  const heightUnit = document.getElementById('vto-height-unit').value;
  
  if (!height) {
    showError('Please enter your height');
    return false;
  }
  
  // Convert to cm if needed
  const heightCm = heightUnit === 'inches' ? height * 2.54 : height;
  
  if (heightCm < 120 || heightCm > 230) {
    showError('Height must be between 120-230 cm (47-90 inches)');
    return false;
  }
  
  return true;
}
```

---

### 4. Step 2 - Camera Capture Screen

**Component:** `CameraScreen`

**HTML:**
```html
<div class="vto-step vto-step--camera">
  <div class="vto-camera-container">
    <div class="vto-camera-header">
      <h3 id="vto-camera-title">Take Front Pose Photo</h3>
      <button class="vto-button vto-button--small" id="vto-switch-camera">
        <svg class="vto-icon"><!-- flip icon --></svg>
        Switch Camera
      </button>
    </div>
    
    <div class="vto-camera-preview">
      <video id="vto-video" autoplay playsinline></video>
      
      <!-- Alignment guide overlay -->
      <div class="vto-camera-overlay">
        <div class="vto-alignment-guide">
          <div class="vto-guide-outline">
            <!-- Human outline SVG -->
            <svg viewBox="0 0 200 400" class="vto-guide-svg">
              <path d="M100,40 C110,40 120,50 120,60 L120,100 L140,140 L140,300 L120,390 L80,390 L60,300 L60,140 L80,100 L80,60 C80,50 90,40 100,40 Z" 
                    stroke="white" 
                    stroke-width="3" 
                    fill="none" 
                    stroke-dasharray="5,5" />
            </svg>
          </div>
          <p class="vto-guide-text">Align your body with the outline</p>
        </div>
      </div>
      
      <!-- Countdown overlay -->
      <div class="vto-countdown" id="vto-countdown" style="display:none;">
        <span class="vto-countdown__number">3</span>
      </div>
      
      <!-- Canvas for capturing -->
      <canvas id="vto-canvas" style="display:none;"></canvas>
    </div>
    
    <div class="vto-camera-controls">
      <button class="vto-button vto-button--capture" id="vto-capture-btn">
        <span class="vto-capture-icon"></span>
      </button>
      <p class="vto-help-text">Click to capture (3 second timer)</p>
    </div>
  </div>
</div>
```

**Camera Logic:**
```javascript
class CameraScreen {
  constructor() {
    this.stream = null;
    this.video = null;
    this.currentPose = 'front'; // or 'side'
    this.facingMode = 'user'; // or 'environment'
  }
  
  async startCamera() {
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: this.facingMode,
          width: { ideal: 1280 },
          height: { ideal: 1920 }
        },
        audio: false
      });
      
      this.video = document.getElementById('vto-video');
      this.video.srcObject = this.stream;
      await this.video.play();
      
    } catch (error) {
      if (error.name === 'NotAllowedError') {
        this.showPermissionDeniedMessage();
      } else {
        this.showCameraErrorMessage();
      }
    }
  }
  
  switchCamera() {
    this.facingMode = this.facingMode === 'user' ? 'environment' : 'user';
    this.stopCamera();
    this.startCamera();
  }
  
  async capturePhoto() {
    // Start countdown
    await this.showCountdown();
    
    // Capture frame
    const canvas = document.getElementById('vto-canvas');
    const context = canvas.getContext('2d');
    
    canvas.width = this.video.videoWidth;
    canvas.height = this.video.videoHeight;
    
    context.drawImage(this.video, 0, 0);
    
    // Convert to blob
    return new Promise((resolve) => {
      canvas.toBlob((blob) => {
        resolve(blob);
      }, 'image/jpeg', 0.95);
    });
  }
  
  async showCountdown() {
    const countdown = document.getElementById('vto-countdown');
    const number = countdown.querySelector('.vto-countdown__number');
    
    countdown.style.display = 'flex';
    
    for (let i = 3; i > 0; i--) {
      number.textContent = i;
      await new Promise(resolve => setTimeout(resolve, 1000));
    }
    
    countdown.style.display = 'none';
  }
  
  stopCamera() {
    if (this.stream) {
      this.stream.getTracks().forEach(track => track.stop());
      this.stream = null;
    }
  }
  
  showPermissionDeniedMessage() {
    alert('Camera access denied. Please allow camera access or use the upload option.');
  }
}
```

**Photo Preview:**
```html
<div class="vto-photo-preview">
  <img id="vto-preview-image" src="" alt="Captured photo">
  <div class="vto-preview-actions">
    <button class="vto-button vto-button--secondary" id="vto-retake-btn">
      ← Retake
    </button>
    <button class="vto-button vto-button--primary" id="vto-use-photo-btn">
      Use Photo →
    </button>
  </div>
</div>
```

---

### 5. Step 2B - Upload Photos Screen

**Component:** `UploadScreen`

**HTML:**
```html
<div class="vto-step vto-step--upload">
  <div class="vto-upload-container">
    <h3>Upload Your Photos</h3>
    
    <div class="vto-upload-grid">
      <!-- Front pose upload -->
      <div class="vto-upload-box" id="vto-upload-front">
        <input 
          type="file" 
          id="vto-file-front" 
          accept="image/jpeg,image/png,image/webp"
          style="display:none;"
        />
        <label for="vto-file-front" class="vto-upload-label">
          <div class="vto-upload-icon">
            <svg><!-- upload cloud icon --></svg>
          </div>
          <p class="vto-upload-text">
            <strong>Front Pose Photo</strong><br>
            Click to select or drag & drop
          </p>
        </label>
        <div class="vto-upload-preview" style="display:none;">
          <img id="vto-preview-front" src="" alt="Front pose">
          <button class="vto-remove-photo" data-pose="front">×</button>
        </div>
      </div>
      
      <!-- Side pose upload -->
      <div class="vto-upload-box" id="vto-upload-side">
        <input 
          type="file" 
          id="vto-file-side" 
          accept="image/jpeg,image/png,image/webp"
          style="display:none;"
        />
        <label for="vto-file-side" class="vto-upload-label">
          <div class="vto-upload-icon">
            <svg><!-- upload cloud icon --></svg>
          </div>
          <p class="vto-upload-text">
            <strong>Side Pose Photo</strong><br>
            Click to select or drag & drop
          </p>
        </label>
        <div class="vto-upload-preview" style="display:none;">
          <img id="vto-preview-side" src="" alt="Side pose">
          <button class="vto-remove-photo" data-pose="side">×</button>
        </div>
      </div>
    </div>
    
    <div class="vto-actions">
      <button class="vto-button vto-button--secondary" id="vto-back-to-camera">
        ← Use Camera Instead
      </button>
      <button 
        class="vto-button vto-button--primary" 
        id="vto-upload-continue-btn"
        disabled
      >
        Continue →
      </button>
    </div>
  </div>
</div>
```

**Upload Logic:**
```javascript
class UploadScreen {
  constructor() {
    this.frontPhoto = null;
    this.sidePhoto = null;
  }
  
  setupDragAndDrop() {
    ['front', 'side'].forEach(pose => {
      const box = document.getElementById(`vto-upload-${pose}`);
      
      box.addEventListener('dragover', (e) => {
        e.preventDefault();
        box.classList.add('vto-upload-box--dragover');
      });
      
      box.addEventListener('dragleave', () => {
        box.classList.remove('vto-upload-box--dragover');
      });
      
      box.addEventListener('drop', (e) => {
        e.preventDefault();
        box.classList.remove('vto-upload-box--dragover');
        
        const file = e.dataTransfer.files[0];
        this.handleFile(file, pose);
      });
    });
  }
  
  handleFile(file, pose) {
    // Validate file
    if (!file.type.match('image/(jpeg|png|webp)')) {
      alert('Please upload a JPEG, PNG, or WebP image');
      return;
    }
    
    if (file.size > 10 * 1024 * 1024) {
      alert('File size must be less than 10MB');
      return;
    }
    
    // Store file
    if (pose === 'front') {
      this.frontPhoto = file;
    } else {
      this.sidePhoto = file;
    }
    
    // Show preview
    const reader = new FileReader();
    reader.onload = (e) => {
      const preview = document.getElementById(`vto-preview-${pose}`);
      preview.src = e.target.result;
      
      const label = document.querySelector(`#vto-upload-${pose} .vto-upload-label`);
      const previewContainer = document.querySelector(`#vto-upload-${pose} .vto-upload-preview`);
      
      label.style.display = 'none';
      previewContainer.style.display = 'block';
    };
    reader.readAsDataURL(file);
    
    // Enable continue button if both photos uploaded
    this.checkCanContinue();
  }
  
  checkCanContinue() {
    const continueBtn = document.getElementById('vto-upload-continue-btn');
    continueBtn.disabled = !(this.frontPhoto && this.sidePhoto);
  }
}
```

---

### 6. Image Validation Screen

**Component:** `ValidationScreen`

**HTML:**
```html
<div class="vto-step vto-step--validation">
  <div class="vto-validation-container">
    <div class="vto-spinner"></div>
    <h3>Validating Photos...</h3>
    <div class="vto-progress-bar">
      <div class="vto-progress-fill" style="width: 50%;"></div>
    </div>
    <p class="vto-status-text">Checking image quality...</p>
  </div>
</div>
```

**Validation Flow:**
```javascript
async function validatePhotos(frontPhoto, sidePhoto) {
  updateStatus('Checking front pose...', 25);
  
  // Validate front photo
  const frontValidation = await api.validateImage(frontPhoto, 'front');
  
  if (!frontValidation.valid) {
    showValidationError('Front Pose', frontValidation.issues);
    return false;
  }
  
  updateStatus('Checking side pose...', 50);
  
  // Validate side photo
  const sideValidation = await api.validateImage(sidePhoto, 'side');
  
  if (!sideValidation.valid) {
    showValidationError('Side Pose', sideValidation.issues);
    return false;
  }
  
  updateStatus('Photos validated!', 100);
  return true;
}

function showValidationError(poseType, issues) {
  const errorHtml = `
    <div class="vto-validation-error">
      <div class="vto-error-icon">⚠️</div>
      <h3>${poseType} Photo Issue</h3>
      <ul class="vto-error-list">
        ${issues.map(issue => `<li>${issue}</li>`).join('')}
      </ul>
      <div class="vto-actions">
        <button class="vto-button vto-button--primary" id="vto-retake-photos">
          Take New Photos
        </button>
      </div>
    </div>
  `;
  
  document.querySelector('.vto-modal__body').innerHTML = errorHtml;
}
```

---

### 7. Step 3 - Processing Screen

**Component:** `ProcessingScreen`

**HTML:**
```html
<div class="vto-step vto-step--processing">
  <div class="vto-processing-container">
    <div class="vto-spinner-large"></div>
    <h3>Analyzing Your Photos...</h3>
    <div class="vto-progress-bar">
      <div class="vto-progress-fill" id="vto-progress-fill" style="width: 0%;"></div>
    </div>
    <p class="vto-status-text" id="vto-status-text">Starting analysis...</p>
    <p class="vto-estimate-text">Estimated time: 5-10 seconds</p>
  </div>
</div>
```

**Progress Simulation:**
```javascript
async function extractMeasurements(frontPhoto, sidePhoto, height, weight, gender) {
  const formData = new FormData();
  formData.append('front_image', frontPhoto);
  formData.append('side_image', sidePhoto);
  formData.append('height_cm', height);
  formData.append('weight_kg', weight || '');
  formData.append('gender', gender);
  
  // Start progress animation
  animateProgress([
    { progress: 20, text: 'Detecting body pose...', delay: 1000 },
    { progress: 40, text: 'Calculating proportions...', delay: 2000 },
    { progress: 60, text: 'Measuring dimensions...', delay: 3000 },
    { progress: 80, text: 'Finalizing measurements...', delay: 4000 }
  ]);
  
  try {
    const response = await fetch(`${API_URL}/api/v1/measurements/extract`, {
      method: 'POST',
      headers: {
        'X-Session-ID': sessionId,
        'X-Store-ID': storeId
      },
      body: formData
    });
    
    if (!response.ok) {
      throw new Error('Measurement extraction failed');
    }
    
    const data = await response.json();
    
    updateProgress(100, 'Complete!');
    
    return data;
    
  } catch (error) {
    showExtractionError(error);
    throw error;
  }
}

function animateProgress(steps) {
  steps.forEach(step => {
    setTimeout(() => {
      updateProgress(step.progress, step.text);
    }, step.delay);
  });
}

function updateProgress(percent, text) {
  document.getElementById('vto-progress-fill').style.width = `${percent}%`;
  document.getElementById('vto-status-text').textContent = text;
}
```

---

### 8. Step 4 - Measurements Display Screen

**Component:** `MeasurementsScreen`

**HTML:**
```html
<div class="vto-step vto-step--measurements">
  <div class="vto-measurements-header">
    <h2>✓ Measurements Complete</h2>
    <div class="vto-confidence-badge vto-confidence--high">
      Confidence: <strong>87%</strong>
    </div>
  </div>
  
  <div class="vto-measurements-grid">
    <!-- LEFT: Measurements List -->
    <div class="vto-measurements-list">
      <h3>Your Measurements</h3>
      
      <div class="vto-measurement-item">
        <span class="vto-measurement-label">Height</span>
        <span class="vto-measurement-value">175.0 cm</span>
        <span class="vto-measurement-status vto-status--user-input">📝</span>
      </div>
      
      <div class="vto-measurement-item">
        <span class="vto-measurement-label">Shoulder Width</span>
        <span class="vto-measurement-value">43.2 cm</span>
        <span class="vto-measurement-status vto-status--measured">✓</span>
      </div>
      
      <div class="vto-measurement-item">
        <span class="vto-measurement-label">Chest</span>
        <span class="vto-measurement-value">94.5 cm</span>
        <span class="vto-measurement-status vto-status--measured">✓</span>
      </div>
      
      <div class="vto-measurement-item">
        <span class="vto-measurement-label">Waist</span>
        <span class="vto-measurement-value">78.3 cm</span>
        <span class="vto-measurement-status vto-status--measured">✓</span>
      </div>
      
      <div class="vto-measurement-item">
        <span class="vto-measurement-label">Hip</span>
        <span class="vto-measurement-value">98.1 cm</span>
        <span class="vto-measurement-status vto-status--measured">✓</span>
      </div>
      
      <div class="vto-measurement-item">
        <span class="vto-measurement-label">Inseam</span>
        <span class="vto-measurement-value">81.2 cm</span>
        <span class="vto-measurement-status vto-status--measured">✓</span>
      </div>
      
      <div class="vto-measurement-item">
        <span class="vto-measurement-label">Arm Length</span>
        <span class="vto-measurement-value">61.4 cm</span>
        <span class="vto-measurement-status vto-status--measured">✓</span>
      </div>
      
      <div class="vto-measurement-item vto-measurement-item--collapsed">
        <button class="vto-expand-btn">
          + Show 8 more measurements
        </button>
      </div>
    </div>
    
    <!-- RIGHT: What's Next -->
    <div class="vto-whats-next">
      <h3>What's Next</h3>
      <div class="vto-next-steps">
        <div class="vto-next-step vto-next-step--complete">
          <span class="vto-step-number">✓</span>
          <span class="vto-step-text">Photos analyzed</span>
        </div>
        <div class="vto-next-step vto-next-step--complete">
          <span class="vto-step-number">✓</span>
          <span class="vto-step-text">Measurements extracted</span>
        </div>
        <div class="vto-next-step vto-next-step--current">
          <span class="vto-step-number">3</span>
          <span class="vto-step-text">Generate virtual try-on</span>
        </div>
      </div>
      
      <div class="vto-cta-card">
        <p>Ready to see how this product looks on you?</p>
        <button class="vto-button vto-button--primary vto-button--large" id="vto-generate-btn">
          View Your Fit →
        </button>
      </div>
      
      <p class="vto-note">
        <small>Note: All measurements are read-only and used to recommend the best size for you.</small>
      </p>
    </div>
  </div>
</div>
```

**Expanded Measurements:**
```javascript
function showAllMeasurements() {
  const allMeasurements = [
    { label: 'Torso Length', value: '65.8 cm', measured: true },
    { label: 'Neck', value: '38.5 cm', measured: true },
    { label: 'Thigh', value: '58.2 cm', measured: true },
    { label: 'Upper Arm', value: '32.1 cm', measured: true },
    { label: 'Wrist', value: '17.3 cm', measured: true },
    { label: 'Calf', value: '36.8 cm', measured: true },
    { label: 'Ankle', value: '23.4 cm', measured: true },
    { label: 'Bicep', value: '31.5 cm', measured: true }
  ];
  
  // Render additional measurements
  // ...
}
```

---

### 9. Step 5 - Generating Try-On Screen

**Component:** `GeneratingScreen`

**HTML:**
```html
<div class="vto-step vto-step--generating">
  <div class="vto-generating-container">
    <div class="vto-spinner-xl"></div>
    <h2>Creating Your Virtual Try-On...</h2>
    <div class="vto-progress-bar">
      <div class="vto-progress-fill" id="vto-generation-progress"></div>
    </div>
    <p class="vto-status-text" id="vto-generation-status">Preparing images...</p>
    <p class="vto-estimate">Estimated time: 45 seconds</p>
  </div>
</div>
```

**Generation Flow:**
```javascript
async function generateTryOn(measurementId, productId, size) {
  try {
    // 1. Initiate generation
    updateStatus('Starting generation...', 10);
    
    const response = await fetch(`${API_URL}/api/v1/tryon/generate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Session-ID': sessionId
      },
      body: JSON.stringify({
        measurement_id: measurementId,
        product_id: productId,
        size: size
      })
    });
    
    const { try_on_id, estimated_time_seconds } = await response.json();
    
    // 2. Poll for completion
    return await pollForCompletion(try_on_id, estimated_time_seconds);
    
  } catch (error) {
    showGenerationError(error);
    throw error;
  }
}

async function pollForCompletion(tryOnId, estimatedTime) {
  const startTime = Date.now();
  const pollInterval = 2000; // 2 seconds
  const maxAttempts = 60; // 2 minutes max
  
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    await new Promise(resolve => setTimeout(resolve, pollInterval));
    
    // Update progress based on elapsed time
    const elapsed = (Date.now() - startTime) / 1000;
    const progress = Math.min(90, (elapsed / estimatedTime) * 100);
    updateStatus('Generating try-on image...', progress);
    
    // Check status
    const response = await fetch(`${API_URL}/api/v1/tryon/${tryOnId}/status`, {
      headers: { 'X-Session-ID': sessionId }
    });
    
    const data = await response.json();
    
    if (data.status === 'completed') {
      updateStatus('Complete!', 100);
      return data;
    } else if (data.status === 'failed') {
      throw new Error(data.error);
    }
  }
  
  throw new Error('Generation timed out');
}
```

---

### 10. Step 6 - Results View Screen

**Component:** `ResultsScreen`

This is the most complex screen with 4 quadrants.

**HTML Structure:**
```html
<div class="vto-step vto-step--results">
  <div class="vto-results-container">
    <!-- TOP ROW -->
    <div class="vto-results-row vto-results-row--top">
      
      <!-- TOP LEFT: Virtual Try-On Image -->
      <div class="vto-results-quad vto-quad--tryon">
        <h3>Your Virtual Try-On</h3>
        <div class="vto-tryon-image-container">
          <img 
            id="vto-tryon-result" 
            src="result-url.png" 
            alt="Virtual try-on result"
            class="vto-tryon-image"
          />
        </div>
      </div>
      
      <!-- TOP RIGHT: Style Templates -->
      <div class="vto-results-quad vto-quad--styles">
        <h3>Try Different Styles</h3>
        
        <div class="vto-style-templates">
          <button class="vto-style-template" data-style="studio_1">
            <img src="studio-1-thumb.jpg" alt="Studio 1">
            <span class="vto-style-name">Studio</span>
          </button>
          <button class="vto-style-template" data-style="outdoor_1">
            <img src="outdoor-1-thumb.jpg" alt="Outdoor">
            <span class="vto-style-name">Outdoor</span>
          </button>
          <button class="vto-style-template" data-style="urban_1">
            <img src="urban-1-thumb.jpg" alt="Urban">
            <span class="vto-style-name">Urban</span>
          </button>
          <button class="vto-style-template" data-style="elegant_1">
            <img src="elegant-1-thumb.jpg" alt="Elegant">
            <span class="vto-style-name">Elegant</span>
          </button>
        </div>
        
        <div class="vto-style-actions">
          <button 
            class="vto-button vto-button--small vto-button--secondary" 
            id="vto-reset-style"
            disabled
          >
            Reset
          </button>
        </div>
        
        <hr class="vto-divider">
        
        <h4>Share Your Look</h4>
        <div class="vto-share-buttons">
          <button class="vto-share-btn vto-share-fb" title="Share on Facebook">
            <svg class="vto-icon"><!-- Facebook icon --></svg>
          </button>
          <button class="vto-share-btn vto-share-tw" title="Share on Twitter">
            <svg class="vto-icon"><!-- Twitter icon --></svg>
          </button>
          <button class="vto-share-btn vto-share-ig" title="Share on Instagram">
            <svg class="vto-icon"><!-- Instagram icon --></svg>
          </button>
          <button class="vto-share-btn vto-share-copy" title="Copy link">
            <svg class="vto-icon"><!-- Link icon --></svg>
          </button>
        </div>
      </div>
    </div>
    
    <!-- BOTTOM ROW -->
    <div class="vto-results-row vto-results-row--bottom">
      
      <!-- BOTTOM LEFT: Heatmap -->
      <div class="vto-results-quad vto-quad--heatmap">
        <h3>Fit Analysis</h3>
        
        <div class="vto-heatmap-container">
          <div class="vto-body-outline">
            <!-- Base body outline image -->
            <img src="body-outline.svg" alt="Body outline" class="vto-outline-base">
            
            <!-- SVG overlay with colored regions -->
            <div class="vto-heatmap-overlay" id="vto-heatmap-overlay">
              <!-- Injected from backend API -->
            </div>
          </div>
        </div>
        
        <div class="vto-heatmap-legend">
          <div class="vto-legend-item">
            <span class="vto-legend-color" style="background: #4CAF50;"></span>
            <span class="vto-legend-label">Perfect Fit</span>
          </div>
          <div class="vto-legend-item">
            <span class="vto-legend-color" style="background: #8BC34A;"></span>
            <span class="vto-legend-label">Good Fit</span>
          </div>
          <div class="vto-legend-item">
            <span class="vto-legend-color" style="background: #FFC107;"></span>
            <span class="vto-legend-label">Slightly Loose/Tight</span>
          </div>
          <div class="vto-legend-item">
            <span class="vto-legend-color" style="background: #F44336;"></span>
            <span class="vto-legend-label">Too Loose/Tight</span>
          </div>
        </div>
      </div>
      
      <!-- BOTTOM RIGHT: Size Selection & Product -->
      <div class="vto-results-quad vto-quad--product">
        <h3>Recommended Size</h3>
        
        <div class="vto-size-recommendation">
          <div class="vto-recommended-badge">
            <span class="vto-size-name">M</span>
            <span class="vto-confidence-tag">Best Fit (92%)</span>
          </div>
        </div>
        
        <div class="vto-all-sizes">
          <label>All Sizes:</label>
          <div class="vto-size-buttons">
            <button class="vto-size-btn" data-size="XS">XS</button>
            <button class="vto-size-btn" data-size="S">S</button>
            <button class="vto-size-btn vto-size-btn--recommended" data-size="M">M</button>
            <button class="vto-size-btn" data-size="L">L</button>
            <button class="vto-size-btn" data-size="XL">XL</button>
          </div>
          <p class="vto-size-note">
            <small>Click a size to see how it would fit</small>
          </p>
        </div>
        
        <hr class="vto-divider">
        
        <div class="vto-product-info">
          <h4 id="vto-product-name">Classic Denim Jacket</h4>
          <div class="vto-product-price" id="vto-product-price">$49.99</div>
          <div class="vto-selected-size">
            Selected Size: <strong id="vto-display-size">M</strong>
          </div>
        </div>
        
        <button class="vto-button vto-button--primary vto-button--large vto-button--cart" id="vto-add-to-cart">
          <svg class="vto-icon"><!-- Cart icon --></svg>
          Add to Cart
        </button>
        
        <button class="vto-button vto-button--secondary vto-button--full-width" id="vto-try-another-product">
          Try Another Product
        </button>
      </div>
    </div>
  </div>
</div>
```

**Styling (Grid Layout):**
```css
.vto-results-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 20px;
}

.vto-results-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

.vto-results-quad {
  background: #f9f9f9;
  border-radius: 8px;
  padding: 20px;
}

.vto-quad--tryon {
  min-height: 400px;
}

.vto-tryon-image-container {
  position: relative;
  background: #fff;
  border-radius: 4px;
  overflow: hidden;
}

.vto-tryon-image {
  width: 100%;
  height: auto;
  display: block;
}

/* Style templates grid */
.vto-style-templates {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  margin: 15px 0;
}

.vto-style-template {
  border: 2px solid #ddd;
  border-radius: 4px;
  padding: 8px;
  cursor: pointer;
  background: #fff;
  transition: all 0.2s;
}

.vto-style-template:hover {
  border-color: #000;
  transform: scale(1.05);
}

.vto-style-template img {
  width: 100%;
  aspect-ratio: 3/4;
  object-fit: cover;
  border-radius: 4px;
}

/* Heatmap */
.vto-body-outline {
  position: relative;
  max-width: 300px;
  margin: 0 auto;
}

.vto-heatmap-overlay svg {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

/* Size buttons */
.vto-size-buttons {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.vto-size-btn {
  padding: 10px 20px;
  border: 2px solid #ddd;
  background: #fff;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 600;
  transition: all 0.2s;
}

.vto-size-btn:hover {
  border-color: #000;
}

.vto-size-btn--recommended {
  border-color: #4CAF50;
  background: #E8F5E9;
}

/* Responsive */
@media (max-width: 768px) {
  .vto-results-row {
    grid-template-columns: 1fr;
  }
  
  .vto-style-templates {
    grid-template-columns: repeat(2, 1fr);
  }
}
```

**Interactive Features:**

```javascript
// Size selection changes heatmap
document.querySelectorAll('.vto-size-btn').forEach(btn => {
  btn.addEventListener('click', async () => {
    const size = btn.dataset.size;
    
    // Update active state
    document.querySelectorAll('.vto-size-btn').forEach(b => {
      b.classList.remove('vto-size-btn--active');
    });
    btn.classList.add('vto-size-btn--active');
    
    // Update displayed size
    document.getElementById('vto-display-size').textContent = size;
    
    // Fetch new heatmap for this size
    showLoadingOverlay('Loading fit analysis...');
    
    try {
      const heatmap = await fetchHeatmap(measurementId, productId, size);
      updateHeatmap(heatmap);
    } catch (error) {
      showError('Failed to load fit analysis');
    } finally {
      hideLoadingOverlay();
    }
  });
});

// Style template selection
document.querySelectorAll('.vto-style-template').forEach(btn => {
  btn.addEventListener('click', async () => {
    const style = btn.dataset.style;
    
    showLoadingOverlay('Applying style...');
    
    try {
      const styledImage = await generateStyledTryOn(tryOnId, style);
      updateTryOnImage(styledImage.result_image_url);
      
      document.getElementById('vto-reset-style').disabled = false;
    } catch (error) {
      showError('Failed to apply style');
    } finally {
      hideLoadingOverlay();
    }
  });
});

// Social sharing
document.querySelector('.vto-share-copy').addEventListener('click', async () => {
  const shareUrl = await generateShareableLink(tryOnId);
  
  try {
    await navigator.clipboard.writeText(shareUrl);
    showToast('Link copied to clipboard!');
  } catch {
    prompt('Copy this link:', shareUrl);
  }
});
```

---

### 11. Success Modal

**Component:** `SuccessModal`

**HTML:**
```html
<div class="vto-success-modal">
  <div class="vto-success-content">
    <div class="vto-success-icon">✓</div>
    <h2>Added to Cart!</h2>
    <p>Your recommended size <strong>M</strong> has been added to your cart.</p>
    
    <div class="vto-success-actions">
      <button class="vto-button vto-button--secondary" id="vto-continue-shopping">
        Continue Shopping
      </button>
      <button class="vto-button vto-button--primary" id="vto-view-cart">
        View Cart →
      </button>
    </div>
  </div>
</div>
```

**Add to Cart Integration:**
```javascript
async function addToCart(productId, variantId, size) {
  try {
    // Use Shopify Cart API
    const response = await fetch('/cart/add.js', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        id: variantId,
        quantity: 1,
        properties: {
          '_vto_size': size,
          '_vto_session': sessionId
        }
      })
    });
    
    if (!response.ok) {
      throw new Error('Failed to add to cart');
    }
    
    // Show success modal
    showSuccessModal(size);
    
    // Track analytics
    trackEvent('add_to_cart', {
      product_id: productId,
      size: size,
      source: 'virtual_try_on'
    });
    
  } catch (error) {
    showError('Failed to add to cart. Please try again.');
  }
}

function showSuccessModal(size) {
  // Replace results view with success modal
  document.querySelector('.vto-modal__body').innerHTML = renderSuccessModal(size);
  
  // Set up button handlers
  document.getElementById('vto-view-cart').addEventListener('click', () => {
    window.location.href = '/cart';
  });
  
  document.getElementById('vto-continue-shopping').addEventListener('click', () => {
    closeModal();
  });
}
```

---

## API Integration

### API Client Module

**File:** `widget/src/api/client.js`

```javascript
class VTOApiClient {
  constructor(config) {
    this.baseUrl = config.apiUrl;
    this.storeId = config.storeId;
    this.sessionId = null;
  }
  
  async createSession(productId) {
    const response = await fetch(`${this.baseUrl}/api/v1/sessions/create`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Store-ID': this.storeId
      },
      body: JSON.stringify({ product_id: productId })
    });
    
    const data = await response.json();
    this.sessionId = data.session_id;
    
    return data;
  }
  
  async validateImage(imageBlob, poseType) {
    const formData = new FormData();
    formData.append('image', imageBlob);
    formData.append('pose_type', poseType);
    
    const response = await fetch(`${this.baseUrl}/api/v1/measurements/validate`, {
      method: 'POST',
      headers: {
        'X-Session-ID': this.sessionId
      },
      body: formData
    });
    
    return await response.json();
  }
  
  async extractMeasurements(frontImage, sideImage, height, weight, gender) {
    const formData = new FormData();
    formData.append('front_image', frontImage);
    formData.append('side_image', sideImage);
    formData.append('height_cm', height);
    formData.append('weight_kg', weight);
    formData.append('gender', gender);
    
    const response = await fetch(`${this.baseUrl}/api/v1/measurements/extract`, {
      method: 'POST',
      headers: {
        'X-Session-ID': this.sessionId,
        'X-Store-ID': this.storeId
      },
      body: formData
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.message);
    }
    
    return await response.json();
  }
  
  async getSizeRecommendation(measurementId, productId) {
    const response = await fetch(`${this.baseUrl}/api/v1/recommendations/size`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Session-ID': this.sessionId
      },
      body: JSON.stringify({
        measurement_id: measurementId,
        product_id: productId
      })
    });
    
    return await response.json();
  }
  
  async generateHeatmap(measurementId, productId, size) {
    const response = await fetch(`${this.baseUrl}/api/v1/heatmap/generate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Session-ID': this.sessionId
      },
      body: JSON.stringify({
        measurement_id: measurementId,
        product_id: productId,
        size: size
      })
    });
    
    return await response.json();
  }
  
  async generateTryOn(measurementId, productId, size, styleReference = null) {
    const response = await fetch(`${this.baseUrl}/api/v1/tryon/generate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Session-ID': this.sessionId
      },
      body: JSON.stringify({
        measurement_id: measurementId,
        product_id: productId,
        size: size,
        style_reference: styleReference
      })
    });
    
    return await response.json();
  }
  
  async getTryOnStatus(tryOnId) {
    const response = await fetch(`${this.baseUrl}/api/v1/tryon/${tryOnId}/status`, {
      headers: {
        'X-Session-ID': this.sessionId
      }
    });
    
    return await response.json();
  }
}

export default VTOApiClient;
```

---

## State Management

### Simple State Machine

**File:** `widget/src/state/StateManager.js`

```javascript
class StateManager {
  constructor() {
    this.state = {
      currentStep: null,
      sessionId: null,
      productId: null,
      
      // User inputs
      height: null,
      weight: null,
      gender: null,
      
      // Photos
      frontPhoto: null,
      sidePhoto: null,
      
      // Results
      measurementId: null,
      measurements: null,
      recommendedSize: null,
      tryOnId: null,
      tryOnImageUrl: null,
      heatmapData: null
    };
    
    this.listeners = [];
  }
  
  setState(updates) {
    this.state = { ...this.state, ...updates };
    this.notifyListeners();
  }
  
  getState(key) {
    return key ? this.state[key] : this.state;
  }
  
  subscribe(listener) {
    this.listeners.push(listener);
    return () => {
      this.listeners = this.listeners.filter(l => l !== listener);
    };
  }
  
  notifyListeners() {
    this.listeners.forEach(listener => listener(this.state));
  }
  
  reset() {
    const productId = this.state.productId; // Keep product ID
    this.state = {
      currentStep: null,
      sessionId: null,
      productId: productId,
      height: null,
      weight: null,
      gender: null,
      frontPhoto: null,
      sidePhoto: null,
      measurementId: null,
      measurements: null,
      recommendedSize: null,
      tryOnId: null,
      tryOnImageUrl: null,
      heatmapData: null
    };
    this.notifyListeners();
  }
}

export default StateManager;
```

---

## Error Handling

### Error Display Component

```javascript
function showError(message, options = {}) {
  const {
    title = 'Oops!',
    allowRetry = true,
    retryAction = null
  } = options;
  
  const errorHtml = `
    <div class="vto-error-screen">
      <div class="vto-error-icon">⚠️</div>
      <h2>${title}</h2>
      <p>${message}</p>
      ${allowRetry ? `
        <div class="vto-error-actions">
          <button class="vto-button vto-button--primary" id="vto-retry-btn">
            Try Again
          </button>
          <button class="vto-button vto-button--secondary" id="vto-cancel-btn">
            Cancel
          </button>
        </div>
      ` : ''}
    </div>
  `;
  
  document.querySelector('.vto-modal__body').innerHTML = errorHtml;
  
  if (allowRetry && retryAction) {
    document.getElementById('vto-retry-btn').addEventListener('click', retryAction);
  }
  
  document.getElementById('vto-cancel-btn')?.addEventListener('click', closeModal);
}

// Specific error handlers
function handleCameraError(error) {
  if (error.name === 'NotAllowedError') {
    showError(
      'Camera access was denied. Please allow camera access in your browser settings, or use the upload option instead.',
      { title: 'Camera Access Denied', allowRetry: false }
    );
  } else if (error.name === 'NotFoundError') {
    showError(
      'No camera was found on your device. Please use the upload option instead.',
      { title: 'Camera Not Found', allowRetry: false }
    );
  } else {
    showError(
      'An error occurred while accessing your camera. Please try again or use the upload option.',
      { title: 'Camera Error', allowRetry: true }
    );
  }
}

function handleMeasurementError(error) {
  showError(
    'We couldn\'t extract measurements from your photos. Please ensure your full body is visible and try again.',
    { 
      title: 'Measurement Error',
      retryAction: () => goToStep('camera')
    }
  );
}

function handleNetworkError(error) {
  showError(
    'A network error occurred. Please check your internet connection and try again.',
    {
      title: 'Connection Error',
      allowRetry: true,
      retryAction: () => window.location.reload()
    }
  );
}
```

---

## Performance

### Bundle Size Optimization

**Webpack Config:**
```javascript
// webpack.config.js
module.exports = {
  entry: './src/index.js',
  output: {
    filename: 'vto-widget.min.js',
    path: path.resolve(__dirname, 'dist'),
  },
  optimization: {
    minimize: true,
    minimizer: [new TerserPlugin({
      terserOptions: {
        compress: {
          drop_console: true, // Remove console.logs in production
        },
      },
    })],
  },
  module: {
    rules: [
      {
        test: /\.css$/,
        use: ['style-loader', 'css-loader', 'postcss-loader'],
      },
    ],
  },
};
```

**Target:** < 150KB gzipped

### Lazy Loading

```javascript
// Load heavy components only when needed
async function loadCameraModule() {
  const { CameraScreen } = await import(/* webpackChunkName: "camera" */ './screens/Camera.js');
  return CameraScreen;
}

// Preload critical assets
function preloadAssets() {
  const assets = [
    '/assets/body-outline.svg',
    '/assets/good-example.jpg',
    '/assets/bad-example.jpg'
  ];
  
  assets.forEach(src => {
    const link = document.createElement('link');
    link.rel = 'prefetch';
    link.href = src;
    document.head.appendChild(link);
  });
}
```

### Image Compression

```javascript
// Compress images before upload
async function compressImage(blob, maxWidth = 1024) {
  return new Promise((resolve) => {
    const img = new Image();
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    
    img.onload = () => {
      const ratio = Math.min(maxWidth / img.width, 1);
      canvas.width = img.width * ratio;
      canvas.height = img.height * ratio;
      
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      
      canvas.toBlob((compressed) => {
        resolve(compressed);
      }, 'image/jpeg', 0.9);
    };
    
    img.src = URL.createObjectURL(blob);
  });
}
```

---

## Browser Support

### Target Browsers
- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+
- Mobile Safari (iOS 14+)
- Chrome Mobile (Android 10+)

### Required APIs
- `getUserMedia` (for camera)
- `FileReader` (for uploads)
- `Fetch API`
- `Canvas API`
- `Clipboard API` (for sharing)

### Polyfills

```javascript
// Check for required features
function checkBrowserSupport() {
  const required = {
    getUserMedia: 'mediaDevices' in navigator,
    fetch: 'fetch' in window,
    canvas: 'HTMLCanvasElement' in window
  };
  
  const unsupported = Object.entries(required)
    .filter(([key, supported]) => !supported)
    .map(([key]) => key);
  
  if (unsupported.length > 0) {
    showBrowserNotSupportedMessage(unsupported);
    return false;
  }
  
  return true;
}
```

---

## Deployment

### CDN Deployment

**Build:**
```bash
npm run build
# Outputs: dist/vto-widget.min.js (< 150KB gzipped)
```

**Upload to CDN:**
```bash
# Cloudflare R2 or similar
aws s3 cp dist/vto-widget.min.js s3://your-cdn/vto/v1/widget.js \
  --cache-control "public, max-age=31536000"
```

**Version Management:**
```
https://cdn.your-app.com/vto/v1.0.0/widget.js
https://cdn.your-app.com/vto/v1.0.1/widget.js
https://cdn.your-app.com/vto/latest/widget.js (symlink)
```

### Script Tag Installation

**Installed by backend during OAuth:**
```javascript
// Backend creates this script tag
{
  event: "onload",
  src: "https://cdn.your-app.com/vto/v1/widget.js?store_id={{store_id}}"
}
```

**Widget auto-initializes:**
```javascript
// widget.js
(function() {
  // Extract store ID from script src
  const script = document.currentScript;
  const params = new URLSearchParams(script.src.split('?')[1]);
  const storeId = params.get('store_id');
  
  // Wait for DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
  
  function init() {
    const widget = new VirtualTryOnWidget({
      storeId: storeId,
      apiUrl: 'https://api.your-app.com'
    });
    
    widget.initialize();
  }
})();
```

---

## Analytics

### Event Tracking

```javascript
function trackEvent(eventName, properties) {
  // Send to backend
  fetch(`${API_URL}/api/v1/analytics/track`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Store-ID': storeId,
      'X-Session-ID': sessionId
    },
    body: JSON.stringify({
      event_type: eventName,
      event_data: properties
    })
  });
  
  // Also send to Google Analytics if available
  if (window.gtag) {
    gtag('event', eventName, properties);
  }
}

// Track key events
trackEvent('widget_opened', { product_id: productId });
trackEvent('photo_captured', { pose_type: 'front' });
trackEvent('measurements_completed', { confidence: 0.87 });
trackEvent('size_recommended', { size: 'M', confidence: 'high' });
trackEvent('tryon_generated', { processing_time: 38.2 });
trackEvent('add_to_cart', { size: 'M', product_id: productId });
```

---

## Testing Checklist

### Manual Testing

- [ ] Button appears on product page (5+ themes)
- [ ] Modal opens on button click
- [ ] Camera permission request works
- [ ] Camera capture works (front & back camera)
- [ ] Upload photos works (drag & drop + click)
- [ ] Image validation shows errors correctly
- [ ] Measurements display correctly
- [ ] Size recommendation makes sense
- [ ] Heatmap renders correctly
- [ ] Try-on image looks realistic
- [ ] Style templates work
- [ ] Size selection updates heatmap
- [ ] Add to cart works
- [ ] Success modal shows
- [ ] Mobile responsive (all screens)
- [ ] Error states display properly
- [ ] Loading states show progress

### Browser Testing

- [ ] Chrome (desktop & mobile)
- [ ] Safari (desktop & iOS)
- [ ] Firefox
- [ ] Edge
- [ ] Samsung Internet (Android)

### Performance Testing

- [ ] Bundle size < 150KB (gzipped)
- [ ] Modal opens in < 500ms
- [ ] Camera starts in < 2s
- [ ] Images upload in < 5s
- [ ] No memory leaks (use Chrome DevTools)

---

**End of Frontend PRD**
