# SnowOS Icon System Style Rules

## Vision
A "Frozen Minimal" aesthetic that emphasizes clarity, soft geometry, and a cold color palette. The icons should feel lightweight and integrated into the frosted glass UI.

## Geometry
- **Stroke-based**: Use thin to medium lines (2px - 3px default).
- **Soft Corners**: All sharp angles should be rounded (radius 2px - 8px depending on scale).
- **Breathable**: Maintain generous internal padding within the icon boundaries.

## Color Palette
- **Primary (Ice Blue)**: `#A5D6F1` - Used for main structural elements.
- **Accent (Frost White)**: `#F0F8FF` - Used for highlights and active states.
- **Deep (Midnight Blue)**: `#001F3F` - Used for shadows or grounding elements.
- **Background (Subtle Blue)**: `#E0F7FA` - Semi-transparent fills if needed.

## Prohibited Elements
- **NO Glossy Effects**: Avoid heavy gradients or "wet" looks common in early 2000s UI.
- **NO Skewmorphism**: No realistic textures (wood, metal, leather).
- **NO Apple Symbols**: Do not use SF Symbols or Apple-specific iconography.
- **NO Complex Details**: If it can't be identified at 16x16, it's too complex.

## Implementation
Icons should be exported as SVG for resolution independence.
Folder structure follows XDG Icon Theme Specification.
