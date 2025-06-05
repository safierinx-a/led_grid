// If you want to use Phoenix channels, run `mix help phx.gen.channel`
// to get started and then uncomment the line below.
// import "./user_socket.js"

// You can include dependencies in two ways.
//
// The simplest option is to put them in assets/vendor and
// import them using relative paths:
//
//     import "../vendor/some-package.js"
//
// Alternatively, you can `npm install some-package --prefix assets` and import
// them using a path starting with the package name:
//
//     import "some-package"
//

// Include phoenix_html to handle method=PUT/DELETE in forms and buttons.
import "phoenix_html";
// Establish Phoenix Socket and LiveView configuration.
import { Socket } from "phoenix";
import { LiveSocket } from "phoenix_live_view";
import topbar from "../vendor/topbar";

// Import our high-performance LED canvas
import { LEDCanvas } from "./led_canvas.js";

// Import hooks
import GridControlHook from "./hooks/grid_control_hook.js";

let csrfToken = document
  .querySelector("meta[name='csrf-token']")
  .getAttribute("content");

// Initialize LED Canvas system
let ledCanvas = null;
let displayChannel = null;
let userSocket = null;

// Setup separate socket for display channel (high-performance frame streaming)
function setupDisplaySocket() {
  userSocket = new Socket("/socket", { params: { token: window.userToken } });
  userSocket.connect();

  displayChannel = userSocket.channel("display:grid", {});

  displayChannel
    .join()
    .receive("ok", (resp) => {
      console.log("✅ Joined display channel successfully", resp);
    })
    .receive("error", (resp) => {
      console.log("❌ Unable to join display channel", resp);
    });

  // Handle frame updates from server
  displayChannel.on("frame_update", (data) => {
    if (ledCanvas && data.pixels) {
      // Convert flat array back to RGB tuples
      const pixels = [];
      for (let i = 0; i < data.pixels.length; i += 3) {
        pixels.push([data.pixels[i], data.pixels[i + 1], data.pixels[i + 2]]);
      }
      ledCanvas.updateFrame(pixels);
    }
  });

  // Handle pattern changes
  displayChannel.on("pattern_changed", (data) => {
    console.log("🔄 Pattern changed to:", data.pattern_id);
    // Could add visual feedback here
  });

  displayChannel.on("pattern_active", (data) => {
    console.log("▶️ Active pattern:", data.pattern_id);
  });
}

// Initialize canvas when DOM is ready
document.addEventListener("DOMContentLoaded", () => {
  // Check if we're on a page with LED grid
  const gridContainer = document.getElementById("led-grid-canvas");
  if (gridContainer) {
    // Initialize high-performance canvas
    ledCanvas = new LEDCanvas("led-grid-canvas", 25, 24, 20);
    console.log("🎨 LED Canvas initialized");

    // Setup display socket for frame streaming
    setupDisplaySocket();
  }
});

let Hooks = {
  // Hook for initializing canvas rendering
  LEDGrid: {
    mounted() {
      // Canvas is already initialized above
      console.log("🔌 LED Grid hook mounted");

      // Add render mode toggle
      const container = this.el;
      const toggleBtn = document.createElement("button");
      toggleBtn.className = "render-mode-toggle";
      toggleBtn.textContent = "Canvas Mode";
      toggleBtn.onclick = () => {
        this.pushEvent("toggle-render-mode");
      };
      container.appendChild(toggleBtn);
    },

    updated() {
      // Handle any updates to grid parameters
      console.log("🔄 LED Grid hook updated");
    },
  },

  // Use the dedicated GridControl hook
  GridControl: GridControlHook,

  // Simple parameter controls without competing with GridControl
  ParameterControls: {
    mounted() {
      console.log("ParameterControls mounted - deferring to GridControl");
      // No additional setup to avoid conflicts with GridControl
    },
  },
};

let liveSocket = new LiveSocket("/live", Socket, {
  longPollFallbackMs: 2500,
  params: { _csrf_token: csrfToken },
  hooks: Hooks,
});

// Show progress bar on live navigation and form submits
topbar.config({
  barColors: { 0: "#29d" },
  shadowColor: "rgba(0, 0, 0, .3)",
});
window.addEventListener("phx:page-loading-start", (_info) => topbar.show(300));
window.addEventListener("phx:page-loading-stop", (_info) => topbar.hide());

// Theme toggle functionality
document.addEventListener("DOMContentLoaded", () => {
  const themeToggle = document.getElementById("theme-toggle");
  if (themeToggle) {
    themeToggle.addEventListener("click", () => {
      document.documentElement.classList.toggle("dark");

      const icon = themeToggle.querySelector(".material-icons");
      if (document.documentElement.classList.contains("dark")) {
        icon.textContent = "light_mode";
      } else {
        icon.textContent = "dark_mode";
      }
    });
  }
});

// Connect if there are any LiveViews on the page
liveSocket.connect();

// Expose liveSocket on window for web console debug logs and latency simulation:
// >> liveSocket.enableDebug()
// >> liveSocket.enableLatencySim(1000)  // enabled for duration of browser session
// >> liveSocket.disableLatencySim()
window.liveSocket = liveSocket;
