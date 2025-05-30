// See the Tailwind configuration guide for advanced usage
// https://tailwindcss.com/docs/configuration

const plugin = require("tailwindcss/plugin");
const fs = require("fs");
const path = require("path");

// Check if @tailwindcss/forms is installed
let hasFormsPlugin = false;
try {
  require.resolve("@tailwindcss/forms");
  hasFormsPlugin = true;
} catch (error) {
  console.warn("@tailwindcss/forms plugin not found, skipping");
}

module.exports = {
  content: [
    "./js/**/*.js",
    "../lib/legrid_web.ex",
    "../lib/legrid_web/**/*.*ex",
  ],
  theme: {
    extend: {
      colors: {
        brand: "#FD4F00",
      },
    },
  },
  plugins: [
    // Only use forms plugin if it's available
    ...(hasFormsPlugin ? [require("@tailwindcss/forms")] : []),
    // Allows prefixing tailwind classes with LiveView classes to add rules
    // only when LiveView classes are applied, for example:
    //
    //     <div class="phx-click-loading:animate-ping">
    //
    plugin(({ addVariant }) =>
      addVariant("phx-click-loading", [
        ".phx-click-loading&",
        ".phx-click-loading &",
      ])
    ),
    plugin(({ addVariant }) =>
      addVariant("phx-submit-loading", [
        ".phx-submit-loading&",
        ".phx-submit-loading &",
      ])
    ),
    plugin(({ addVariant }) =>
      addVariant("phx-change-loading", [
        ".phx-change-loading&",
        ".phx-change-loading &",
      ])
    ),

    // Embeds Heroicons (https://heroicons.com) into your app.css bundle
    // See your `CoreComponents.icon/1` for more information.
    //
    plugin(function ({ matchComponents, theme }) {
      let iconsDir = path.join(__dirname, "../deps/heroicons/optimized");
      let values = {};

      // Only proceed if the heroicons directory exists
      if (fs.existsSync(iconsDir)) {
        let icons = [
          ["", "/24/outline"],
          ["-solid", "/24/solid"],
          ["-mini", "/20/solid"],
          ["-micro", "/16/solid"],
        ];
        icons.forEach(([suffix, dir]) => {
          const fullDir = path.join(iconsDir, dir);
          if (fs.existsSync(fullDir)) {
            fs.readdirSync(fullDir).forEach((file) => {
              let name = path.basename(file, ".svg") + suffix;
              values[name] = { name, fullPath: path.join(fullDir, file) };
            });
          }
        });
      }

      matchComponents(
        {
          hero: ({ name, fullPath }) => {
            // Skip if the path doesn't exist
            if (!fullPath || !fs.existsSync(fullPath)) {
              return {};
            }

            let content = fs
              .readFileSync(fullPath)
              .toString()
              .replace(/\r?\n|\r/g, "");
            let size = theme("spacing.6");
            if (name.endsWith("-mini")) {
              size = theme("spacing.5");
            } else if (name.endsWith("-micro")) {
              size = theme("spacing.4");
            }
            return {
              [`--hero-${name}`]: `url('data:image/svg+xml;utf8,${content}')`,
              "-webkit-mask": `var(--hero-${name})`,
              mask: `var(--hero-${name})`,
              "mask-repeat": "no-repeat",
              "background-color": "currentColor",
              "vertical-align": "middle",
              display: "inline-block",
              width: size,
              height: size,
            };
          },
        },
        { values }
      );
    }),
  ],
};
