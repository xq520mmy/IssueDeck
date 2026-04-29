module.exports = {
  darkMode: "class",
  content: [
    "./src/issuedeck/features/dashboard/templates/**/*.html",
    "./src/issuedeck/features/dashboard/**/*.py",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Source Sans 3"', '"Segoe UI"', "sans-serif"],
        display: ['"General Sans"', '"Segoe UI"', "sans-serif"],
        mono: ['"IBM Plex Mono"', '"JetBrains Mono"', "monospace"],
        code: ['"JetBrains Mono"', '"IBM Plex Mono"', "monospace"],
      },
      colors: {
        primary: {
          50: "#ecfdf5",
          100: "#ccfbf1",
          200: "#99f6e4",
          300: "#5eead4",
          400: "#2dd4bf",
          500: "#14b8a6",
          600: "#0f766e",
          700: "#0b4f4a",
          800: "#134e4a",
          900: "#0f3b37",
          950: "#071110",
        },
        ledger: {
          bg: "#f7f7f2",
          surface: "#ffffff",
          surfaceAlt: "#fbfcf8",
          ink: "#161a1d",
          inkSoft: "#394046",
          muted: "#687076",
          line: "#d8ded8",
          lineStrong: "#aeb8af",
          darkBg: "#0c0f0e",
          darkPanel: "#141817",
          darkPanelAlt: "#101412",
          darkLine: "#27302d",
          darkLineStrong: "#3b4943",
        },
        ship: {
          50: "#fff7ed",
          100: "#ffedd5",
          500: "#f59e0b",
          600: "#b45309",
          700: "#92400e",
        },
        surface: {
          light: "#ffffff",
          dark: "#141817",
        },
        muted: {
          light: "#fbfcf8",
          dark: "#101412",
        },
      },
    },
  },
};
