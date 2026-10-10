/*
 Estilo del mapa por tema y tiempos de las animaciones del mapa (lógica pura).

 Los `styles` locales de Google Maps solo aplican a mapas SIN Map ID: con un Map ID el estilo
 vive en la nube (Cloud Console) y los `styles` se ignoran. Hoy NetworkMap no pasa mapId, así
 que usamos `styles`; si algún día se usa un Map ID, hay que pedir `colorScheme: "DARK"` en su lugar.
*/

export type MapTheme = "light" | "dark";

type Style = google.maps.MapTypeStyle;

// Base minimalista: sin puntos de interés ni transporte, colores apagados
const BASE: Style[] = [
  { featureType: "poi", stylers: [{ visibility: "off" }] },
  { featureType: "transit", stylers: [{ visibility: "off" }] },
  { featureType: "road", elementType: "labels.icon", stylers: [{ visibility: "off" }] },
];

const LIGHT: Style[] = [
  ...BASE,
  { elementType: "geometry", stylers: [{ saturation: -55 }] },
  { featureType: "water", elementType: "geometry", stylers: [{ color: "#d6e2ea" }] },
];

// Oscuro desaturado: fondo casi negro, carreteras algo más claras, agua azul muy oscura
const DARK: Style[] = [
  ...BASE,
  { elementType: "geometry", stylers: [{ color: "#17181b" }] },
  { elementType: "labels.text.fill", stylers: [{ color: "#8b8e96" }] },
  { elementType: "labels.text.stroke", stylers: [{ color: "#17181b" }] },
  { featureType: "administrative", elementType: "geometry", stylers: [{ color: "#2c2d32" }] },
  { featureType: "landscape", elementType: "geometry", stylers: [{ color: "#1a1b1e" }] },
  { featureType: "road", elementType: "geometry", stylers: [{ color: "#2a2b30" }] },
  { featureType: "road.highway", elementType: "geometry", stylers: [{ color: "#35363c" }] },
  { featureType: "road", elementType: "geometry.stroke", stylers: [{ color: "#17181b" }] },
  { featureType: "water", elementType: "geometry", stylers: [{ color: "#0f1a24" }] },
  { featureType: "water", elementType: "labels.text.fill", stylers: [{ color: "#4b5a68" }] },
];

export function mapStyles(theme: MapTheme): Style[] {
  return theme === "dark" ? DARK : LIGHT;
}

/**
 Retardo (s) del elemento `index` de `count` en una cascada que dura `total` s en conjunto.
 Así 10 o 400 elementos terminan de aparecer en el mismo tiempo.
*/
export function cascadeDelay(index: number, count: number, total: number): number {
  if (count <= 1 || index <= 0) return 0;
  return (Math.min(index, count - 1) / (count - 1)) * total;
}
