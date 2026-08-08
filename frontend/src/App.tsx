import { useEffect, useMemo, useState } from "react";

import { fetchIndicators, fetchTerritoryOptions } from "./api";
import { MapView } from "./components/MapView";
import {
  DEFAULT_INDICATOR,
  getAvailableIndicatorGroups,
  getIndicatorOption,
  type IndicatorOption,
} from "./indicatorCatalog";
import type { ColorMode, LayerSettings, TerritoryOption, ViewMode } from "./types";

const YEAR = 2022;

const DEFAULT_LAYER_SETTINGS: LayerSettings = {
  indicator: DEFAULT_INDICATOR,
  colorMode: "indicator",
  viewMode: "flat",
  provinceIds: [],
};

const COLOR_MODE_LABELS: Record<ColorMode, string> = {
  indicator: "Valor",
  province: "Provincia",
};

const VIEW_MODE_LABELS: Record<ViewMode, string> = {
  flat: "2D",
  extruded: "3D",
};

function areArraysEqual(first: string[], second: string[]) {
  return first.length === second.length && first.every((value, index) => value === second[index]);
}

function areLayerSettingsEqual(first: LayerSettings, second: LayerSettings) {
  return (
    first.indicator === second.indicator &&
    first.colorMode === second.colorMode &&
    first.viewMode === second.viewMode &&
    areArraysEqual(first.provinceIds, second.provinceIds)
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

function getProvinceLabel(provinceIds: string[], territoryOptions: TerritoryOption[]) {
  if (provinceIds.length === 0) {
    return "Todas";
  }

  if (provinceIds.length === 1) {
    return territoryOptions.find((territory) => territory.id === provinceIds[0])?.name ?? "1 provincia";
  }

  return `${provinceIds.length} provincias`;
}

export function App() {
  const [indicators, setIndicators] = useState<string[]>([]);
  const [territoryOptions, setTerritoryOptions] = useState<TerritoryOption[]>([]);
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
    Promise.all([fetchIndicators(), fetchTerritoryOptions()])
      .then(([loadedIndicators, loadedTerritories]) => {
        const initialLayer = getInitialLayerSettings(loadedIndicators);

        setIndicators(loadedIndicators);
        setTerritoryOptions(loadedTerritories);
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

  function toggleProvince(provinceId: string) {
    setDraftLayer((currentLayer) => {
      const isSelected = currentLayer.provinceIds.includes(provinceId);
      const provinceIds = isSelected
        ? currentLayer.provinceIds.filter((currentProvinceId) => currentProvinceId !== provinceId)
        : [
            ...currentLayer.provinceIds,
            provinceId,
          ].sort((first, second) => {
            const firstIndex = territoryOptions.findIndex((territory) => territory.id === first);
            const secondIndex = territoryOptions.findIndex((territory) => territory.id === second);
            return firstIndex - secondIndex;
          });

      return {
        ...currentLayer,
        provinceIds,
      };
    });
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
          <p>Indicadores provinciales - Ano {YEAR}</p>
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

        <section className="control-block" aria-labelledby="province-heading">
          <div className="control-title">
            <label id="province-heading">Provincias</label>
            <span>{getProvinceLabel(draftLayer.provinceIds, territoryOptions)}</span>
          </div>

          <div className="province-actions">
            <button
              className={draftLayer.provinceIds.length === 0 ? "province-action is-active" : "province-action"}
              type="button"
              onClick={() => updateDraftLayer({ provinceIds: [] })}
            >
              Todas
            </button>
          </div>

          <div className="province-list">
            {territoryOptions.map((territory) => (
              <button
                aria-pressed={draftLayer.provinceIds.includes(territory.id)}
                className={
                  draftLayer.provinceIds.includes(territory.id) ? "province-button is-active" : "province-button"
                }
                key={territory.id}
                type="button"
                onClick={() => toggleProvince(territory.id)}
              >
                {territory.name}
              </button>
            ))}
          </div>
        </section>

        <section className="control-grid" aria-label="Opciones de visualizacion">
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
            Color: {COLOR_MODE_LABELS[appliedLayer.colorMode]} - Vista: {VIEW_MODE_LABELS[appliedLayer.viewMode]}
          </p>
          <p>Provincias: {getProvinceLabel(appliedLayer.provinceIds, territoryOptions)}</p>
        </section>

        {indicatorError && <p className="error">{indicatorError}</p>}
        {mapError && <p className="error">{mapError}</p>}
      </aside>

      <MapView
        colorMode={appliedLayer.colorMode}
        indicator={appliedLayer.indicator}
        onDataError={setMapError}
        provinceIds={appliedLayer.provinceIds}
        viewMode={appliedLayer.viewMode}
        year={YEAR}
      />
    </>
  );
}
