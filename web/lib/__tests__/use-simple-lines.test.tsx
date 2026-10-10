import { act, render } from "@testing-library/react";
import { useRef } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { SimpleLinesProps } from "@/lib/island-loader";
import { useSimpleLines } from "@/lib/use-simple-lines";

const island = vi.hoisted(() => {
  const state = {
    withUpdate: true,
    resolve: null as null | (() => void),
    deferred: false,
  };
  const dispose = vi.fn();
  const update = vi.fn();
  const mountSimpleLines = vi.fn((_target: HTMLElement, _props: unknown) => (state.withUpdate ? Object.assign(() => dispose(), { update }) : () => dispose()));
  const api = { mountSimpleLines };
  const loadIslands = vi.fn(() => {
    if (!state.deferred) return Promise.resolve(api);
    return new Promise((resolve) => {
      state.resolve = () => resolve(api);
    });
  });
  return { state, dispose, update, mountSimpleLines, loadIslands };
});

vi.mock("@/lib/island-loader", () => ({ loadIslands: island.loadIslands }));

function props(label: string): SimpleLinesProps {
  return { series: [], height: 120, label };
}

function Chart({ p, mountKey }: { p: SimpleLinesProps | null; mountKey: string }) {
  const ref = useRef<HTMLDivElement>(null);
  useSimpleLines(ref, p, mountKey);
  return <div ref={ref} />;
}

async function flush() {
  await act(async () => {
    await Promise.resolve();
  });
}

beforeEach(() => {
  island.state.withUpdate = true;
  island.state.deferred = false;
  island.state.resolve = null;
  island.dispose.mockClear();
  island.update.mockClear();
  island.mountSimpleLines.mockClear();
  island.loadIslands.mockClear();
});

describe("useSimpleLines", () => {
  it("mounts once with the latest props", async () => {
    const a = props("a");
    const view = render(<Chart p={a} mountKey="1d" />);
    await flush();
    expect(island.mountSimpleLines).toHaveBeenCalledTimes(1);
    expect(island.mountSimpleLines.mock.calls[0]).toEqual([expect.any(HTMLDivElement), a]);
    view.rerender(<Chart p={a} mountKey="1d" />);
    await flush();
    expect(island.mountSimpleLines).toHaveBeenCalledTimes(1);
    expect(island.update).not.toHaveBeenCalled();
  });

  it("a props change calls update once, no re-mount", async () => {
    const view = render(<Chart p={props("a")} mountKey="1d" />);
    await flush();
    const b = props("b");
    view.rerender(<Chart p={b} mountKey="1d" />);
    await flush();
    expect(island.update).toHaveBeenCalledTimes(1);
    expect(island.update).toHaveBeenCalledWith(b);
    expect(island.mountSimpleLines).toHaveBeenCalledTimes(1);
    expect(island.dispose).not.toHaveBeenCalled();
  });

  it("a handle without update is re-mounted", async () => {
    island.state.withUpdate = false;
    const view = render(<Chart p={props("a")} mountKey="1d" />);
    await flush();
    const b = props("b");
    view.rerender(<Chart p={b} mountKey="1d" />);
    await flush();
    expect(island.dispose).toHaveBeenCalledTimes(1);
    expect(island.mountSimpleLines).toHaveBeenCalledTimes(2);
    expect(island.mountSimpleLines.mock.calls[1][1]).toBe(b);
  });

  it("a mountKey change disposes and re-mounts", async () => {
    const a = props("a");
    const view = render(<Chart p={a} mountKey="1d" />);
    await flush();
    const b = props("b");
    view.rerender(<Chart p={b} mountKey="4h" />);
    await flush();
    expect(island.dispose).toHaveBeenCalledTimes(1);
    expect(island.mountSimpleLines).toHaveBeenCalledTimes(2);
    expect(island.mountSimpleLines.mock.calls[1][1]).toBe(b);
    expect(island.update).not.toHaveBeenCalled();
  });

  it("unmount disposes", async () => {
    const view = render(<Chart p={props("a")} mountKey="1d" />);
    await flush();
    view.unmount();
    expect(island.dispose).toHaveBeenCalledTimes(1);
  });

  it("a change before the async mount ends mounts with the latest props, no update", async () => {
    island.state.deferred = true;
    const view = render(<Chart p={props("a")} mountKey="1d" />);
    const b = props("b");
    view.rerender(<Chart p={b} mountKey="1d" />);
    await act(async () => {
      island.state.resolve!();
      await Promise.resolve();
    });
    await flush();
    expect(island.mountSimpleLines).toHaveBeenCalledTimes(1);
    expect(island.mountSimpleLines.mock.calls[0][1]).toBe(b);
    expect(island.update).not.toHaveBeenCalled();
  });

  it("dispose before resolve never mounts", async () => {
    island.state.deferred = true;
    const view = render(<Chart p={props("a")} mountKey="1d" />);
    view.unmount();
    await act(async () => {
      island.state.resolve!();
      await Promise.resolve();
    });
    await flush();
    expect(island.mountSimpleLines).not.toHaveBeenCalled();
    expect(island.dispose).not.toHaveBeenCalled();
  });
});
