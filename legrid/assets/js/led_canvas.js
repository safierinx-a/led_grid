// High-performance LED grid canvas renderer
export class LEDCanvas {
  constructor(containerId, width, height, pixelSize) {
    this.container = document.getElementById(containerId);
    this.width = width;
    this.height = height;
    this.pixelSize = pixelSize;

    // Create canvas
    this.canvas = document.createElement("canvas");
    this.canvas.width = width * pixelSize;
    this.canvas.height = height * pixelSize;
    this.canvas.style.width = `${width * pixelSize}px`;
    this.canvas.style.height = `${height * pixelSize}px`;

    this.ctx = this.canvas.getContext("2d");
    this.container.appendChild(this.canvas);

    // Frame interpolation for smooth 60fps display
    this.currentFrame = new Array(width * height).fill([0, 0, 0]);
    this.targetFrame = new Array(width * height).fill([0, 0, 0]);
    this.isInterpolating = false;
    this.interpolationFactor = 0;

    // Performance monitoring
    this.frameCount = 0;
    this.lastFpsUpdate = performance.now();
    this.fps = 0;

    // Start render loop
    this.startRenderLoop();

    // Setup mouse interactions
    this.setupInteractions();
  }

  // Update with new frame data from server
  updateFrame(pixels) {
    if (!pixels || pixels.length !== this.width * this.height) return;

    // Set new target frame
    this.targetFrame = pixels.map((pixel) =>
      Array.isArray(pixel) ? pixel : [pixel.r || 0, pixel.g || 0, pixel.b || 0]
    );

    // Start interpolation for smooth transition
    this.isInterpolating = true;
    this.interpolationFactor = 0;
  }

  // High-performance render loop using requestAnimationFrame
  startRenderLoop() {
    const render = (timestamp) => {
      this.renderFrame();
      this.updateFPS();
      requestAnimationFrame(render);
    };
    requestAnimationFrame(render);
  }

  renderFrame() {
    // Clear canvas
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

    // Interpolate between current and target frames for smooth animation
    if (this.isInterpolating) {
      this.interpolationFactor = Math.min(this.interpolationFactor + 0.15, 1.0);

      for (let i = 0; i < this.currentFrame.length; i++) {
        const current = this.currentFrame[i];
        const target = this.targetFrame[i];

        this.currentFrame[i] = [
          Math.round(
            current[0] + (target[0] - current[0]) * this.interpolationFactor
          ),
          Math.round(
            current[1] + (target[1] - current[1]) * this.interpolationFactor
          ),
          Math.round(
            current[2] + (target[2] - current[2]) * this.interpolationFactor
          ),
        ];
      }

      if (this.interpolationFactor >= 1.0) {
        this.isInterpolating = false;
      }
    }

    // Render pixels using efficient batch operations
    this.renderPixelsBatch();
  }

  renderPixelsBatch() {
    // Use ImageData for maximum performance
    const imageData = this.ctx.createImageData(
      this.canvas.width,
      this.canvas.height
    );
    const data = imageData.data;

    for (let y = 0; y < this.height; y++) {
      for (let x = 0; x < this.width; x++) {
        const pixelIndex = y * this.width + x;
        const [r, g, b] = this.currentFrame[pixelIndex];

        // Draw pixel as a block
        for (let py = 0; py < this.pixelSize; py++) {
          for (let px = 0; px < this.pixelSize; px++) {
            const canvasX = x * this.pixelSize + px;
            const canvasY = y * this.pixelSize + py;
            const canvasIndex = (canvasY * this.canvas.width + canvasX) * 4;

            if (canvasIndex < data.length) {
              data[canvasIndex] = r; // R
              data[canvasIndex + 1] = g; // G
              data[canvasIndex + 2] = b; // B
              data[canvasIndex + 3] = 255; // A
            }
          }
        }
      }
    }

    this.ctx.putImageData(imageData, 0, 0);

    // Add LED effects overlay
    this.renderLEDEffects();
  }

  renderLEDEffects() {
    // Add subtle grid lines and glow effects
    this.ctx.strokeStyle = "rgba(0, 0, 0, 0.1)";
    this.ctx.lineWidth = 1;

    // Vertical lines
    for (let x = 0; x <= this.width; x++) {
      this.ctx.beginPath();
      this.ctx.moveTo(x * this.pixelSize, 0);
      this.ctx.lineTo(x * this.pixelSize, this.canvas.height);
      this.ctx.stroke();
    }

    // Horizontal lines
    for (let y = 0; y <= this.height; y++) {
      this.ctx.beginPath();
      this.ctx.moveTo(0, y * this.pixelSize);
      this.ctx.lineTo(this.canvas.width, y * this.pixelSize);
      this.ctx.stroke();
    }
  }

  setupInteractions() {
    let isHovering = false;
    const coordsDisplay = document.getElementById("grid-coords");

    this.canvas.addEventListener("mousemove", (e) => {
      const rect = this.canvas.getBoundingClientRect();
      const x = Math.floor((e.clientX - rect.left) / this.pixelSize);
      const y = Math.floor((e.clientY - rect.top) / this.pixelSize);

      if (x >= 0 && x < this.width && y >= 0 && y < this.height) {
        const pixelIndex = y * this.width + x;
        const [r, g, b] = this.currentFrame[pixelIndex];
        const brightness = Math.round(
          ((0.299 * r + 0.587 * g + 0.114 * b) / 255) * 100
        );

        if (coordsDisplay) {
          coordsDisplay.textContent = `Pixel (${x}, ${y}) | RGB(${r}, ${g}, ${b}) | ${brightness}% brightness`;
        }
        isHovering = true;
      }
    });

    this.canvas.addEventListener("mouseleave", () => {
      if (coordsDisplay && isHovering) {
        coordsDisplay.textContent = "Hover to see pixel data";
        isHovering = false;
      }
    });
  }

  updateFPS() {
    this.frameCount++;
    const now = performance.now();

    if (now - this.lastFpsUpdate >= 1000) {
      this.fps = Math.round(
        (this.frameCount * 1000) / (now - this.lastFpsUpdate)
      );
      this.frameCount = 0;
      this.lastFpsUpdate = now;

      // Update FPS display if available
      const fpsDisplay = document.getElementById("canvas-fps");
      if (fpsDisplay) {
        fpsDisplay.textContent = `${this.fps} FPS`;
      }
    }
  }

  // Get current performance metrics
  getMetrics() {
    return {
      fps: this.fps,
      isInterpolating: this.isInterpolating,
      interpolationFactor: this.interpolationFactor,
    };
  }
}
