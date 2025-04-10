/**
 * LiveView JS Hooks for LEGrid
 */

const Hooks = {
  // Update the display value in real-time as the slider changes
  UpdateDisplay: {
    mounted() {
      this.el.addEventListener("input", (e) => {
        const displayId = this.el.getAttribute("data-display-id");
        if (displayId) {
          const displayElement = document.getElementById(displayId);
          if (displayElement) {
            displayElement.textContent = e.target.value;
          }
        }
      });
    },
  },
};

export default Hooks;
