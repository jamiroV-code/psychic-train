"use client";

import { useEffect, useRef, type RefObject } from "react";
import { loadIslands, type IslandApi, type SimpleLinesHandle, type SimpleLinesProps } from "@/lib/island-loader";

/**
 * T43 / S11b: one simple-lines island per `mountKey`, updated in place.
 *
 * The island mounts once per `mountKey` (and once `props` stops being null)
 * with the LATEST props, however long the bundle takes to load. After that a
 * change of the memoised `props` goes to the handle's `update`, so the chart
 * keeps its zoom and the page its scroll; a handle without `update` is
 * re-mounted. A `mountKey` change, null props or unmount disposes it.
 */
export function useSimpleLines(
  ref: RefObject<HTMLElement | null>,
  props: SimpleLinesProps | null,
  mountKey: string,
): void {
  const latest = useRef(props);
  latest.current = props;
  const mounted = useRef<{ api: IslandApi; handle: SimpleLinesHandle; props: SimpleLinesProps } | null>(null);
  const hasProps = props !== null;

  useEffect(() => {
    const target = ref.current;
    if (!target || !hasProps) return;
    let disposed = false;

    loadIslands()
      .then((api) => {
        const initial = latest.current;
        if (disposed || !initial) return;
        mounted.current = { api, handle: api.mountSimpleLines(target, initial), props: initial };
      })
      .catch(() => {
        // The numbers around the chart still say what is there; a chart that
        // cannot load stays silent rather than breaking the view.
      });

    return () => {
      disposed = true;
      const current = mounted.current;
      mounted.current = null;
      current?.handle();
    };
  }, [ref, mountKey, hasProps]);

  useEffect(() => {
    const current = mounted.current;
    if (!current || !props || current.props === props) return;
    if (typeof current.handle.update === "function") {
      current.handle.update(props);
      current.props = props;
      return;
    }
    const target = ref.current;
    current.handle();
    if (!target) {
      mounted.current = null;
      return;
    }
    mounted.current = { api: current.api, handle: current.api.mountSimpleLines(target, props), props };
  }, [ref, props]);
}
