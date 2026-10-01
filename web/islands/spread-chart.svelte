<script>
  import { Chart, Svg, Axis, Spline, Rule } from "layerchart";
  import { scaleTime, scaleLinear } from "d3-scale";
  import { toSpreadSeries } from "../lib/pairs-spread-series";

  /**
   * The /pairs spread chart, as the LayerChart pilot.
   *
   * Direction D: this renders on a LIGHT analytical panel inside the dark
   * shell, so it takes the light ink/grid tokens and the light series slot.
   *
   * "One source of numerical truth" applies here literally: `spread` values are
   * plotted exactly as the API sent them. Only the date string is turned into a
   * Date so a time scale can position it — no rounding, no resampling, no fill.
   */
  let { points = [], height = 260 } = $props();

  const data = $derived(toSpreadSeries(points));
</script>

<div class="spread-chart" style="height: {height}px" data-points={points.length}>
  {#if data.length > 0}
    <Chart
      {data}
      x="date"
      xScale={scaleTime()}
      y="value"
      yScale={scaleLinear()}
      yNice
      padding={{ left: 52, bottom: 26, top: 8, right: 12 }}
    >
      <Svg>
        <Axis placement="left" grid rule />
        <Axis placement="bottom" rule />
        <!-- A spread oscillates around zero, so the zero line is the reference
             the eye needs; it is drawn under the series, never over it. -->
        <Rule y={0} class="spread-chart__zero" />
        <Spline class="spread-chart__line" />
      </Svg>
    </Chart>
  {/if}
</div>
