import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "#0B1120",
        foreground: "#E5F1FF",
        card: "rgba(15, 23, 42, 0.66)",
        border: "rgba(148, 163, 184, 0.18)",
        cyan: {
          glow: "#22D3EE"
        },
        electric: "#38BDF8",
        violet: "#8B5CF6",
        alert: "#FB3B64"
      },
      boxShadow: {
        glow: "0 0 38px rgba(34, 211, 238, 0.18)",
        alert: "0 0 36px rgba(251, 59, 100, 0.18)"
      },
      backgroundImage: {
        "radial-grid": "radial-gradient(circle at top left, rgba(34, 211, 238, 0.2), transparent 32%), radial-gradient(circle at 80% 20%, rgba(139, 92, 246, 0.22), transparent 28%), linear-gradient(135deg, #0B1120 0%, #111827 48%, #090E1B 100%)"
      },
      keyframes: {
        scan: {
          "0%": { transform: "translateY(-120%)" },
          "100%": { transform: "translateY(120%)" }
        },
        pulseGlow: {
          "0%, 100%": { opacity: "0.45" },
          "50%": { opacity: "1" }
        }
      },
      animation: {
        scan: "scan 2.8s ease-in-out infinite",
        pulseGlow: "pulseGlow 2.2s ease-in-out infinite"
      }
    }
  },
  plugins: []
};

export default config;
