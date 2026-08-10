const TRANSPORT_ROUTE_COLORS = [
  "#00e5ff",
  "#ff2bd6",
  "#7cff00",
  "#ff9f1c",
  "#8b5cf6",
  "#faff00",
  "#00ffa3",
  "#ff3864",
  "#2d7dff",
  "#ff7a00",
  "#bf00ff",
  "#38f8c9",
  "#b6ff00",
  "#ff66cc",
  "#60a5fa",
  "#facc15",
  "#34d399",
  "#e879f9",
  "#f97316",
  "#67e8f9",
  "#c084fc",
  "#4ade80",
  "#fde047",
  "#f43f5e",
  "#2dd4bf",
  "#a78bfa",
  "#fb7185",
  "#22d3ee",
  "#a3ff12",
  "#ff5e00",
  "#00ffcc",
  "#ff00a8",
];

const GENERATED_COLOR_HUE_STEP = 137.508;

export function compareTransportRouteLines(first: string, second: string) {
  const firstNumber = Number.parseInt(first, 10);
  const secondNumber = Number.parseInt(second, 10);

  if (Number.isFinite(firstNumber) && Number.isFinite(secondNumber) && firstNumber !== secondNumber) {
    return firstNumber - secondNumber;
  }

  return first.localeCompare(second, "es-AR", { numeric: true });
}

function hueToRgbChannel(p: number, q: number, hue: number) {
  if (hue < 0) {
    hue += 1;
  }

  if (hue > 1) {
    hue -= 1;
  }

  if (hue < 1 / 6) {
    return p + (q - p) * 6 * hue;
  }

  if (hue < 1 / 2) {
    return q;
  }

  if (hue < 2 / 3) {
    return p + (q - p) * (2 / 3 - hue) * 6;
  }

  return p;
}

function hslToHex(hue: number, saturation: number, lightness: number) {
  const normalizedHue = (((hue % 360) + 360) % 360) / 360;
  const normalizedSaturation = Math.max(0, Math.min(100, saturation)) / 100;
  const normalizedLightness = Math.max(0, Math.min(100, lightness)) / 100;
  const q =
    normalizedLightness < 0.5
      ? normalizedLightness * (1 + normalizedSaturation)
      : normalizedLightness + normalizedSaturation - normalizedLightness * normalizedSaturation;
  const p = 2 * normalizedLightness - q;
  const red = hueToRgbChannel(p, q, normalizedHue + 1 / 3);
  const green = hueToRgbChannel(p, q, normalizedHue);
  const blue = hueToRgbChannel(p, q, normalizedHue - 1 / 3);

  return [red, green, blue]
    .map((channel) =>
      Math.round(channel * 255)
        .toString(16)
        .padStart(2, "0"),
    )
    .join("")
    .replace(/^/, "#");
}

function getGeneratedTransportRouteColor(index: number) {
  const generatedIndex = index - TRANSPORT_ROUTE_COLORS.length;
  const hue = (generatedIndex * GENERATED_COLOR_HUE_STEP + 18) % 360;
  const saturation = 92 - (generatedIndex % 3) * 6;
  const lightness = 54 + (generatedIndex % 4) * 4;

  return hslToHex(hue, saturation, lightness);
}

export function getTransportRouteColorByIndex(index: number) {
  if (index < TRANSPORT_ROUTE_COLORS.length) {
    return TRANSPORT_ROUTE_COLORS[index];
  }

  return getGeneratedTransportRouteColor(index);
}

export function getFallbackTransportRouteColor(routeKey: string) {
  let hash = 0;

  for (let index = 0; index < routeKey.length; index += 1) {
    hash = (hash * 31 + routeKey.charCodeAt(index)) >>> 0;
  }

  return getTransportRouteColorByIndex(hash % 256);
}

export function getStableTransportColorScope(availableLines: string[], visibleLines: string[]) {
  return availableLines.length > 0 ? availableLines : visibleLines;
}

export function createTransportLineColorMap(lines: string[]) {
  const uniqueLines = Array.from(new Set(lines.filter(Boolean))).sort(compareTransportRouteLines);

  return new Map(uniqueLines.map((line, index) => [line, getTransportRouteColorByIndex(index)]));
}
