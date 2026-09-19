export const DELETED = Symbol("deleted");
export type Path = Array<string | number>;
export interface Change { path: Path; value: unknown }
export type Delta = Change[];

const isObject = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);

/** Leaf changes that turn `from` into `to`. Values are deep-copied so later mutation of `to` cannot alter the record. */
export function diff(from: unknown, to: unknown, path: Path = [], out: Delta = []): Delta {
  if (from === to) return out;
  if (Array.isArray(from) && Array.isArray(to)) {
    const shared = Math.min(from.length, to.length);
    for (let i = 0; i < shared; i += 1) diff(from[i], to[i], [...path, i], out);
    for (let i = shared; i < to.length; i += 1) out.push({ path: [...path, i], value: structuredClone(to[i]) });
    if (to.length < from.length) out.push({ path: [...path, "length"], value: to.length });
    return out;
  }
  if (isObject(from) && isObject(to)) {
    for (const key of Object.keys(from)) if (!(key in to)) out.push({ path: [...path, key], value: DELETED });
    for (const key of Object.keys(to)) diff(from[key], to[key], [...path, key], out);
    return out;
  }
  if (typeof from === "number" && typeof to === "number" && Number.isNaN(from) && Number.isNaN(to)) return out;
  out.push({ path, value: typeof to === "object" && to !== null ? structuredClone(to) : to });
  return out;
}

/** Applies a delta to `target` in place. Changes are applied in order; array `length` entries truncate. */
export function apply(target: unknown, delta: Delta): void {
  for (const change of delta) {
    if (change.path.length === 0) continue;
    let node: any = target;
    for (let i = 0; i < change.path.length - 1; i += 1) {
      const key = change.path[i];
      if (node[key] === undefined || node[key] === null) node[key] = typeof change.path[i + 1] === "number" ? [] : {};
      node = node[key];
    }
    const last = change.path[change.path.length - 1];
    if (change.value === DELETED) delete node[last];
    else node[last] = typeof change.value === "object" && change.value !== null ? structuredClone(change.value) : change.value;
  }
}

/** Approximate bytes a delta holds, for the memory report. */
export function deltaSize(delta: Delta): number {
  let size = 0;
  for (const change of delta) size += 16 + change.path.length * 8 + (change.value === DELETED ? 0 : JSON.stringify(change.value ?? null).length);
  return size;
}
