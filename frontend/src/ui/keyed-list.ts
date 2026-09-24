/** Put `ordered` into `parent` in that order, dropping every other element child, with the fewest moves. */
export function reconcile(parent: HTMLElement, ordered: Element[]): void {
  const wanted = new Set(ordered);
  for (const child of Array.from(parent.children)) {
    if (!wanted.has(child)) child.remove();
  }
  let cursor: Element | null = parent.firstElementChild;
  for (const node of ordered) {
    if (node === cursor) cursor = cursor.nextElementSibling;
    else parent.insertBefore(node, cursor);
  }
}
