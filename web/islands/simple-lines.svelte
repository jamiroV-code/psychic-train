<script>
  import { Chart, Canvas, Svg, Spline, Points, Axis } from "layerchart";
  import { scaleTime, scaleUtc, scaleLinear } from "d3-scale";
  import { utcAxis } from "../lib/chart-time-format";
  import {
    extentOf,
    fullRange,
    isZoomed,
    zoomAt,
    pan,
    pinchFactor,
    wheelFactor,
    isDoubleTap,
    shouldHandleWheel,
    touchActionFor,
    isoZ,
  } from "../lib/chart-viewport";

  /**
   * A plain multi-line time chart: the board's coin boxes, the drill-down
   * MiniChart and the spaghetti chart. A handful of series over timestamps, no
   * shared range, no crosshair group, no `gap_before`.
   *
   * T37 / S6 (C6): every chart zooms and pans on its own. Ctrl or Cmd + wheel
   * zooms about the pointer (a plain wheel scrolls the page), two pointers
   * pinch, a drag pans while zoomed, a double-click or double-tap resets, and
   * so does the reset button. The range math is lib/chart-viewport.ts; this
   * file only turns events into calls to it. The y axis re-fits to what is
   * visible, and the zoom resets whenever the series change.
   *
   * Axis text is drawn in an <Svg> layer so it stays vector-sharp at any
   * pixel ratio; the lines stay on the <Canvas> below it.
   */
  let {
    series = [],
    height = 120,
    format = null,
    label = "chart",
    timeframe = null,
    highlight = false,
  } = $props();

  const PAD_LEFT = 52;
  const PAD_TOP = 6;
  const PAD_BOTTOM = 18;
  // Average width of a 10px tabular label character, for the right padding.
  const CHAR_PX = 6;

  const lines = $derived(
    series.map((s) => {
      const points = s.points
        .map((p) => ({ date: new Date(p.timestamp), value: p.value }))
        .filter((p) => Number.isFinite(p.value) && !Number.isNaN(p.date.getTime()))
        .sort((a, b) => a.date - b.date);
      return { key: s.key, color: s.color, width: s.width ?? 2, points };
    }),
  );

  const extent = $derived(extentOf(lines.flatMap((l) => l.points.map((p) => p.date.getTime()))));

  // null = the full range. Reset whenever the series prop changes.
  let range = $state(null);
  $effect(() => {
    void series;
    range = null;
  });

  const view = $derived(range ?? (extent ? fullRange(extent) : null));
  const zoomed = $derived(isZoomed(range, extent));

  // What is drawn: the points inside the visible range, plus one either side
  // so a line runs to the plot edge instead of stopping short of it.
  const visibleLines = $derived(
    lines.map((l) => {
      if (!view || !zoomed) return l;
      let lo = l.points.findIndex((p) => p.date.getTime() >= view.from);
      if (lo === -1) return { ...l, points: [] };
      let hi = l.points.length - 1;
      while (hi > 0 && l.points[hi].date.getTime() > view.to) hi -= 1;
      return { ...l, points: l.points.slice(Math.max(0, lo - 1), Math.min(l.points.length, hi + 2)) };
    }),
  );

  const xDomain = $derived.by(() => {
    if (!view) return null;
    if (view.from === view.to) return [new Date(view.from - 86_400_000), new Date(view.to + 86_400_000)];
    return [new Date(view.from), new Date(view.to)];
  });

  // With a timeframe the x axis is UTC, its ticks and labels taken from
  // chart-time-format for the VISIBLE span, so they never depend on the
  // browser's zone. Without one it stays a local time axis.
  const xAxis = $derived(timeframe && xDomain ? utcAxis(xDomain[0], xDomain[1], timeframe, 4) : null);

  // The last tick label is centred on the plot's right edge, so the right
  // padding is at least half the widest label: it never clips.
  const padRight = $derived.by(() => {
    const widest = xAxis ? Math.max(0, ...xAxis.labels.map((t) => String(t).length)) : 10;
    return Math.max(10, Math.ceil((widest * CHAR_PX) / 2) + 4);
  });

  // y re-fits to the points inside the visible range.
  const yDomain = $derived.by(() => {
    let min = Infinity;
    let max = -Infinity;
    for (const l of visibleLines) {
      for (const p of l.points) {
        if (view && zoomed) {
          const t = p.date.getTime();
          if (t < view.from || t > view.to) continue;
        }
        if (p.value < min) min = p.value;
        if (p.value > max) max = p.value;
      }
    }
    if (min === Infinity) return null;
    if (min === max) return [min - 1, max + 1];
    const pad = (max - min) * 0.08;
    return [min - pad, max + pad];
  });

  // ---- interaction --------------------------------------------------------

  let el = $state(null);
  let hoverKey = $state(null);

  function plotWidth() {
    return Math.max(1, (el?.clientWidth ?? 0) - PAD_LEFT - padRight);
  }

  function fractionAt(clientX) {
    const rect = el.getBoundingClientRect();
    return Math.min(1, Math.max(0, (clientX - rect.left - PAD_LEFT) / plotWidth()));
  }

  function zoomBy(clientX, factor) {
    if (!extent || !view) return;
    const next = zoomAt(view, fractionAt(clientX), factor, extent);
    range = isZoomed(next, extent) ? next : null;
  }

  function reset() {
    range = null;
  }

  // Non-passive, so Ctrl/Cmd + wheel can stop the browser's own page zoom; a
  // plain wheel is left alone and scrolls the page.
  $effect(() => {
    if (!el) return;
    const onWheel = (e) => {
      if (!shouldHandleWheel(e)) return;
      e.preventDefault();
      zoomBy(e.clientX, wheelFactor(e.deltaY));
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  });

  const pointers = new Map();
  let pinchStart = null;
  let lastTap = null;

  function distance() {
    const [a, b] = [...pointers.values()];
    return Math.hypot(a.x - b.x, a.y - b.y);
  }

  function onPointerDown(e) {
    if (e.target.closest?.("[data-testid='chart-reset']")) return;
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pointers.size === 2) {
      pinchStart = { dist: distance(), range: view };
    }
    if (e.pointerType !== "mouse" && pointers.size === 1) {
      const now = e.timeStamp;
      if (lastTap && isDoubleTap(lastTap.ts, now, Math.hypot(e.clientX - lastTap.x, e.clientY - lastTap.y))) {
        reset();
        lastTap = null;
      } else {
        lastTap = { ts: now, x: e.clientX, y: e.clientY };
      }
    }
    try {
      el.setPointerCapture?.(e.pointerId);
    } catch {
      // A synthetic pointer cannot be captured; the drag still works inside the plot.
    }
  }

  function onPointerMove(e) {
    const prev = pointers.get(e.pointerId);
    if (!prev) {
      if (highlight) hoverKey = nearestLine(e);
      return;
    }
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pointers.size === 2 && pinchStart && extent) {
      const [a, b] = [...pointers.values()];
      const mid = (a.x + b.x) / 2;
      const next = zoomAt(pinchStart.range, fractionAt(mid), pinchFactor(pinchStart.dist, distance()), extent);
      range = isZoomed(next, extent) ? next : null;
      return;
    }
    if (pointers.size === 1 && zoomed && extent && view) {
      range = pan(view, (e.clientX - prev.x) / plotWidth(), extent);
    }
  }

  function onPointerUp(e) {
    pointers.delete(e.pointerId);
    if (pointers.size < 2) pinchStart = null;
  }

  // Island-internal emphasis: the line nearest the pointer is drawn thicker.
  function nearestLine(e) {
    if (!view || !yDomain || !xDomain) return null;
    const rect = el.getBoundingClientRect();
    const plotH = Math.max(1, height - PAD_TOP - PAD_BOTTOM);
    const y = e.clientY - rect.top - PAD_TOP;
    const valueAt = yDomain[1] - (y / plotH) * (yDomain[1] - yDomain[0]);
    const t = xDomain[0].getTime() + fractionAt(e.clientX) * (xDomain[1].getTime() - xDomain[0].getTime());
    let best = null;
    let bestDist = Infinity;
    for (const l of visibleLines) {
      if (l.points.length === 0) continue;
      let nearest = l.points[0];
      for (const p of l.points) {
        if (Math.abs(p.date.getTime() - t) < Math.abs(nearest.date.getTime() - t)) nearest = p;
      }
      const d = Math.abs(nearest.value - valueAt);
      if (d < bestDist) {
        bestDist = d;
        best = l.key;
      }
    }
    return best;
  }
