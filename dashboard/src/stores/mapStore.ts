/**
 * @file mapStore.ts
 * @description Zustand store for map UI state. Controls viewport (centre, zoom),
 * selected animal highlighting, layer visibility toggles, and the interactive
 * geofence polygon drawing workflow.
 *
 * State:
 * - `center` — Map centre as [longitude, latitude]
 * - `zoom` — Current zoom level
 * - `selectedAnimalId` — Currently focused animal (highlights marker + opens info panel)
 * - `visibleLayers` — Toggle flags for map layers (animals, geofences, heatmap, trails)
 * - `isDrawingFence` — Whether the user is in polygon drawing mode
 * - `drawingCoordinates` — Vertices collected during fence drawing
 *
 * Actions:
 * - `setCenter/setZoom` — Programmatic viewport control
 * - `selectAnimal` — Focus on an animal marker
 * - `toggleLayer` — Show/hide a map layer
 * - `startDrawing/addDrawingPoint/finishDrawing/cancelDrawing` — Geofence creation workflow
 */
import { create } from 'zustand';

interface MapState {
  center: [number, number];
  zoom: number;
  selectedAnimalId: string | null;
  visibleLayers: {
    animals: boolean;
    geofences: boolean;
    heatmap: boolean;
    trails: boolean;
  };
  isDrawingFence: boolean;
  drawingCoordinates: [number, number][];
  setCenter: (center: [number, number]) => void;
  setZoom: (zoom: number) => void;
  selectAnimal: (animalId: string | null) => void;
  toggleLayer: (layer: keyof MapState['visibleLayers']) => void;
  startDrawing: () => void;
  addDrawingPoint: (point: [number, number]) => void;
  finishDrawing: () => [number, number][];
  cancelDrawing: () => void;
}

export const useMapStore = create<MapState>((set, get) => ({
  center: [149.13, -35.28],
  zoom: 13,
  selectedAnimalId: null,
  visibleLayers: {
    animals: true,
    geofences: true,
    heatmap: false,
    trails: false,
  },
  isDrawingFence: false,
  drawingCoordinates: [],

  setCenter: (center) => set({ center }),
  setZoom: (zoom) => set({ zoom }),
  selectAnimal: (animalId) => set({ selectedAnimalId: animalId }),

  toggleLayer: (layer) =>
    set((state) => ({
      visibleLayers: {
        ...state.visibleLayers,
        [layer]: !state.visibleLayers[layer],
      },
    })),

  startDrawing: () => set({ isDrawingFence: true, drawingCoordinates: [] }),

  addDrawingPoint: (point) =>
    set((state) => ({
      drawingCoordinates: [...state.drawingCoordinates, point],
    })),

  finishDrawing: () => {
    const coords = get().drawingCoordinates;
    set({ isDrawingFence: false, drawingCoordinates: [] });
    return coords;
  },

  cancelDrawing: () => set({ isDrawingFence: false, drawingCoordinates: [] }),
}));
