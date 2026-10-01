<script>
  import { Chart, Canvas, Spline, Points, Area, Axis } from "layerchart";
  import { scaleTime, scaleLinear } from "d3-scale";
  import { clipSegmentToWindow, toLineSegments } from "../lib/chart-segments";
  import { formatCount } from "../lib/onchain-view-model";

  /**
   * One /onchain chain panel.
   *
   * Four marks on one y-axis: pre-launch context as a muted area, the daily
   * value as a thin translucent line, the 28-day EMA heavy on top, and the
   * API's floor/ramp markers. Range and hover come from the shared store, so
   * every chain panel shows the same window — the same arrangement as /regime.
   */
  let {
    store,
    gridDates,
    value,
    preLaunchValue,
    ema28,
    gapBefore,
    markers = [],
    color,
    rawColor,
    preLaunchColor,
    preLaunchFill,
    floorColor,
    rampColor,
    height = 180,
    label = "chart",
  } = $props();

  const bounds = $derived(store.visibleBounds());

  function cut(values) {
    const segments = toLineSegments(gridDates, values, gapBefore);
    return {
      drawn: segments
        .map((s) => clipSegmentToWindow(s, bounds.lo, bounds.hi))
        .filter((s) => s.length > 1),
      isolated: segments
        .filter((s) => s.length === 1)
        .map((s) => s[0])
        .filter((p) => p.i >= bounds.lo && p.i <= bounds.hi),
    };
  }

  const raw = $derived(cut(value));
  const pre = $derived(cut(preLaunchValue));
  const ema = $derived(cut(ema28));

  const indexByDate = $derived(new Map(gridDates.map((d, i) => [d, i])));
  const markerPoints = $derived(
    markers
      .map((m) => {
        const i = indexByDate.get(m.date);
        if (i === undefined || i < bounds.lo || i > bounds.hi) return null;
        const v = ema28[i] ?? value[i];
        if (v === null || v === undefined || !Number.isFinite(v)) return null;
        return { i, date: new Date(`${m.date}T00:00:00Z`), value: v, kind: m.kind };
      })
      .filter(Boolean),
  );

  const xDomain = $derived([
    new Date(`${gridDates[bounds.lo]}T00:00:00Z`),
    new Date(`${gridDates[bounds.hi]}T00:00:00Z`),
  ]);

  const yDomain = $derived.by(() => {
    let min = Infinity;
    let max = -Infinity;
    const eat = (p) => {
      if (p.value < min) min = p.value;
      if (p.value > max) max = p.value;
    };
    for (const group of [raw, pre, ema]) {
      for (const seg of group.drawn) for (const p of seg) eat(p);
      for (const p of group.isolated) eat(p);
    }
    if (!Number.isFinite(min) || !Number.isFinite(max)) return null;
    if (min === max) return [min - 1, max + 1];
    const pad = (max - min) * 0.08;
    // Counts are never negative, so the axis is not dragged below zero.
    return [Math.max(0, min - pad), max + pad];
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
      padding={{ left: 56, bottom: 18, top: 6, right: 10 }}
    >
      <Canvas>
        <Axis placement="left" grid rule ticks={4} format={(v) => formatCount(v)} />
        <Axis placement="bottom" rule ticks={4} />

        <!-- Pre-launch first, so real values always sit on top of context. -->
        {#each pre.drawn as segment, s (s)}
          <Area data={segment} fill={preLaunchFill} line={{ stroke: preLaunchColor, strokeWidth: 1 }} />
        {/each}

        {#each raw.drawn as segment, s (s)}
          <Spline data={segment} stroke={rawColor} strokeWidth={1} />
        {/each}
        {#if raw.isolated.length > 0}
          <Points data={raw.isolated} r={2} fill={color} />
        {/if}

        {#each ema.drawn as segment, s (s)}
          <Spline data={segment} stroke={color} strokeWidth={2} />
        {/each}

        {#if markerPoints.length > 0}
          <!-- Floor and ramp are told apart by colour, not by glyph: a canvas
               Points mark is a circle. The panel legend uses the same two
               colours so the key still matches what is drawn. -->
          <Points
            data={markerPoints.filter((m) => m.kind === "floor")}
            r={3.5}
            fill={floorColor}
          />
          <Points
            data={markerPoints.filter((m) => m.kind !== "floor")}
            r={3.5}
            fill={rampColor}
          />
        {/if}
      </Canvas>
    </Chart>
  {/if}
</div>
