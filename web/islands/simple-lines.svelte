<script>
  import { Chart, Canvas, Spline, Points, Axis } from "layerchart";
  import { scaleTime, scaleLinear } from "d3-scale";

  /**
   * A plain multi-line time chart.
   *
   * The last two charts to leave lightweight-charts — the screener's
   * relative-performance lines and the drill-down MiniChart — are the same
   * shape: a handful of series over timestamps, no shared range, no crosshair
   * group, no `gap_before`. One island serves both rather than two that differ
   * only in how many lines they take.
   *
   * Points arrive as the API sent them, already a list rather than a
   * grid-aligned array, so there is no whitespace to reason about here: a
   * series is drawn through exactly the points it has.
   */
  let { series = [], height = 120, format = null, label = "chart" } = $props();

  const lines = $derived(
    series.map((s) => {
      const points = s.points
        .map((p) => ({ date: new Date(p.timestamp), value: p.value }))
        .filter((p) => Number.isFinite(p.value) && !Number.isNaN(p.date.getTime()))
        .sort((a, b) => a.date - b.date);
      return { key: s.key, color: s.color, width: s.width ?? 2, points };
    }),
  );

  const all = $derived(lines.flatMap((l) => l.points));

  const xDomain = $derived.by(() => {
    if (all.length === 0) return null;
    let lo = Infinity;
    let hi = -Infinity;
    for (const p of all) {
      const t = p.date.getTime();
      if (t < lo) lo = t;
      if (t > hi) hi = t;
    }
    if (lo === hi) return [new Date(lo - 86_400_000), new Date(hi + 86_400_000)];
    return [new Date(lo), new Date(hi)];
  });

  const yDomain = $derived.by(() => {
    if (all.length === 0) return null;
    let min = Infinity;
    let max = -Infinity;
    for (const p of all) {
      if (p.value < min) min = p.value;
      if (p.value > max) max = p.value;
    }
    if (min === max) return [min - 1, max + 1];
    const pad = (max - min) * 0.08;
    return [min - pad, max + pad];
  });
</script>

<div class="analytic-plot" style="height: {height}px" role="img" aria-label={label}>
  {#if xDomain && yDomain}
    <Chart
      x="date"
      xScale={scaleTime()}
      {xDomain}
      y="value"
      yScale={scaleLinear()}
      {yDomain}
      padding={{ left: 52, bottom: 18, top: 6, right: 10 }}
    >
      <Canvas>
        <Axis placement="left" grid rule ticks={4} format={format ?? undefined} />
        <Axis placement="bottom" rule ticks={4} />
        {#each lines as line (line.key)}
          {#if line.points.length > 1}
            <Spline data={line.points} stroke={line.color} strokeWidth={line.width} />
          {:else if line.points.length === 1}
            <!-- A single reading still has to be visible; a one-point line is not. -->
            <Points data={line.points} r={2} fill={line.color} />
          {/if}
        {/each}
      </Canvas>
    </Chart>
  {/if}
</div>
