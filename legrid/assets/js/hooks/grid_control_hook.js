const GridControlHook = {
  mounted() {
    // Parameter tracking
    this.pendingChanges = {};
    this.updateTimer = null;
    this.updateDelay = 50; // Increased from 16ms to reduce server load
    this.lastSentValues = {}; // Track last sent values to prevent duplicates
    this.controlsInitialized = false; // Track if controls are already set up

    // Set up all UI controls
    this.setupControls();

    // Set up pixel hover effects
    this.setupPixelEffects();

    // Set up mutation observer to detect DOM changes in parameters section
    this.setupMutationObserver();

    // Listen for pattern changes
    this.handleEvent("pattern_changed", ({ pattern_id }) => {
      console.log("Pattern changed to:", pattern_id);

      // Clear any pending updates when pattern changes
      this.pendingChanges = {};
      this.lastSentValues = {};

      // Reset controls initialization flag
      this.controlsInitialized = false;

      // Wait for DOM to update with new controls
      setTimeout(() => {
        this.setupControls();
      }, 100); // Increased delay to ensure DOM is ready
    });
  },

  updated() {
    // Only reinitialize if controls aren't already set up
    if (!this.controlsInitialized) {
      setTimeout(() => {
        this.setupControls();
      }, 50);
    }
  },

  setupMutationObserver() {
    // Create a mutation observer to detect when parameters are added/removed
    const parameterContainer = document.getElementById("parameter-controls");
    if (!parameterContainer) return;

    const observer = new MutationObserver((mutations) => {
      // Reset initialization flag when DOM changes significantly
      let significantChange = false;
      mutations.forEach((mutation) => {
        if (mutation.type === "childList" && mutation.addedNodes.length > 0) {
          significantChange = true;
        }
      });

      if (significantChange) {
        this.controlsInitialized = false;
        this.setupControls();
      }
    });

    // Start observing the parameter container for DOM changes
    observer.observe(parameterContainer, {
      childList: true,
      subtree: true,
      attributes: false,
    });
  },

  setupControls() {
    // Find all responsive controls
    const controls = document.querySelectorAll(".responsive-control");
    if (!controls.length) return;

    // Mark as initialized to prevent duplicate setup
    this.controlsInitialized = true;

    // Remove existing event listeners to prevent duplicates
    controls.forEach((control) => {
      // Clone the node to remove all event listeners
      const newControl = control.cloneNode(true);
      control.parentNode.replaceChild(newControl, control);
    });

    // Re-query controls after cloning
    const cleanControls = document.querySelectorAll(".responsive-control");

    // Handle parameter changes from any control
    cleanControls.forEach((control) => {
      // Update display immediately when control changes
      control.addEventListener("input", (e) => {
        this.handleControlChange(control);
      });

      // Specific handlers by control type
      if (control.type === "range") {
        // Handle slider touch/mouse up for immediate updates
        control.addEventListener("pointerup", () => {
          this.flushChanges();
        });
      } else if (control.type === "checkbox") {
        // Handle checkbox changes - send immediately
        control.addEventListener("change", () => {
          this.handleControlChange(control, true); // true = immediate
        });
      } else if (control.type === "select-one") {
        // Handle dropdown changes - send immediately
        control.addEventListener("change", () => {
          this.handleControlChange(control, true); // true = immediate
        });
      } else if (control.type === "text") {
        // Handle text input changes - send immediately on blur/enter
        control.addEventListener("blur", () => {
          this.handleControlChange(control, true); // true = immediate
        });
        control.addEventListener("keypress", (e) => {
          if (e.key === "Enter") {
            this.handleControlChange(control, true); // true = immediate
          }
        });
      }
    });
  },

  setupPixelEffects() {
    // Find all LED pixels
    const pixels = document.querySelectorAll(".led-pixel");
    if (!pixels.length) return;

    pixels.forEach((pixel) => {
      pixel.addEventListener("mouseenter", () => {
        // Show pixel info on hover
        const x = pixel.getAttribute("data-x");
        const y = pixel.getAttribute("data-y");
        const rgb = pixel.getAttribute("data-rgb");

        // Could display tooltip or update info panel
        console.log(`Pixel (${x},${y}): RGB ${rgb}`);
      });
    });
  },

  handleControlChange(control, immediate = false) {
    // Get the control value
    const key = control.id;
    let value;

    if (control.type === "checkbox") {
      value = control.checked;
    } else if (control.type === "select-one") {
      value = control.options[control.selectedIndex].value;
    } else {
      value = control.value;
    }

    // Convert to appropriate type based on data attribute
    const paramType = control.getAttribute("data-param-type");
    if (paramType === "integer") {
      value = parseInt(value, 10);
    } else if (paramType === "float") {
      value = parseFloat(value);
    } else if (paramType === "boolean") {
      value = Boolean(value);
    }

    // Check if this value has actually changed from what we last sent
    if (this.lastSentValues && this.lastSentValues[key] === value) {
      // Value hasn't changed, don't send again
      return;
    }

    // Update display immediately with a visual indication of pending state
    const displayEl = document.getElementById(`display-${key}`);
    if (displayEl) {
      displayEl.textContent = value;
      displayEl.classList.add("pending-update");

      // Set a timeout to remove the pending status after a reasonable time
      setTimeout(() => {
        displayEl.classList.remove("pending-update");
      }, 1000); // 1 second should be enough for most patterns to catch up
    }

    // Queue for batched update
    this.pendingChanges[key] = value;

    // Cache the current value to prevent visual reverts
    control._lastValue =
      control.type === "checkbox" ? control.checked : control.value;

    // Handle immediate vs debounced updates
    if (immediate) {
      // Send immediately for discrete controls
      this.flushChanges();
    } else {
      // Use debouncing for continuous controls like sliders
      this.scheduleBatchUpdate();
    }
  },

  scheduleBatchUpdate() {
    // Clear existing timers
    if (this.updateTimer) {
      clearTimeout(this.updateTimer);
    }

    // Schedule a new update
    this.updateTimer = setTimeout(() => {
      this.sendBatchUpdate();
    }, this.updateDelay);
  },

  flushChanges() {
    if (this.updateTimer) {
      clearTimeout(this.updateTimer);
      this.updateTimer = null;
      this.sendBatchUpdate();
    }
  },

  sendBatchUpdate() {
    if (Object.keys(this.pendingChanges).length === 0) return;

    // Filter out changes that haven't actually changed from last sent values
    const actualChanges = {};
    for (const [key, value] of Object.entries(this.pendingChanges)) {
      if (this.lastSentValues[key] !== value) {
        actualChanges[key] = value;
      }
    }

    // Only send if we have actual changes
    if (Object.keys(actualChanges).length === 0) {
      this.pendingChanges = {};
      return;
    }

    // Send the batch update to the server
    this.pushEvent("batch-param-update", { params: actualChanges });

    // Update our tracking of last sent values
    Object.assign(this.lastSentValues, actualChanges);

    // Clear pending changes
    this.pendingChanges = {};
  },

  // Prevent LiveView from automatically reverting control values
  disconnected() {
    // Clear any pending timers to prevent issues
    if (this.updateTimer) {
      clearTimeout(this.updateTimer);
      this.updateTimer = null;
    }

    // Clear pending changes
    this.pendingChanges = {};

    // Reset initialization flag
    this.controlsInitialized = false;

    // Optional: backup values only if we were actively using controls
    const controls = document.querySelectorAll(".responsive-control");
    if (controls.length > 0) {
      this.backupValues = {};
      controls.forEach((control) => {
        if (control.type === "checkbox") {
          this.backupValues[control.id] = control.checked;
        } else {
          this.backupValues[control.id] = control.value;
        }
      });
    }
  },

  reconnected() {
    // Reset state
    this.pendingChanges = {};
    this.lastSentValues = {};
    this.controlsInitialized = false;

    // Restore backed up values if available and setup controls
    if (this.backupValues) {
      setTimeout(() => {
        const controls = document.querySelectorAll(".responsive-control");
        const params = {};

        controls.forEach((control) => {
          const savedValue = this.backupValues[control.id];
          if (savedValue !== undefined) {
            if (control.type === "checkbox") {
              control.checked = savedValue;
            } else {
              control.value = savedValue;
            }

            // Update display values
            const displayEl = document.getElementById(`display-${control.id}`);
            if (displayEl) {
              displayEl.textContent = savedValue;
            }

            // Prepare for batch update
            const paramType = control.getAttribute("data-param-type");
            if (paramType === "integer") {
              params[control.id] = parseInt(savedValue, 10);
            } else if (paramType === "float") {
              params[control.id] = parseFloat(savedValue);
            } else if (paramType === "boolean") {
              params[control.id] = Boolean(savedValue);
            } else {
              params[control.id] = savedValue;
            }
          }
        });

        // Send restored values as a single batch
        if (Object.keys(params).length > 0) {
          this.pushEvent("batch-param-update", { params });
          // Update tracking
          Object.assign(this.lastSentValues, params);
        }

        // Setup controls after restoration
        this.setupControls();
      }, 100);
    } else {
      // Just setup controls if no backup values
      setTimeout(() => {
        this.setupControls();
      }, 50);
    }
  },
};

export default GridControlHook;
