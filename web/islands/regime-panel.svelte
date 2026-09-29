<script>
  import { Chart, Canvas, Spline, Points, Axis, Rule } from "layerchart";
  import { scaleTime, scaleLinear } from "d3-scale";
  import { clipSegmentToWindow, toLineSegments } from "../lib/chart-segments";
  import { formatRegimeValue } from "../lib/format-regime-value";

  /**
   * One /regime panel's plot.
   *
   * Rendered to LayerChart's CANVAS context rather than SVG: seven panels over
   * ~2000 grid dates redraw on every wheel event, and canvas keeps that smooth.
   * It also keeps the end-to-end contract intact — the suite targets the plot
   * with `locator("canvas")` and drives real wheel/move events at it.
   *
   * Canvas marks cannot be reached by CSS, but LayerChart's defaults resolve
   * against `currentColor`, so the panel's colour is set on `.regime-plot` in
   * globals.css and inherited here. The series colours are the only ones passed
   * explicitly, because they carry meaning.
   *
   * Range and hover come from the shared store, so every panel is looking at
   * the same window without any panel knowing another exists.
   */
  let { store, gridDates, lines, unit = "", height = 120, label = "chart" } = $props();

  const bounds = $derived(store.visibleBounds());

  // Segments are cut once per line from the full grid; slicing to the visible
  // window happens on the scale, so zooming never re-derives the geometry.
  const lineSegments = $derived(
    lines.map((line) => {
      const segments = toLineSegments(gridDates, line.values, line.gapBefore);
      return {
        color: line.color,
        // A one-point segment has no line to draw. Those readings are real and
        // must still be visible, so they are drawn as dots — the same choice
        // the lightweight-charts path made with its separate dots-only series.
        drawn: segments.filter((s) => s.length > 1),
        isolated: segments.filter((s) => s.length === 1).map((s) => s[0]),
      };
    }),
  );

  // Canvas does not clip, so anything outside the window would be painted over
  // the axis labels. Clipping here also means a wheel event only ever redraws
  // the points actually on screen, instead of all ~2000 of them.
  const visible = $derived(
    lineSegments.map((line) => ({
      color: line.color,
      drawn: line.drawn
        .map((segment) => clipSegmentToWindow(segment, bounds.lo, bounds.hi))
        .filter((segment) => segment.length > 1),
      isolated: line.isolated.filter((p) => p.i >= bounds.lo && p.i <= bounds.hi),
    })),
  );

  const xDomain = $derived([
    new Date(`${gridDates[bounds.lo]}T00:00:00Z`),
    new Date(`${gridDates[bounds.hi]}T00:00:00Z`),
  ]);

  // The y domain follows what is actually in view, so zooming in on a quiet
  // stretch does not leave the line pinned flat against the axis.
  const yDomain = $derived.by(() => {
    let min = Infinity;
    let max = -Infinity;
    // Measured on the clipped geometry, so a line entering steeply from off
    // screen cannot push past the axis it is drawn against.
    for (const { drawn, isolated } of visible) {
      for (const seg of drawn) {
        for (const p of seg) {
          if (p.value < min) min = p.value;
          if (p.value > max) max = p.value;
        }
      }
      for (const p of isolated) {
        if (p.value < min) min = p.value;
        if (p.value > max) max = p.value;
      }
    }
    if (!Number.isFinite(min) || !Number.isFinite(max)) return null;
    if (min === max) return [min - 1, max + 1];
    const pad = (max - min) * 0.08;
    return [min - pad, max + pad];
  });

  let plot;

  function fractionFrom(event) {
    const el = plot?.querySelector("canvas") ?? plot;
    if (!el) return 0.5;
    const r = el.getBoundingClientRect();
    if (r.width === 0) return 0.5;
    return Math.min(1, Math.max(0, (event.clientX - r.left) / r.width));
  }

  function onwheel(event) {
    event.preventDefault();
    store.zoomAt(fractionFrom(event), event.deltaY);
  }

  function onpointermove(event) {
    const f = fractionFrom(event);
    const i = Math.round(bounds.lo + f * (bounds.hi - bounds.lo));
    store.setHover(Math.min(bounds.hi, Math.max(bounds.lo, i)));
  }

  function onpointerleave() {
    store.setHover(null);
  }
</script>

<div
  class="analytic-plot"
  style="height: {height}px"
  role="img"
  aria-label={label}
  bind:this={plot}
  {onwheel}
  {onpointermove}
  {onpointerleave}
>
  {#if yDomain}
    <Chart
      x="date"
      xScale={scaleTime()}
      {xDomain}
      y="value"
      yScale={scaleLinear()}
      {yDomain}
      padding={{ left: 68, bottom: 18, top: 6, right: 12 }}
    >
      <Canvas>
        <!-- Same formatter the readout uses, so an axis label and a
             readout cell never disagree about the same number. -->
        <Axis placement="left" grid rule ticks={4} format={(v) => formatRegimeValue(v, unit)} />
        <Axis placement="bottom" rule ticks={4} />
        <Rule y={0} />
        {#each visible as line (line.color)}
          {#each line.drawn as segment, s (s)}
            <Spline data={segment} stroke={line.color} strokeWidth={1.5} />
          {/each}
          {#if line.isolated.length > 0}
            <Points data={line.isolated} r={1.5} fill={line.color} />
          {/if}
        {/each}
      </Canvas>
    </Chart>
  {/if}
</div>
