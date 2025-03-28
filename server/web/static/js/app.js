/**
 * LED Grid Dashboard
 * Main application JavaScript
 */

document.addEventListener("DOMContentLoaded", () => {
  // Grid dimensions (will be configurable)
  let width = 24;
  let height = 25;
  let pixelSize = 15; // Default pixel size in px
  let pixelGap = 1; // Default gap between pixels in px
  let ledStripMode = false; // LED strip mode toggle

  // Hardware state
  let powerState = true;
  let brightnessValue = 1.0;

  // Create grid
  const gridContainer = document.getElementById("grid-container");
  let pixels = [];

  function createGrid() {
    // Clear existing grid
    gridContainer.innerHTML = "";
    pixels = [];

    if (ledStripMode) {
      // In LED strip mode, we create a single row with many columns
      // This simulates a 60 pixel/meter WS2812B LED strip
      width = 60; // 60 pixels per meter
      height = 1; // Single row
      pixelSize = 10; // Smaller pixels
      pixelGap = 2; // Slightly larger gap

      // Add LED strip mode class to grid container
      gridContainer.classList.add("led-strip-mode");
    } else {
      // Remove LED strip mode class if not in LED strip mode
      gridContainer.classList.remove("led-strip-mode");
    }

    // Update grid container style
    gridContainer.style.gridTemplateColumns = `repeat(${width}, ${pixelSize}px)`;
    gridContainer.style.gridTemplateRows = `repeat(${height}, ${pixelSize}px)`;
    gridContainer.style.gap = `${pixelGap}px`;

    // Create new grid
    for (let y = 0; y < height; y++) {
      pixels[y] = [];
      for (let x = 0; x < width; x++) {
        const pixel = document.createElement("div");
        pixel.className = "pixel";
        pixel.dataset.x = x;
        pixel.dataset.y = y;
        pixel.style.width = `${pixelSize}px`;
        pixel.style.height = `${pixelSize}px`;
        gridContainer.appendChild(pixel);
        pixels[y][x] = pixel;
      }
    }

    // Update input fields to match current grid configuration
    document.getElementById("grid-width").value = width;
    document.getElementById("grid-height").value = height;
    document.getElementById("pixel-size").value = pixelSize;
    document.getElementById("pixel-gap").value = pixelGap;
  }

  // Initialize grid
  createGrid();

  // Connect to WebSocket
  const socket = io();

  // Handle frame updates
  socket.on("frame_update", (data) => {
    // Update grid
    const grid = data.grid;
    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        if (grid[y] && grid[y][x]) {
          const [r, g, b] = grid[y][x];
          // Apply brightness to the displayed colors
          const adjustedR = Math.floor(r * brightnessValue);
          const adjustedG = Math.floor(g * brightnessValue);
          const adjustedB = Math.floor(b * brightnessValue);

          // Only show pixels if power is on
          if (powerState) {
            if (pixels[y] && pixels[y][x]) {
              pixels[y][
                x
              ].style.backgroundColor = `rgb(${adjustedR},${adjustedG},${adjustedB})`;
            }
          } else {
            if (pixels[y] && pixels[y][x]) {
              pixels[y][x].style.backgroundColor = "#000";
            }
          }
        }
      }
    }
  });

  // Handle connection status
  socket.on("connect", () => {
    console.log("Connected to server");
    // Load current status when connected
    loadStatus();

    // Load patterns after connection with a small delay to ensure server is ready
    console.log("Waiting a moment for server initialization...");
    setTimeout(() => {
      loadPatterns();
    }, 1500); // Wait 1.5 seconds before first pattern load
  });

  socket.on("disconnect", () => {
    console.log("Disconnected from server");
  });

  // Load hardware status
  function loadStatus() {
    fetch("/api/status")
      .then((response) => response.json())
      .then((data) => {
        // Update power toggle
        powerState = data.power;
        document.getElementById("power-toggle").checked = powerState;

        // Update brightness slider
        brightnessValue = data.brightness;
        const brightnessSlider = document.getElementById("brightness-slider");
        brightnessSlider.value = brightnessValue;
        document.querySelector(".brightness-value").textContent = `${Math.round(
          brightnessValue * 100
        )}%`;
      })
      .catch((error) => {
        console.error("Error loading status:", error);
      });
  }

  // Power toggle handler
  const powerToggle = document.getElementById("power-toggle");
  powerToggle.addEventListener("change", () => {
    powerState = powerToggle.checked;

    fetch("/api/power", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        state: powerState,
      }),
    })
      .then((response) => response.json())
      .then((data) => {
        console.log("Power set:", data);
      })
      .catch((error) => {
        console.error("Error setting power:", error);
        // Revert UI if there was an error
        powerToggle.checked = !powerState;
        powerState = !powerState;
      });
  });

  // Brightness slider handler
  const brightnessSlider = document.getElementById("brightness-slider");
  const brightnessValue_el = document.querySelector(".brightness-value");

  brightnessSlider.addEventListener("input", () => {
    brightnessValue = parseFloat(brightnessSlider.value);
    brightnessValue_el.textContent = `${Math.round(brightnessValue * 100)}%`;
  });

  brightnessSlider.addEventListener("change", () => {
    fetch("/api/brightness", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        value: brightnessValue,
      }),
    })
      .then((response) => response.json())
      .then((data) => {
        console.log("Brightness set:", data);
      })
      .catch((error) => {
        console.error("Error setting brightness:", error);
      });
  });

  // LED Strip Mode toggle handler
  const ledStripToggle = document.getElementById("led-strip-mode");
  ledStripToggle.addEventListener("change", () => {
    ledStripMode = ledStripToggle.checked;
    createGrid(); // Recreate grid with new settings
  });

  // Grid configuration apply button handler
  document.getElementById("apply-grid-config").addEventListener("click", () => {
    // Get grid dimensions and visual settings
    const width = parseInt(document.getElementById("grid-width").value);
    const height = parseInt(document.getElementById("grid-height").value);
    const pixelSize = parseInt(document.getElementById("pixel-size").value);

    // Get grid orientation settings
    const startCorner = document.getElementById("start-corner").value;
    const firstRowDirection = document.getElementById(
      "first-row-direction"
    ).value;
    const rowProgression = document.getElementById("row-progression").value;
    const serpentine = document.getElementById("serpentine").checked;

    // Validate values
    const validWidth = Math.max(1, Math.min(100, width));
    const validHeight = Math.max(1, Math.min(100, height));
    const validPixelSize = Math.max(1, Math.min(50, pixelSize));

    // Update local variables for the grid preview
    if (
      width !== validWidth ||
      height !== validHeight ||
      pixelSize !== validPixelSize
    ) {
      showNotification("Invalid values corrected to valid range", "warning");
    }

    // Set the grid dimensions for the preview
    window.gridWidth = validWidth;
    window.gridHeight = validHeight;
    window.pixelSize = validPixelSize;

    // Send configuration to server
    fetch("/api/grid_config", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        width: validWidth,
        height: validHeight,
        start_corner: startCorner,
        first_row_direction: firstRowDirection,
        row_progression: rowProgression,
        serpentine: serpentine,
      }),
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          showNotification(
            "Grid configuration updated successfully",
            "success"
          );
          // Update grid preview
          createGrid();
        } else {
          showNotification(
            `Failed to update configuration: ${data.error}`,
            "error"
          );
        }
      })
      .catch((error) => {
        console.error("Error updating grid configuration:", error);
        showNotification("Failed to update grid configuration", "error");
      });
  });

  // Save grid configuration as default
  document.getElementById("save-grid-config").addEventListener("click", () => {
    // Get current values from UI
    const width = parseInt(document.getElementById("grid-width").value);
    const height = parseInt(document.getElementById("grid-height").value);
    const startCorner = document.getElementById("start-corner").value;
    const firstRowDirection = document.getElementById(
      "first-row-direction"
    ).value;
    const rowProgression = document.getElementById("row-progression").value;
    const serpentine = document.getElementById("serpentine").checked;

    // Validate values
    const validWidth = Math.max(1, Math.min(100, width));
    const validHeight = Math.max(1, Math.min(100, height));

    // Save as default configuration
    fetch("/api/grid_config/save_default", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        width: validWidth,
        height: validHeight,
        start_corner: startCorner,
        first_row_direction: firstRowDirection,
        row_progression: rowProgression,
        serpentine: serpentine,
      }),
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          showNotification("Grid configuration saved as default", "success");
        } else {
          showNotification(
            `Failed to save configuration: ${data.error}`,
            "error"
          );
        }
      })
      .catch((error) => {
        console.error("Error saving grid configuration:", error);
        showNotification("Failed to save grid configuration", "error");
      });
  });

  // Function to load grid configuration from server
  function loadGridConfig() {
    fetch("/api/grid_config")
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          const config = data.config;

          // Update form values
          document.getElementById("grid-width").value = config.width;
          document.getElementById("grid-height").value = config.height;

          // Set start corner
          const cornerRow = config.start_corner[0];
          const cornerCol = config.start_corner[1];
          const isBottom = cornerRow >= config.height / 2;
          const isRight = cornerCol >= config.width / 2;
          const cornerValue = `${isBottom ? "bottom" : "top"}-${
            isRight ? "right" : "left"
          }`;
          document.getElementById("start-corner").value = cornerValue;

          // Set other orientation parameters
          document.getElementById("first-row-direction").value =
            config.first_row_direction;
          document.getElementById("row-progression").value =
            config.row_progression;
          document.getElementById("serpentine").checked = config.serpentine;

          // Update local variables
          window.gridWidth = config.width;
          window.gridHeight = config.height;

          // Update grid preview
          createGrid();
        } else {
          showNotification(
            `Failed to load grid configuration: ${data.error}`,
            "error"
          );
        }
      })
      .catch((error) => {
        console.error("Error loading grid configuration:", error);
        showNotification("Failed to load grid configuration", "error");
      });
  }

  // Load grid configuration when page loads
  loadGridConfig();

  // Function to load patterns
  function loadPatterns() {
    console.log("Loading patterns...");

    fetch("/api/patterns")
      .then((response) => {
        if (!response.ok) {
          throw new Error(`HTTP error! Status: ${response.status}`);
        }
        return response.json();
      })
      .then((data) => {
        console.log("Patterns loaded:", data);

        if (!data || !data.patterns || !Array.isArray(data.patterns)) {
          console.error("Invalid pattern data received:", data);
          return;
        }

        const patternSelect = document.getElementById("pattern-select");
        const patternGallery = document.getElementById("pattern-gallery");

        // Clear existing content
        patternSelect.innerHTML = "";
        patternGallery.innerHTML = "";

        if (data.patterns.length === 0) {
          console.warn("No patterns available, triggering reload_patterns...");

          // Show loading message
          patternSelect.innerHTML =
            "<option value=''>Loading patterns...</option>";
          patternGallery.innerHTML = "<p>Loading patterns, please wait...</p>";

          // Automatically trigger pattern reload
          return fetch("/api/reload_patterns", {
            method: "POST",
          })
            .then((response) => response.json())
            .then((reloadData) => {
              console.log("Patterns reloaded:", reloadData);
              // Wait a bit and try loading patterns again
              setTimeout(() => {
                loadPatterns();
              }, 1000); // Wait 1 second before trying again
            })
            .catch((error) => {
              console.error("Error reloading patterns:", error);
              patternSelect.innerHTML =
                "<option value=''>Error loading patterns</option>";
              patternGallery.innerHTML = `
                <div class="error-message">
                  <p>Error loading patterns: ${error.message}</p>
                  <button id="retry-patterns" class="preset-button">Retry</button>
                </div>
              `;
              document
                .getElementById("retry-patterns")
                ?.addEventListener("click", loadPatterns);
            });
        }

        // Group patterns by category
        const patternsByCategory = {};
        data.patterns.forEach((pattern) => {
          const category = pattern.category || "Uncategorized";
          if (!patternsByCategory[category]) {
            patternsByCategory[category] = [];
          }
          patternsByCategory[category].push(pattern);
        });

        // Add patterns to select dropdown
        Object.keys(patternsByCategory)
          .sort()
          .forEach((category) => {
            const optgroup = document.createElement("optgroup");
            optgroup.label =
              category.charAt(0).toUpperCase() + category.slice(1);

            patternsByCategory[category].forEach((pattern) => {
              const option = document.createElement("option");
              option.value = pattern.name;
              option.textContent = pattern.name;
              optgroup.appendChild(option);

              // Create pattern card for gallery
              const card = document.createElement("div");
              card.className = "pattern-card";
              card.innerHTML = `
                <div class="pattern-preview"></div>
                <div class="pattern-info">
                    <h3>${pattern.name}</h3>
                    <p>${pattern.description || "No description available"}</p>
                </div>
              `;
              card.addEventListener("click", () => {
                setPattern(pattern.name);
                patternSelect.value = pattern.name;
                updateParameterControls(pattern);
              });
              patternGallery.appendChild(card);
            });

            patternSelect.appendChild(optgroup);
          });

        // Set current pattern if available
        if (data.current_pattern) {
          patternSelect.value = data.current_pattern;
          const currentPattern = data.patterns.find(
            (p) => p.name === data.current_pattern
          );
          if (currentPattern) {
            updateParameterControls(currentPattern);
          }
        }

        // Show success notification
        showNotification("Patterns loaded successfully", "success");

        // Handle pattern selection change
        patternSelect.addEventListener("change", () => {
          const patternName = patternSelect.value;
          if (patternName) {
            setPattern(patternName);
            const pattern = data.patterns.find((p) => p.name === patternName);
            if (pattern) {
              updateParameterControls(pattern);
            }
          }
        });
      })
      .catch((error) => {
        console.error("Error loading patterns:", error);

        // Show error message in UI
        const patternSelect = document.getElementById("pattern-select");
        const patternGallery = document.getElementById("pattern-gallery");

        patternSelect.innerHTML =
          "<option value=''>Error loading patterns</option>";
        patternGallery.innerHTML = `
          <div class="error-message">
            <p>Error loading patterns. Please check the server connection.</p>
            <button id="retry-patterns" class="preset-button">Retry</button>
          </div>
        `;

        // Add retry button handler
        document
          .getElementById("retry-patterns")
          ?.addEventListener("click", loadPatterns);
      });
  }

  // Initial patterns load
  loadPatterns();

  // Add reload patterns button
  const patternSelector = document.querySelector(".pattern-selector");
  const reloadButton = document.createElement("button");
  reloadButton.className = "preset-button";
  reloadButton.style.marginTop = "8px";
  reloadButton.textContent = "Reload Patterns";
  reloadButton.addEventListener("click", () => {
    // Disable button during reload
    reloadButton.disabled = true;
    reloadButton.textContent = "Reloading...";

    // Call the reload patterns API endpoint
    fetch("/api/reload_patterns", {
      method: "POST",
    })
      .then((response) => {
        if (!response.ok) {
          return response.json().then((data) => {
            throw new Error(
              data.message || `HTTP error! Status: ${response.status}`
            );
          });
        }
        return response.json();
      })
      .then((data) => {
        console.log("Patterns reloaded:", data);

        // Show success message
        const message = `${data.message} (${data.before_count} → ${data.after_count})`;
        showNotification(message, "success");

        // Reload the patterns in the UI
        loadPatterns();
      })
      .catch((error) => {
        console.error("Error reloading patterns:", error);

        // Show error message
        showNotification(`Error: ${error.message}`, "error");

        // Try to reload patterns anyway to show what's available
        loadPatterns();
      })
      .finally(() => {
        // Re-enable button
        reloadButton.disabled = false;
        reloadButton.textContent = "Reload Patterns";
      });
  });
  patternSelector.appendChild(reloadButton);

  // Helper function to show notifications
  function showNotification(message, type = "info") {
    // Create notification element if it doesn't exist
    let notification = document.getElementById("notification");
    if (!notification) {
      notification = document.createElement("div");
      notification.id = "notification";
      document.body.appendChild(notification);

      // Add styles
      notification.style.position = "fixed";
      notification.style.bottom = "20px";
      notification.style.right = "20px";
      notification.style.padding = "10px 20px";
      notification.style.borderRadius = "4px";
      notification.style.color = "#fff";
      notification.style.zIndex = "1000";
      notification.style.transition = "opacity 0.3s ease";
    }

    // Set type-specific styles
    if (type === "success") {
      notification.style.backgroundColor = "rgba(3, 218, 198, 0.9)";
    } else if (type === "error") {
      notification.style.backgroundColor = "rgba(207, 102, 121, 0.9)";
    } else {
      notification.style.backgroundColor = "rgba(187, 134, 252, 0.9)";
    }

    // Set message and show
    notification.textContent = message;
    notification.style.opacity = "1";

    // Hide after 5 seconds
    setTimeout(() => {
      notification.style.opacity = "0";
    }, 5000);
  }

  // Set pattern function
  function setPattern(patternName, params = {}) {
    fetch("/api/patterns/set", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        name: patternName,
        params: params,
      }),
    })
      .then((response) => response.json())
      .then((data) => {
        console.log("Pattern set:", data);
      })
      .catch((error) => {
        console.error("Error setting pattern:", error);
      });
  }

  // Update parameter controls
  function updateParameterControls(pattern) {
    const parametersList = document.getElementById("parameters-list");
    parametersList.innerHTML = "";

    if (!pattern.parameters || pattern.parameters.length === 0) {
      parametersList.innerHTML =
        "<p>No adjustable parameters for this pattern</p>";
      return;
    }

    pattern.parameters.forEach((param) => {
      const paramContainer = document.createElement("div");
      paramContainer.className = "parameter";

      const label = document.createElement("label");
      label.textContent =
        param.name.charAt(0).toUpperCase() + param.name.slice(1);
      label.title = param.description || "";

      let input;

      if (param.type === "float" || param.type === "int") {
        input = document.createElement("input");
        input.type = "range";
        input.min = param.min_value !== null ? param.min_value : 0;
        input.max = param.max_value !== null ? param.max_value : 1;
        input.step = param.type === "float" ? 0.01 : 1;
        input.value = param.default;

        const valueDisplay = document.createElement("span");
        valueDisplay.className = "param-value";
        valueDisplay.textContent = param.default;

        input.addEventListener("input", () => {
          valueDisplay.textContent = input.value;
          updateParameter(param.name, parseFloat(input.value));
        });

        paramContainer.appendChild(label);
        paramContainer.appendChild(input);
        paramContainer.appendChild(valueDisplay);
      } else if (
        param.type === "str" &&
        param.description &&
        param.description.includes("(") &&
        param.description.includes(")")
      ) {
        // Handle enum-like string parameters
        const options = param.description
          .split("(")[1]
          .split(")")[0]
          .split(",")
          .map((opt) => opt.trim());

        input = document.createElement("select");

        options.forEach((option) => {
          const opt = document.createElement("option");
          opt.value = option;
          opt.textContent = option;
          input.appendChild(opt);
        });

        input.value = param.default;

        input.addEventListener("change", () => {
          updateParameter(param.name, input.value);
        });

        paramContainer.appendChild(label);
        paramContainer.appendChild(input);
      } else if (param.type === "bool") {
        input = document.createElement("input");
        input.type = "checkbox";
        input.checked = param.default;

        input.addEventListener("change", () => {
          updateParameter(param.name, input.checked);
        });

        paramContainer.appendChild(label);
        paramContainer.appendChild(input);
      } else {
        // Default to text input for other types
        input = document.createElement("input");
        input.type = "text";
        input.value = param.default;

        input.addEventListener("change", () => {
          updateParameter(param.name, input.value);
        });

        paramContainer.appendChild(label);
        paramContainer.appendChild(input);
      }

      parametersList.appendChild(paramContainer);
    });
  }

  // Update parameter function
  function updateParameter(name, value) {
    fetch("/api/params/update", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        params: {
          [name]: value,
        },
      }),
    })
      .then((response) => response.json())
      .then((data) => {
        console.log("Parameter updated:", data);
      })
      .catch((error) => {
        console.error("Error updating parameter:", error);
      });
  }
});
