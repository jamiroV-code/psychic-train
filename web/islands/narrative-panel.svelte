<script>
  import { Chart, Canvas, Spline, Points, Axis } from "layerchart";
  import { scaleTime, scaleLinear } from "d3-scale";
  import { toLineSegments } from "../lib/chart-segments";

  /**
   * One /narrative category's plot.
   *
   * Unlike /regime these panels are deliberately independent — no shared range,
   * no crosshair sync (narrative-v2 ADR-9) — so there is no store here. Each
   * panel shows its whole history, which is what `fitContent()` did before.
   *
   * Canvas context, like /regime: the marks resolve against `currentColor`, so
   * the axis colour comes from `.analytic-plot` in globals.css. Series colours
   * are passed in, because they carry meaning.
   */
  let { dates, lines = [], composite, mixedScale = null, height = 160 } = $props();

  const asDate = (d) => new Date(`${d}T00:00:00Z`);

  // Cut once per line. `gap_before` breaks a line; a date with no reading is
  // whitespace and does not (see lib/chart-segments.ts).
  const drawn = $derived(
    lines.map((line) => {
      const segments = toLineSegments(dates, line.values, line.gapBefore);
      return {
        key: line.key,
        color: line.color,
        dashed: !!line.dashed,
        segments: segments.filter((s) => s.length > 1),
        isolated: segments.filter((s) => s.length === 1).map((s) => s[0]),
      };
    }),
  );

  const compositeSegments = $derived.by(() => {
    if (!composite) return { segments: [], isolated: [] };
    const segments = toLineSegments(dates, composite.values, composite.gapBefore);
    return {
      segments: segments.filter((s) => s.length > 1),
      isolated: segments.filter((s) => s.length === 1).map((s) => s[0]),
    };
  });

  /** Composite points drawn on a different Google Trends scale, marked as dots. */
  const mixedPoints = $derived(
    !mixedScale
      ? []
      : dates
          .map((d, i) => ({ i, date: asDate(d), value: mixedScale.values[i] }))
          .filter((p) => p.value !== null && p.value !== undefined && Number.isFinite(p.value)),
  );

  const xDomain = $derived(dates.length > 0 ? [asDate(dates[0]), asDate(dates[dates.length - 1])] : null);

  const yDomain = $derived.by(() => {
    let min = Infinity;
    let max = -Infinity;
    const eat = (p) => {
      if (p.value < min) min = p.value;
      if (p.value > max) max = p.value;
    };
    for (const line of drawn) {
      for (const seg of line.segments) for (const p of seg) eat(p);
      for (const p of line.isolated) eat(p);
    }
    for (const seg of compositeSegments.segments) for (const p of seg) eat(p);
    for (const p of compositeSegments.isolated) eat(p);
    for (const p of mixedPoints) eat(p);
    if (!Number.isFinite(min) || !Number.isFinite(max)) return null;
    if (min === max) return [min - 0.5, max + 0.5];
    const pad = (max - min) * 0.08;
    return [min - pad, max + pad];
  });
</script>

<div class="analytic-plot" style="height: {height}px">
  {#if xDomain && yDomain}
    <Chart
      x="date"
      xScale={scaleTime()}
      {xDomain}
      y="value"
      yScale={scaleLinear()}
      {yDomain}
      padding={{ left: 44, bottom: 18, top: 6, right: 12 }}
    >
      <Canvas>
        <Axis placement="left" grid rule ticks={4} format={(v) => v.toFixed(2)} />
        <Axis placement="bottom" rule ticks={4} />

        {#each drawn as line (line.key)}
          {#each line.segments as segment, s (s)}
            <Spline
              data={segment}
              stroke={line.color}
              strokeWidth={1}
              strokeDasharray={line.dashed ? "4 3" : undefined}
            />
          {/each}
          {#if line.isolated.length > 0}
            <Points data={line.isolated} r={1.5} fill={line.color} />
          {/if}
        {/each}

        <!-- The composite is the headline reading, so it is drawn last and
             heaviest — nothing else should sit on top of it. -->
        {#each compositeSegments.segments as segment, s (s)}
          <Spline data={segment} stroke={composite.color} strokeWidth={2.5} />
        {/each}
        {#if compositeSegments.isolated.length > 0}
          <Points data={compositeSegments.isolated} r={2} fill={composite.color} />
        {/if}

        {#if mixedPoints.length > 0}
          <Points data={mixedPoints} r={3} fill={mixedScale.color} />
        {/if}
      </Canvas>
    </Chart>
  {/if}
</div>
