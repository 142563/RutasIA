export type Pixel = [number, number];
export interface PixelBounds { left: number; top: number; right: number; bottom: number }

function distanceSquared(point: Pixel, a: Pixel, b: Pixel) {
  const dx = b[0] - a[0];
  const dy = b[1] - a[1];
  const length = dx * dx + dy * dy;
  const t = length ? Math.max(0, Math.min(1, ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / length)) : 0;
  return (point[0] - a[0] - t * dx) ** 2 + (point[1] - a[1] - t * dy) ** 2;
}

/** Simplifica solo el dibujo: conserva extremos y curvas que exceden 0.75 píxeles. */
export function simplifyPixels(points: Pixel[], tolerance = 0.75): Pixel[] {
  if (points.length < 3) return points;
  const keep = new Set([0, points.length - 1]);
  const stack: Pixel[] = [[0, points.length - 1]];
  while (stack.length) {
    const [first, last] = stack.pop()!;
    let farthest = tolerance ** 2;
    let index = -1;
    for (let i = first + 1; i < last; i++) {
      const distance = distanceSquared(points[i], points[first], points[last]);
      if (distance > farthest) { farthest = distance; index = i; }
    }
    if (index !== -1) {
      keep.add(index);
      stack.push([first, index], [index, last]);
    }
  }
  return points.filter((_, i) => keep.has(i));
}

export function preparePixelPath(points: Pixel[], scale: number) {
  const pixels = simplifyPixels(points.map(([x, y]) => [x * scale, y * scale]));
  const bounds: PixelBounds = { left: Infinity, top: Infinity, right: -Infinity, bottom: -Infinity };
  for (const [x, y] of pixels) {
    bounds.left = Math.min(bounds.left, x);
    bounds.top = Math.min(bounds.top, y);
    bounds.right = Math.max(bounds.right, x);
    bounds.bottom = Math.max(bounds.bottom, y);
  }
  return { bounds, d: pixels.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(2)} ${y.toFixed(2)}`).join("") };
}

/** Incluye los tramos que cruzan la pantalla aunque sus extremos queden afuera. */
export function intersectsViewport(bounds: PixelBounds, offset: Pixel, viewport: Pixel, padding = 8) {
  return bounds.right + offset[0] >= -padding && bounds.left + offset[0] <= viewport[0] + padding
    && bounds.bottom + offset[1] >= -padding && bounds.top + offset[1] <= viewport[1] + padding;
}

/** Agrupa los avisos de cámara; al desmontar no deja trabajo pendiente. */
export function frameScheduler(draw: () => void, request: (callback: () => void) => number, cancel: (id: number) => void) {
  let pending: number | null = null;
  let disposed = false;
  return {
    schedule() {
      if (disposed || pending !== null) return;
      pending = request(() => { pending = null; if (!disposed) draw(); });
    },
    dispose() {
      disposed = true;
      if (pending !== null) cancel(pending);
      pending = null;
    },
  };
}