</script>

<div
  bind:this={el}
  class="analytic-plot simple-lines"
  style="height: {height}px; touch-action: {touchActionFor(zoomed)}"
  role="img"
  aria-label={label}
  data-zoomed={zoomed ? "true" : "false"}
  data-visible-from={view ? isoZ(view.from) : undefined}
  data-visible-to={view ? isoZ(view.to) : undefined}
  data-highlight={hoverKey ?? undefined}
  ondblclick={reset}
  onpointerdown={onPointerDown}
  onpointermove={onPointerMove}
  onpointerup={onPointerUp}
  onpointercancel={onPointerUp}
  onpointerleave={() => (hoverKey = null)}
>
  {#if xDomain && yDomain}
    <Chart
      x="date"
      xScale={xAxis ? scaleUtc() : scaleTime()}
      {xDomain}
      y="value"
      yScale={scaleLinear()}
      {yDomain}
      padding={{ left: PAD_LEFT, bottom: PAD_BOTTOM, top: PAD_TOP, right: padRight }}
    >
      <Svg>
        <Axis placement="left" grid rule ticks={4} format={format ?? undefined} />
        {#if xAxis}
          <Axis placement="bottom" rule ticks={xAxis.ticks} format={xAxis.format} />
        {:else}
          <Axis placement="bottom" rule ticks={4} />
        {/if}
      </Svg>
      <Canvas>
        {#each visibleLines as line (line.key)}
          {#if line.points.length > 1}
            <Spline
              data={line.points}
              stroke={line.color}
              strokeWidth={hoverKey === line.key ? line.width + 1.5 : line.width}
            />
          {:else if line.points.length === 1}
            <!-- A single reading still has to be visible; a one-point line is not. -->
            <Points data={line.points} r={2} fill={line.color} />
          {/if}
        {/each}
      </Canvas>
    </Chart>
  {/if}
  {#if zoomed}
    <button type="button" class="simple-lines__reset" data-testid="chart-reset" onclick={reset}>
      Reset zoom
    </button>
  {/if}
</div>
