const W = 256;
const H = 110;

export class LumaScope {
  readonly canvas = document.createElement("canvas");
  private ctx = this.canvas.getContext("2d")!;
  private probe = document.createElement("canvas");
  private pctx = this.probe.getContext("2d", { willReadFrequently: true })!;
  private ink = "";
  private grid = "";
  private last = 0;

  constructor() {
    this.canvas.width = W;
    this.canvas.height = H;
    this.canvas.className = "scope-canvas";
    this.probe.width = 128;
    this.probe.height = 72;
    this.refreshColours();
    this.clear();
  }

  refreshColours(): void {
    const style = getComputedStyle(document.documentElement);
    this.ink = style.getPropertyValue("--tag-audio").trim() || "white";
    this.grid = style.getPropertyValue("--edge-strong").trim() || "gray";
  }

  private clear(): void {
    const g = this.ctx;
    g.clearRect(0, 0, W, H);
    g.strokeStyle = this.grid;
    g.lineWidth = 1;
    for (const level of [0, 0.25, 0.5, 0.75, 1]) {
      const y = Math.round(4 + (1 - level) * (H - 8)) + 0.5;
      g.beginPath();
      g.moveTo(0, y);
      g.lineTo(W, y);
      g.stroke();
    }
  }

  update(source: HTMLCanvasElement, force: boolean): void {
    const now = performance.now();
    if (!force && now - this.last < 90) return;
    this.last = now;
    this.pctx.drawImage(source, 0, 0, this.probe.width, this.probe.height);
    const data = this.pctx.getImageData(0, 0, this.probe.width, this.probe.height).data;
    this.clear();
    const g = this.ctx;
    g.fillStyle = this.ink;
    g.globalAlpha = 0.22;
    const pw = this.probe.width;
    const ph = this.probe.height;
    for (let y = 0; y < ph; y += 1) {
      for (let x = 0; x < pw; x += 1) {
        const i = (y * pw + x) * 4;
        const luma = (0.2126 * data[i] + 0.7152 * data[i + 1] + 0.0722 * data[i + 2]) / 255;
        g.fillRect(Math.floor((x / pw) * W), Math.round(4 + (1 - luma) * (H - 8)), 3, 2);
      }
    }
    g.globalAlpha = 1;
  }
}
