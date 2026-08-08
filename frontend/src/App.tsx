import { useEffect, useMemo, useState } from "react";

import { fetchIndicators, fetchTerritoryLevels, fetchTerritoryOptions } from "./api";
import { MapView } from "./components/MapView";
import { getAvailableIndicatorGroups, getIndicatorOption, type IndicatorOption } from "./indicatorCatalog";
import {
  DEFAULT_LAYER_SETTINGS,
  FALLBACK_TERRITORY_LEVELS,
  areLayerSettingsEqual,
  getDefaultIndicator,
  getInitialLayerSettings,
  getInitialTerritoryLevel,
  getTerritoryLevelsOrFallback,
  getTerritorySelectionLabel,
} from "./territoryMetadata";
import type { ColorMode, LayerSettings, TerritoryLevel, TerritoryLevelId, TerritoryOption, ViewMode } from "./types";

const YEAR = 2022;

const COLOR_MODE_LABELS: Record<ColorMode, string> = {
  indicator: "Valor",
  territory: "Territorio",
};

const VIEW_MODE_LABELS: Record<ViewMode, string> = {
  flat: "2D",
  extruded: "3D",
};

export function App() {
  const [indicatorsByLevel, setIndicatorsByLevel] = useState<Partial<Record<TerritoryLevelId, string[]>>>({});
  const [territoryLevels, setTerritoryLevels] = useState<TerritoryLevel[]>(FALLBACK_TERRITORY_LEVELS);
  const [territoryOptionsByLevel, setTerritoryOptionsByLevel] = useState<
    Partial<Record<TerritoryLevelId, TerritoryOption[]>>
  >({});
  const [draftLayer, setDraftLayer] = useState<LayerSettings>(DEFAULT_LAYER_SETTINGS);
  const [appliedLayer, setAppliedLayer] = useState<LayerSettings>(DEFAULT_LAYER_SETTINGS);
  const [metadataError, setMetadataError] = useState<string | null>(null);
  const [mapError, setMapError] = useState<string | null>(null);

  const indicators = indicatorsByLevel[draftLayer.territoryLevel] ?? [];
  const appliedIndicators = indicatorsByLevel[appliedLayer.territoryLevel] ?? indicators;
  const availableIndicatorGroups = useMemo(() => getAvailableIndicatorGroups(indicators), [indicators]);
  const appliedIndicatorGroups = useMemo(() => getAvailableIndicatorGroups(appliedIndicators), [appliedIndicators]);
  const selectedDraftIndicator =
    getIndicatorOption(draftLayer.indicator, availableIndicatorGroups) ??
    availableIndicatorGroups[0]?.indicators[0] ??
    ({ id: draftLayer.indicator, label: draftLayer.indicator } satisfies IndicatorOption);
  const selectedAppliedIndicator =
    getIndicatorOption(appliedLayer.indicator, appliedIndicatorGroups) ??
    ({ id: appliedLayer.indicator, label: appliedLayer.indicator } satisfies IndicatorOption);
  const selectedDraftLevel =
    territoryLevels.find((level) => level.id === draftLayer.territoryLevel) ?? FALLBACK_TERRITORY_LEVELS[0];
  const selectedAppliedLevel =
    territoryLevels.find((level) => level.id === appliedLayer.territoryLevel) ?? FALLBACK_TERRITORY_LEVELS[0];
  const territoryOptions = territoryOptionsByLevel[draftLayer.territoryLevel] ?? [];
  const appliedTerritoryOptions = territoryOptionsByLevel[appliedLayer.territoryLevel] ?? [];
  const hasPendingChanges = !areLayerSettingsEqual(draftLayer, appliedLayer);

  useEffect(() => {
    async function loadInitialMetadata() {
      try {
        const levels = await getTerritoryLevelsOrFallback(fetchTerritoryLevels);
        const initialTerritoryLevel = getInitialTerritoryLevel(levels);
        const [loadedIndicators, loadedTerritories] = await Promise.all([
          fetchIndicators(initialTerritoryLevel),
          fetchTerritoryOptions(initialTerritoryLevel),
        ]);
        const initialLayer = getInitialLayerSettings(loadedIndicators, initialTerritoryLevel);

        setTerritoryLevels(levels);
        setIndicatorsByLevel({ [initialTerritoryLevel]: loadedIndicators });
        setTerritoryOptionsByLevel({ [initialTerritoryLevel]: loadedTerritories });
        setDraftLayer(initialLayer);
        setAppliedLayer(initialLayer);
        setMetadataError(null);
      } catch (caughtError) {
        setMetadataError(caughtError instanceof Error ? caughtError.message : "No se pudieron cargar los metadatos.");
      }
    }

    loadInitialMetadata();
  }, []);

  useEffect(() => {
    let isCancelled = false;

    Promise.all([fetchIndicators(draftLayer.territoryLevel), fetchTerritoryOptions(draftLayer.territoryLevel)])
      .then(([loadedIndicators, loadedTerritories]) => {
        if (!isCancelled) {
          setIndicatorsByLevel((currentIndicators) => ({
            ...currentIndicators,
            [draftLayer.territoryLevel]: loadedIndicators,
          }));
          setTerritoryOptionsByLevel((currentOptions) => ({
            ...currentOptions,
            [draftLayer.territoryLevel]: loadedTerritories,
          }));
          setDraftLayer((currentLayer) => {
            if (currentLayer.territoryLevel !== draftLayer.territoryLevel) {
              return currentLayer;
            }

            if (loadedIndicators.includes(currentLayer.indicator)) {
              return currentLayer;
            }

            return {
              ...currentLayer,
              indicator: getDefaultIndicator(loadedIndicators),
            };
          });
          setMetadataError(null);
        }
      })
      .catch((caughtError: Error) => {
        if (!isCancelled) {
          setMetadataError(caughtError.message);
        }
      });

    return () => {
      isCancelled = true;
    };
  }, [draftLayer.territoryLevel]);

  function updateDraftLayer(nextLayer: Partial<LayerSettings>) {
    setDraftLayer((currentLayer) => ({
      ...currentLayer,
      ...nextLayer,
    }));
  }

  function updateTerritoryLevel(territoryLevel: TerritoryLevelId) {
    updateDraftLayer({
      territoryLevel,
      territoryIds: [],
    });
  }

  function toggleTerritory(territoryId: string) {
    setDraftLayer((currentLayer) => {
      const isSelected = currentLayer.territoryIds.includes(territoryId);
      const territoryIds = isSelected
        ? currentLayer.territoryIds.filter((currentTerritoryId) => currentTerritoryId !== territoryId)
        : [
            ...currentLayer.territoryIds,
            territoryId,
          ].sort((first, second) => {
            const firstIndex = territoryOptions.findIndex((territory) => territory.id === first);
            const secondIndex = territoryOptions.findIndex((territory) => territory.id === second);
            return firstIndex - secondIndex;
          });

      return {
        ...currentLayer,
        territoryIds,
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
          <span className="eyebrow">Atlas territorial</span>
          <h1>Territorio Argentino</h1>
          <p>Indicadores territoriales - Ano {YEAR}</p>
        </header>

        <section className="control-block" aria-labelledby="level-heading">
          <div className="control-title">
            <label id="level-heading">Nivel territorial</label>
            <span>{selectedDraftLevel.label}</span>
          </div>

          <div className="segmented territory-level-list" role="group" aria-label="Nivel territorial">
            {territoryLevels.map((level) => (
              <button
                aria-pressed={level.id === draftLayer.territoryLevel}
                className={level.id === draftLayer.territoryLevel ? "segment is-active" : "segment"}
                disabled={level.territory_count === 0}
                key={level.id}
                type="button"
                onClick={() => updateTerritoryLevel(level.id)}
              >
                {level.label}
              </button>
            ))}
          </div>
        </section>

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

        <section className="control-block" aria-labelledby="territory-heading">
          <div className="control-title">
            <label id="territory-heading">Territorios</label>
            <span>{getTerritorySelectionLabel(draftLayer.territoryIds, territoryOptions)}</span>
          </div>

          <div className="territory-actions">
            <button
              className={draftLayer.territoryIds.length === 0 ? "territory-action is-active" : "territory-action"}
              type="button"
              onClick={() => updateDraftLayer({ territoryIds: [] })}
            >
              Todos
            </button>
          </div>

          <div className="territory-list">
            {territoryOptions.map((territory) => (
              <button
                aria-pressed={draftLayer.territoryIds.includes(territory.id)}
                className={
                  draftLayer.territoryIds.includes(territory.id) ? "territory-button is-active" : "territory-button"
                }
                key={territory.id}
                type="button"
                onClick={() => toggleTerritory(territory.id)}
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
                aria-pressed={draftLayer.colorMode === "territory"}
                className={draftLayer.colorMode === "territory" ? "segment is-active" : "segment"}
                type="button"
                onClick={() => updateDraftLayer({ colorMode: "territory" })}
              >
                Territorio
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
            Nivel: {selectedAppliedLevel.label} - Color: {COLOR_MODE_LABELS[appliedLayer.colorMode]} - Vista:{" "}
            {VIEW_MODE_LABELS[appliedLayer.viewMode]}
          </p>
          <p>Territorios: {getTerritorySelectionLabel(appliedLayer.territoryIds, appliedTerritoryOptions)}</p>
        </section>

        {metadataError && <p className="error">{metadataError}</p>}
        {mapError && <p className="error">{mapError}</p>}
      </aside>

      <MapView
        colorMode={appliedLayer.colorMode}
        indicator={appliedLayer.indicator}
        onDataError={setMapError}
        territoryIds={appliedLayer.territoryIds}
        territoryLevel={appliedLayer.territoryLevel}
        viewMode={appliedLayer.viewMode}
        year={YEAR}
      />
    </>
  );
}
