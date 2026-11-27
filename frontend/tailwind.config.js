import animate from 'tailwindcss-animate'

/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // 表面 / 文字 / 半透明遮罩均由 CSS 变量驱动，随 data-mode 自动反色
        ink: {
          950: 'rgb(var(--ink-950) / <alpha-value>)',
          900: 'rgb(var(--ink-900) / <alpha-value>)',
          800: 'rgb(var(--ink-800) / <alpha-value>)',
          700: 'rgb(var(--ink-700) / <alpha-value>)',
          600: 'rgb(var(--ink-600) / <alpha-value>)',
        },
        mist: {
          100: 'rgb(var(--mist-100) / <alpha-value>)',
          300: 'rgb(var(--mist-300) / <alpha-value>)',
          500: 'rgb(var(--mist-500) / <alpha-value>)',
        },
        // 覆盖内置 white：夜间是白色半透明，白天自动变成墨蓝半透明
        white: 'rgb(var(--tint) / <alpha-value>)',
        // 强调色渐变上的文字（夜间深色字，白天白色字）
        'on-accent': 'rgb(var(--on-accent) / <alpha-value>)',
        // 固定深色，用于彩色渐变上的图标，不随模式翻转
        'icon-ink': '#04120F',
        aurora: {
          // 主题色：由 <html data-accent="..."> 上的 CSS 变量驱动，切换主题即时生效
          teal: 'rgb(var(--accent-1) / <alpha-value>)',
          violet: 'rgb(var(--accent-2) / <alpha-value>)',
          blue: 'rgb(var(--accent-3) / <alpha-value>)',
        },
        hue: {
          // 卡片自身的强调色（与全局主题解耦）
          teal: '#35E0C8',
          violet: '#7C6CFF',
          blue: '#3B82F6',
          amber: '#F5A524',
          rose: '#FF5C7A',
        },
        state: {
          ok: 'rgb(var(--ok) / <alpha-value>)',
          warn: 'rgb(var(--warn) / <alpha-value>)',
          bad: 'rgb(var(--bad) / <alpha-value>)',
        },
      },
      fontFamily: {
        sans: ['"Noto Sans SC"', 'Inter', 'system-ui', 'sans-serif'],
        // 等宽字体后补充中文字体，保证终端 / 日志中的中文输出不出现方框
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', '"Noto Sans SC"', 'monospace'],
      },
      boxShadow: {
        glass: '0 24px 60px -32px rgba(0, 0, 0, 0.9), inset 0 1px 0 rgba(255, 255, 255, 0.06)',
        'glow-teal': '0 0 32px -8px rgb(var(--accent-1) / 0.45)',
        'glow-violet': '0 0 32px -8px rgb(var(--accent-2) / 0.45)',
      },
      keyframes: {
        breathe: {
          '0%, 100%': { opacity: '1', transform: 'scale(1)' },
          '50%': { opacity: '0.45', transform: 'scale(0.86)' },
        },
        drift: {
          '0%, 100%': { transform: 'translate3d(0, 0, 0) scale(1)' },
          '50%': { transform: 'translate3d(4%, -3%, 0) scale(1.08)' },
        },
        'fade-up': {
          from: { opacity: '0', transform: 'translateY(10px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        pulseRing: {
          '0%': { boxShadow: '0 0 0 0 rgba(47, 191, 113, 0.5)' },
          '70%': { boxShadow: '0 0 0 8px rgba(47, 191, 113, 0)' },
          '100%': { boxShadow: '0 0 0 0 rgba(47, 191, 113, 0)' },
        },
      },
      animation: {
        breathe: 'breathe 2.4s ease-in-out infinite',
        drift: 'drift 22s ease-in-out infinite',
        'fade-up': 'fade-up 0.5s ease-out both',
        'pulse-ring': 'pulseRing 2.4s ease-out infinite',
      },
    },
  },
  plugins: [animate],
}
