import type { GeometryMode, ViewMode } from "./types";

export type CameraPreset = {
  pitch: number;
  bearing: number;
  duration: number;
};

export type TransportVisualMode = "standard" | "neon";

export type LayerVisibility = {
  fill: "visible" | "none";
  outline: "visible" | "none";
  surfaceExtrusion: "visible" | "none";
  barFill: "visible" | "none";
  barExtrusion: "visible" | "none";
  barOutline: "visible" | "none";
};

const CAMERA_DURATION_MS = 350;
const EXTRUDED_CAMERA_DURATION_MS = 650;

export function getCameraPreset(viewMode: ViewMode): CameraPreset {
  if (viewMode === "extruded") {
    return {
      pitch: 58,
      bearing: -28,
      duration: EXTRUDED_CAMERA_DURATION_MS,
    };
  }

  return {
    pitch: 0,
    bearing: 0,
    duration: CAMERA_DURATION_MS,
  };
}

export function getTransportVisualMode(viewMode: ViewMode): TransportVisualMode {
  return viewMode === "extruded" ? "neon" : "standard";
}

export function getTransportCameraPreset(viewMode: ViewMode): CameraPreset {
  if (viewMode === "extruded") {
    return {
      pitch: 60,
      bearing: -30,
      duration: EXTRUDED_CAMERA_DURATION_MS,
    };
  }

  return getCameraPreset("flat");
}

export function getEffectiveGeometryMode(
  viewMode: ViewMode,
  geometryMode: GeometryMode,
  hasBarGeometry: boolean,
): GeometryMode {
  if (viewMode !== "extruded") {
    return "surface";
  }

  return geometryMode === "bars" && hasBarGeometry ? "bars" : "surface";
}

export function getLayerVisibility(
  viewMode: ViewMode,
  geometryMode: GeometryMode,
  hasBarGeometry: boolean,
): LayerVisibility {
  const effectiveGeometryMode = getEffectiveGeometryMode(viewMode, geometryMode, hasBarGeometry);

  return {
    fill: viewMode === "flat" ? "visible" : "none",
    outline: effectiveGeometryMode === "bars" ? "none" : "visible",
    surfaceExtrusion: viewMode === "extruded" && effectiveGeometryMode === "surface" ? "visible" : "none",
    barFill: viewMode === "extruded" && effectiveGeometryMode === "bars" ? "visible" : "none",
    barExtrusion: viewMode === "extruded" && effectiveGeometryMode === "bars" ? "visible" : "none",
    barOutline: viewMode === "extruded" && effectiveGeometryMode === "bars" ? "visible" : "none",
  };
}
