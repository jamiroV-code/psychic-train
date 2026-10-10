/**
 * T43 / S11b: props a mounted island can be handed again without a re-mount.
 *
 * The values live in one `$state.raw` object (replaced whole, never proxied:
 * the series arrays are large and only ever swapped). `mount` gets a props
 * object of getters over it, which Svelte reads as reactive props, so
 * `set(next)` re-renders the component in place and its own state (the
 * zoom) survives. `keys` lists every prop the component may read, so a prop
 * absent at mount can still arrive later.
 */
export function createLiveProps(initial, keys) {
  let current = $state.raw(initial);
  const props = {};
  for (const key of new Set([...keys, ...Object.keys(initial)])) {
    Object.defineProperty(props, key, { enumerable: true, get: () => current[key] });
  }
  return {
    props,
    set(next) {
      current = next;
    },
  };
}
