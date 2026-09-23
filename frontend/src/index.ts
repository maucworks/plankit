import { listVariants, getVariant, type VariantSummary, type VariantDetail } from "./api.js";
import { renderGeometry } from "./render.js";

const variantListEl = document.getElementById("variants")!;
const planEl = document.getElementById("plan")!;
const reportEl = document.getElementById("report")!;
const posEl = document.getElementById("pos")!;

let variants: VariantSummary[] = [];
let idx = 0;

async function refresh(): Promise<void> {
  try {
    variants = await listVariants();
  } catch (e) {
    variantListEl.innerHTML = `<p class="hint">geen API op :8000 (${String(e)})</p>`;
    return;
  }
  renderList();
  if (variants.length) await select(0);
}

function renderList(): void {
  variantListEl.innerHTML = variants
    .map(
      (v, i) =>
        `<div class="item" data-i="${i}">#${v.step} ${v.label ?? v.id.slice(0, 8)}</div>`,
    )
    .join("");
  variantListEl.querySelectorAll<HTMLElement>(".item").forEach((el) =>
    el.addEventListener("click", () => select(Number(el.dataset.i))),
  );
}

async function select(i: number): Promise<void> {
  if (!variants.length) return;
  idx = i;
  const v = variants[i];
  const d: VariantDetail = await getVariant(v.id);
  planEl.innerHTML = renderGeometry(d.geometry.faces, d.geometry.doors);
  reportEl.textContent = JSON.stringify(d.report, null, 2);
  posEl.textContent = `${i + 1} / ${variants.length}`;
}

document.getElementById("prev")!.addEventListener("click", () => {
  select((idx - 1 + variants.length) % variants.length);
});
document.getElementById("next")!.addEventListener("click", () => {
  select((idx + 1) % variants.length);
});

void refresh();
