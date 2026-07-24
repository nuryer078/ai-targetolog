import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0a0b0f",
        surface: "#111319",
        accent: { DEFAULT: "#39d98a", soft: "#39d98a22" },
        danger: "#ff6b6b",
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(57,217,138,.15), 0 8px 40px -12px rgba(57,217,138,.25)",
        card: "0 8px 40px -16px rgba(0,0,0,.6)",
      },
      borderRadius: { xl2: "1.25rem" },
    },
  },
  plugins: [],
};
export default config;
