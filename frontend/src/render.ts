import type { Face, Door } from "./api.js";

const PALETTE = ["#e8f0fe", "#fce8e6", "#e6f4ea", "#fef7e0", "#f3e8fd", "#e0f7fa", "#fff3e0", "#ede7f6"];

export function renderGeometry(faces: Face[], doors: Door[]): string {
  const pts = faces.flatMap((f) => f.points);
  if (!pts.length) return "";
  const xs = pts.map((p) => p[0]);
  const ys = pts.map((p) => p[1]);
  const x0 = Math.min(...xs);
  const y0 = Math.min(...ys);
  const x1 = Math.max(...xs);
  const y1 = Math.max(...ys);
  const W = 640;
  const H = 480;
  const pad = 20;
  const scale = Math.min((W - 2 * pad) / (x1 - x0 || 1), (H - 2 * pad) / (y1 - y0 || 1));
  const sx = (x: number) => pad + (x - x0) * scale;
  const sy = (y: number) => H - pad - (y - y0) * scale;

  const polys = faces
    .map((f, i) => {
      const p = f.points.map(([x, y]) => `${sx(x).toFixed(1)},${sy(y).toFixed(1)}`).join(" ");
      const cx = f.points.reduce((s, pt) => s + pt[0], 0) / f.points.length;
      const cy = f.points.reduce((s, pt) => s + pt[1], 0) / f.points.length;
      return (
        `<polygon points="${p}" fill="${PALETTE[i % PALETTE.length]}" stroke="#555"/>` +
        `<text x="${sx(cx).toFixed(1)}" y="${sy(cy).toFixed(1)}" text-anchor="middle" font-size="12">${f.label}</text>`
      );
    })
    .join("");

  const doorLines = doors
    .map(
      (d) =>
        `<line x1="${sx(d.x1).toFixed(1)}" y1="${sy(d.y1).toFixed(1)}" x2="${sx(d.x2).toFixed(1)}" y2="${sy(d.y2).toFixed(1)}" stroke="red" stroke-width="3" stroke-dasharray="6,4"/>`,
    )
    .join("");

  return (
    `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">` +
    `<rect width="${W}" height="${H}" fill="white"/>${polys}${doorLines}</svg>`
  );
}
