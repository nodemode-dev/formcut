import { registerEffect } from "../registry";

const STYLIZE: Array<[string, string, string]> = [
  ["Mono", "grayscale(1)", "hue=s=0"],
  ["Invert", "invert(1)", "negate"],
  ["Warm", "sepia(0.35) saturate(1.2)", "colorbalance=rm=0.1:bm=-0.1,eq=saturation=1.2"],
  ["Cool", "hue-rotate(-15deg) saturate(1.1)", "hue=h=-15,eq=saturation=1.1"],
  ["Vignette Pop", "contrast(1.2) saturate(1.15)", "eq=contrast=1.2:saturation=1.15,vignette"],
];

for (const [name, css, ffmpeg] of STYLIZE) {
  registerEffect({
    id: "fc." + name.toLowerCase().replace(/\s+/g, "-"),
    name,
    category: "Stylize",
    group: "video",
    css,
    ffmpeg,
  });
}
