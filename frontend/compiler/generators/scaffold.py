"""Scaffold generator — emits static project files that don't depend on IR.

These files form the installable Next.js shell: package.json, tsconfig,
tailwind, eslint, postcss, globals.css, and utility helpers.

Theme tokens (primary/accent colors, neutral palette, font, radius) flow
in from ``ThemeIR`` so each marketplace gets a tailored visual identity.
"""

from __future__ import annotations

from compiler.constants import GENERATOR_VERSION
from compiler.ir import ThemeIR


def emit_scaffold(theme: ThemeIR | None = None) -> dict[str, str]:
    """Return ``{relative_path: file_content}`` for all scaffold files.

    ``theme`` may be ``None`` for tests that don't care about visual tokens;
    when omitted, neutral defaults are used.
    """
    if theme is None:
        theme = ThemeIR(
            primary="#2563eb",
            accent="#4f46e5",
            neutral="neutral",
            font="Inter",
            radius="md",
            logo_emoji="◎",
            voice="",
        )

    files: dict[str, str] = {}
    files["package.json"] = _package_json()
    files["tsconfig.json"] = _tsconfig()
    files["next.config.ts"] = _next_config()
    files["tailwind.config.ts"] = _tailwind_config(theme)
    files["postcss.config.mjs"] = _postcss_config()
    files[".eslintrc.json"] = _eslintrc()
    files["components.json"] = _shadcn_components_json()
    files["src/styles/globals.css"] = _globals_css(theme)
    files["src/lib/utils.ts"] = _utils_ts()
    files["src/lib/motion.tsx"] = _motion_helpers()
    files["src/env.ts"] = _env_ts()
    files["src/middleware.ts"] = _middleware_ts()
    return files


# ── Color / palette helpers ───────────────────────────────────────────


def _hex_to_hsl(hex_color: str) -> str:
    """Convert ``#rrggbb`` (or ``rrggbb``) to the ``H S% L%`` form Tailwind shadcn uses.

    >>> _hex_to_hsl("#2563eb")
    '221 83% 53%'
    """
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return "0 0% 50%"
    r = int(h[0:2], 16) / 255
    g = int(h[2:4], 16) / 255
    b = int(h[4:6], 16) / 255
    cmax, cmin = max(r, g, b), min(r, g, b)
    delta = cmax - cmin
    luminance = (cmax + cmin) / 2
    if delta == 0:
        hue = 0.0
    elif cmax == r:
        hue = 60 * (((g - b) / delta) % 6)
    elif cmax == g:
        hue = 60 * (((b - r) / delta) + 2)
    else:
        hue = 60 * (((r - g) / delta) + 4)
    saturation = 0 if delta == 0 else delta / (1 - abs(2 * luminance - 1))
    return f"{round(hue)} {round(saturation * 100)}% {round(luminance * 100)}%"


def _foreground_hsl_for(hex_color: str) -> str:
    """Return a near-white or near-black HSL based on the color's luminance.

    Light backgrounds get dark text, dark backgrounds get light text.
    """
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return "0 0% 9%"
    r = int(h[0:2], 16) / 255
    g = int(h[2:4], 16) / 255
    b = int(h[4:6], 16) / 255
    luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return "0 0% 98%" if luminance < 0.5 else "0 0% 9%"


_NEUTRAL_PALETTES: dict[str, dict[str, str]] = {
    "warm": {
        "background": "30 40% 99%",
        "foreground": "20 14% 12%",
        "card": "30 40% 100%",
        "card_foreground": "20 14% 12%",
        "popover": "30 40% 100%",
        "popover_foreground": "20 14% 12%",
        "muted": "30 25% 94%",
        "muted_foreground": "30 8% 38%",
        "secondary": "30 25% 94%",
        "secondary_foreground": "20 14% 12%",
        "border": "30 18% 88%",
        "input": "30 18% 88%",
        "sidebar_background": "30 30% 97%",
        "sidebar_foreground": "30 14% 22%",
        "sidebar_accent": "30 25% 92%",
        "sidebar_accent_foreground": "30 14% 22%",
        "sidebar_border": "30 18% 86%",
    },
    "cool": {
        "background": "210 40% 99%",
        "foreground": "222 14% 12%",
        "card": "210 40% 100%",
        "card_foreground": "222 14% 12%",
        "popover": "210 40% 100%",
        "popover_foreground": "222 14% 12%",
        "muted": "210 25% 94%",
        "muted_foreground": "210 8% 38%",
        "secondary": "210 25% 94%",
        "secondary_foreground": "222 14% 12%",
        "border": "210 18% 88%",
        "input": "210 18% 88%",
        "sidebar_background": "210 30% 97%",
        "sidebar_foreground": "210 14% 22%",
        "sidebar_accent": "210 25% 92%",
        "sidebar_accent_foreground": "210 14% 22%",
        "sidebar_border": "210 18% 86%",
    },
    "neutral": {
        "background": "0 0% 100%",
        "foreground": "0 0% 3.9%",
        "card": "0 0% 100%",
        "card_foreground": "0 0% 3.9%",
        "popover": "0 0% 100%",
        "popover_foreground": "0 0% 3.9%",
        "muted": "0 0% 96.1%",
        "muted_foreground": "0 0% 45.1%",
        "secondary": "0 0% 96.1%",
        "secondary_foreground": "0 0% 9%",
        "border": "0 0% 89.8%",
        "input": "0 0% 89.8%",
        "sidebar_background": "0 0% 98%",
        "sidebar_foreground": "240 5.3% 26.1%",
        "sidebar_accent": "240 4.8% 95.9%",
        "sidebar_accent_foreground": "240 5.9% 10%",
        "sidebar_border": "220 13% 91%",
    },
}


