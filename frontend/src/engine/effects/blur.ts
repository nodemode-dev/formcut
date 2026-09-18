import { registerEffect } from "../registry";

const BLUR: Array<[string, string, string]> = [
  ["Gaussian Blur", "blur(6px)", "gblur=sigma=6"],
  ["Box Blur", "blur(3px)", "boxblur=3:1"],
  ["Motion Blur", "blur(2px) contrast(1.05)", "gblur=sigma=2,eq=contrast=1.05"],
];

for (const [name, css, ffmpeg] of BLUR) {
  registerEffect({
    id: "fc." + name.toLowerCase().replace(/\s+/g, "-"),
    name,
    category: "Blur",
    group: "video",
    css,
    ffmpeg,
  });
}
