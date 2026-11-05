/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'media',
  theme: {
    extend: {
      colors: {
        // Restrained teal brand. Amber/green/red are reserved for clearance decisions.
        brand: {
          50: '#f0fdfa', 100: '#ccfbf1', 200: '#99f6e4', 300: '#5eead4', 400: '#2dd4bf',
          500: '#14b8a6', 600: '#0d9488', 700: '#0f766e', 800: '#115e59', 900: '#134e4a',
        },
        // Deep navy "ink" for the shell (sidebar / top bar) and dark surfaces.
        ink: {
          50: '#f5f7fa', 100: '#e9edf3', 200: '#d3dae5', 300: '#aab6c8', 400: '#7686a0', 500: '#4f607d',
          600: '#3a4862', 700: '#28344a', 800: '#1a2335', 900: '#111827', 950: '#0b1220',
        },
        surface: { 50: '#f7f8fa', 100: '#f1f3f6', 200: '#e6e9ee' },
        decision: { green: '#16a34a', amber: '#d97706', red: '#dc2626' },
      },
      fontFamily: { sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'Ubuntu', 'sans-serif'] },
      boxShadow: {
        card: '0 1px 2px rgba(16, 24, 40, 0.04), 0 1px 3px rgba(16, 24, 40, 0.06)',
        pop: '0 10px 30px -10px rgba(16, 24, 40, 0.25)',
      },
      borderRadius: { xl: '14px', '2xl': '16px' },
      keyframes: { shimmer: { '0%': { backgroundPosition: '-400px 0' }, '100%': { backgroundPosition: '400px 0' } } },
      animation: { shimmer: 'shimmer 1.4s linear infinite' },
    },
  },
  plugins: [],
};
