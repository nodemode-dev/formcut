import { locale, t } from "./index";
import en from "./en.json";
import { PHRASES } from "./language-pack";

const additional: Record<string, Record<string, string>> = {
  de: { "Creator tools": "Kreativwerkzeuge", "Speed curve": "Geschwindigkeitskurve", "Motion presets": "Bewegungsvorlagen", "Visual effects": "Visuelle Effekte", "Audio processing": "Audioverarbeitung", "Cutout and brushes": "Freistellen und Pinsel", "LUT, shader and expressions": "LUT, Shader und Ausdrücke", "Apply curve": "Kurve anwenden", "Constant speed": "Konstante Geschwindigkeit", "Apply keyframes": "Keyframes anwenden", "Add effect": "Effekt hinzufügen", "Remove": "Entfernen", "Up": "Nach oben", "Volume": "Lautstärke", "Pan": "Panorama", "Add processor": "Verarbeitung hinzufügen", "Apply transition": "Übergang anwenden", "Object cutout": "Objekt freistellen", "Person cutout": "Person freistellen", "Enable cutout": "Freistellen aktivieren", "Remove cutout": "Freistellung entfernen", "Restore": "Wiederherstellen", "Erase": "Radieren", "Off": "Aus", "Project": "Projekt", "Timeline templates": "Zeitleistenvorlagen", "Local speech": "Lokale Sprachausgabe", "Local models": "Lokale Modelle", "Project settings": "Projekteinstellungen", "Apply settings": "Einstellungen anwenden", "Add track": "Spur hinzufügen", "Add timeline": "Zeitleiste hinzufügen", "Create project": "Projekt erstellen", "Download": "Herunterladen", "Cancel job": "Auftrag abbrechen", "Ready offline": "Offline bereit", "Not installed": "Nicht installiert", "Preview": "Vorschau", "Full size": "Volle Größe" },
  es: { "Creator tools": "Herramientas creativas", "Speed curve": "Curva de velocidad", "Motion presets": "Preajustes de movimiento", "Visual effects": "Efectos visuales", "Audio processing": "Procesamiento de audio", "Cutout and brushes": "Recorte y pinceles", "LUT, shader and expressions": "LUT, shader y expresiones", "Apply curve": "Aplicar curva", "Constant speed": "Velocidad constante", "Apply keyframes": "Aplicar fotogramas clave", "Add effect": "Añadir efecto", "Remove": "Eliminar", "Up": "Subir", "Volume": "Volumen", "Pan": "Panorámica", "Add processor": "Añadir procesamiento", "Apply transition": "Aplicar transición", "Object cutout": "Recorte de objeto", "Person cutout": "Recorte de persona", "Enable cutout": "Activar recorte", "Remove cutout": "Quitar recorte", "Restore": "Restaurar", "Erase": "Borrar", "Off": "Desactivado", "Project": "Proyecto", "Timeline templates": "Plantillas de línea de tiempo", "Local speech": "Voz local", "Local models": "Modelos locales", "Project settings": "Ajustes del proyecto", "Apply settings": "Aplicar ajustes", "Add track": "Añadir pista", "Add timeline": "Añadir línea de tiempo", "Create project": "Crear proyecto", "Download": "Descargar", "Cancel job": "Cancelar tarea", "Ready offline": "Disponible sin conexión", "Not installed": "No instalado", "Preview": "Vista previa", "Full size": "Tamaño completo" },
};
const keys = new Map(Object.entries(en).map(([key, value]) => [value, key]));
export function text(value: string): string {
  const key = keys.get(value);
  return PHRASES[locale]?.[value] ?? additional[locale]?.[value] ?? (key ? t(key) : value);
}
export function localizeElement(root: HTMLElement): void {
  if (locale === "en") return;
  for (const option of root.querySelectorAll("option")) if (!option.hasAttribute("value")) option.value = option.value;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let node: Node | null;
  while ((node = walker.nextNode())) {
    const original = node.textContent ?? "", trimmed = original.trim();
    const translated = text(trimmed);
    if (translated !== trimmed) node.textContent = original.replace(trimmed, translated);
  }
  for (const element of [root, ...root.querySelectorAll<HTMLElement>("[title],[placeholder],[aria-label]")]) {
    for (const key of ["title", "placeholder", "aria-label"]) {
      const value = element.getAttribute(key); if (value) element.setAttribute(key, text(value));
    }
  }
}
