/**
 * LED Grid Dashboard
 * Main application JavaScript
 */

document.addEventListener("DOMContentLoaded", () => {
  // Grid dimensions
  const width = 24;
  const height = 25;

  // Create grid
  const gridContainer = document.getElementById("grid-container");
  const pixels = [];

  for (let y = 0; y < height; y++) {
    pixels[y] = [];
    for (let x = 0; x < width; x++) {
      const pixel = document.createElement("div");
      pixel.className = "pixel";
      pixel.dataset.x = x;
      pixel.dataset.y = y;
      gridContainer.appendChild(pixel);
      pixels[y][x] = pixel;
    }
  }

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
          pixels[y][x].style.backgroundColor = `rgb(${r},${g},${b})`;
        }
      }
    }
  });

  // Handle connection status
  socket.on("connect", () => {
    console.log("Connected to server");
  });

  socket.on("disconnect", () => {
    console.log("Disconnected from server");
  });

  // Load patterns
  fetch("/api/patterns")
    .then((response) => response.json())
    .then((data) => {
      const patternSelect = document.getElementById("pattern-select");
      const patternGallery = document.getElementById("pattern-gallery");

      // Clear loading option
      patternSelect.innerHTML = "";

      // Group patterns by category
      const patternsByCategory = {};
      data.patterns.forEach((pattern) => {
        if (!patternsByCategory[pattern.category]) {
          patternsByCategory[pattern.category] = [];
        }
        patternsByCategory[pattern.category].push(pattern);
      });

      // Add patterns to select dropdown
      Object.keys(patternsByCategory)
        .sort()
        .forEach((category) => {
          const optgroup = document.createElement("optgroup");
          optgroup.label = category.charAt(0).toUpperCase() + category.slice(1);

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
                            <p>${pattern.description}</p>
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
    });

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

    pattern.parameters.forEach((param) => {
      const paramContainer = document.createElement("div");
      paramContainer.className = "parameter";

      const label = document.createElement("label");
      label.textContent =
        param.name.charAt(0).toUpperCase() + param.name.slice(1);
      label.title = param.description;

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
