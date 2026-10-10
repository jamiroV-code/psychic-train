<script>
  import { untrack } from "svelte";
  import { Chart, Canvas, Svg, Spline, Points, Axis } from "layerchart";
  import { scaleTime, scaleUtc, scaleLinear } from "d3-scale";
  import { brusselsAxis } from "../lib/chart-time-format";
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
    keepRange,
  } from "../lib/chart-viewport";

  /**
   * A plain multi-line time chart: the board's coin boxes, the drill-down
   * MiniChart and the spaghetti chart. A handful of series over timestamps, no
   * shared range, no crosshair group, no `gap_before`.
   *
   * T37 / S6 (C6): every chart zooms and pans on its own. Ctrl or Cmd + wheel
   * zooms about the pointer (a plain wheel scrolls the page), two pointers
   * pinch, a drag pans while zoomed, a double-click or double-tap resets, and
   * so does the reset button (not on a linked chart). The range math is lib/chart-viewport.ts; this
   * file only turns events into calls to it. The y axis re-fits to what is
   * visible.
   *
   * T44: a linked chart has no reset button. With `onRangeChange` the chart is linked: every
   * zoom, pan or reset is reported (null = full range), and a `linkedRange`
   * handed back in is applied, clamped into this chart's own data by
   * `keepRange`. The board's small charts share one range this way.
   *
   * T43 / S11b: the page hands new data in place (`update` in entry.js). The
   * zoom resets only when the timeframe or the list of line keys changes; a
   * zoomed range is carried through new data by `keepRange`.
   *
   * Axis text is drawn in an <Svg> layer so it stays vector-sharp at any
   * pixel ratio; the lines stay on the <Canvas> below it.
   *
   * T38 / S7 (additive): `bands` shade time spans in two tints and `markers`
   * draw a dated vertical line each (the BTC leg chart). Both are plain
   * absolutely positioned elements under the plot, placed from the same
   * x domain and padding the Chart uses, so they zoom and pan with it.
   */
  let {
    series = [],
    height = 120,
    format = null,
    label = "chart",
    timeframe = null,
    highlight = false,
    bands = [],
    markers = [],
    linkedRange = null,
    onRangeChange = null,
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

  // null = the full range. Reset when the timeframe or the set of lines
  // changes; new data for the same lines keeps a zoom, clamped into it.
  // The props are getters over one object that `update` replaces whole, so
  // this effect re-runs on every update; it compares the actual values.
  let range = $state(null);
  let resetKey = null;
  $effect(() => {
    const key = `${timeframe ?? ""}|${series.map((s) => s.key).join("\n")}`;
    untrack(() => {
      if (resetKey !== null && key !== resetKey && range !== null) range = null;
      resetKey = key;
    });
  });
  $effect(() => {
    const next = extent;
    untrack(() => {
      if (range !== null) range = keepRange(range, next);
    });
  });

  // T44: a shared range from the page, applied when its value changes. The
  // range this chart reported itself is remembered, so its echo is a no-op.
  let linkedKey = "";
  const rangeKey = (r) => (r ? `${r.from}|${r.to}` : "");
  $effect(() => {
    const next = linkedRange;
    untrack(() => {
      const key = rangeKey(next);
      if (!onRangeChange || key === linkedKey) return;
      linkedKey = key;
      range = keepRange(next, extent);
    });
  });

  function setRange(next) {
    range = next;
    if (!onRangeChange) return;
    linkedKey = rangeKey(next);
    onRangeChange(next ? { from: next.from, to: next.to } : null);
  }

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

  // With a timeframe the x axis is Brussels time, its ticks and labels taken from
  // chart-time-format for the VISIBLE span, so they never depend on the
  // browser's zone. Without one it stays a local time axis.
  const xAxis = $derived(timeframe && xDomain ? brusselsAxis(xDomain[0], xDomain[1], timeframe, 4) : null);

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

  // Fraction of the plot width at time `t` for the visible x domain.
  function xFraction(t) {
    if (!xDomain) return 0;
    const lo = xDomain[0].getTime();
    const hi = xDomain[1].getTime();
    return hi === lo ? 0 : (t - lo) / (hi - lo);
  }

  function plotLeft(fraction) {
    return `calc(${PAD_LEFT}px + ${fraction} * (100% - ${PAD_LEFT + padRight}px))`;
  }

  function plotWidthCss(fraction) {
    return `calc(${fraction} * (100% - ${PAD_LEFT + padRight}px))`;
  }

  // Bands and markers clipped to the visible range; anything outside is not drawn.
  const visibleBands = $derived(
    xDomain
      ? bands
          .map((b) => {
            const from = Math.max(0, xFraction(new Date(b.from).getTime()));
            const to = Math.min(1, xFraction(new Date(b.to).getTime()));
            return { ...b, f0: from, f1: to };
          })
          .filter((b) => Number.isFinite(b.f0) && Number.isFinite(b.f1) && b.f1 > b.f0)
      : [],
  );
  const visibleMarkers = $derived(
    xDomain
      ? markers
          .map((m) => ({ ...m, f: xFraction(new Date(m.timestamp).getTime()) }))
          .filter((m) => Number.isFinite(m.f) && m.f >= 0 && m.f <= 1)
      : [],
  );

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
    setRange(isZoomed(next, extent) ? next : null);
  }

  function reset() {
    setRange(null);
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
      setRange(isZoomed(next, extent) ? next : null);
      return;
    }
    if (pointers.size === 1 && zoomed && extent && view) {
      setRange(pan(view, (e.clientX - prev.x) / plotWidth(), extent));
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
  {#if xDomain && yDomain && (visibleBands.length || visibleMarkers.length)}
    <div
      class="simple-lines__overlay"
      style="top: {PAD_TOP}px; bottom: {PAD_BOTTOM}px"
      aria-hidden="true"
      data-band-count={visibleBands.length}
      data-marker-count={visibleMarkers.length}
    >
      {#each visibleBands as band (band.from)}
        <div
          class="simple-lines__band simple-lines__band--{band.tint}"
          data-current={band.current ? "true" : undefined}
          style="left: {plotLeft(band.f0)}; width: {plotWidthCss(band.f1 - band.f0)}"
        ></div>
      {/each}
      {#each visibleMarkers as marker (marker.timestamp)}
        <div class="simple-lines__marker" style="left: {plotLeft(marker.f)}" title={marker.label}></div>
      {/each}
    </div>
  {/if}
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
  {#if zoomed && !onRangeChange}
    <button type="button" class="simple-lines__reset" data-testid="chart-reset" onclick={reset}>
      Reset zoom
    </button>
  {/if}
</div>
