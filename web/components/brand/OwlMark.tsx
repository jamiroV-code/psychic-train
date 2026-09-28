/**
 * The owl, redrawn as vector from owl.png.
 *
 * The supplied artwork is a 1024px JPEG (despite the .png extension) with a
 * baked white background and no alpha, so it cannot sit on the dark shell and
 * turns to mush at favicon size. This redraw fixes both and makes the colourway
 * a one-prop change.
 *
 * Two colourways, because brand navy measures 1.89:1 against the shell ground
 * where a graphic needs 3:1:
 *   - `light`: as supplied — navy body, sage wings. For light/analytical panels.
 *   - `dark`:  body inverts to shell ink, sage lifts to #8aa37d (6.96:1).
 *   - `mono`:  single `currentColor`, for favicons and one-colour contexts.
 *
 * Geometry is hand-fitted to measurements of the original, not traced; the
 * colours are sampled and exact. See ui-shell_DIRECTION-D_28-09-26.md.
 */
export type OwlTone = "dark" | "light" | "mono";

export interface OwlMarkProps {
  size?: number;
  tone?: OwlTone;
  /** Decorative by default; pass a label when the mark stands alone as content. */
  title?: string;
  className?: string;
}

const TONES: Record<OwlTone, { body: string; wing: string; eye: string }> = {
  light: { body: "var(--brand-navy)", wing: "var(--brand-sage)", eye: "#ffffff" },
  dark: { body: "var(--ink-1)", wing: "var(--brand-sage-lift)", eye: "var(--sh-0)" },
  mono: { body: "currentColor", wing: "currentColor", eye: "var(--sh-1)" },
};

export function OwlMark({ size = 24, tone = "dark", title, className }: OwlMarkProps) {
  const c = TONES[tone];
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      className={className}
      role={title ? "img" : undefined}
      aria-label={title}
      aria-hidden={title ? undefined : true}
      focusable="false"
      style={{ display: "block", flex: "none" }}
    >
      {title ? <title>{title}</title> : null}
      {/* Wings sit behind the body; the head hides their upper third, which is
          what opens the white gap lower down where the body has narrowed. */}
      <path
        fill={c.wing}
        d="M26.2 29.4 C22.2 31.4 19.9 35.4 19.9 39.6 C19.9 42.3 20.8 44.3 22.2 45.4 C23.3 41.6 24.5 35.8 26.2 29.4 Z"
      />
      <path
        fill={c.wing}
        d="M37.8 29.4 C41.8 31.4 44.1 35.4 44.1 39.6 C44.1 42.3 43.2 44.3 41.8 45.4 C40.7 41.6 39.5 35.8 37.8 29.4 Z"
      />
      {/* Ear tufts */}
      <path fill={c.body} d="M26.8 17.4 C24.6 15.4 22.4 14.0 21.0 13.6 C21.4 16.4 21.9 19.2 22.9 21.8 Z" />
      <path fill={c.body} d="M37.2 17.4 C39.4 15.4 41.6 14.0 43.0 13.6 C42.6 16.4 42.1 19.2 41.1 21.8 Z" />
      {/* Head and body as one form */}
      <path
        fill={c.body}
        d="M32 14.1 C38.3 14.1 43.4 19.2 43.4 25.5 C43.4 29.4 41.6 32.9 38.6 35.0 C37.9 39.2 36.5 44.4 34.4 47.6 C33.6 48.8 32.8 49.3 32 49.3 C31.2 49.3 30.4 48.8 29.6 47.6 C27.5 44.4 26.1 39.2 25.4 35.0 C22.4 32.9 20.6 29.4 20.6 25.5 C20.6 19.2 25.7 14.1 32 14.1 Z"
      />
      {/* Heavy-lidded eyes: a near-full arc closed by a lid that slopes inward */}
      <path fill={c.eye} d="M25.63 19.92 A3.7 3.7 0 1 0 30.10 21.55 Z" />
      <path fill={c.eye} d="M38.37 19.92 A3.7 3.7 0 1 1 33.90 21.55 Z" />
      <circle fill={c.body} cx="27.5" cy="23.6" r="1.3" />
      <circle fill={c.body} cx="36.5" cy="23.6" r="1.3" />
      {/* Beak */}
      <path fill={c.body} d="M32 25.0 C33.1 26.2 33.2 27.4 32 29.6 C30.8 27.4 30.9 26.2 32 25.0 Z" />
    </svg>
  );
}
