export interface GradeParams {
  exposure?: number;
  contrast?: number;
  lift?: number;
  gamma?: number;
  saturation?: number;
  vibrance?: number;
  temperature?: number;
  tint?: number;
  sepia?: number;
  shadows_r?: number;
  shadows_g?: number;
  shadows_b?: number;
  highlights_r?: number;
  highlights_g?: number;
  highlights_b?: number;
}

export interface Look {
  id: string;
  name: string;
  params: GradeParams;
}

export const LOOKS: Look[] = [
  { id: "golden-hour", name: "Golden Hour", params: { temperature: 0.35, saturation: 1.15, contrast: 1.05, highlights_r: 0.04 } },
  { id: "teal-orange", name: "Teal Orange", params: { shadows_b: 0.08, shadows_g: 0.03, highlights_r: 0.08, highlights_g: 0.02, saturation: 1.1, contrast: 1.1 } },
  { id: "blue-hour", name: "Blue Hour", params: { temperature: -0.3, tint: 0.05, saturation: 0.9, exposure: -0.1, shadows_b: 0.06 } },
  { id: "night-city", name: "Night City", params: { temperature: -0.2, contrast: 1.25, exposure: -0.3, shadows_b: 0.08, highlights_r: 0.04, saturation: 1.2 } },
  { id: "bleach-bypass", name: "Bleach Bypass", params: { saturation: 0.45, contrast: 1.35, gamma: 1.05 } },
  { id: "cross-process", name: "Cross Process", params: { shadows_b: 0.1, highlights_g: 0.06, highlights_r: 0.05, contrast: 1.2, saturation: 1.2 } },
  { id: "faded-film", name: "Faded Film", params: { contrast: 0.82, lift: 0.06, saturation: 0.8, highlights_r: 0.03 } },
  { id: "matte", name: "Matte", params: { lift: 0.1, contrast: 0.9, saturation: 0.9 } },
  { id: "autumn", name: "Autumn", params: { temperature: 0.25, tint: 0.05, saturation: 1.2, highlights_r: 0.06, shadows_r: 0.03 } },
  { id: "desert", name: "Desert", params: { temperature: 0.45, saturation: 0.9, contrast: 1.05, lift: 0.03, highlights_r: 0.05 } },
  { id: "arctic", name: "Arctic", params: { temperature: -0.45, saturation: 0.8, exposure: 0.1, highlights_b: 0.05 } },
  { id: "moody-green", name: "Moody Green", params: { tint: -0.12, saturation: 0.85, contrast: 1.1, exposure: -0.15, shadows_g: 0.04 } },
  { id: "mint", name: "Mint", params: { tint: -0.1, temperature: -0.1, lift: 0.05, saturation: 0.9, highlights_g: 0.04 } },
  { id: "pastel", name: "Pastel", params: { saturation: 0.75, lift: 0.08, contrast: 0.85, exposure: 0.15, tint: 0.04 } },
  { id: "punchy-contrast", name: "Punchy Contrast", params: { contrast: 1.4, saturation: 1.1, gamma: 0.95 } },
  { id: "rose-tint", name: "Rose Tint", params: { tint: 0.18, highlights_r: 0.05, saturation: 1.05 } },
  { id: "vivid-pop", name: "Vivid Pop", params: { saturation: 1.45, vibrance: 0.3, contrast: 1.12 } },
  { id: "sepia-print", name: "Sepia Print", params: { sepia: 0.85, contrast: 1.05, lift: 0.03 } },
  { id: "silver-mono", name: "Silver Mono", params: { saturation: 0, contrast: 1.1, lift: 0.03, highlights_b: 0.02 } },
  { id: "noir", name: "Noir", params: { saturation: 0, contrast: 1.4, gamma: 1.1 } },
];

export const lookById = (id: string | undefined): Look | undefined => (id ? LOOKS.find((look) => look.id === id) : undefined);
