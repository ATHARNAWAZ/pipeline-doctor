/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // GitHub dark palette -- familiar to engineers
        canvas: {
          default: '#0d1117',
          subtle: '#161b22',
          inset: '#010409',
        },
        border: {
          default: '#30363d',
          muted: '#21262d',
        },
        fg: {
          default: '#e6edf3',
          muted: '#8b949e',
          subtle: '#6e7681',
        },
        accent: {
          fg: '#58a6ff',
        },
        success: {
          fg: '#3fb950',
          emphasis: '#238636',
        },
        danger: {
          fg: '#f85149',
          emphasis: '#da3633',
        },
        attention: {
          fg: '#d29922',
          emphasis: '#9e6a03',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'Cascadia Code', 'monospace'],
      },
    },
  },
  plugins: [],
}
