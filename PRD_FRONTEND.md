# Virtual Try-On Shopify App - Frontend PRD (Storefront Widget)

**Version:** 1.1
**Last Updated:** 2026-02-17
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
Widget creates/resumes session
    ↓
Backend checks: Has user's measurements within 24h?
    ↓
┌──────────────────────────────┬────────────────────────────┐
│ NEW USER                     │ RETURNING USER (< 24h)     │
│ (no cached measurements)     │ (has cached measurements)  │
└──────────────────────────────┴────────────────────────────┘
             ↓                              ↓
┌─────────────────────────────┐  ┌─────────────────────────┐
│  STEP 1: BASIC INFO         │  │  SKIP TO PROCESSING     │
│  • Height, Weight, Gender   │  │  • Show "Welcome back!" │
│  • Photo guidelines         │  │  • Use cached data      │
│  • [Camera] [Upload]        │  │  • Generate for new     │
└────────────┬────────────────┘  │    product directly     │
             ↓                    └────────────┬────────────┘
┌─────────────────────────────┐               ↓
│  STEP 2: CAMERA/UPLOAD      │  ┌─────────────────────────┐
│  • Capture front + side     │  │  STEP 5: GENERATING     │
│  • OR upload both           │  │  • Size recommendation  │
└────────────┬────────────────┘  │  • Heatmap generation   │
             ↓                    │  • Try-on generation    │
     [Validation]                 └────────────┬────────────┘
     ↓ (if pass)                               ↓
┌─────────────────────────────┐  ┌─────────────────────────┐
│  STEP 3: PROCESSING         │  │  STEP 6: RESULTS        │
│  • Extract measurements     │  │  • Try-on image         │
└────────────┬────────────────┘  │  • Heatmap              │
             ↓                    │  • Size selector        │
┌─────────────────────────────┐  │  • Add to cart          │
│  STEP 4: MEASUREMENTS       │  └─────────────────────────┘
│  • Display 15 measurements  │
│  • Show confidence score    │
│  • [View Your Fit] →        │
└────────────┬────────────────┘
             ↓
┌─────────────────────────────┐
│  STEP 5: GENERATING         │
│  • Size recommendation      │
│  • Heatmap generation       │
│  • Try-on generation        │
└────────────┬────────────────┘
             ↓
┌─────────────────────────────┐
│  STEP 6: RESULTS            │
│  • Try-on image             │
│  • Heatmap                  │
│  • Size selector            │
│  • Add to cart              │
└─────────────────────────────┘
```

**Cross-Product Flow (User tries on Product B after Product A):**

```
User views Product B
    ↓
Clicks "Try On" button
    ↓
Widget detects user has recent data (< 24h)
    ↓
Skip photos & measurements
    ↓
Show loading: "Generating try-on for new product..."
    ↓
Backend uses cached measurements + Product B images
    ↓
