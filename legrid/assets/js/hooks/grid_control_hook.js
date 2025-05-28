const GridControlHook = {
  mounted() {
    // Parameter tracking
    this.pendingChanges = {};
    this.updateTimer = null;
    this.updateDelay = 30; // ms delay between batched updates
    this.throttleTimer = null;
    this.throttleDelay = 100; // ms delay for limiting rapid changes
    this.parameterHasChanged = false;
    this.currentPatternId = null;

    // Locks to prevent parameter reverts
    this.controlLocks = new Map(); // Map of control IDs to timestamp locks
    this.lockDuration = 1500; // Lock duration in ms

    // Set up all UI controls
    this.setupControls();

    // Set up pixel hover effects
    this.setupPixelEffects();

    // Set up mutation observer to detect DOM changes in parameters section
    this.setupMutationObserver();

    // Listen for pattern changes
    this.handleEvent("pattern_changed", ({ pattern_id }) => {
      console.log("Pattern changed to:", pattern_id);
      this.currentPatternId = pattern_id;

      // Clear all locks when pattern changes
      this.controlLocks.clear();

      // Wait for DOM to update with new controls
      setTimeout(() => {
        this.setupControls();
      }, 50);
    });

    // Listen for parameter changes from other users/tabs
    this.handleEvent("parameter_update", ({ key, value }) => {
      const control = document.getElementById(key);
      if (control) {
        // Only update if not locked (not recently changed by user)
        if (!this.isControlLocked(key)) {
          if (control.type === "checkbox") {
            control.checked = value;
          } else {
            control.value = value;
          }
          // Update display value
          const displayEl = document.getElementById(`display-${key}`);
          if (displayEl) {
            displayEl.textContent = value;
          }
        }
      }
    });
  },

  updated() {
    // This is called when the LiveView updates the element

    // Check if we have backup values - these take precedence over server values
    // Only restore values for controls that were updated externally (not by user)
    if (this.backupValues) {
      setTimeout(() => {
        const controls = document.querySelectorAll(".responsive-control");
        controls.forEach((control) => {
          const savedValue = this.backupValues[control.id];
          // Only update controls that the user has changed
          if (savedValue !== undefined && control._lastValue !== undefined) {
            if (control.type === "checkbox") {
              control.checked = control._lastValue;
            } else {
              control.value = control._lastValue;
            }
            // Update display values too
            const displayEl = document.getElementById(`display-${control.id}`);
            if (displayEl) {
              displayEl.textContent = control._lastValue;
            }
          }
        });
      }, 50);
    }

    // Reinitialize controls
    this.setupControls();
  },

  setupMutationObserver() {
    // Create a mutation observer to detect when parameters are added/removed
    const parameterContainer = document.getElementById("parameter-controls");
    if (!parameterContainer) return;

    const observer = new MutationObserver((mutations) => {
      // If parameters have changed, reinitialize controls
      this.setupControls();
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

    // Handle parameter changes from any control
    controls.forEach((control) => {
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
        // Handle checkbox changes
        control.addEventListener("change", () => {
          this.handleControlChange(control);
          this.flushChanges();
        });
      } else if (control.type === "select-one") {
        // Handle dropdown changes
        control.addEventListener("change", () => {
          this.handleControlChange(control);
          this.flushChanges();
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

  // Check if a control is locked (recently changed by user)
  isControlLocked(controlId) {
    if (!this.controlLocks.has(controlId)) {
      return false;
    }

    const lockTime = this.controlLocks.get(controlId);
    const now = Date.now();

    // If lock has expired, remove it and return false
    if (now - lockTime > this.lockDuration) {
      this.controlLocks.delete(controlId);
      return false;
    }

    return true;
  },

  // Lock a control to prevent server updates from overriding it
  lockControl(controlId) {
    this.controlLocks.set(controlId, Date.now());
  },

  handleControlChange(control) {
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

    // Lock this control to prevent server updates from overriding it
    this.lockControl(key);

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

    // Convert to appropriate type based on data attribute
    const paramType = control.getAttribute("data-param-type");
    if (paramType === "integer") {
      value = parseInt(value, 10);
    } else if (paramType === "float") {
      value = parseFloat(value);
    } else if (paramType === "boolean") {
      value = Boolean(value);
    }

    // Queue for batched update
    this.pendingChanges[key] = value;
    this.parameterHasChanged = true;

    // Cache the current value to prevent visual reverts
    control._lastValue =
      control.type === "checkbox" ? control.checked : control.value;

    // Handle throttling of updates
    this.scheduleBatchUpdate();
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

    // Throttle repeated rapid changes
    if (!this.throttleTimer) {
      this.throttleTimer = setTimeout(() => {
        // Force an update if any changes are pending
        if (this.parameterHasChanged) {
          this.flushChanges();
        }
        this.throttleTimer = null;
      }, this.throttleDelay);
    }
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

    // Send the batch update to the server
    this.pushEvent("batch-param-update", { params: this.pendingChanges });

    // Clear pending changes
    this.pendingChanges = {};
    this.parameterHasChanged = false;
  },

  // Prevent LiveView from automatically reverting control values
  disconnected() {
    // Backup all current parameter values so we can restore them when reconnected
    this.backupValues = {};
    const controls = document.querySelectorAll(".responsive-control");
    controls.forEach((control) => {
      if (control.type === "checkbox") {
        this.backupValues[control.id] = control.checked;
      } else {
        this.backupValues[control.id] = control.value;
      }
    });
  },

  reconnected() {
    // Restore backed up values on reconnection
    if (this.backupValues) {
      setTimeout(() => {
        const controls = document.querySelectorAll(".responsive-control");
        controls.forEach((control) => {
          const savedValue = this.backupValues[control.id];
          if (savedValue !== undefined) {
            if (control.type === "checkbox") {
              control.checked = savedValue;
            } else {
              control.value = savedValue;
            }
            // Update display values too
            const displayEl = document.getElementById(`display-${control.id}`);
            if (displayEl) {
              displayEl.textContent = savedValue;
            }
          }
        });

        // Send all values as a batch update
        const params = {};
        Object.entries(this.backupValues).forEach(([key, value]) => {
          const control = document.getElementById(key);
          if (control) {
            const paramType = control.getAttribute("data-param-type");
            if (paramType === "integer") {
              params[key] = parseInt(value, 10);
            } else if (paramType === "float") {
              params[key] = parseFloat(value);
            } else if (paramType === "boolean") {
              params[key] = Boolean(value);
            } else {
              params[key] = value;
            }
          }
        });

        if (Object.keys(params).length > 0) {
          this.pushEvent("batch-param-update", { params });
        }
      }, 200);
    }
  },
};

export default GridControlHook;
