---
name: Ressy Zen Dashboard
colors:
  surface: '#faf9f6'
  surface-dim: '#dbdad7'
  surface-bright: '#faf9f6'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f4f3f0'
  surface-container: '#efeeeb'
  surface-container-high: '#e9e8e5'
  surface-container-highest: '#e3e2e0'
  on-surface: '#1a1c1a'
  on-surface-variant: '#4f4446'
  inverse-surface: '#2f312f'
  inverse-on-surface: '#f2f1ee'
  outline: '#817476'
  outline-variant: '#d2c3c5'
  surface-tint: '#75565e'
  primary: '#75565e'
  on-primary: '#ffffff'
  primary-container: '#f7cfd8'
  on-primary-container: '#75565e'
  inverse-primary: '#e3bdc5'
  secondary: '#b71329'
  on-secondary: '#ffffff'
  secondary-container: '#da323f'
  on-secondary-container: '#fffbff'
  tertiary: '#5f5e5e'
  on-tertiary: '#ffffff'
  tertiary-container: '#dbd8d8'
  on-tertiary-container: '#5f5e5e'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#ffd9e1'
  primary-fixed-dim: '#e3bdc5'
  on-primary-fixed: '#2b151b'
  on-primary-fixed-variant: '#5b3f46'
  secondary-fixed: '#ffdad8'
  secondary-fixed-dim: '#ffb3b0'
  on-secondary-fixed: '#410007'
  on-secondary-fixed-variant: '#92001b'
  tertiary-fixed: '#e5e2e1'
  tertiary-fixed-dim: '#c8c6c5'
  on-tertiary-fixed: '#1c1b1b'
  on-tertiary-fixed-variant: '#474746'
  background: '#faf9f6'
  on-background: '#1a1c1a'
  surface-variant: '#e3e2e0'
typography:
  display:
    fontFamily: EB Garamond
    fontSize: 48px
    fontWeight: '500'
    lineHeight: '1.2'
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: EB Garamond
    fontSize: 32px
    fontWeight: '500'
    lineHeight: '1.3'
  headline-md:
    fontFamily: EB Garamond
    fontSize: 24px
    fontWeight: '500'
    lineHeight: '1.4'
  body-lg:
    fontFamily: Hanken Grotesk
    fontSize: 18px
    fontWeight: '400'
    lineHeight: '1.6'
  body-md:
    fontFamily: Hanken Grotesk
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.6'
  label-sm:
    fontFamily: Hanken Grotesk
    fontSize: 12px
    fontWeight: '600'
    lineHeight: '1'
    letterSpacing: 0.05em
  headline-lg-mobile:
    fontFamily: EB Garamond
    fontSize: 28px
    fontWeight: '500'
    lineHeight: '1.3'
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  unit: 8px
  container-max: 1200px
  gutter: 24px
  margin-desktop: 64px
  margin-tablet: 32px
  margin-mobile: 20px
---

## Brand & Style

The design system is rooted in the "Ma" (間) philosophy—the Japanese concept of negative space—blending modern digital utility with a traditional spiritual aesthetic. The target audience consists of Discord community managers who value tranquility and artistic precision over chaotic, "gamer-centric" interfaces.

The visual style is a hybrid of **Minimalism** and **Glassmorphism**, creating a sense of ethereal lightness. High-quality whitespace is used to reduce cognitive load, while subtle translucent layers evoke the texture of shoji paper. The atmosphere is "Zen-Digital": professional, calm, and meticulously organized, featuring fluid animations of falling Sakura petals that serve as non-intrusive background life.

## Colors

The palette is inspired by traditional Japanese pigments and natural materials.