Show results directly (try-on + heatmap + size recommendation)
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
async function generateTryOn(productId) {
  try {
    // 1. Initiate generation (only product_id needed — person image comes from session cache)
    updateStatus('Starting generation...', 10);

    const response = await fetch(`${API_URL}/api/v1/tryon/generate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Session-ID': sessionId,
        'X-Store-ID': storeId
      },
      body: JSON.stringify({
        product_id: productId
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
      // result_image_url is a local endpoint: /api/v1/tryon/{id}/image
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
      
      <!-- TOP RIGHT: Studio Look Backgrounds -->
      <div class="vto-results-quad vto-quad--studio">
        <h3>Studio Look</h3>
        <p class="vto-help-text">Select a background to see yourself in different environments</p>

        <!-- Backgrounds loaded from GET /api/v1/tryon/studio-backgrounds?gender={gender} -->
        <!-- Frontend randomizes display order on each render -->
        <div class="vto-studio-grid" id="vto-studio-grid">
          <!-- "Original" button — always first -->
          <button class="vto-studio-option vto-studio-option--active" data-studio-id="none">
            <div class="vto-studio-thumb vto-studio-thumb--original">
              <span>Original</span>
            </div>
          </button>

          <!-- Studio backgrounds loaded dynamically -->
          <!-- Each one rendered as: -->
          <!--
          <button class="vto-studio-option" data-studio-id="{uuid}">
            <img src="/api/v1/tryon/studio-backgrounds/{id}/image" alt="Studio" class="vto-studio-thumb">
          </button>
          -->
        </div>

        <!-- Loading indicator shown when generating studio look -->
        <div class="vto-studio-loading" id="vto-studio-loading" style="display:none;">
          <div class="vto-spinner"></div>
          <span>Generating studio look...</span>
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

// Studio look background selection
async function loadStudioBackgrounds(gender) {
  const response = await fetch(
    `${API_URL}/api/v1/tryon/studio-backgrounds?gender=${gender}`
  );
  const backgrounds = await response.json();

  // Randomize order
  backgrounds.sort(() => Math.random() - 0.5);

  const grid = document.getElementById('vto-studio-grid');
  backgrounds.forEach(bg => {
    const btn = document.createElement('button');
    btn.className = 'vto-studio-option';
    btn.dataset.studioId = bg.id;
    btn.innerHTML = `<img src="${API_URL}${bg.image_url}" alt="Studio" class="vto-studio-thumb">`;
    grid.appendChild(btn);
  });
}

// Cache: map studio_background_id → generated try_on_id (avoid re-generating)
const studioCache = {};

// Helper: disable/enable all studio option buttons
function setStudioOptionsDisabled(disabled) {
  document.querySelectorAll('.vto-studio-option').forEach(btn => {
    btn.disabled = disabled;
    btn.classList.toggle('vto-studio-option--disabled', disabled);
  });
}

document.getElementById('vto-studio-grid').addEventListener('click', async (e) => {
  const btn = e.target.closest('.vto-studio-option');
  if (!btn || btn.disabled) return;

  const studioId = btn.dataset.studioId;

  // Update active state
  document.querySelectorAll('.vto-studio-option').forEach(b =>
    b.classList.remove('vto-studio-option--active')
  );
  btn.classList.add('vto-studio-option--active');

  // "Original" — instantly show the original try-on image
  if (studioId === 'none') {
    document.getElementById('vto-tryon-result').src =
      `${API_URL}/api/v1/tryon/${originalTryOnId}/image`;
    return;
  }

  // Check local (in-memory) cache first
  if (studioCache[studioId]) {
    document.getElementById('vto-tryon-result').src =
      `${API_URL}/api/v1/tryon/${studioCache[studioId]}/image`;
    return;
  }

  // Disable all studio options while generating
  setStudioOptionsDisabled(true);
  document.getElementById('vto-studio-loading').style.display = 'flex';

  try {
    const response = await fetch(`${API_URL}/api/v1/tryon/studio`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        try_on_id: originalTryOnId,
        studio_background_id: studioId
      })
    });

    const data = await response.json();

    // Backend returns status:"completed" with result_image_url if cached (1-hour TTL)
    if (data.status === 'completed' && data.result_image_url) {
      studioCache[studioId] = data.try_on_id;
      document.getElementById('vto-tryon-result').src =
        `${API_URL}${data.result_image_url}`;
      return;
    }

    // Otherwise poll for completion (new generation)
    const result = await pollForCompletion(data.try_on_id, 45);

    // Cache the result and display
    studioCache[studioId] = data.try_on_id;
    document.getElementById('vto-tryon-result').src =
      `${API_URL}${result.result_image_url}`;
  } catch (error) {
    showError('Failed to generate studio look');
  } finally {
    // Re-enable all studio options
    setStudioOptionsDisabled(false);
    document.getElementById('vto-studio-loading').style.display = 'none';
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
    this.userIdentifier = this.getUserIdentifier();
  }
  
  getUserIdentifier() {
    /**
     * Generate browser fingerprint for user recognition
     * Uses combination of browser properties
     */
    
    // Check if we have saved identifier in localStorage
    let identifier = localStorage.getItem('vto_user_id');
    
    if (!identifier) {
      // Generate new identifier from browser fingerprint
      const components = [
        navigator.userAgent,
        navigator.language,
        screen.width + 'x' + screen.height,
        new Date().getTimezoneOffset(),
        navigator.platform
      ];
      
      // Simple hash function
      identifier = this.simpleHash(components.join('|'));
      
      // Save to localStorage
      localStorage.setItem('vto_user_id', identifier);
    }
    
    return identifier;
  }
  
  simpleHash(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash;
    }
    return 'user_' + Math.abs(hash).toString(36);
  }
  
  async createSession(productId) {
    /**
     * Create new session or resume existing one
     * 
     * Backend will check if user has measurements from last 24h
     * and return them if available
     */
    const response = await fetch(`${this.baseUrl}/api/v1/sessions/create`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Store-ID': this.storeId
      },
      body: JSON.stringify({ 
        product_id: productId,
        user_identifier: this.userIdentifier
      })
    });
    
    const data = await response.json();
    this.sessionId = data.session_id;
    
    // Return session data which includes existing measurements if available
    return {
      sessionId: data.session_id,
      hasExistingMeasurements: data.has_existing_measurements || false,
      measurementId: data.measurement_id || null,
      measurements: data.measurements || null,
      photosAvailable: data.photos_available || false,
      cachedUntil: data.cached_until || null
    };
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
        'X-Session-ID': this.sessionId,
        'X-Store-ID': this.storeId
      },
      body: JSON.stringify({
        measurement_id: measurementId,
        product_id: productId,
        size: size
      })
    });

    return await response.json();
  }
  
  async generateTryOn(productId) {
    // Only product_id is needed — person image comes from session's cached front photo
    const response = await fetch(`${this.baseUrl}/api/v1/tryon/generate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Session-ID': this.sessionId,
        'X-Store-ID': this.storeId
      },
      body: JSON.stringify({
        product_id: productId
      })
    });

    return await response.json();
  }
  
  async getStudioBackgrounds(gender) {
    const response = await fetch(
      `${this.baseUrl}/api/v1/tryon/studio-backgrounds?gender=${gender}`
    );
    return await response.json();
  }

  async generateStudioTryOn(tryOnId, studioBackgroundId) {
    const response = await fetch(`${this.baseUrl}/api/v1/tryon/studio`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        try_on_id: tryOnId,
        studio_background_id: studioBackgroundId
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

### Session Reuse Implementation

**Main Widget Initialization:**

```javascript
// widget/src/main.js

class VirtualTryOnWidget {
  async initialize(productId) {
    // Create or resume session
    const sessionData = await this.api.createSession(productId);
    
    this.state.setState({
      sessionId: sessionData.sessionId,
      productId: productId
    });
    
    // Check if user has existing measurements
    if (sessionData.hasExistingMeasurements && sessionData.photosAvailable) {
      // Returning user - skip to results
      this.handleReturningUser(sessionData);
    } else {
      // New user - show full flow
      this.showBasicInfoScreen();
    }
  }
  
  async handleReturningUser(sessionData) {
    /**
     * User has measurements from last 24 hours
     * Skip photo capture and go directly to generating try-on
     */
    
    // Show welcome back message
    showToast(`Welcome back! Using your measurements from earlier.`, {
      duration: 3000,
      icon: '👋'
    });
    
    // Store cached measurement data
    this.state.setState({
      measurementId: sessionData.measurementId,
      measurements: sessionData.measurements,
      fromCache: true
    });
    
    // Show processing screen
    this.showProcessingScreen({
      title: 'Generating Your Try-On',
      message: 'Using your saved measurements for this product...'
    });
    
    // Generate everything for new product
    try {
      // 1. Get size recommendation
      updateProgress(30, 'Finding best size...');
      const recommendation = await this.api.getSizeRecommendation(
        sessionData.measurementId,
        this.state.getState('productId')
      );
      
      // 2. Generate heatmap
      updateProgress(50, 'Analyzing fit...');
      const heatmap = await this.api.generateHeatmap(
        sessionData.measurementId,
        this.state.getState('productId'),
        recommendation.recommended_size
      );
      
      // 3. Generate try-on (only needs product_id)
      updateProgress(70, 'Creating virtual try-on...');
      const tryOnResult = await this.api.generateTryOn(
        this.state.getState('productId')
      );
      
      // Poll for completion
      const tryOn = await this.pollTryOnCompletion(tryOnResult.try_on_id);
      
      updateProgress(100, 'Complete!');
      
      // Store results
      this.state.setState({
        recommendation: recommendation,
        heatmap: heatmap,
        tryOn: tryOn
      });
      
      // Show results screen
      this.showResultsScreen();
      
    } catch (error) {
      console.error('Error generating try-on:', error);
      showError(
        'Failed to generate try-on. Would you like to take new photos?',
        {
          allowRetry: true,
          retryAction: () => {
            // Clear cached data and start fresh
            this.state.setState({
              measurementId: null,
              measurements: null,
              fromCache: false
            });
            this.showBasicInfoScreen();
          }
        }
      );
    }
  }
  
  async pollTryOnCompletion(tryOnId) {
    /**
     * Poll for try-on generation completion
     */
    const maxAttempts = 60; // 2 minutes max
    const pollInterval = 2000; // 2 seconds
    
    for (let attempt = 0; attempt < maxAttempts; attempt++) {
      await new Promise(resolve => setTimeout(resolve, pollInterval));
      
      const status = await this.api.getTryOnStatus(tryOnId);
      
      if (status.status === 'completed') {
        return status;
      } else if (status.status === 'failed') {
        throw new Error(status.error);
      }
      
      // Update progress if available
      if (status.progress) {
        updateProgress(70 + (status.progress * 0.3), status.message);
      }
    }
    
    throw new Error('Try-on generation timed out');
  }
}
```

**User Experience:**

**First Visit (Product A):**
```
1. User clicks "Try On"
2. Enter height, weight, gender
3. Take/upload photos
4. View measurements
5. See try-on results
```

**Second Visit (Product B, within 24h):**
```
1. User clicks "Try On" on Product B
2. See "Welcome back!" message
3. Immediately see loading screen
4. Skip directly to results (5-10 seconds)
   - No photos needed
   - No measurement input
```

**After 24 Hours:**
```
1. User clicks "Try On"
2. Backend: "No recent measurements found"
3. Start full flow again (like first visit)
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

---

---

# Part 2: Merchant Admin App

**Version:** 1.0
**Last Updated:** 2026-02-21
**Tech Stack:** Remix (Node.js), Polaris, App Bridge, `@shopify/shopify-app-remix`
**Target:** Merchants — embedded inside Shopify Admin

---

## Overview

### What It Is

A second frontend application (separate from the storefront widget) that lives inside the Shopify Admin as an embedded app. When a merchant installs our app from the Shopify App Store, they are taken through this onboarding wizard. After onboarding, the same app serves as the merchant dashboard.

### How It Embeds in Shopify

- The app runs as a **Remix (Node.js)** server that serves a React frontend
- Shopify loads this frontend inside an `<iframe>` within `admin.shopify.com`
- The merchant sees it in the left sidebar under Apps → Virtual Try-On
- **App Bridge** (from `@shopify/app-bridge-react`) handles communication with the Shopify admin host — navigation, toasts, modal dialogs, session tokens
- **Polaris** (`@shopify/polaris`) provides React components that look native to Shopify Admin

### Technology Stack

```
Framework:      Remix (Node.js)
UI Library:     Polaris (@shopify/polaris)
App Bridge:     @shopify/app-bridge-react
Shopify Remix:  @shopify/shopify-app-remix (handles OAuth, session tokens)
Language:       TypeScript
Shopify APIs:   Admin GraphQL API (for collections/products/themes)
Billing:        Shopify Billing API (appSubscriptionCreate)
Backend:        Calls our FastAPI backend to save onboarding state
```

### App Structure

```
merchant-admin/
├── app/
│   ├── shopify.server.ts        # Shopify app config (OAuth, session storage)
│   ├── root.tsx                 # Root layout with AppProvider + Polaris
│   ├── routes/
│   │   ├── auth.$.tsx           # Shopify OAuth route (auto-handled by library)
│   │   ├── app._index.tsx       # Redirects to onboarding or dashboard
│   │   ├── app.onboarding.tsx   # Layout: progress bar + step container
│   │   ├── app.onboarding.step-1.tsx   # Welcome screen
│   │   ├── app.onboarding.step-2.tsx   # Goals
│   │   ├── app.onboarding.step-3.tsx   # Referral source
│   │   ├── app.onboarding.step-4.tsx   # Widget scope (collections/products)
│   │   ├── app.onboarding.step-5.tsx   # Theme setup
│   │   ├── app.onboarding.step-6.tsx   # Plan selection
│   │   └── app.dashboard.tsx    # Post-onboarding dashboard (simple for now)
│   └── utils/
│       └── api.ts               # Calls to FastAPI backend
├── shopify.app.toml             # Shopify CLI app config
└── extensions/
    └── virtual-tryon-widget/    # Theme App Extension
        ├── blocks/
        │   └── try-on-button.liquid
        ├── assets/
        │   └── tryon-widget.js  # (symlink/copy of storefront widget bundle)
        └── shopify.extension.toml
```

---

## OAuth Installation Flow

When a merchant clicks **Install** from the Shopify App Store:

```
1. Shopify redirects to: GET /auth?shop=merchant.myshopify.com
2. Remix app (via @shopify/shopify-app-remix) validates shop param
3. Redirects merchant to Shopify OAuth consent screen
4. Merchant approves permissions
5. Shopify redirects to: GET /auth/callback?code=...&shop=...&hmac=...
6. Remix exchanges code for access_token, saves to session storage
7. FastAPI backend called: creates Store record in PostgreSQL
8. Merchant redirected into embedded app: app/_index.tsx
9. Backend checks: is onboarding complete?
   → No: redirect to /app/onboarding/step-1
   → Yes: redirect to /app/dashboard
```

**Required OAuth Scopes:**

```
read_products          - List merchant's products for step 4 ResourcePicker
read_collections       - List merchant's collections for step 4
read_themes            - Check if theme extension block is installed (step 5)
read_script_tags       - Legacy (may be removed)
```

---

## Navigation Structure

After onboarding, the sidebar navigation (configured in Shopify Partner Dashboard + rendered via App Bridge `NavMenu`):

```
Virtual Try-On
├── Dashboard          /app/dashboard
├── Products           /app/products       (future)
├── Analytics          /app/analytics      (future — uses existing merchant API)
├── Widget Settings    /app/settings       (future)
└── Billing / Plan     /app/billing        (future)
```

During onboarding, only the onboarding routes are accessible. The sidebar nav is hidden or shows just the app name.

---

## Onboarding Wizard — Shared Layout

**File:** `app/routes/app.onboarding.tsx`

The onboarding layout wraps all 6 steps. It provides:
- A **ProgressBar** at the top showing current step out of 6
- Back / Continue / Skip navigation buttons
- Step title

**Progress bar:** Uses Polaris `ProgressBar` component. Step percentages: 0%, 20%, 40%, 60%, 80%, 100%.

**On each page load**, the Remix loader calls `GET /api/v1/merchant/onboarding/status` to check which step the merchant is currently on. If they land on a step they already completed, they are redirected to their current step (prevents skipping ahead or going back to re-enter data).

**"Need help? Contact our support team"** link shown at the bottom of steps 4 and 5 (no screen to build yet — just an `mailto:` or Intercom link).

---

## Step 1 — Welcome Screen

**Route:** `/app/onboarding/step-1`
**Polaris components:** `Page`, `Card`, `Layout`, `Text`, `Button`, `List`
**Backend call:** None (display only)

**Content:**
- App logo / hero graphic
- Headline: "Welcome to Virtual Try-On"
- Sub-headline: "Let's get your store set up in just a few minutes"
- Feature highlights (use Polaris `List` with icons or a custom grid):
  - Virtual Try-On — let customers see how clothes look on them
  - AI Studio Look — professional background photo generator
  - Fit Heatmap — visual size guidance for your customers
  - Dashboard & Analytics — track conversions and returns
  - Marketing Content — generate try-on images for ads and social
- Single CTA button: **Get Started →** → navigates to step 2

**No Back button on step 1.**

---

## Step 2 — Goals

**Route:** `/app/onboarding/step-2`
**Polaris components:** `Page`, `Card`, `ChoiceList` (multi-select), `Button`, `InlineStack`
**Backend call:** `POST /api/v1/merchant/onboarding/goals`

**Content:**
- Headline: "What do you want to achieve?"
- Sub-text: "Select all that apply. This helps us tailor your experience."
- **Checkbox list** (multi-select, at least 1 required):
  - Improve conversion rates
  - Reduce return rates
  - Collect customer emails
  - Create marketing content (ads, social media)
  - Improve customer experience & confidence
- Navigation: **← Back** (goes to step 1) | **Continue →** (validates at least 1 checked, saves, goes to step 3)

**Validation:** At least one option must be selected before Continue is enabled.

**Polaris implementation:**
```tsx
<ChoiceList
  title="What do you want to achieve?"
  allowMultiple
  choices={[
    { label: "Improve conversion rates", value: "improve_conversion" },
    { label: "Reduce return rates", value: "reduce_returns" },
    { label: "Collect customer emails", value: "collect_emails" },
    { label: "Create marketing content", value: "create_marketing_content" },
    { label: "Improve customer experience & confidence", value: "improve_ux" },
  ]}
  selected={selectedGoals}
  onChange={setSelectedGoals}
/>
```

---

## Step 3 — Referral Source

**Route:** `/app/onboarding/step-3`
**Polaris components:** `Page`, `Card`, `ChoiceList` (single-select), `TextField` (conditional), `Button`, `InlineStack`
**Backend call:** `POST /api/v1/merchant/onboarding/referral`

**Content:**
- Headline: "How did you hear about us?"
- Sub-text: "This helps us improve our marketing."
- **Radio button list** (single-select, one required):
  - Shopify App Store search
  - Google / web search
  - Social media (Instagram, TikTok, etc.)
  - Friend or colleague recommendation
  - Influencer or blog recommendation
  - Other (reveals a free-text field below)
- If "Other" selected: a `TextField` appears with placeholder "Please tell us more (optional)"
- Navigation: **← Back** | **Continue →** (validates one option selected)

---

## Step 4 — Widget Scope (Where to Show the Widget)

**Route:** `/app/onboarding/step-4`
**Polaris components:** `Page`, `Card`, `Layout`, `Button`, `InlineStack`, `Banner`, `Toast`
**App Bridge:** `ResourcePicker` (built-in Shopify component — no custom UI needed)
**Backend call:** `POST /api/v1/merchant/onboarding/widget-scope`

**Content:**
- Headline: "Where should the try-on widget appear?"
- Sub-text: "The widget button appears on product pages. Choose which products to enable it on."
- Two action buttons side by side:
  - **Select Collections** → opens App Bridge `ResourcePicker` (type: Collection, multi-select)
  - **Select Products** → opens App Bridge `ResourcePicker` (type: Product, multi-select)
- Merchants can click both buttons to mix collections and individual products
- After closing the ResourcePicker with selections, a success toast appears: "X collections added" / "X products added"
- Selected items shown as Polaris `Tag` chips below each button (with × to remove)
- "Selected scope" summary: e.g. "Widget enabled on: 2 collections, 3 individual products"

**ResourcePicker usage:**
```tsx
import { ResourcePicker } from "@shopify/app-bridge-react";

// Opens Shopify's native collection picker
<ResourcePicker
  resourceType="Collection"
  open={pickerOpen}
  allowMultiple={true}
  onSelection={(resources) => {
    const ids = resources.selection.map(r => r.id);
    // Add to selectedCollectionIds state
  }}
  onCancel={() => setPickerOpen(false)}
/>
```

**Navigation:**
- **← Back** | **Skip for now** (saves `scope_type: "all"`, goes to step 5) | **Continue →** (saves selection, goes to step 5)
- If no selections were made, Continue behaves the same as "Skip for now" (`scope_type: "all"`)

**Note on "Skip for now":** Widget is enabled for ALL products by default. Merchant can update scope later from Widget Settings page.

**Help link:** "Need help? Contact our support team" shown at bottom (mailto link).

---

## Step 5 — Theme Setup

**Route:** `/app/onboarding/step-5`
**Polaris components:** `Page`, `Card`, `Layout`, `Banner`, `Button`, `List`, `InlineStack`, `Badge`
**App Bridge:** External redirect to Theme Editor (using `redirect` from App Bridge or standard URL)
**Backend call:** `POST /api/v1/merchant/onboarding/theme-status`

**Content — Two Sections:**

**Section 1: Widget Block Detection**
- If `theme_extension_detected == false`:
  - Banner (warning): "Widget block not detected in your theme"
  - Text: "You need to add the Virtual Try-On button to your product page template."
  - Button: **Open Theme Editor** (opens the Shopify Theme Editor with our app extension pre-selected via deep link — opens in same tab using App Bridge redirect)
  - After merchant adds the block and returns, a **"Check Again"** button re-polls the Themes API
- If `theme_extension_detected == true`:
  - Banner (success): "Widget block detected in your theme"
  - Green checkmark badge next to section title

**Section 2: Instructions & Guidance**
- Polaris `List` with numbered steps:
  1. Click "Open Theme Editor" above
  2. In the Theme Editor, click "Add block" in the Product page template
  3. Find "Virtual Try-On" under "Apps" in the block list
  4. Click to add it — it appears near the Add to Cart button
  5. Save your theme
  6. Come back here and click "Check Again"
- A note: "Video walkthrough coming soon" (placeholder for now — no video needed yet)

**Navigation:**
- **← Back** | **Skip for now** (saves `detected: false`, goes to step 6) | **Continue →** (requires detection or merchant confirmation)

**"Continue" behavior:** Either `theme_extension_detected: true` (auto-detected) OR the merchant can click Continue without detection (same effect as Skip for now — they can set it up later).

**Help link:** "Need help? Contact our support team" shown at bottom.

---

## Step 6 — Plan Selection

**Billing:** Shopify Billing API via `admin.graphql()` in Remix loader/action
**Backend call:** `POST /api/v1/merchant/billing/activate` (after billing confirmation)

**Content:**
- Headline: "Choose your plan"
- Sub-text: "You can upgrade or downgrade anytime."
- **Monthly / Annual toggle** (default: Monthly) — annual shows "Save 17%"
- Two plan cards (Starter + Growth). No free plan option.
All plans include a mandatory 14-day free trial (always applied, no toggle).

Note: Founding merchants (first 50 installs, configurable via FOUNDING_MERCHANT_LIMIT env var)
skip this step entirely. They receive plan_name="founding_trial" with 300 credits for 14 days,
auto-assigned during step 5 (theme-status). After their trial expires, this billing screen is shown.

**Starter Plan Card:**
- Badge: "Most Popular"
- Title: "Starter"
- Price: "$17/mo" (monthly) or "$14/mo · $179 billed annually" (annual)
- Trial badge: "14-day free trial"
- Feature list: 600 credits/month, AI Try-On, AI Studio Look, Fit heatmap, Analytics, Email support
- CTA Button: **Start Free Trial**
  - Posts `{ plan_name: "starter", billing_interval, return_url }` to `POST /billing/create-subscription`
  - Redirects to Shopify approval page; after approval: callback calls `POST /billing/activate`

**Growth Plan Card:**
- Badge: "Best Value" (annual) or none
- Title: "Growth"
- Price: "$29/mo" (monthly) or "$24/mo · $299 billed annually" (annual)
- Trial badge: "14-day free trial"
- Feature list: 1,000 credits/month, AI Try-On, AI Studio Look, Fit heatmap, Analytics, Priority support, Custom widget branding
- CTA Button: **Start Free Trial**
  - Same billing flow as Starter with `plan_name: "growth"`

**Credits note:** 1 try-on = 4 credits (displayed as a tooltip/footnote on plan cards).

**Navigation:** **← Back** only (no Skip — merchant must choose a plan).

---

## Dashboard (Post-Onboarding)

**Route:** `/app/dashboard`
**Polaris components:** `Page`, `Card`, `Banner`, `Layout`, `Text`

For now, this is a simple placeholder screen:

**Content:**
- If arriving from completed onboarding: success `Banner` (dismissable):
  - "Your store is set up! The virtual try-on widget is now active on your selected products."
- Headline: "Dashboard"
- Two placeholder cards:
  - "Try-Ons This Month: — (coming soon)"
  - "Conversion Rate: — (coming soon)"
- Note: Full analytics dashboard content comes from the existing `/api/v1/merchant/dashboard` API endpoint — to be wired up in a later segment

---

## Shopify App Bridge & Session Tokens

In the Remix app, every route that needs to call the FastAPI backend or Shopify Admin API must go through the Remix server loader (not directly from the client). The loader calls `authenticate.admin(request)` to get a session with `shop` and `accessToken`, then makes the FastAPI call with `X-Store-ID`.

```typescript
// Example loader pattern
export async function loader({ request }: LoaderFunctionArgs) {
  const { session } = await authenticate.admin(request);
  // session.shop = "merchant.myshopify.com"
  // session.accessToken = "shpat_..."

  // Look up our internal store_id from shop domain
  const store = await getStoreByDomain(session.shop);

  // Call FastAPI backend
  const status = await fetch(`${BACKEND_URL}/api/v1/merchant/onboarding/status`, {
    headers: { "X-Store-ID": store.store_id }
  }).then(r => r.json());

  return json({ status, step: status.onboarding_step });
}
```

---

## Theme App Extension

**Directory:** `merchant-admin/extensions/virtual-tryon-widget/`

The extension is a Liquid block that merchants add to their product page template via the Theme Editor. This is the recommended modern approach — it replaces the old ScriptTag method.

**Key file: `blocks/try-on-button.liquid`**

```liquid
{% if product %}
  <div
    id="virtual-tryon-widget"
    data-product-id="{{ product.id }}"
    data-shop="{{ shop.permanent_domain }}"
    {{ block.shopify_attributes }}
  >
    <!-- Widget button injected by tryon-widget.js -->
  </div>
{% endif %}

{% schema %}
{
  "name": "Virtual Try-On Button",
  "target": "section",
  "javascript": "tryon-widget.js",
  "settings": [
    {
      "type": "text",
      "id": "button_text",
      "label": "Button Text",
      "default": "Try it on"
    }
  ]
}
{% endschema %}
```

**`shopify.extension.toml`:**
```toml
name = "Virtual Try-On Widget"
handle = "virtual-tryon-widget"
type = "theme"
```

The extension is deployed via `shopify app deploy` as part of the app deployment pipeline. It does not need to be redeployed separately.

---

## Polaris UX Guidelines for Merchant Admin

- Use **Polaris Page** as the top-level wrapper with a `title` on each screen
- Use **Polaris Card** to group related content sections
- Use **Polaris Button** for all actions — `variant="primary"` for the main CTA, `variant="plain"` for secondary actions
- Use **Polaris Banner** for status messages (success/warning/info)
- Use **Polaris Toast** for transient confirmations (e.g. "Collection saved")
- Progress bar should use Polaris `ProgressBar` component with `size="small"`
- All forms should use Polaris `FormLayout` for consistent spacing
- Use Polaris `InlineStack` or `BlockStack` for button groups (Back / Skip / Continue)
- Stick to Polaris color tokens — do not use custom colors that conflict with the Shopify admin theme

---

## Merchant Settings Screens

**Added:** 2026-02-22

### Overview

Settings is a top-level sidebar navigation item. Clicking it opens a tabbed page with four sub-sections:

| Tab | Route | Status |
|-----|-------|--------|
| Custom | `/app/settings/custom` | Planned (backend done) |
| Billing | `/app/settings/billing` | Planned |
| Privacy | `/app/settings/privacy` | Planned |
| Support | `/app/settings/support` | Planned |

### Sidebar Navigation Update

The NavMenu in `app/routes/app.tsx` must be updated to add a Settings link:

```tsx
// app/routes/app.tsx
import { NavMenu } from "@shopify/app-bridge-react";
import { Link, Outlet } from "@remix-run/react";

export default function AppLayout() {
  return (
    <>
      <NavMenu>
        <Link to="/app" rel="home">Overview</Link>
        <Link to="/app/analytics">Analytics</Link>
        <Link to="/app/settings/custom">Settings</Link>
      </NavMenu>
      <Outlet />
    </>
  );
}
```

**Note:** Shopify's NavMenu does not support nested/collapsible navigation. The Settings link points to the first sub-screen (`/custom`). Sub-screen switching uses **Polaris `Tabs`** inside the settings page layout, not sidebar items.

### Settings Layout Route (`app/routes/app.settings.tsx`)

Shared layout wrapping all settings sub-screens. Renders Polaris `Tabs` and an `<Outlet />`:

```tsx
// app/routes/app.settings.tsx
import { Tabs, Page } from "@shopify/polaris";
import { Outlet, useNavigate, useMatches } from "@remix-run/react";

const TABS = [
  { id: "custom",  content: "Custom",  url: "/app/settings/custom"  },
  { id: "billing", content: "Billing", url: "/app/settings/billing" },
  { id: "privacy", content: "Privacy", url: "/app/settings/privacy" },
  { id: "support", content: "Support", url: "/app/settings/support" },
];

export default function SettingsLayout() {
  const navigate = useNavigate();
  const matches = useMatches();
  const activeTab = TABS.findIndex(t => matches.some(m => m.pathname.includes(t.id)));

  return (
    <Page title="Settings">
      <Tabs
        tabs={TABS}
        selected={activeTab >= 0 ? activeTab : 0}
        onSelect={(index) => navigate(TABS[index].url)}
      />
      <Outlet />
    </Page>
  );
}
```

---

### Settings — Custom Screen (`app/routes/app.settings.custom.tsx`)

**Purpose:** Brand customisation and usage controls for the storefront widget.

**API calls:**
- `GET /api/v1/merchant/widget-config` on load → initial state
- `PATCH /api/v1/merchant/widget-config` on Save → `{ "widget_color": "#RRGGBB", "weekly_tryon_limit": 10 }`

**Layout (three vertical sections inside a Card):**

```
┌─────────────────────────────────────────────────────┐
│  Brand Customisation                                │
│ ─────────────────────────────────────────────────── │
│  Widget Color                                       │
│  [ Color swatch ] [ #FF0000  hex input ]            │
│                                                     │
│  [ Full color palette (color picker) ]              │
│                                                     │
│  ─────────────────────────────────────────────────  │
│                                                     │
│  Preview                                            │
│  ┌──────────────────────────────────────────────┐  │
│  │  [ Try it on ]   ← widget button in chosen  │  │
│  │                    color, real styling        │  │
│  └──────────────────────────────────────────────┘  │
│                                                     │
│  ─────────────────────────────────────────────────  │
│                                                     │
│  Usage Controls                                     │
│  Weekly Generation Limit                            │
│  [ 10  ▲▼ ]   (whole numbers, min 5)               │
│  Help text: "Maximum try-ons a single customer can  │
│  generate per week. Minimum 5. Set higher to allow  │
│  more exploration, lower to prevent misuse."        │
└─────────────────────────────────────────────────────┘
                            [ Cancel ]  [ Save ]
```

**Component spec:**

```tsx
// app/routes/app.settings.custom.tsx
import { useState } from "react";
import { useLoaderData, useFetcher } from "@remix-run/react";
import { Card, BlockStack, Text, InlineStack, Button, TextField, Banner, Divider } from "@shopify/polaris";

// Loader: fetch current config from backend
export async function loader({ request }) {
  const { session } = await authenticate.admin(request);
  const res = await fetch(`${BACKEND_URL}/api/v1/merchant/widget-config`, {
    headers: { "X-Store-ID": session.shop },
  });
  return await res.json();
}

// Action: save updated color + weekly limit
export async function action({ request }) {
  const { session } = await authenticate.admin(request);
  const formData = await request.formData();
  const widget_color = formData.get("widget_color");
  const weekly_tryon_limit = Number(formData.get("weekly_tryon_limit"));
  const res = await fetch(`${BACKEND_URL}/api/v1/merchant/widget-config`, {
    method: "PATCH",
    headers: { "X-Store-ID": session.shop, "Content-Type": "application/json" },
    body: JSON.stringify({ widget_color, weekly_tryon_limit }),
  });
  return await res.json();
}

const MIN_WEEKLY_LIMIT = 5;

export default function CustomSettings() {
  const saved = useLoaderData();
  const fetcher = useFetcher();

  const [color, setColor] = useState(saved.widget_color ?? "#FF0000");
  const [weeklyLimit, setWeeklyLimit] = useState(String(saved.weekly_tryon_limit ?? 10));

  const weeklyLimitNum = parseInt(weeklyLimit, 10);
  const weeklyLimitError =
    isNaN(weeklyLimitNum) || weeklyLimitNum < MIN_WEEKLY_LIMIT
      ? `Minimum is ${MIN_WEEKLY_LIMIT}`
      : undefined;

  const isDirty =
    color !== (saved.widget_color ?? "#FF0000") ||
    weeklyLimitNum !== (saved.weekly_tryon_limit ?? 10);

  const canSave = isDirty && !weeklyLimitError;

  const handleSave = () => {
    fetcher.submit(
      { widget_color: color, weekly_tryon_limit: String(weeklyLimitNum) },
      { method: "PATCH" }
    );
  };

  const handleCancel = () => {
    setColor(saved.widget_color ?? "#FF0000");
    setWeeklyLimit(String(saved.weekly_tryon_limit ?? 10));
  };

  return (
    <BlockStack gap="400">
      {fetcher.data && <Banner tone="success">Saved successfully</Banner>}
      <Card>
        <BlockStack gap="400">
          {/* Section 1: Color picker */}
          <Text variant="headingMd">Brand Customisation</Text>
          <BlockStack gap="300">
            <Text>Widget Color</Text>
            <InlineStack gap="300" align="start">
              {/* Native color picker — provides full palette */}
              <input
                type="color"
                value={color}
                onChange={(e) => setColor(e.target.value)}
                style={{ width: 40, height: 40, border: "none", cursor: "pointer" }}
              />
              {/* Hex text input for precise entry */}
              <TextField
                label=""
                labelHidden
                value={color}
                onChange={(v) => { if (/^#[0-9A-Fa-f]{0,6}$/.test(v)) setColor(v); }}
                maxLength={7}
                monospaced
                autoComplete="off"
              />
            </InlineStack>
          </BlockStack>

          {/* Section 2: Widget preview */}
          <BlockStack gap="200">
            <Text variant="headingMd">Preview</Text>
            <div style={{ padding: "16px", background: "#f4f6f8", borderRadius: "8px" }}>
              <button
                style={{
                  background: color,
                  color: "#fff",
                  border: "none",
                  borderRadius: "6px",
                  padding: "10px 20px",
                  fontSize: "14px",
                  cursor: "default",
                }}
              >
                Try it on
              </button>
            </div>
          </BlockStack>

          <Divider />

          {/* Section 3: Usage controls */}
          <BlockStack gap="300">
            <Text variant="headingMd">Usage Controls</Text>
            <TextField
              label="Weekly Generation Limit"
              type="number"
              value={weeklyLimit}
              onChange={(v) => {
                // Allow only whole numbers
                if (/^\d*$/.test(v)) setWeeklyLimit(v);
              }}
              min={MIN_WEEKLY_LIMIT}
              step={1}
              error={weeklyLimitError}
              helpText={`Maximum try-ons a single customer can generate per week. Minimum ${MIN_WEEKLY_LIMIT}. Set higher to allow more exploration, lower to prevent misuse.`}
              autoComplete="off"
            />
          </BlockStack>
        </BlockStack>
      </Card>

      {/* Action bar */}
      <InlineStack gap="300" align="end">
        <Button onClick={handleCancel} disabled={!isDirty}>Cancel</Button>
        <Button variant="primary" onClick={handleSave} disabled={!canSave}
          loading={fetcher.state !== "idle"}>
          Save
        </Button>
      </InlineStack>
    </BlockStack>
  );
}
```

**Behaviour rules:**
- Cancel reverts both `color` and `weeklyLimit` to their saved values — no API call
- Save is enabled only when at least one field is dirty AND there are no validation errors (`canSave`)
- `weekly_tryon_limit` must be a whole number ≥ 5; a Polaris `TextField` inline error is shown if the value is below 5 or non-numeric
- The `type="number"` field rejects decimals via the `/^\d*$/` onChange guard (no dot, no negative sign)
- After a successful PATCH, the success Banner appears; saved values update on next loader call
- The hex `TextField` validates that input matches `#[0-9A-Fa-f]{0,6}` to prevent storing invalid values
- The native `<input type="color">` provides the full colour palette including custom hex entry

**Backend note (implementation pending):**
- `widget_color` field already exists in `widget_configs` table and `PATCH /merchant/widget-config`
- `weekly_tryon_limit` field needs to be added to the `widget_configs` table (new column), the `WidgetConfig` DB model, the `WidgetConfigUpdateRequest` schema, and the PATCH endpoint handler
- The widget itself will need to enforce this limit client-side by tracking per-customer usage against a backend counter (implementation tracked separately)

---

## Settings → Billing Screen

**Added:** 2026-02-22

### Route
`app/routes/app.settings.billing.tsx` — child of the Settings layout (`app/routes/app.settings.tsx`).

### Billing Callback Route
`app/routes/app.billing.callback.tsx` — receives `charge_id` from Shopify after merchant approves, calls FastAPI, redirects.

---

### Data Loading (Loader)

```ts
export async function loader({ request }) {
  const { session } = await authenticate.admin(request);
  const [plansRes, statusRes] = await Promise.all([
    fetch(`${BACKEND_URL}/api/v1/merchant/billing/plans`, { headers: { "X-Store-ID": session.shop } }),
    fetch(`${BACKEND_URL}/api/v1/merchant/billing/status`, { headers: { "X-Store-ID": session.shop } }),
  ]);
  return { plans: await plansRes.json(), status: await statusRes.json() };
}
```

---

### UI Layout

```
┌───────────────────────────────────────────────────────────────┐
│  Billing                                                       │
│ ─────────────────────────────────────────────────────────────  │
│                                                               │
│  Subscription Plan                                            │
│  ┌─────────────────────────┐  ┌────────────────────────────┐  │
│  │  Free Plan              │  │  Starter Plan              │  │
│  │  $0 / month             │  │  $9.99 / month             │  │
│  │                         │  │                            │  │
│  │  ✓ 10 try-ons/month     │  │  ✓ 100 try-ons/month       │  │
│  │  ✓ Basic widget         │  │  ✓ AI Studio Look          │  │
│  │  ✓ Email support        │  │  ✓ Fit heatmap             │  │
│  │                         │  │  ✓ Analytics               │  │
│  │  [ Current Plan ]badge  │  │  ✓ Priority support        │  │
│  │                         │  │                            │  │
│  │                         │  │  [ Upgrade to Starter ]    │  │
│  └─────────────────────────┘  └────────────────────────────┘  │
│                                                               │
│  Subscription Details  (shown only if plan_name != 'free')   │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  Status: Active                                         │  │
│  │  Next billing date: March 22, 2026                      │  │
│  │                                                         │  │
│  │  [ Update payment method ]    [ View invoices ]         │  │
│  │  (links to Shopify admin)     (links to Shopify admin)  │  │
│  │                                                         │  │
│  │  [ Downgrade to Free ]  (plain/destructive button)      │  │
│  └─────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────┘
```

---

### Component spec (`app/routes/app.settings.billing.tsx`)

```tsx
import { useLoaderData, useFetcher, useNavigation } from "@remix-run/react";
import {
  Page, Layout, Card, Grid, Badge, Text, Button,
  BlockStack, InlineStack, Banner, Modal, Spinner
} from "@shopify/polaris";

export default function BillingSettings() {
  const { plans, status } = useLoaderData();
  const fetcher = useFetcher();
  const [showCancelModal, setShowCancelModal] = useState(false);

  const shopDomain = /* from session */ "";
  const billingAdminUrl = `https://${shopDomain}/admin/settings/billing`;

  const handleUpgrade = (planName) => {
    fetcher.submit(
      { action: "create_subscription", plan_name: planName },
      { method: "POST" }
    );
    // Action returns { confirmation_url } → redirect handled in action()
  };

  const handleCancelConfirm = () => {
    fetcher.submit({ action: "cancel_subscription" }, { method: "POST" });
    setShowCancelModal(false);
  };

  return (
    <Page title="Billing">
      {/* Plan cards */}
      <Layout>
        <Layout.Section>
          <Card>
            <BlockStack gap="400">
              <Text variant="headingMd">Subscription Plan</Text>
              <Grid columns={{ sm: 1, md: 2 }}>
                {plans.plans.map(plan => (
                  <Card key={plan.name} background={plan.is_current ? "bg-surface-selected" : undefined}>
                    <BlockStack gap="300">
                      <InlineStack align="space-between">
                        <Text variant="headingMd">{plan.display_name}</Text>
                        {plan.is_current && <Badge tone="success">Current Plan</Badge>}
                      </InlineStack>
                      <Text variant="headingLg">
                        {/* billingInterval: "monthly" | "annual" from component state */}
                        {plan.price_monthly === 0
                          ? "Free"
                          : billingInterval === "annual"
                          ? `$${plan.price_annual_per_month}/mo · $${plan.price_annual_total} billed annually`
                          : `$${plan.price_monthly}/mo`}
                      </Text>
                      <BlockStack gap="100">
                        {plan.features.map(f => <Text key={f}>✓ {f}</Text>)}
                      </BlockStack>
                      {!plan.is_current && (
                        <Button
                          variant="primary"
                          onClick={() => handleUpgrade(plan.name)}
                          loading={fetcher.state !== "idle"}
                        >
                          {plan.price_usd > 0 ? `Upgrade to ${plan.display_name}` : "Downgrade to Free"}
                        </Button>
                      )}
                    </BlockStack>
                  </Card>
                ))}
              </Grid>
            </BlockStack>
          </Card>
        </Layout.Section>

        {/* Subscription details — only for paid plans */}
        {status.plan_name !== "free" && (
          <Layout.Section>
            <Card>
              <BlockStack gap="400">
                <Text variant="headingMd">Subscription Details</Text>
                <InlineStack gap="600">
                  <BlockStack>
                    <Text tone="subdued">Status</Text>
                    <Text>{status.subscription_status ?? "—"}</Text>
                  </BlockStack>
                  <BlockStack>
                    <Text tone="subdued">Next billing date</Text>
                    <Text>
                      {status.current_period_end
                        ? new Date(status.current_period_end).toLocaleDateString()
                        : "—"}
                    </Text>
                  </BlockStack>
                </InlineStack>
                <InlineStack gap="300">
                  <Button url={billingAdminUrl} external>Update payment method</Button>
                  <Button url={billingAdminUrl} external>View invoices</Button>
                </InlineStack>
                <Button
                  tone="critical"
                  variant="plain"
                  onClick={() => setShowCancelModal(true)}
                >
                  Downgrade to Free
                </Button>
              </BlockStack>
            </Card>
          </Layout.Section>
        )}
      </Layout>

      {/* Downgrade confirmation modal */}
      <Modal
        open={showCancelModal}
        onClose={() => setShowCancelModal(false)}
        title="Downgrade to Free Plan?"
        primaryAction={{ content: "Downgrade", destructive: true, onAction: handleCancelConfirm }}
        secondaryActions={[{ content: "Keep current plan", onAction: () => setShowCancelModal(false) }]}
      >
        <Modal.Section>
          <Text>
            Your subscription will be cancelled immediately and you'll be moved to the free plan
            (10 try-ons/month). This cannot be undone — you'll need to upgrade again to access
            premium features.
          </Text>
        </Modal.Section>
      </Modal>
    </Page>
  );
}
```

### Action (Remix server-side)

```ts
export async function action({ request }) {
  const { session } = await authenticate.admin(request);
  const formData = await request.formData();
  const actionType = formData.get("action");

  if (actionType === "create_subscription") {
    const plan_name = formData.get("plan_name");
    const billing_interval = formData.get("billing_interval") ?? "monthly";
    // Encode params so they survive Shopify's redirect pass-through
    const callbackParams = `plan=${plan_name}&interval=${billing_interval}`;
    const returnUrl = `${process.env.SHOPIFY_APP_URL}/app/billing/callback?${callbackParams}`;
    const res = await fetch(`${BACKEND_URL}/api/v1/merchant/billing/create-subscription`, {
      method: "POST",
      headers: { "X-Store-ID": session.shop, "Content-Type": "application/json" },
      body: JSON.stringify({ plan_name, billing_interval, return_url: returnUrl }),
    });
    const { confirmation_url } = await res.json();
    return redirect(confirmation_url);  // merchant goes to Shopify approval page
  }

  if (actionType === "cancel_subscription") {
    await fetch(`${BACKEND_URL}/api/v1/merchant/billing/cancel-subscription`, {
      method: "POST",
      headers: { "X-Store-ID": session.shop },
    });
    return redirect("/app/settings/billing?downgraded=1");
  }
}
```

### Billing Callback Route (`app/routes/app.billing.callback.tsx`)

Called by Shopify after merchant approves the subscription.

```ts
// URL: /app/billing/callback?charge_id=gid://shopify/AppSubscription/123&shop=...
export async function loader({ request }) {
  const { session } = await authenticate.admin(request);
  const url = new URL(request.url);
  const chargeId = url.searchParams.get("charge_id");

  if (!chargeId) return redirect("/app/settings/billing?error=missing_charge");

  // plan_name, billing_interval are passed as query params in return_url
  const planName = url.searchParams.get("plan") ?? "starter";
  const billingInterval = url.searchParams.get("interval") ?? "monthly";

  await fetch(`${BACKEND_URL}/api/v1/merchant/billing/activate`, {
    method: "POST",
    headers: { "X-Store-ID": session.shop, "Content-Type": "application/json" },
    body: JSON.stringify({
      plan_name: planName,
      billing_interval: billingInterval,
      shopify_subscription_id: chargeId,
      status: "active",
    }),
  });

  return redirect("/app/settings/billing?activated=1");
}
```

**Note on passing params through the callback:** Include `plan`, `interval`, and `trial` as query params in the `return_url` (e.g. `?plan=starter&interval=annual&trial=1`), which Shopify passes through unchanged.

### Behaviour Rules
- Upgrade → calls Shopify Billing API with selected interval → full-page redirect to Shopify approval page
- Annual toggle shows "Save 17%" badge; selected plan card shows discounted per-month price
- After approval → Shopify redirects to callback → plan activated (14-day trial always applied) → redirect to billing screen with `?activated=1` success banner
- "Downgrade to Free" → show confirmation modal → on confirm call cancel → redirect with `?downgraded=1` banner
- "Update payment method" and "View invoices" → external links to `https://{shop}/admin/settings/billing`
- Subscription details section only visible when `plan_name !== "free"`
- `current_period_end` displays as a localised date string; shows "—" if null (graceful Shopify call failure)
- Test subscriptions (dev) show `is_test_subscription: true` as an informational badge

---

## Settings → Privacy Screen

**Added:** 2026-02-22

### Route
`app/routes/app.settings.privacy.tsx` — child of Settings layout.

### Purpose
Static informational screen explaining the app's privacy practices to the merchant. No API calls, no state — pure content.

### Layout (5 policy cards stacked vertically)

```
┌─────────────────────────────────────────────────────┐
│  Privacy Policy                                     │
│ ─────────────────────────────────────────────────── │
│  ┌───────────────────────────────────────────────┐  │
│  │  📸  Data We Collect                          │  │
│  │  • Customer-uploaded photos (front/side pose) │  │
│  │  • Body measurements derived from photos      │  │
│  │  • Session identifiers (anonymous)            │  │
│  │  • Try-on results and preferences             │  │
│  └───────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────┐  │
│  │  🔒  How We Use Your Data                     │  │
│  │  • Photos are processed to extract body       │  │
│  │    measurements using AI models               │  │
│  │  • Measurements are used solely for size      │  │
│  │    recommendations and virtual try-on         │  │
│  │  • No data is sold to third parties           │  │
│  │  • Photos are never used for advertising      │  │
│  └───────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────┐  │
│  │  ⏱️  Data Retention                           │  │
│  │  • Customer photos: deleted within 24 hours   │  │
│  │  • Measurements: retained for 30 days to      │  │
│  │    avoid re-upload on return visits           │  │
│  │  • Try-on images: cached for 24 hours then    │  │
│  │    permanently deleted                        │  │
│  │  • Merchants can request immediate deletion   │  │
│  │    by contacting support                      │  │
│  └───────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────┐  │
│  │  🌍  Third-Party Services                     │  │
│  │  • Google Vertex AI (Gemini) — used for       │  │
│  │    virtual try-on image generation            │  │
│  │  • Image data is sent to Google's API for     │  │
│  │    processing and is subject to Google's      │  │
│  │    data processing terms                      │  │
│  │  • No other third-party services receive      │  │
│  │    customer image data                        │  │
│  └───────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────┐  │
│  │  ⚖️  GDPR & CCPA Compliance                   │  │
│  │  • Customers may request access to or         │  │
│  │    deletion of their data at any time         │  │
│  │  • No personally identifiable information     │  │
│  │    is linked to uploaded photos by default    │  │
│  │  • Merchants are responsible for updating     │  │
│  │    their store's own privacy policy to        │  │
│  │    disclose use of this app                   │  │
│  │  • Full privacy policy: [link TBD]            │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

### Component spec (`app/routes/app.settings.privacy.tsx`)

```tsx
import { Page, BlockStack, Card, Text, List } from "@shopify/polaris";

const PRIVACY_SECTIONS = [
  {
    title: "Data We Collect",
    icon: "📸",
    points: [
      "Customer-uploaded photos (front and side pose)",
      "Body measurements derived from those photos using AI",
      "Anonymous session identifiers",
      "Try-on results and style preferences",
    ],
  },
  {
    title: "How We Use Your Data",
    icon: "🔒",
    points: [
      "Photos are processed solely to extract body measurements",
      "Measurements power size recommendations and virtual try-on",
      "No customer data is sold to or shared with third parties for marketing",
      "Photos are never used for advertising or model training without explicit consent",
    ],
  },
  {
    title: "Data Retention",
    icon: "⏱️",
    points: [
      "Customer photos are deleted from our servers within 24 hours of upload",
      "Measurements are retained for 30 days to avoid repeat uploads on return visits",
      "Try-on images are cached for 24 hours, then permanently deleted",
      "Merchants can request immediate deletion of all store data by contacting support",
    ],
  },
  {
    title: "Third-Party Services",
    icon: "🌍",
    points: [
      "Google Vertex AI (Gemini) is used for virtual try-on image generation",
      "Image data is transmitted to Google's API and subject to Google's data processing terms",
      "No other third-party services receive customer image or measurement data",
    ],
  },
  {
    title: "GDPR & CCPA Compliance",
    icon: "⚖️",
    points: [
      "Customers may request access to or deletion of their data at any time",
      "No personally identifiable information is linked to uploaded photos by default",
      "Merchants are responsible for disclosing use of this app in their store's own privacy policy",
      "For the full privacy policy, contact support@[yourdomain].com",
    ],
  },
];

export default function PrivacySettings() {
  return (
    <Page title="Privacy">
      <BlockStack gap="400">
        {PRIVACY_SECTIONS.map(({ title, icon, points }) => (
          <Card key={title}>
            <BlockStack gap="300">
              <Text variant="headingMd">{icon}  {title}</Text>
              <List type="bullet">
                {points.map(point => (
                  <List.Item key={point}>{point}</List.Item>
                ))}
              </List>
            </BlockStack>
          </Card>
        ))}
      </BlockStack>
    </Page>
  );
}
```

### Behaviour rules
- Fully static — no loader, no action, no API calls
- Content is defined in the `PRIVACY_SECTIONS` constant — update copy there as policy evolves
- The final card's "full privacy policy" link should be updated to the actual hosted policy URL before launch

---

## Settings → Support Screen

**Added:** 2026-02-22

### Route
`app/routes/app.settings.support.tsx` — child of Settings layout.

### Purpose
Two-card screen giving the merchant two ways to get help: email (opens their default mail client) and a booking link (opens a Cal.com / Calendly page in a new tab).

### Layout

```
┌─────────────────────────────────────────────────────┐
│  Support                                            │
│ ─────────────────────────────────────────────────── │
│  ┌───────────────────────────────────────────────┐  │
│  │  📧  Email Support                            │  │
│  │                                               │  │
│  │  Have a question or need help setting up      │  │
│  │  your store? Our team typically responds      │  │
│  │  within 24 hours.                             │  │
│  │                                               │  │
│  │  [ Email us at support@yourdomain.com ]       │  │
│  │    (opens default mail client)                │  │
│  └───────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────┐  │
│  │  📅  Book a Call                              │  │
│  │                                               │  │
│  │  Want a live walkthrough or have a complex    │  │
│  │  setup question? Book a free 30-minute call   │  │
│  │  with our team.                               │  │
│  │                                               │  │
│  │  [ Book a time slot → ]                       │  │
│  │    (opens booking page in new tab)            │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

### Component spec (`app/routes/app.settings.support.tsx`)

```tsx
import { Page, BlockStack, Card, Text, Button, InlineStack } from "@shopify/polaris";

// ── Update these two constants before launch ─────────────────
const SUPPORT_EMAIL = "support@yourdomain.com";
const BOOKING_URL   = "https://cal.com/yourusername/30min";  // or Calendly equivalent
// ─────────────────────────────────────────────────────────────

export default function SupportSettings() {
  return (
    <Page title="Support">
      <BlockStack gap="400">

        {/* Card 1 — Email */}
        <Card>
          <BlockStack gap="400">
            <Text variant="headingMd">📧  Email Support</Text>
            <Text tone="subdued">
              Have a question or need help setting up your store?
              Our team typically responds within 24 hours.
            </Text>
            <InlineStack>
              <Button
                url={`mailto:${SUPPORT_EMAIL}`}
                variant="primary"
              >
                Email us at {SUPPORT_EMAIL}
              </Button>
            </InlineStack>
          </BlockStack>
        </Card>

        {/* Card 2 — Book a call */}
        <Card>
          <BlockStack gap="400">
            <Text variant="headingMd">📅  Book a Call</Text>
            <Text tone="subdued">
              Want a live walkthrough or have a complex setup question?
              Book a free 30-minute call with our team.
            </Text>
            <InlineStack>
              <Button
                url={BOOKING_URL}
                external          // opens in new tab
                variant="primary"
              >
                Book a time slot
              </Button>
            </InlineStack>
          </BlockStack>
        </Card>

      </BlockStack>
    </Page>
  );
}
```

### Behaviour rules
- Fully static — no loader, no action, no API calls
- `mailto:` link opens the merchant's default email client with the To field pre-filled
- Booking link uses Polaris `Button` with `external` prop → opens in a new tab (not an iframe)
- Replace `SUPPORT_EMAIL` and `BOOKING_URL` constants before launch
- Polaris `Button` with `url` prop renders as an `<a>` tag — no JS required for either interaction

---

## AI Photoshoot (Merchant Admin Feature)

**Route group:** `app/routes/app.photoshoot.*`
**Nav entry:** "AI Photoshoot" in the main sidebar nav

### Landing Page — `app/routes/app.photoshoot.tsx`

Three feature cards in a Polaris `Grid` (3-column on desktop, stacked on mobile):

| Card | Icon | Title | Body |
|---|---|---|---|
| Ghost Mannequin | 👻 | Ghost Mannequin | Turn any product photo into a professional ghost mannequin shot |
| Try-On for Model | 👗 | Try-On for Model | Place your product on a model — use our library or upload your own |
| Model Swap | 🔄 | Model Swap | Swap the model in an existing product photo while keeping the garment |

Each card has a primary `Button` that navigates to the relevant sub-route.

No loader, no API calls on the landing page.

---

### Common UX Pattern (all three sub-screens)

Every sub-screen follows the same flow:

```
Step 1: Pick product + image  →  Step 2: Second image input (if needed)  →  Step 3: Generate  →  Step 4: Preview + Approve/Download
```

#### Step 1 — Product & Image Picker
- `Button` labelled "Select Product" → opens Shopify ResourcePicker (`shopify.resourcePicker({ type: 'product', multiple: false })`)
- On selection: display product title + thumbnail grid of all its images (Polaris `Thumbnail` components in a flex row)
- Merchant clicks a thumbnail to select it — selected state shows a blue border/checkmark overlay
- Selected image URL is stored in state as `selectedImageUrl`

#### Step 2 — Second Image (Try-On & Model Swap only)
Two tabs or a segmented control:
- **"Use model library"** — calls `GET /api/v1/merchant/photoshoot/models?gender=unisex` (or filtered), shows a thumbnail grid, merchant picks one
- **"Upload photo"** — `DropZone` component (Polaris), accepts JPEG/PNG, max 10 MB

#### Step 3 — Generate Button
- Disabled until required images are selected
- On click: calls the relevant `POST` endpoint
  - Ghost mannequin: JSON body
  - Try-On / Model Swap: `multipart/form-data` (use `fetch` with `FormData`, not `fetcher.submit`)
- Returns `{ job_id, status: "queued" }` → start polling

#### Step 3b — Polling
- `useEffect` with `setInterval` every 3 seconds calling `GET /jobs/{job_id}/status`
- Show Polaris `ProgressBar` (indeterminate spinner) + status message during processing
- Stop polling when `status === "completed"` or `status === "failed"`
- Estimated wait: 30–60 seconds

#### Step 4 — Preview
- Side-by-side layout: original selected image (left) vs generated result (right)
- Result image loaded from `result_image_url` (e.g. `/api/v1/merchant/photoshoot/jobs/{job_id}/result`)
- Two action buttons:
  - **"Regenerate"** — clears result, re-POSTs with same inputs
  - **"Approve & Push to Shopify"** → calls `POST /jobs/{job_id}/approve` with optional alt text (Polaris `TextField` below the result)
  - **"Download"** — `<a href={result_image_url} download>` button
- On approve success: show Polaris `Toast` "Image added to your product gallery!" + disable the Approve button

---

### Sub-Route: Ghost Mannequin — `app/routes/app.photoshoot.ghost-mannequin.tsx`

**No loader.** All state is client-side.

**State:**
```ts
selectedProduct: ShopifyProduct | null
image1Url: string | null
image2Url: string | null
jobId: string | null
jobStatus: "idle" | "generating" | "completed" | "failed"
resultImageUrl: string | null
altText: string
```

**Layout:**
- `Page` title "Ghost Mannequin"
- `Card` "Select Product Images" → ResourcePicker + image grid
  - Merchant selects image 1 (shown with label "Image 1 ✓"), then image 2 (shown with label "Image 2 ✓")
  - Clicking the same image deselects it; the two slots fill in order of click
- `Card` "Generate" → `Button` "Create Ghost Mannequin" (disabled until both images selected)
- Result card (shown after completion)

**API call:**
```ts
await fetch('/api/v1/merchant/photoshoot/ghost-mannequin', {
  method: 'POST',
  headers: { 'X-Store-ID': storeId, 'Content-Type': 'application/json' },
  body: JSON.stringify({
    image1_url: image1Url,
    image2_url: image2Url,
    shopify_product_gid: selectedProduct.id,
  }),
});
```

---

### Sub-Route: Try-On for Model — `app/routes/app.photoshoot.try-on-model.tsx`

**State:** `selectedProduct`, `productImageUrl`, `modelSource: "library" | "upload"`, `modelLibraryId`, `uploadedModelFile`, `jobId`, `jobStatus`, `resultImageUrl`, `altText`

**Layout:**
- `Card` "1. Select Product Image" → ResourcePicker + single-select image grid
- `Card` "2. Choose Model" → Polaris `Tabs` with "Model Library" and "Upload Photo"
  - Library tab: fetches `GET /api/v1/merchant/photoshoot/models?gender=unisex`, shows thumbnail grid
  - Upload tab: Polaris `DropZone`
- `Card` "3. Generate" → `Button` "Generate Try-On" (disabled until step 1 & 2 complete)
- Result card

**API call (multipart):**
```ts
const form = new FormData();
form.append('shopify_product_gid', selectedProduct.id);
form.append('product_image_url', productImageUrl);
if (modelSource === 'library') {
  form.append('model_library_id', modelLibraryId);
} else {
  form.append('model_image', uploadedModelFile);
}
await fetch('/api/v1/merchant/photoshoot/try-on-model', {
  method: 'POST',
  headers: { 'X-Store-ID': storeId },   // NO Content-Type header — let browser set multipart boundary
  body: form,
});
```

---

### Sub-Route: Model Swap — `app/routes/app.photoshoot.model-swap.tsx`

**State:** `selectedProduct`, `originalImageUrl`, `newModelSource: "library" | "upload"`, `newModelLibraryId`, `uploadedNewModelFile`, `jobId`, `jobStatus`, `resultImageUrl`, `altText`

**Layout:**
- `Card` "1. Select Original Product Image" → ResourcePicker + single-select image grid
  - Note below card: *"Select an image that shows a model wearing the product"*
- `Card` "2. Choose Replacement Model" → Polaris `Tabs` (Library / Upload)
- `Card` "3. Generate" → `Button` "Swap Model"
- Result card

**API call (multipart):**
```ts
const form = new FormData();
form.append('shopify_product_gid', selectedProduct.id);
form.append('original_image_url', originalImageUrl);
if (newModelSource === 'library') {
  form.append('new_model_library_id', newModelLibraryId);
} else {
  form.append('new_model_image', uploadedNewModelFile);
}
await fetch('/api/v1/merchant/photoshoot/model-swap', {
  method: 'POST',
  headers: { 'X-Store-ID': storeId },
  body: form,
});
```

---

### Approve Flow Detail

When merchant clicks "Approve & Push to Shopify":

```ts
// Optional alt text from TextField
const res = await fetch(`/api/v1/merchant/photoshoot/jobs/${jobId}/approve`, {
  method: 'POST',
  headers: { 'X-Store-ID': storeId, 'Content-Type': 'application/json' },
  body: JSON.stringify({ alt_text: altText || undefined }),
});
const data = await res.json();
if (data.approved) {
  shopify.toast.show("Image added to your product gallery!");
  setApproved(true);  // disable Approve button
}
```

**Error cases:**
- `410 Gone` — image expired (24h TTL): show banner "This result has expired. Please regenerate."
- `502` — Shopify error: show banner with error message

---

### Polling Implementation

```ts
useEffect(() => {
  if (!jobId || jobStatus !== "generating") return;
  const interval = setInterval(async () => {
    const res = await fetch(`/api/v1/merchant/photoshoot/jobs/${jobId}/status`, {
      headers: { 'X-Store-ID': storeId },
    });
    const data = await res.json();
    if (data.status === "completed") {
      setJobStatus("completed");
      setResultImageUrl(data.result_image_url);
      clearInterval(interval);
    } else if (data.status === "failed") {
      setJobStatus("failed");
      setErrorMessage(data.error || "Generation failed");
      clearInterval(interval);
    }
  }, 3000);
  return () => clearInterval(interval);
}, [jobId, jobStatus]);
```

---

### Notes

- `X-Store-ID` header must be sent on all authenticated calls; retrieve from `useLoaderData` (populated by `GET /merchant/onboarding/status` or session)
- Do NOT send `Content-Type: application/json` on multipart requests — the browser sets the boundary automatically
- The ResourcePicker is opened via `shopify.resourcePicker(...)` from `useAppBridge()` (App Bridge v4 hook)
- Model library thumbnails: use `<img src={model.image_url} />` where `image_url` is `/api/v1/merchant/photoshoot/models/{id}/image`
- For the Download button use `<a href={resultImageUrl} download="ai-photoshoot-result.jpg">` — this works because the endpoint serves image bytes with no auth check

---

## AI Photoshoot — Extended Image Library UI (Segment 10b)

The following updates extend the AI Photoshoot screens with richer model/face filtering and ghost mannequin reference images.

---

### Ghost Mannequin Screen — Extended

**New field: Clothing Type dropdown**
- Label: "Clothing Type"
- Options: Tops | Bottoms | Dresses | Outerwear
- Required (shown before the image picker)
- Sends `clothing_type` in the `POST /merchant/photoshoot/ghost-mannequin` body

**New field: Reference Pose Images**
- After selecting a clothing type, call `GET /merchant/photoshoot/ghost-mannequin-refs?clothing_type={type}` (requires `X-Store-ID`)
- Display the 3 returned reference images (front/side/back) as a small gallery labelled "Example poses for [type]"
- These are read-only reference images — they help the merchant understand which product photos work best
- Each image is served from `/api/v1/merchant/photoshoot/ghost-mannequin-refs/{id}/image`

**Updated flow:**
1. Merchant selects Clothing Type → reference poses load dynamically below
2. Merchant selects 2 product images via ResourcePicker
3. POST includes `clothing_type` in the JSON body

---

### Try-On for Model Screen — Extended

**New filter controls:**

```
Gender:    [Male] [Female] [Unisex]   ← existing
Age:       [All] [18-25] [26-35] [36-45] [45+]    ← NEW
Body Type: [All] [Slim] [Athletic] [Regular] [Plus] ← NEW
```

- When any filter changes, re-fetch `GET /merchant/photoshoot/models?gender=&age=&body_type=` with the active values
- Omit `age` and `body_type` params when "All" is selected (so they default to no filter)
- Model grid rendering is unchanged — still shows thumbnails from `model.image_url`

---

### Model Swap Screen — Reworked (Face-Only Swap)

**Concept change:** Model swap now replaces only the face in the original product photo. The body, pose, clothing, and background remain identical. The merchant picks a replacement face from the face library (or uploads their own headshot).

**Updated input fields:**

| Field | Type | Notes |
|---|---|---|
| Product image | URL (ResourcePicker) | Image of original model wearing the product |
| Replacement face | Library picker OR upload | Either `face_library_id` (from face library) or `face_image` (file upload) |

**Face Library UI:**
- Filters: Gender (Male/Female — no unisex), Age (optional), Skin Tone (optional: Fair/Light/Medium/Tan/Dark)
- API: `GET /merchant/photoshoot/model-faces?gender=&age=&skin_tone=` (requires `X-Store-ID`)
- Each face is served from `/api/v1/merchant/photoshoot/model-faces/{id}/image`
- Same thumbnail grid pattern as the full-body model library

**Form submission (multipart/form-data):**
```
shopify_product_gid  (string)
original_image_url   (string — from ResourcePicker)
face_library_id      (string UUID — if face selected from library)
face_image           (file — if headshot uploaded)
```
Exactly one of `face_library_id` or `face_image` must be provided.

**Result description label:**
Show "Only the face will be replaced. Body, clothing, and background remain unchanged." near the submit button.

---

## Analytics Screen — Standard Sub-Tab

**Route:** `app/routes/app.analytics.tsx` (parent) + `app/routes/app.analytics.standard.tsx`

The Analytics screen mirrors the Settings screen tab pattern: a top-level page with two sub-tabs — **Standard** (this segment) and **Advanced** (future).

---

### Tab Bar

```
┌──────────────────────────────────────────────────────────────┐
│  Analytics                                                    │
│  [ Standard ]  [ Advanced ]                                   │
│ ─────────────────────────────────────────────────────────────│
```

Use Polaris `Tabs` component. "Advanced" tab renders a "Coming soon" placeholder.

---

### Period Filter

Immediately below the tab bar — a right-aligned segmented control:

```
                        Period:  [ 7 days ]  [ 30 days ]  [ 90 days ]
```

Use Polaris `ButtonGroup` (segmented). Default selection: **30 days**.
On change, re-fetch `GET /api/v1/merchant/analytics/standard?period={n}` and re-render all cards/charts.

---

### Layout — Standard Sub-Tab

```
┌────────────────────────────────────────────────────────────────┐
│  Analytics › Standard                        Period: [30 days]  │
│ ─────────────────────────────────────────────────────────────  │
│                                                                  │
│  ENGAGEMENT                                                      │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────┐ │
│  │ Widget Opens │ │ Active Users │ │  Try-Ons     │ │Credits │ │
│  │    1,240     │ │     834      │ │     412      │ │ 1,648  │ │
│  │              │ │              │ │   completed  │ │  used  │ │
│  └──────────────┘ └──────────────┘ └──────────────┘ └────────┘ │
│                                                                  │
│  CONVERSIONS                                                     │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────┐ │
│  │  Add to Cart │ │ Conversions  │ │ Conv. Rate   │ │Revenue │ │
│  │     198      │ │      87      │ │    7.0 %     │ │$3,240  │ │
│  │              │ │  (orders)    │ │ / widget open│ │ impact │ │
│  └──────────────┘ └──────────────┘ └──────────────┘ └────────┘ │
│                                                                  │
│  RETURNS                                                         │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Returns (orders with refund): 12                          │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  TRY-ON TREND ─────────────────────────────────────────────── │ │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Try-Ons Per Day                                            │ │
│  │                                                             │ │
│  │  25 ┤                  *                                    │ │
│  │  20 ┤           *   *     *                                 │ │
│  │  15 ┤       *              *   *                            │ │
│  │  10 ┤   *                       *                           │ │
│  │   5 ┤ *                           *   *                     │ │
│  │   0 └─────────────────────────────────────────────── days  │ │
│  │      Mar 1  Mar 5  Mar 10  Mar 15  Mar 20  Mar 25  Mar 30  │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  TOP PERFORMING PRODUCTS ──────────────────────────────────── │ │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ #  Product            Try-Ons  Add-to-Cart  Conv. Rate     │ │
│  │ ─────────────────────────────────────────────────────────  │ │
│  │ 1  Blue Slim Jeans        82        41       50.0 %        │ │
│  │ 2  White Linen Shirt      61        24       39.3 %        │ │
│  │ 3  Floral Dress           45        14       31.1 %        │ │
│  │ 4  Classic Blazer         38         9       23.7 %        │ │
│  │ 5  Grey Hoodie            29         5       17.2 %        │ │
│  └────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────┘
```

---

### Component Breakdown

#### Metric Cards (Engagement + Conversions rows)

- Use Polaris `Card` + `BlockStack` in a 4-column `Grid`.
- Each card: large bold number (`Text variant="heading2xl"`), small label below.
- **Null / loading states:**
  - When Shopify data is unavailable (`conversions`, `conversion_rate`, `revenue_impact`, `return_count` are `null`): show `—` with a subdued tooltip "Shopify data unavailable".
  - While loading: replace number with a `SkeletonDisplayText`.

**Engagement row (always from DB — never null):**
| Card | Value field | Label |
|---|---|---|
| Widget Opens | `widget_opens` | "widget sessions" |
| Active Users | `unique_users` | "unique sessions" |
| Try-Ons | `total_try_ons` | "completed" |
| Credits Used | `credits_used` | "this period" |

**Conversions row (Shopify cross-ref — may be null):**
| Card | Value field | Label |
|---|---|---|
| Add to Cart | `add_to_cart_count` | "from widget" |
| Conversions | `conversions` | "orders placed" |
| Conv. Rate | `conversion_rate` + "%" | "per widget open" |
| Revenue Impact | "$" + `revenue_impact` | "from conversions" |

**Returns (single wide card, Shopify — may be null):**
- One full-width card: "Returns (orders with refund): `return_count`"

---

#### Try-On Trend Chart (Line Chart)

- **Library:** Recharts (`LineChart`) — already used in many Shopify Remix apps. Install: `npm install recharts`.
- **Data:** `trend` array — `[{ date: "2026-03-01", try_ons: 14 }, ...]`
- **X-axis:** `date` field formatted as `MMM D` (e.g. "Mar 1"). Tick density: show every N-th label to avoid crowding (every 3rd for 30 days, every 7th for 90 days, every 1st for 7 days).
- **Y-axis:** `try_ons` count; always starts at 0.
- **Line:** single line, Shopify Indigo (`#5C6AC4`), dot on each point, smooth curve (`type="monotone"`).
- **Tooltip:** on hover — show "Mar 15: 21 try-ons".
- **Empty state:** if all `try_ons === 0` across the period, show a centred subdued message "No try-ons in this period" instead of the chart.
- **Container:** wrap in a Polaris `Card` with title "Try-Ons Per Day".

```tsx
// Minimal Recharts example
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

<ResponsiveContainer width="100%" height={220}>
  <LineChart data={trend}>
    <CartesianGrid strokeDasharray="3 3" stroke="#E4E5E7" />
    <XAxis dataKey="date" tickFormatter={(d) => formatAxisDate(d)} />
    <YAxis allowDecimals={false} />
    <Tooltip formatter={(v) => [`${v} try-ons`, ""]} labelFormatter={(d) => formatTooltipDate(d)} />
    <Line type="monotone" dataKey="try_ons" stroke="#5C6AC4" strokeWidth={2} dot={{ r: 3 }} />
  </LineChart>
</ResponsiveContainer>
```

---

#### Top Performing Products Table

- Polaris `IndexTable` (or plain `DataTable`) with 5 rows max.
- Columns: Rank, Product Name, Try-Ons, Add-to-Cart, Conv. Rate
- **Conv. Rate column:** colour-coded badge:
  - `>= 30%` → `status="success"` (green)
  - `10–29%` → `status="warning"` (yellow)
  - `< 10%` → `status="critical"` (red)
  - `0 try-ons` → `—` (no badge)
- **Rank column:** `#1` through `#5` in subdued text.
- **Empty state:** "No product data yet" centred in the table body.

---

### Loader

```typescript
// app/routes/app.analytics.standard.tsx
export async function loader({ request }: LoaderFunctionArgs) {
  const { session } = await authenticate.admin(request);
  const url = new URL(request.url);
  const period = url.searchParams.get("period") ?? "30";

  const store = await getStoreByDomain(session.shop);
  const res = await fetch(
    `${BACKEND_URL}/api/v1/merchant/analytics/standard?period=${period}`,
    { headers: { "X-Store-ID": store.store_id } }
  );
  const data = await res.json();
  return { analytics: data, period: Number(period) };
}
```

Period switching is handled by the client: clicking a period button navigates to the same route with `?period=7/30/90` as a search param (use `useNavigate` or `<Link>`), which triggers the loader to re-fetch.

---

### Error / Loading States Summary

| Situation | Behaviour |
|---|---|
| Initial load | Show `SkeletonDisplayText` in all metric cards, skeleton rows in table, no chart |
| Shopify fields null | Show `—` in Conversions / Revenue / Returns cards with tooltip |
| All try-ons = 0 | Show zeros in cards; replace chart with "No try-ons in this period" message |
| Top products empty | Show "No product data yet" placeholder in table |
| API error (500) | Polaris `Banner` (status="critical"): "Could not load analytics. Please try again." |

---

### Navigation Update

Update the main app sidebar to include the Analytics link (no longer "future"):

```tsx
// app/components/Sidebar.tsx (or equivalent nav)
<Navigation.Item
  label="Analytics"
  icon={ChartLineIcon}
  url="/app/analytics"
  selected={location.pathname.startsWith("/app/analytics")}
/>
```

Default redirect: `/app/analytics` → `/app/analytics/standard`.

---

**End of Frontend PRD**