_RADIUS_REM: dict[str, str] = {
    "sm": "0.375rem",
    "md": "0.5rem",
    "lg": "0.625rem",
    "xl": "0.875rem",
}


def _resolve_neutral(name: str) -> dict[str, str]:
    return _NEUTRAL_PALETTES.get(name, _NEUTRAL_PALETTES["neutral"])


def _resolve_radius(name: str) -> str:
    return _RADIUS_REM.get(name, _RADIUS_REM["md"])


# ── Individual file generators ────────────────────────────────────────


def _package_json() -> str:
    return """\
{
  "name": "cosolvent-frontend",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint",
    "type-check": "tsc --noEmit"
  },
  "dependencies": {
    "@hookform/resolvers": "^3.9.1",
    "@radix-ui/react-avatar": "^1.1.2",
    "@radix-ui/react-dialog": "^1.1.4",
    "@radix-ui/react-dropdown-menu": "^2.1.4",
    "@radix-ui/react-label": "^2.1.1",
    "@radix-ui/react-select": "^2.1.4",
    "@radix-ui/react-separator": "^1.1.1",
    "@radix-ui/react-slot": "^1.1.1",
    "@radix-ui/react-tabs": "^1.1.2",
    "@radix-ui/react-toast": "^1.2.4",
    "@tanstack/react-query": "^5.62.0",
    "class-variance-authority": "^0.7.1",
    "clsx": "^2.1.1",
    "lucide-react": "^0.468.0",
    "next": "^15.1.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "react-hook-form": "^7.54.0",
    "tailwind-merge": "^2.6.0",
    "tailwindcss-animate": "^1.0.7",
    "zod": "^3.24.0"
  },
  "devDependencies": {
    "@types/node": "^22.0.0",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "autoprefixer": "^10.4.20",
    "eslint": "^9.0.0",
    "eslint-config-next": "^15.1.0",
    "postcss": "^8.4.49",
    "tailwindcss": "^3.4.16",
    "typescript": "^5.7.0"
  },
  "generatedBy": "cosolvent-frontend-compiler",
  "generatorVersion": \"""" + GENERATOR_VERSION + """\"
}
"""


def _tsconfig() -> str:
    return """\
{
  "compilerOptions": {
    "target": "ES2017",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
"""


def _next_config() -> str:
    return """\
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
};

export default nextConfig;
"""