- **Silk White (#F9F8F5):** The foundation of the UI, used for main backgrounds to provide a warm, organic feel compared to pure digital white.
- **Sakura Petal (#F7CFD8):** The primary brand color. Used for soft highlights, active states, and decorative elements.
- **Crimson Red (#A80021):** The "Hanko" (stamp) color. Reserved for high-priority actions, critical alerts, and focal points that require immediate attention.
- **Sumi Ink (#1A1A1A):** Used for typography and deep structural elements, providing a grounded contrast to the lighter hues.
- **Glass Overlay:** A semi-transparent white (rgba(255, 255, 255, 0.6)) with high backdrop-blur (20px) to simulate frosted glass.

## Typography

This design system utilizes a sophisticated pairing of a geometric Sans-Serif and a classical Serif to bridge the gap between technology and tradition.

- **Headlines:** **EB Garamond** provides an elegant, calligraphic feel reminiscent of ink-brush strokes. It is used for page titles and section headers to establish an artistic identity.
- **Interface & Body:** **Hanken Grotesk** is chosen for its extreme legibility and modern, clean geometry. It handles all functional text, settings, and data labels.
- **Labels:** Small labels and metadata use all-caps with increased letter-spacing to mirror the structured precision of Japanese architectural stamps.

## Layout & Spacing

The layout follows a **Fixed Grid** model centered on the screen, creating a focused, "shrine-like" sanctuary for data. 

- **Grid:** A 12-column grid on desktop with generous 24px gutters. 
- **Margins:** Large outer margins (64px+) are essential to maintain the Zen aesthetic, ensuring the content never feels crowded.
- **Rhythm:** Spacing follows an 8px base unit. Vertical rhythm should be intentionally sparse, using white space as a primary separator rather than heavy lines.
- **Breakpoints:** On mobile, the 12-column grid collapses to a single column with 20px side margins, and the sidebar navigation transforms into a bottom-sheet or a minimal overlay.

## Elevation & Depth

Depth is conveyed through "Paper Stacking" and atmospheric blurs rather than aggressive shadows.

- **Surface Layers:** The base layer is Silk White. Content cards use a glassmorphism effect (semi-transparent white) to appear as if floating slightly above the base.
- **Shadows:** Only used for active components. Shadows are extremely soft, using the Crimson or Sakura hue at 5% opacity to create a subtle glow rather than a dark void (e.g., `0px 10px 30px rgba(168, 0, 33, 0.05)`).
- **Patterns:** The *Seigaiha* (wave) and *Asanoha* (hemp leaf) patterns are applied as low-opacity SVG backgrounds (3% opacity) within containers to provide tactile texture without distracting from text.

## Shapes

Shapes are "Softened Organic." While the system uses modern geometry, the corners are rounded to 0.5rem (8px) for standard components and 1.5rem (24px) for major containers to evoke the smoothness of river stones.

- **Interactive Elements:** Buttons and inputs use a standard 8px radius.
- **Decorative Elements:** Profile avatars and status indicators may use a "Squircle" or circular shape to maintain a friendly, approachable feel.
- **Dividers:** Instead of solid lines, use the *Seigaiha* pattern as a thin horizontal fade or a simple 1px line that fades out at the edges.

## Components

- **Buttons:** Primary buttons are solid Sakura Petal with Sumi Ink text. Secondary buttons are outlined in Crimson Red with a transparent background. Interaction includes a subtle "bloom" animation where the background color expands slightly.
- **Cards:** Glassmorphic backgrounds with a 1px border in a slightly lighter Silk White. The *Asanoha* pattern appears in the bottom right corner of cards at very low opacity.
- **Navigation:** A minimalist sidebar with large vertical spacing between items. Active items are marked by a vertical Crimson Red line (resembling a bookmark) and a subtle Sakura glow.
- **Inputs:** Clean fields with only a bottom border (Sumi Ink). Upon focus, a Sakura-colored underline expands from the center.
- **Sakura Particles:** A global background component that renders high-performance SVG petals falling slowly. These should pause or hide when the user is interacting with complex forms to ensure focus.
- **Chips/Badges:** Small, pill-shaped elements with light Sakura backgrounds and Sumi Ink text, used for Discord roles or bot status.