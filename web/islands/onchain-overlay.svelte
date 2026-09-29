<script>
  import { Chart, Canvas, Spline, Points, Axis } from "layerchart";
  import { scaleTime, scaleLinear, scaleLog } from "d3-scale";
  import { clipSegmentToWindow, toLineSegments } from "../lib/chart-segments";

  /**
   * The /onchain normalised comparison overlay.
   *
   * One y-axis for every chain (never a dual axis) — these are normalised
   * series, so they are directly comparable by construction. The store is its
   * OWN instance, not the one the chain panels share: the overlay has its own
   * range and its own readout, exactly as it did before.
   */
  let { store, gridDates, lines = [], logScale = false, format, height = 320, label = "chart" } = $props();

  const bounds = $derived(store.visibleBounds());

  const drawn = $derived(
    lines.map((line) => {
      const segments = toLineSegments(gridDates, line.values, line.gapBefore);
      return {
        key: line.key,
        color: line.color,
        segments: segments
          .map((s) => clipSegmentToWindow(s, bounds.lo, bounds.hi))
          .filter((s) => s.length > 1),
        isolated: segments
          .filter((s) => s.length === 1)
          .map((s) => s[0])
          .filter((p) => p.i >= bounds.lo && p.i <= bounds.hi),
      };
    }),
  );

  const xDomain = $derived([
    new Date(`${gridDates[bounds.lo]}T00:00:00Z`),
    new Date(`${gridDates[bounds.hi]}T00:00:00Z`),
  ]);

  const yDomain = $derived.by(() => {
    let min = Infinity;
    let max = -Infinity;
    for (const line of drawn) {
      for (const seg of line.segments) for (const p of seg) {
        if (p.value < min) min = p.value;
        if (p.value > max) max = p.value;
      }
      for (const p of line.isolated) {
        if (p.value < min) min = p.value;
        if (p.value > max) max = p.value;
      }
    }
    if (!Number.isFinite(min) || !Number.isFinite(max)) return null;
    if (min === max) return logScale ? [min / 2, max * 2] : [min - 1, max + 1];
    const pad = (max - min) * 0.08;
    // A log scale cannot show zero or below, so the floor stays positive. The
    // toggle is only offered on the index view, whose values are positive.
    if (logScale) return [Math.max(min * 0.9, Number.EPSILON), max * 1.1];
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
      yScale={logScale ? scaleLog() : scaleLinear()}
      {yDomain}
      padding={{ left: 56, bottom: 18, top: 6, right: 10 }}
    >
      <Canvas>
        <Axis placement="left" grid rule ticks={4} format={(v) => format(v)} />
        <Axis placement="bottom" rule ticks={4} />
        {#each drawn as line (line.key)}
          {#each line.segments as segment, s (s)}
            <Spline data={segment} stroke={line.color} strokeWidth={2} />
          {/each}
          {#if line.isolated.length > 0}
            <Points data={line.isolated} r={2} fill={line.color} />
          {/if}
        {/each}
      </Canvas>
    </Chart>
  {/if}
</div>
