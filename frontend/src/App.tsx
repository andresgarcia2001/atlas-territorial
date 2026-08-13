import { useEffect, useMemo, useState, type CSSProperties } from "react";

import { fetchIndicators, fetchTerritoryLevels, fetchTerritoryOptions, fetchTransportRouteLines } from "./api";
import { MapView } from "./components/MapView";
import { getAvailableIndicatorGroups, getIndicatorLabel, getIndicatorOption, type IndicatorOption } from "./indicatorCatalog";
import {
  DEFAULT_LAYER_SETTINGS,
  FALLBACK_TERRITORY_LEVELS,
  areLayerSettingsEqual,
  getDefaultIndicator,
  getDefaultColorMode,
  getDefaultTerritoryParentId,
  getDefaultTerritoryProvinceId,
  getInitialLayerSettings,
  getInitialTerritoryLevel,
  getTerritoryOptionsKey,
  getTerritoryLevelsOrFallback,
  getTerritorySelectionLabel,
  getTransportRouteLineSelectionLabel,
  shouldUseParentTerritoryFilter,
  shouldUseProvinceTerritoryFilter,
} from "./territoryMetadata";
import {
  compareTransportRouteLines,
  createTransportLineColorMap,
  getStableTransportColorScope,
} from "./transportColors";
import type {
  ColorMode,
  GeometryMode,
  HeightMode,
  LayerSettings,
  TerritoryLevel,
  TerritoryLevelId,
  TerritoryOption,
  TerritoryLayerMode,
  TransportOverlayMode,
  TransportRouteLineOption,
  ViewMode,
} from "./types";

const YEAR = 2022;
const BA_BUS_ROUTES_SOURCE = "BA DATA colectivos recorridos";

const COLOR_MODE_LABELS: Record<ColorMode, string> = {
  indicator: "Valor",
  territory: "Territorio",
};

const VIEW_MODE_LABELS: Record<ViewMode, string> = {
  flat: "2D",
  extruded: "3D",
};

const GEOMETRY_MODE_LABELS: Record<GeometryMode, string> = {
  surface: "Relieve",
  bars: "Barras",
};

const HEIGHT_MODE_LABELS: Record<HeightMode, string> = {
  indicator: "Dato elegido",
  uniform: "Uniforme",
  visual: "Visual",
};

function getHeightModeLabel(heightMode: HeightMode, indicatorLabel: string, hasIndicators: boolean) {
  if (heightMode === "indicator") {
    return hasIndicators ? indicatorLabel : "Sin datos";
  }

  return HEIGHT_MODE_LABELS[heightMode];
}

const TERRITORY_LAYER_LABELS: Record<TerritoryLayerMode, string> = {
  visible: "Visible",
  hidden: "Oculto",
};

const TRANSPORT_OVERLAY_LABELS: Record<TransportOverlayMode, string> = {
  none: "Sin transporte",
  ba_bus_routes: "Colectivos BA",
};

const MAX_VISIBLE_TERRITORY_OPTIONS = 240;
const EMPTY_TERRITORY_OPTIONS: TerritoryOption[] = [];