def _tailwind_config(theme: ThemeIR) -> str:
    """Tailwind config — colors driven by CSS variables, font-display from theme."""
    font = theme.font
    return f"""\
import type {{ Config }} from "tailwindcss";
import tailwindAnimate from "tailwindcss-animate";

const config: Config = {{
  darkMode: "class",
  content: ["./src/**/*.{{ts,tsx}}"],
  theme: {{
    extend: {{
      fontFamily: {{
        sans: ["var(--font-display)", "{font}", "ui-sans-serif", "system-ui", "sans-serif"],
        display: ["var(--font-display)", "{font}", "ui-sans-serif", "system-ui", "sans-serif"],
      }},
      colors: {{
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {{
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        }},
        secondary: {{
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        }},
        destructive: {{
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        }},
        muted: {{
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        }},
        accent: {{
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        }},
        popover: {{
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        }},
        card: {{
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        }},
        sidebar: {{
          DEFAULT: "hsl(var(--sidebar-background))",
          foreground: "hsl(var(--sidebar-foreground))",
          primary: "hsl(var(--sidebar-primary))",
          "primary-foreground": "hsl(var(--sidebar-primary-foreground))",
          accent: "hsl(var(--sidebar-accent))",
          "accent-foreground": "hsl(var(--sidebar-accent-foreground))",
          border: "hsl(var(--sidebar-border))",
          ring: "hsl(var(--sidebar-ring))",
        }},
      }},
      borderRadius: {{
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      }},
      keyframes: {{
        "fade-in": {{
          "0%": {{ opacity: "0" }},
          "100%": {{ opacity: "1" }},
        }},
        "fade-in-up": {{
          "0%": {{ opacity: "0", transform: "translateY(8px)" }},
          "100%": {{ opacity: "1", transform: "translateY(0)" }},
        }},
        "fade-in-down": {{
          "0%": {{ opacity: "0", transform: "translateY(-8px)" }},
          "100%": {{ opacity: "1", transform: "translateY(0)" }},
        }},
        "slide-in-right": {{
          "0%": {{ opacity: "0", transform: "translateX(12px)" }},
          "100%": {{ opacity: "1", transform: "translateX(0)" }},
        }},
        "scale-in": {{
          "0%": {{ opacity: "0", transform: "scale(0.97)" }},
          "100%": {{ opacity: "1", transform: "scale(1)" }},
        }},
        "shimmer": {{
          "0%": {{ backgroundPosition: "-200% 0" }},
          "100%": {{ backgroundPosition: "200% 0" }},
        }},
      }},
      animation: {{
        "fade-in": "fade-in 200ms ease-out both",
        "fade-in-up": "fade-in-up 320ms cubic-bezier(0.22, 1, 0.36, 1) both",
        "fade-in-down": "fade-in-down 320ms cubic-bezier(0.22, 1, 0.36, 1) both",
        "slide-in-right": "slide-in-right 280ms cubic-bezier(0.22, 1, 0.36, 1) both",
        "scale-in": "scale-in 220ms cubic-bezier(0.22, 1, 0.36, 1) both",
        "shimmer": "shimmer 1.4s ease-in-out infinite",
      }},
      transitionTimingFunction: {{
        "out-soft": "cubic-bezier(0.22, 1, 0.36, 1)",
      }},
    }},
  }},
  plugins: [tailwindAnimate],
}};

export default config;
"""


def _postcss_config() -> str:
    return """\
const config = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};

export default config;
"""


def _eslintrc() -> str:
    return """\
{
  "extends": "next/core-web-vitals"
}
"""


def _shadcn_components_json() -> str:
    return """\
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "new-york",
  "rsc": true,
  "tsx": true,
  "tailwind": {
    "config": "tailwind.config.ts",
    "css": "src/styles/globals.css",
    "baseColor": "neutral",
    "cssVariables": true
  },
  "aliases": {
    "components": "@/components",
    "utils": "@/lib/utils"
  }
}
"""


def _globals_css(theme: ThemeIR) -> str:
    p = _resolve_neutral(theme.neutral)
    primary = _hex_to_hsl(theme.primary)
    primary_fg = _foreground_hsl_for(theme.primary)
    accent = _hex_to_hsl(theme.accent)
    accent_fg = _foreground_hsl_for(theme.accent)
    radius = _resolve_radius(theme.radius)
    font = theme.font
    return f"""\
/* AUTO-GENERATED by Cosolvent Frontend Compiler */
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {{
  :root {{
    --background: {p["background"]};
    --foreground: {p["foreground"]};
    --card: {p["card"]};
    --card-foreground: {p["card_foreground"]};
    --popover: {p["popover"]};
    --popover-foreground: {p["popover_foreground"]};
    --primary: {primary};
    --primary-foreground: {primary_fg};
    --secondary: {p["secondary"]};
    --secondary-foreground: {p["secondary_foreground"]};
    --muted: {p["muted"]};
    --muted-foreground: {p["muted_foreground"]};
    --accent: {accent};
    --accent-foreground: {accent_fg};
    --destructive: 0 84.2% 60.2%;
    --destructive-foreground: 0 0% 98%;
    --border: {p["border"]};
    --input: {p["input"]};
    --ring: {primary};
    --radius: {radius};

    --sidebar-background: {p["sidebar_background"]};
    --sidebar-foreground: {p["sidebar_foreground"]};
    --sidebar-primary: {primary};
    --sidebar-primary-foreground: {primary_fg};
    --sidebar-accent: {p["sidebar_accent"]};
    --sidebar-accent-foreground: {p["sidebar_accent_foreground"]};
    --sidebar-border: {p["sidebar_border"]};
    --sidebar-ring: {primary};

    --font-display: "{font}", ui-sans-serif, system-ui, sans-serif;
  }}

  .dark {{
    --background: 0 0% 3.9%;
    --foreground: 0 0% 98%;
    --card: 0 0% 3.9%;
    --card-foreground: 0 0% 98%;
    --popover: 0 0% 3.9%;
    --popover-foreground: 0 0% 98%;
    --primary: {primary};
    --primary-foreground: {primary_fg};
    --secondary: 0 0% 14.9%;
    --secondary-foreground: 0 0% 98%;
    --muted: 0 0% 14.9%;
    --muted-foreground: 0 0% 63.9%;
    --accent: {accent};
    --accent-foreground: {accent_fg};
    --destructive: 0 62.8% 30.6%;
    --destructive-foreground: 0 0% 98%;
    --border: 0 0% 14.9%;
    --input: 0 0% 14.9%;
    --ring: {primary};

    --sidebar-background: 240 5.9% 10%;
    --sidebar-foreground: 240 4.8% 95.9%;
    --sidebar-primary: {primary};
    --sidebar-primary-foreground: {primary_fg};
    --sidebar-accent: 240 3.7% 15.9%;
    --sidebar-accent-foreground: 240 4.8% 95.9%;
    --sidebar-border: 240 3.7% 15.9%;
    --sidebar-ring: {primary};
  }}
}}

@layer base {{
  * {{
    @apply border-border;
  }}
  html, body {{
    font-family: var(--font-display);
  }}
  body {{
    @apply bg-background text-foreground antialiased;
  }}
}}
"""


