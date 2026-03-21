import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        genesis: {
          50: "#f0f4ff",
          100: "#dbe4ff",
          500: "#4f6ef7",
          600: "#3b5bdb",
          700: "#2b4acb",
          900: "#1a2e6e",
        },
      },
    },
  },
  plugins: [],
};
export default config;