function normalizeSearchText(value: string) {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

export function App() {
  const [indicatorsByLevel, setIndicatorsByLevel] = useState<Partial<Record<TerritoryLevelId, string[]>>>({});
  const [territoryLevels, setTerritoryLevels] = useState<TerritoryLevel[]>(FALLBACK_TERRITORY_LEVELS);
  const [territoryOptionsByKey, setTerritoryOptionsByKey] = useState<Record<string, TerritoryOption[]>>({});
  const [transportRouteLines, setTransportRouteLines] = useState<TransportRouteLineOption[]>([]);
  const [draftLayer, setDraftLayer] = useState<LayerSettings>(DEFAULT_LAYER_SETTINGS);
  const [appliedLayer, setAppliedLayer] = useState<LayerSettings>(DEFAULT_LAYER_SETTINGS);
  const [territorySearch, setTerritorySearch] = useState("");
  const [metadataError, setMetadataError] = useState<string | null>(null);
  const [mapError, setMapError] = useState<string | null>(null);

  const indicators = indicatorsByLevel[draftLayer.territoryLevel] ?? [];
  const appliedIndicators = indicatorsByLevel[appliedLayer.territoryLevel] ?? indicators;
  const availableIndicatorGroups = useMemo(() => getAvailableIndicatorGroups(indicators), [indicators]);
  const appliedIndicatorGroups = useMemo(() => getAvailableIndicatorGroups(appliedIndicators), [appliedIndicators]);
  const hasDraftIndicators = indicators.length > 0;
  const hasAppliedIndicators = appliedIndicators.length > 0;
  const selectedDraftIndicator =
    getIndicatorOption(draftLayer.indicator, availableIndicatorGroups) ??
    availableIndicatorGroups[0]?.indicators[0] ??
    ({
      id: draftLayer.indicator,
      label: hasDraftIndicators ? getIndicatorLabel(draftLayer.indicator) : "Sin indicadores",
    } satisfies IndicatorOption);
  const selectedAppliedIndicator =
    getIndicatorOption(appliedLayer.indicator, appliedIndicatorGroups) ??
    ({
      id: appliedLayer.indicator,
      label: hasAppliedIndicators ? getIndicatorLabel(appliedLayer.indicator) : "Sin indicadores",
    } satisfies IndicatorOption);
  const selectedDraftLevel =
    territoryLevels.find((level) => level.id === draftLayer.territoryLevel) ?? FALLBACK_TERRITORY_LEVELS[0];
  const selectedAppliedLevel =
    territoryLevels.find((level) => level.id === appliedLayer.territoryLevel) ?? FALLBACK_TERRITORY_LEVELS[0];
  const provinceTerritoryOptions =
    territoryOptionsByKey[getTerritoryOptionsKey("province")] ?? EMPTY_TERRITORY_OPTIONS;
  const shouldShowProvinceTerritoryFilter = shouldUseProvinceTerritoryFilter(draftLayer.territoryLevel);
  const shouldShowParentTerritoryFilter = shouldUseParentTerritoryFilter(draftLayer.territoryLevel);
  const selectedDraftProvinceTerritory = provinceTerritoryOptions.find(
    (territory) => territory.id === draftLayer.territoryProvinceId,
  );
  const selectedAppliedProvinceTerritory = provinceTerritoryOptions.find(
    (territory) => territory.id === appliedLayer.territoryProvinceId,
  );
  const parentTerritoryOptionsKey = getTerritoryOptionsKey("municipality", draftLayer.territoryProvinceId);
  const appliedParentTerritoryOptionsKey = getTerritoryOptionsKey("municipality", appliedLayer.territoryProvinceId);
  const cachedParentTerritoryOptions = territoryOptionsByKey[parentTerritoryOptionsKey];
  const parentTerritoryOptions = shouldShowParentTerritoryFilter
    ? cachedParentTerritoryOptions ?? EMPTY_TERRITORY_OPTIONS
    : EMPTY_TERRITORY_OPTIONS;
  const appliedParentTerritoryOptions = shouldUseParentTerritoryFilter(appliedLayer.territoryLevel)
    ? territoryOptionsByKey[appliedParentTerritoryOptionsKey] ?? EMPTY_TERRITORY_OPTIONS
    : EMPTY_TERRITORY_OPTIONS;
  const isLoadingParentTerritoryOptions =
    shouldShowParentTerritoryFilter &&
    Boolean(draftLayer.territoryProvinceId) &&
    cachedParentTerritoryOptions === undefined;
  const selectedDraftParentTerritory = parentTerritoryOptions.find(
    (territory) => territory.id === draftLayer.territoryParentId,
  );
  const selectedAppliedParentTerritory = appliedParentTerritoryOptions.find(
    (territory) => territory.id === appliedLayer.territoryParentId,
  );
  const territoryOptionsParentId = shouldShowParentTerritoryFilter ? draftLayer.territoryParentId : null;
  const appliedTerritoryOptionsParentId = shouldUseParentTerritoryFilter(appliedLayer.territoryLevel)
    ? appliedLayer.territoryParentId
    : null;
  const territoryOptionsKey = getTerritoryOptionsKey(draftLayer.territoryLevel, territoryOptionsParentId);
  const appliedTerritoryOptionsKey = getTerritoryOptionsKey(
    appliedLayer.territoryLevel,
    appliedTerritoryOptionsParentId,
  );
  const territoryOptions = territoryOptionsByKey[territoryOptionsKey] ?? EMPTY_TERRITORY_OPTIONS;
  const appliedTerritoryOptions = territoryOptionsByKey[appliedTerritoryOptionsKey] ?? EMPTY_TERRITORY_OPTIONS;
  const normalizedTerritorySearch = normalizeSearchText(territorySearch);
  const filteredTerritoryOptions = normalizedTerritorySearch
    ? territoryOptions.filter((territory) => normalizeSearchText(territory.name).includes(normalizedTerritorySearch))
    : territoryOptions;
  const visibleTerritoryOptions = filteredTerritoryOptions.slice(0, MAX_VISIBLE_TERRITORY_OPTIONS);
  const hiddenTerritoryOptionCount = Math.max(0, filteredTerritoryOptions.length - visibleTerritoryOptions.length);
  const availableTransportRouteLines = useMemo(
    () => transportRouteLines.map((routeLine) => routeLine.line),
    [transportRouteLines],
  );
  const transportLineColorByLine = useMemo(
    () =>
      createTransportLineColorMap(
        getStableTransportColorScope(availableTransportRouteLines, draftLayer.transportRouteLines),
      ),
    [availableTransportRouteLines, draftLayer.transportRouteLines],
  );
  const hasPendingChanges = !areLayerSettingsEqual(draftLayer, appliedLayer);
  const isMissingRequiredProvinceTerritory =
    shouldShowProvinceTerritoryFilter && !draftLayer.territoryProvinceId;
  const isMissingRequiredParentTerritory = shouldShowParentTerritoryFilter && !draftLayer.territoryParentId;
  const isMissingRequiredTerritoryFilter = isMissingRequiredProvinceTerritory || isMissingRequiredParentTerritory;

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
        setTerritoryOptionsByKey({
          [getTerritoryOptionsKey(initialTerritoryLevel)]: loadedTerritories,
        });
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
    const level = draftLayer.territoryLevel;
    const parentId = shouldUseParentTerritoryFilter(level) ? draftLayer.territoryParentId : null;
    const optionsKey = getTerritoryOptionsKey(level, parentId);

    if (shouldUseParentTerritoryFilter(level) && !parentId) {
      fetchIndicators(level)
        .then((loadedIndicators) => {
          if (!isCancelled) {
            setIndicatorsByLevel((currentIndicators) => ({
              ...currentIndicators,
              [level]: loadedIndicators,
            }));
            setTerritoryOptionsByKey((currentOptions) => ({
              ...currentOptions,
              [optionsKey]: EMPTY_TERRITORY_OPTIONS,
            }));
            if (loadedIndicators.length === 0) {
              setDraftLayer((currentLayer) =>
                currentLayer.territoryLevel === level && currentLayer.heightMode === "indicator"
                  ? { ...currentLayer, heightMode: DEFAULT_LAYER_SETTINGS.heightMode }
                  : currentLayer,
              );
            }
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
    }

    Promise.all([fetchIndicators(level), fetchTerritoryOptions(level, parentId)])
      .then(([loadedIndicators, loadedTerritories]) => {
        if (!isCancelled) {
          setIndicatorsByLevel((currentIndicators) => ({
            ...currentIndicators,
            [level]: loadedIndicators,
          }));
          setTerritoryOptionsByKey((currentOptions) => ({
            ...currentOptions,
            [optionsKey]: loadedTerritories,
          }));
          setDraftLayer((currentLayer) => {
            if (currentLayer.territoryLevel !== level) {
              return currentLayer;
            }

            if (loadedIndicators.includes(currentLayer.indicator)) {
              return currentLayer;
            }

            return {
              ...currentLayer,
              indicator: getDefaultIndicator(loadedIndicators),
              colorMode: getDefaultColorMode(loadedIndicators),
              heightMode:
                loadedIndicators.length === 0 && currentLayer.heightMode === "indicator"
                  ? DEFAULT_LAYER_SETTINGS.heightMode
                  : currentLayer.heightMode,
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
  }, [draftLayer.territoryLevel, draftLayer.territoryParentId]);

  useEffect(() => {
    if (shouldUseProvinceTerritoryFilter(draftLayer.territoryLevel) && !draftLayer.territoryProvinceId) {
      updateDraftLayer({
        territoryProvinceId: provinceTerritoryOptions[0]?.id ?? null,
        territoryParentId: null,
        territoryIds: [],
      });
    }
  }, [draftLayer.territoryLevel, draftLayer.territoryProvinceId, provinceTerritoryOptions]);

  useEffect(() => {
    let isCancelled = false;

    if (!shouldUseProvinceTerritoryFilter(draftLayer.territoryLevel) || !draftLayer.territoryProvinceId) {
      return () => {
        isCancelled = true;
      };
    }

    const optionsKey = getTerritoryOptionsKey("municipality", draftLayer.territoryProvinceId);

    if (cachedParentTerritoryOptions) {
      if (
        !draftLayer.territoryParentId ||
        !cachedParentTerritoryOptions.some((territory) => territory.id === draftLayer.territoryParentId)
      ) {
        updateDraftLayer({
          territoryParentId: cachedParentTerritoryOptions[0]?.id ?? null,
          territoryIds: [],
        });
      }

      return () => {
        isCancelled = true;
      };
    }

    fetchTerritoryOptions("municipality", draftLayer.territoryProvinceId)
      .then((loadedMunicipalities) => {
        if (isCancelled) {
          return;
        }

        setTerritoryOptionsByKey((currentOptions) => ({
          ...currentOptions,
          [optionsKey]: loadedMunicipalities,
        }));
        setDraftLayer((currentLayer) => {
          if (
            currentLayer.territoryLevel !== draftLayer.territoryLevel ||
            currentLayer.territoryProvinceId !== draftLayer.territoryProvinceId
          ) {
            return currentLayer;
          }

          if (
            currentLayer.territoryParentId &&
            loadedMunicipalities.some((territory) => territory.id === currentLayer.territoryParentId)
          ) {
            return currentLayer;
          }

          return {
            ...currentLayer,
            territoryParentId: loadedMunicipalities[0]?.id ?? null,
            territoryIds: [],
          };
        });
        setMetadataError(null);
      })
      .catch((caughtError: Error) => {
        if (!isCancelled) {
          setMetadataError(caughtError.message);
        }
      });

    return () => {
      isCancelled = true;
    };
  }, [
    draftLayer.territoryLevel,
    draftLayer.territoryParentId,
    draftLayer.territoryProvinceId,
    cachedParentTerritoryOptions,
  ]);

  useEffect(() => {
    let isCancelled = false;

    fetchTransportRouteLines(BA_BUS_ROUTES_SOURCE)
      .then((loadedLines) => {
        if (!isCancelled) {
          setTransportRouteLines(loadedLines);
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
  }, []);

  function updateDraftLayer(nextLayer: Partial<LayerSettings>) {
    setDraftLayer((currentLayer) => ({
      ...currentLayer,
      ...nextLayer,
    }));
  }

  function updateTerritoryLevel(territoryLevel: TerritoryLevelId) {
    const territoryProvinceId = getDefaultTerritoryProvinceId(territoryLevel, provinceTerritoryOptions);
    const cachedMunicipalities = territoryProvinceId
      ? territoryOptionsByKey[getTerritoryOptionsKey("municipality", territoryProvinceId)] ?? EMPTY_TERRITORY_OPTIONS
      : EMPTY_TERRITORY_OPTIONS;
    const territoryParentId = getDefaultTerritoryParentId(territoryLevel, cachedMunicipalities);

    updateDraftLayer({
      territoryLevel,
      territoryProvinceId,
      territoryParentId,
      territoryLayerMode: territoryLevel === "electoral_circuit" ? "visible" : draftLayer.territoryLayerMode,
      territoryIds: [],
    });
    setTerritorySearch("");
  }

  function updateTerritoryProvince(territoryProvinceId: string) {
    const cachedMunicipalities =
      territoryOptionsByKey[getTerritoryOptionsKey("municipality", territoryProvinceId)] ?? EMPTY_TERRITORY_OPTIONS;

    updateDraftLayer({
      territoryProvinceId,
      territoryParentId: getDefaultTerritoryParentId(draftLayer.territoryLevel, cachedMunicipalities),
      territoryIds: [],
    });
    setTerritorySearch("");
  }

  function updateTerritoryParent(territoryParentId: string) {
    updateDraftLayer({
      territoryParentId,
      territoryIds: [],
    });
    setTerritorySearch("");
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

  function toggleTransportRouteLine(line: string) {
    setDraftLayer((currentLayer) => {
      const isSelected = currentLayer.transportRouteLines.includes(line);
      const transportRouteLines = isSelected
        ? currentLayer.transportRouteLines.filter((currentLine) => currentLine !== line)
        : [...currentLayer.transportRouteLines, line].sort(compareTransportRouteLines);

      return {
        ...currentLayer,
        transportRouteLines,
      };
    });
  }

  function applyDraftLayer() {
    if (!hasPendingChanges || isMissingRequiredTerritoryFilter) {
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
          <p>Indicadores territoriales - Año {YEAR}</p>
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

          {availableIndicatorGroups.length === 0 ? (
            <p className="empty-state">Sin indicadores para este nivel</p>
          ) : (
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
          )}
        </section>

        {shouldShowProvinceTerritoryFilter && (
          <section className="control-block" aria-labelledby="province-territory-heading">
            <div className="control-title">
              <label id="province-territory-heading">Provincia</label>
              <span>{selectedDraftProvinceTerritory?.name ?? "Seleccionar"}</span>
            </div>

            <div className="parent-territory-list">
              {provinceTerritoryOptions.map((territory) => (
                <button
                  aria-pressed={territory.id === draftLayer.territoryProvinceId}
                  className={
                    territory.id === draftLayer.territoryProvinceId ? "territory-button is-active" : "territory-button"
                  }
                  key={territory.id}
                  type="button"
                  onClick={() => updateTerritoryProvince(territory.id)}
                >
                  {territory.name}
                </button>
              ))}
            </div>
          </section>
        )}

        {shouldShowParentTerritoryFilter && (
          <section className="control-block" aria-labelledby="parent-territory-heading">
            <div className="control-title">
              <label id="parent-territory-heading">Municipio</label>
              <span>{selectedDraftParentTerritory?.name ?? "Seleccionar"}</span>
            </div>

            <div className="parent-territory-list">
              {parentTerritoryOptions.length === 0 ? (
                <p className="empty-state">
                  {isLoadingParentTerritoryOptions ? "Cargando municipios" : "Sin municipios"}
                </p>
              ) : (
                parentTerritoryOptions.map((territory) => (
                  <button
                    aria-pressed={territory.id === draftLayer.territoryParentId}
                    className={
                      territory.id === draftLayer.territoryParentId ? "territory-button is-active" : "territory-button"
                    }
                    key={territory.id}
                    type="button"
                    onClick={() => updateTerritoryParent(territory.id)}
                  >
                    {territory.name}
                  </button>
                ))
              )}
            </div>
          </section>
        )}

        <section className="control-block" aria-labelledby="territory-heading">
          <div className="control-title">
            <label id="territory-heading">Territorios</label>
            <span>{getTerritorySelectionLabel(draftLayer.territoryIds, territoryOptions)}</span>
          </div>

          {territoryOptions.length > 24 && (
            <input
              aria-label="Buscar territorio"
              className="territory-search"
              type="search"
              value={territorySearch}
              onChange={(event) => setTerritorySearch(event.target.value)}
            />
          )}

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
            {visibleTerritoryOptions.map((territory) => (
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
            {hiddenTerritoryOptionCount > 0 && (
              <p className="empty-state">{`${visibleTerritoryOptions.length} de ${filteredTerritoryOptions.length}`}</p>
            )}
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

          <div className="control-block is-compact">
            <div className="control-title">
              <label>3D</label>
            </div>
            <div className="segmented" role="group" aria-label="Geometría 3D">
              <button
                aria-pressed={draftLayer.geometryMode === "surface"}
                className={draftLayer.geometryMode === "surface" ? "segment is-active" : "segment"}
                type="button"
                onClick={() => updateDraftLayer({ geometryMode: "surface" })}
              >
                Relieve
              </button>
              <button
                aria-pressed={draftLayer.geometryMode === "bars"}
                className={draftLayer.geometryMode === "bars" ? "segment is-active" : "segment"}
                type="button"
                onClick={() => updateDraftLayer({ geometryMode: "bars" })}
              >
                Barras
              </button>
            </div>
          </div>
        </section>

        {draftLayer.viewMode === "extruded" && (
          <section className="control-block" aria-labelledby="height-mode-heading">
            <div className="control-title">
              <label id="height-mode-heading">Altura 3D</label>
              <span>{getHeightModeLabel(draftLayer.heightMode, selectedDraftIndicator.label, hasDraftIndicators)}</span>
            </div>
            <div className="segmented height-mode-list" role="group" aria-label="Altura 3D">
              <button
                aria-pressed={draftLayer.heightMode === "indicator"}
                className={draftLayer.heightMode === "indicator" ? "segment is-active" : "segment"}
                disabled={!hasDraftIndicators}
                type="button"
                onClick={() => updateDraftLayer({ heightMode: "indicator" })}
              >
                Dato elegido
              </button>
              <button
                aria-pressed={draftLayer.heightMode === "uniform"}
                className={draftLayer.heightMode === "uniform" ? "segment is-active" : "segment"}
                type="button"
                onClick={() => updateDraftLayer({ heightMode: "uniform" })}
              >
                Uniforme
              </button>
              <button
                aria-pressed={draftLayer.heightMode === "visual"}
                className={draftLayer.heightMode === "visual" ? "segment is-active" : "segment"}
                type="button"
                onClick={() => updateDraftLayer({ heightMode: "visual" })}
              >
                Visual
              </button>
            </div>
          </section>
        )}

        <section className="control-block" aria-labelledby="territory-layer-heading">
          <div className="control-title">
            <label id="territory-layer-heading">Mapa territorial</label>
            <span>{TERRITORY_LAYER_LABELS[draftLayer.territoryLayerMode]}</span>
          </div>
          <div className="segmented" role="group" aria-label="Mapa territorial">
            <button
              aria-pressed={draftLayer.territoryLayerMode === "visible"}
              className={draftLayer.territoryLayerMode === "visible" ? "segment is-active" : "segment"}
              type="button"
              onClick={() => updateDraftLayer({ territoryLayerMode: "visible" })}
            >
              Visible
            </button>
            <button
              aria-pressed={draftLayer.territoryLayerMode === "hidden"}
              className={draftLayer.territoryLayerMode === "hidden" ? "segment is-active" : "segment"}
              type="button"
              onClick={() => updateDraftLayer({ territoryLayerMode: "hidden" })}
            >
              Oculto
            </button>
          </div>
        </section>

        <section className="control-block" aria-labelledby="overlays-heading">
          <div className="control-title">
            <label id="overlays-heading">Overlays</label>
            <span>{TRANSPORT_OVERLAY_LABELS[draftLayer.transportOverlay]}</span>
          </div>
          <div className="segmented" role="group" aria-label="Capas de transporte">
            <button
              aria-pressed={draftLayer.transportOverlay === "none"}
              className={draftLayer.transportOverlay === "none" ? "segment is-active" : "segment"}
              type="button"
              onClick={() => updateDraftLayer({ transportOverlay: "none" })}
            >
              Ninguno
            </button>
            <button
              aria-pressed={draftLayer.transportOverlay === "ba_bus_routes"}
              className={draftLayer.transportOverlay === "ba_bus_routes" ? "segment is-active" : "segment"}
              type="button"
              onClick={() => updateDraftLayer({ transportOverlay: "ba_bus_routes" })}
            >
              Colectivos BA
            </button>
          </div>

          {draftLayer.transportOverlay === "ba_bus_routes" && (
            <div className="transport-lines" aria-labelledby="transport-lines-heading">
              <div className="control-title">
                <label id="transport-lines-heading">Líneas</label>
                <span>{getTransportRouteLineSelectionLabel(draftLayer.transportRouteLines)}</span>
              </div>

              <div className="territory-actions">
                <button
                  className={
                    draftLayer.transportRouteLines.length === 0 ? "territory-action is-active" : "territory-action"
                  }
                  type="button"
                  onClick={() => updateDraftLayer({ transportRouteLines: [] })}
                >
                  Todas
                </button>
              </div>

              <div className="transport-line-list">
                {transportRouteLines.length === 0 ? (
                  <p className="empty-state">Sin líneas cargadas</p>
                ) : (
                  transportRouteLines.map((routeLine) => (
                    <button
                      aria-pressed={draftLayer.transportRouteLines.includes(routeLine.line)}
                      className={
                        draftLayer.transportRouteLines.includes(routeLine.line)
                          ? "transport-line-button is-active"
                          : "transport-line-button"
                      }
                      key={routeLine.line}
                      style={
                        {
                          "--line-color": transportLineColorByLine.get(routeLine.line) ?? "#d7e0da",
                        } as CSSProperties
                      }
                      type="button"
                      onClick={() => toggleTransportRouteLine(routeLine.line)}
                    >
                      <span>{routeLine.line}</span>
                      <small>{routeLine.route_count}</small>
                    </button>
                  ))
                )}
              </div>
            </div>
          )}
        </section>

        <button
          className="apply-button"
          type="button"
          disabled={!hasPendingChanges || isMissingRequiredTerritoryFilter}
          onClick={applyDraftLayer}
        >
          Buscar
        </button>

        <section className="current-layer" aria-label="Capa actual">
          <span>Capa aplicada</span>
          <strong>{selectedAppliedIndicator.label}</strong>
          <p>
            Nivel: {selectedAppliedLevel.label} - Color: {COLOR_MODE_LABELS[appliedLayer.colorMode]} - Vista:{" "}
            {VIEW_MODE_LABELS[appliedLayer.viewMode]} - 3D: {GEOMETRY_MODE_LABELS[appliedLayer.geometryMode]}
          </p>
          {appliedLayer.viewMode === "extruded" && (
            <p>
              Altura 3D:{" "}
              {getHeightModeLabel(appliedLayer.heightMode, selectedAppliedIndicator.label, hasAppliedIndicators)}
            </p>
          )}
          <p>Mapa territorial: {TERRITORY_LAYER_LABELS[appliedLayer.territoryLayerMode]}</p>
          <p>Overlay: {TRANSPORT_OVERLAY_LABELS[appliedLayer.transportOverlay]}</p>
          {appliedLayer.transportOverlay === "ba_bus_routes" && (
            <p>Líneas: {getTransportRouteLineSelectionLabel(appliedLayer.transportRouteLines)}</p>
          )}
          {shouldUseProvinceTerritoryFilter(appliedLayer.territoryLevel) && selectedAppliedProvinceTerritory && (
            <p>Provincia: {selectedAppliedProvinceTerritory.name}</p>
          )}
          {shouldUseParentTerritoryFilter(appliedLayer.territoryLevel) && selectedAppliedParentTerritory && (
            <p>Municipio: {selectedAppliedParentTerritory.name}</p>
          )}
          <p>Territorios: {getTerritorySelectionLabel(appliedLayer.territoryIds, appliedTerritoryOptions)}</p>
        </section>

        {metadataError && <p className="error">{metadataError}</p>}
        {mapError && <p className="error">{mapError}</p>}
      </aside>

      <MapView
        colorMode={appliedLayer.colorMode}
        indicator={appliedLayer.indicator}
        onDataError={setMapError}
        geometryMode={appliedLayer.geometryMode}
        heightMode={appliedLayer.heightMode}
        territoryLayerMode={appliedLayer.territoryLayerMode}
        transportAvailableLines={availableTransportRouteLines}
        transportOverlay={appliedLayer.transportOverlay}
        transportRouteLines={appliedLayer.transportRouteLines}
        territoryIds={appliedLayer.territoryIds}
        territoryLevel={appliedLayer.territoryLevel}
        territoryParentId={appliedLayer.territoryParentId}
        territoryProvinceId={appliedLayer.territoryProvinceId}
        viewMode={appliedLayer.viewMode}
        year={YEAR}
      />
    </>
  );
}
