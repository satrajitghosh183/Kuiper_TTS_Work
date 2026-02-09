/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // StringTune Design System Colors
        background: '#101214',
        surface: '#1A1C1F',
        border: '#2A2C2F',
        accent: {
          DEFAULT: '#FF4F36',
          hover: '#FF6B54',
          active: '#E63E25',
          glow: 'rgba(255, 79, 54, 0.15)',
        },
        text: {
          primary: '#FFFFFF',
          secondary: '#A0A0A0',
          muted: '#606060',
        },
      },
      fontFamily: {
        sans: ['Inter', 'SF Pro Display', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'SF Mono', 'Fira Code', 'monospace'],
      },
      fontSize: {
        'display': ['clamp(36px, 5vw, 72px)', { lineHeight: '1.1', letterSpacing: '-0.02em', fontWeight: '700' }],
        'h1': ['clamp(28px, 4vw, 48px)', { lineHeight: '1.2', letterSpacing: '-0.015em', fontWeight: '600' }],
        'h2': ['clamp(20px, 3vw, 32px)', { lineHeight: '1.25', letterSpacing: '-0.01em', fontWeight: '600' }],
        'h3': ['clamp(18px, 2.5vw, 24px)', { lineHeight: '1.3', letterSpacing: '-0.005em', fontWeight: '500' }],
        'body-lg': ['clamp(16px, 1.5vw, 18px)', { lineHeight: '1.5', letterSpacing: '0', fontWeight: '400' }],
        'body': ['clamp(14px, 1.2vw, 15px)', { lineHeight: '1.6', letterSpacing: '0', fontWeight: '400' }],
        'caption': ['clamp(12px, 1vw, 13px)', { lineHeight: '1.5', letterSpacing: '0.005em', fontWeight: '400' }],
        'micro': ['clamp(10px, 0.8vw, 11px)', { lineHeight: '1.4', letterSpacing: '0.01em', fontWeight: '500' }],
      },
      spacing: {
        'xs': 'clamp(4px, 0.5vw, 8px)',
        'sm': 'clamp(8px, 1vw, 16px)',
        'md': 'clamp(12px, 1.5vw, 24px)',
        'lg': 'clamp(16px, 2vw, 32px)',
        'xl': 'clamp(24px, 3vw, 48px)',
        '2xl': 'clamp(32px, 4vw, 64px)',
        '3xl': 'clamp(48px, 6vw, 96px)',
        '4xl': 'clamp(64px, 8vw, 128px)',
      },
      containers: {
        'xs': '20rem',
        'sm': '24rem',
        'md': '28rem',
        'lg': '32rem',
        'xl': '36rem',
        '2xl': '42rem',
        '3xl': '48rem',
        '4xl': '56rem',
        '5xl': '64rem',
        '6xl': '72rem',
        '7xl': '80rem',
      },
      borderRadius: {
        DEFAULT: '8px',
        'lg': '12px',
        'xl': '16px',
      },
      boxShadow: {
        'card': '0 4px 24px rgba(0, 0, 0, 0.4)',
        'card-hover': '0 8px 32px rgba(0, 0, 0, 0.5)',
        'glow': '0 0 0 3px rgba(255, 79, 54, 0.15)',
      },
      backdropBlur: {
        'modal': '8px',
      },
      transitionTimingFunction: {
        'default': 'cubic-bezier(0.25, 0.1, 0.25, 1)',
        'entrance': 'cubic-bezier(0, 0, 0.2, 1)',
        'exit': 'cubic-bezier(0.4, 0, 1, 1)',
        'bounce': 'cubic-bezier(0.34, 1.56, 0.64, 1)',
      },
      transitionDuration: {
        'micro': '100ms',
        'fast': '150ms',
        'standard': '200ms',
        'slow': '300ms',
        'complex': '400ms',
      },
      animation: {
        'fade-in': 'fadeIn 200ms ease-out',
        'fade-out': 'fadeOut 150ms ease-in',
        'scale-in': 'scaleIn 200ms ease-out',
        'slide-up': 'slideUp 300ms ease-out',
        'pulse-subtle': 'pulseSubtle 2s infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        fadeOut: {
          '0%': { opacity: '1' },
          '100%': { opacity: '0' },
        },
        scaleIn: {
          '0%': { opacity: '0', transform: 'scale(0.95)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(20px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        pulseSubtle: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.8' },
        },
      },
    },
  },
  plugins: [],
}

