import { useMapStore } from '@/stores/mapStore';
import { useRealtimeStore } from '@/stores/realtimeStore';

export default function MapPage() {
  const { visibleLayers, toggleLayer, isDrawingFence, startDrawing, cancelDrawing } = useMapStore();
  const positions = useRealtimeStore((state) => state.positions);
  const animalCount = positions.size;

  return (
    <div className="h-full flex flex-col">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-2 bg-white border-b">
        <div className="flex items-center gap-4">
          <h2 className="text-lg font-semibold text-gray-800">Live Map</h2>
          <div className="flex items-center gap-2">
            {(Object.keys(visibleLayers) as Array<keyof typeof visibleLayers>).map((layer) => (
              <button
                key={layer}
                onClick={() => toggleLayer(layer)}
                className={`px-3 py-1 text-xs rounded-full border transition-colors ${
                  visibleLayers[layer]
                    ? 'bg-brand-100 border-brand-500 text-brand-700'
                    : 'bg-gray-100 border-gray-300 text-gray-600'
                }`}
              >
                {layer}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-3">
          {!isDrawingFence ? (
            <button
              onClick={startDrawing}
              className="px-3 py-1 text-sm bg-brand-600 text-white rounded-lg hover:bg-brand-700"
            >
              Draw Fence
            </button>
          ) : (
            <button
              onClick={cancelDrawing}
              className="px-3 py-1 text-sm bg-red-600 text-white rounded-lg hover:bg-red-700"
            >
              Cancel Drawing
            </button>
          )}
        </div>
      </div>

      {/* Map container */}
      <div className="flex-1 relative bg-gray-200">
        <div
          id="map-container"
          className="absolute inset-0 flex items-center justify-center text-gray-500"
        >
          {/* MapLibre GL JS will mount here */}
          <p className="text-center">
            <span className="block text-4xl mb-2">🗺️</span>
            Map View - MapLibre GL JS
          </p>
        </div>
      </div>

      {/* Status bar */}
      <div className="flex items-center justify-between px-4 py-2 bg-white border-t text-sm text-gray-600">
        <div className="flex items-center gap-4">
          <span>Animals tracked: <strong>{animalCount}</strong></span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-green-500"></span>
            Live
          </span>
        </div>
        <div>
          <span>Last update: just now</span>
        </div>
      </div>
    </div>
  );
}