def _utils_ts() -> str:
    return """\
import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
"""


def _motion_helpers() -> str:
    """Tiny motion primitives used across pages.

    ``Reveal`` fades + slides children in once on mount with an optional delay.
    ``Stagger`` applies sequential delays to its direct children — pair with
    ``Reveal`` per child for a list/grid stagger effect.
    """
    return """\
// AUTO-GENERATED by Cosolvent Frontend Compiler
"use client";

import { Children, cloneElement, isValidElement, type ReactNode } from "react";
import { cn } from "@/lib/utils";

interface RevealProps {
  children: ReactNode;
  delay?: number;          // milliseconds
  className?: string;
  as?: keyof React.JSX.IntrinsicElements;
}

/** Fade-in-up wrapper. Mount-only, no scroll trigger. */
export function Reveal({
  children,
  delay = 0,
  className,
  as: Tag = "div",
}: RevealProps) {
  const TagName = Tag as unknown as React.ElementType;
  return (
    <TagName
      className={cn("animate-fade-in-up", className)}
      style={delay ? { animationDelay: `${delay}ms` } : undefined}
    >
      {children}
    </TagName>
  );
}

interface StaggerProps {
  children: ReactNode;
  step?: number;     // milliseconds between siblings
  start?: number;    // initial delay
  className?: string;
}

/** Apply a cascading animation-delay to direct children. */
export function Stagger({ children, step = 60, start = 0, className }: StaggerProps) {
  const items = Children.toArray(children).map((child, idx) => {
    if (!isValidElement(child)) return child;
    type Stylable = { style?: React.CSSProperties };
    const existing = (child.props as Stylable).style ?? {};
    return cloneElement(child as React.ReactElement<Stylable>, {
      style: { ...existing, animationDelay: `${start + idx * step}ms` },
    });
  });
  return <div className={className}>{items}</div>;
}
"""


def _env_ts() -> str:
    return """\
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:18000";
"""


def _middleware_ts() -> str:
    """Cookie-based auth route guards.

    Edge-runtime middleware that checks for the ``session_token`` cookie set
    by the FastAPI backend on login. Visitors without it are redirected to
    ``/login`` (with a ``?next=`` hint), and authenticated visitors hitting
    ``/login`` or ``/signup`` are bounced to the dashboard.
    """
    return """\
// AUTO-GENERATED by Cosolvent Frontend Compiler
// DO NOT EDIT — changes will be overwritten on next compile

import { NextRequest, NextResponse } from "next/server";

const SESSION_COOKIE = "session_token";

const PUBLIC_PREFIXES = [
  "/login",
  "/signup",
  "/bootstrap",
  "/register",
  "/api",
  "/_next",
  "/favicon",
];

const AUTH_ONLY_PREFIXES = ["/login", "/signup"];

function isPublic(pathname: string): boolean {
  if (pathname === "/") return true;
  return PUBLIC_PREFIXES.some((p) => pathname.startsWith(p));
}

export function middleware(req: NextRequest) {
  const { pathname, search } = req.nextUrl;
  const hasSession = Boolean(req.cookies.get(SESSION_COOKIE)?.value);

  if (hasSession && AUTH_ONLY_PREFIXES.some((p) => pathname.startsWith(p))) {
    const url = req.nextUrl.clone();
    url.pathname = "/dashboard";
    url.search = "";
    return NextResponse.redirect(url);
  }

  if (!hasSession && !isPublic(pathname)) {
    const url = req.nextUrl.clone();
    url.pathname = "/login";
    url.search = `?next=${encodeURIComponent(pathname + search)}`;
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    /**
     * Run on every route except Next.js internals and static assets.
     * Public route gating still happens inside ``middleware`` above so the
     * matcher can stay simple and we avoid edge-cases with nested groups.
     */
    "/((?!_next/static|_next/image|favicon.ico|.*\\\\..*).*)",
  ],
};
"""
