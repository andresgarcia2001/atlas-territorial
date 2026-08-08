import { useEffect, useMemo, useState } from "react";

import { fetchIndicators } from "./api";
import { MapView } from "./components/MapView";
import {
  DEFAULT_INDICATOR,
  getAvailableIndicatorGroups,
  getIndicatorOption,
  type IndicatorOption,
} from "./indicatorCatalog";
import type { ColorMode, LayerSettings, ViewMode } from "./types";

const YEAR = 2022;

const DEFAULT_LAYER_SETTINGS: LayerSettings = {
  indicator: DEFAULT_INDICATOR,
  colorMode: "indicator",
  viewMode: "flat",
};

const COLOR_MODE_LABELS: Record<ColorMode, string> = {
  indicator: "Valor",
  province: "Provincia",
};

const VIEW_MODE_LABELS: Record<ViewMode, string> = {
  flat: "2D",
  extruded: "3D",
};

function areLayerSettingsEqual(first: LayerSettings, second: LayerSettings) {
  return (
    first.indicator === second.indicator &&
    first.colorMode === second.colorMode &&
    first.viewMode === second.viewMode
  );
}

function getInitialLayerSettings(loadedIndicators: string[]): LayerSettings {
  const loadedGroups = getAvailableIndicatorGroups(loadedIndicators);
  const firstIndicator = loadedGroups[0]?.indicators[0];

  return {
    ...DEFAULT_LAYER_SETTINGS,
    indicator: loadedIndicators.includes(DEFAULT_INDICATOR)
      ? DEFAULT_INDICATOR
      : firstIndicator?.id ?? DEFAULT_INDICATOR,
  };
}

export function App() {
  const [indicators, setIndicators] = useState<string[]>([]);
  const [draftLayer, setDraftLayer] = useState<LayerSettings>(DEFAULT_LAYER_SETTINGS);
  const [appliedLayer, setAppliedLayer] = useState<LayerSettings>(DEFAULT_LAYER_SETTINGS);
  const [indicatorError, setIndicatorError] = useState<string | null>(null);
  const [mapError, setMapError] = useState<string | null>(null);

  const availableIndicatorGroups = useMemo(() => getAvailableIndicatorGroups(indicators), [indicators]);
  const selectedDraftIndicator =
    getIndicatorOption(draftLayer.indicator, availableIndicatorGroups) ??
    availableIndicatorGroups[0]?.indicators[0] ??
    ({ id: draftLayer.indicator, label: draftLayer.indicator } satisfies IndicatorOption);
  const selectedAppliedIndicator =
    getIndicatorOption(appliedLayer.indicator, availableIndicatorGroups) ??
    ({ id: appliedLayer.indicator, label: appliedLayer.indicator } satisfies IndicatorOption);
  const hasPendingChanges = !areLayerSettingsEqual(draftLayer, appliedLayer);

  useEffect(() => {
    fetchIndicators()
      .then((loadedIndicators) => {
        const initialLayer = getInitialLayerSettings(loadedIndicators);

        setIndicators(loadedIndicators);
        setDraftLayer(initialLayer);
        setAppliedLayer(initialLayer);
        setIndicatorError(null);
      })
      .catch((caughtError: Error) => {
        setIndicatorError(caughtError.message);
      });
  }, []);

  function updateDraftLayer(nextLayer: Partial<LayerSettings>) {
    setDraftLayer((currentLayer) => ({
      ...currentLayer,
      ...nextLayer,
    }));
  }

  function applyDraftLayer() {
    if (!hasPendingChanges) {
      return;
    }

    setAppliedLayer(draftLayer);
  }

  return (
    <>
      <aside className="panel" aria-label="Controles del atlas">
        <header className="panel-header">
          <span className="eyebrow">Atlas provincial</span>
          <h1>Territorio Argentino</h1>
          <p>Indicadores provinciales · Año {YEAR}</p>
        </header>

        <section className="control-block" aria-labelledby="indicator-heading">
          <div className="control-title">
            <label id="indicator-heading">Indicador</label>
            <span>{selectedDraftIndicator.label}</span>
          </div>

          <div className="indicator-groups">
            {availableIndicatorGroups.map((group) => (
              <div className="indicator-group" key={group.id}>
                <h2>{group.label}</h2>
                <div className="indicator-list">
                  {group.indicators.map((option) => (
                    <button
                      aria-pressed={option.id === draftLayer.indicator}
                      className={
                        option.id === draftLayer.indicator ? "indicator-button is-active" : "indicator-button"
                      }
                      key={option.id}
                      type="button"
                      onClick={() => updateDraftLayer({ indicator: option.id })}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="control-grid" aria-label="Opciones de visualización">
          <div className="control-block is-compact">
            <div className="control-title">
              <label>Color</label>
            </div>
            <div className="segmented" role="group" aria-label="Color del mapa">
              <button
                aria-pressed={draftLayer.colorMode === "indicator"}
                className={draftLayer.colorMode === "indicator" ? "segment is-active" : "segment"}
                type="button"
                onClick={() => updateDraftLayer({ colorMode: "indicator" })}
              >
                Valor
              </button>
              <button
                aria-pressed={draftLayer.colorMode === "province"}
                className={draftLayer.colorMode === "province" ? "segment is-active" : "segment"}
                type="button"
                onClick={() => updateDraftLayer({ colorMode: "province" })}
              >
                Provincia
              </button>
            </div>
          </div>

          <div className="control-block is-compact">
            <div className="control-title">
              <label>Vista</label>
            </div>
            <div className="segmented" role="group" aria-label="Vista del mapa">
              <button
                aria-pressed={draftLayer.viewMode === "flat"}
                className={draftLayer.viewMode === "flat" ? "segment is-active" : "segment"}
                type="button"
                onClick={() => updateDraftLayer({ viewMode: "flat" })}
              >
                2D
              </button>
              <button
                aria-pressed={draftLayer.viewMode === "extruded"}
                className={draftLayer.viewMode === "extruded" ? "segment is-active" : "segment"}
                type="button"
                onClick={() => updateDraftLayer({ viewMode: "extruded" })}
              >
                3D
              </button>
            </div>
          </div>
        </section>

        <button className="apply-button" type="button" disabled={!hasPendingChanges} onClick={applyDraftLayer}>
          Buscar
        </button>

        <section className="current-layer" aria-label="Capa actual">
          <span>Capa aplicada</span>
          <strong>{selectedAppliedIndicator.label}</strong>
          <p>
            Color: {COLOR_MODE_LABELS[appliedLayer.colorMode]} · Vista: {VIEW_MODE_LABELS[appliedLayer.viewMode]}
          </p>
        </section>

        {indicatorError && <p className="error">{indicatorError}</p>}
        {mapError && <p className="error">{mapError}</p>}
      </aside>

      <MapView
        colorMode={appliedLayer.colorMode}
        indicator={appliedLayer.indicator}
        onDataError={setMapError}
        viewMode={appliedLayer.viewMode}
        year={YEAR}
      />
    </>
  );
}
