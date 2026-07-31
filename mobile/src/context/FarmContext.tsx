import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { Farm, getMyFarms, getSelectedFarmId, setSelectedFarmId } from '../services/api';

interface FarmContextValue {
  farms: Farm[];
  selectedFarm: Farm | null;
  loading: boolean;
  switchFarm: (farmId: string) => void;
  refreshFarms: () => Promise<void>;
}

const FarmContext = createContext<FarmContextValue>({
  farms: [],
  selectedFarm: null,
  loading: true,
  switchFarm: () => {},
  refreshFarms: async () => {},
});

export function useFarm() {
  return useContext(FarmContext);
}

interface FarmProviderProps {
  children: React.ReactNode;
  role: string;
}

export function FarmProvider({ children, role }: FarmProviderProps) {
  const [farms, setFarms] = useState<Farm[]>([]);
  const [selectedFarm, setSelectedFarm] = useState<Farm | null>(null);
  const [loading, setLoading] = useState(true);

  const loadFarms = useCallback(async () => {
    try {
      setLoading(true);
      const farmList = await getMyFarms();
      setFarms(farmList);

      // Determine which farm to select
      const savedId = await getSelectedFarmId();
      const savedFarm = savedId ? farmList.find((f) => f.id === savedId) : null;

      if (savedFarm) {
        // Restore previously selected farm
        setSelectedFarm(savedFarm);
      } else if (farmList.length === 1) {
        // Auto-select if only one farm (herdsman or single-farm owner)
        setSelectedFarm(farmList[0]);
        await setSelectedFarmId(farmList[0].id);
      } else if (farmList.length > 0) {
        // Default to first farm
        setSelectedFarm(farmList[0]);
        await setSelectedFarmId(farmList[0].id);
      }
    } catch (err) {
      console.warn('Failed to load farms:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadFarms();
  }, [loadFarms]);

  const switchFarm = useCallback(
    (farmId: string) => {
      const farm = farms.find((f) => f.id === farmId);
      if (farm) {
        setSelectedFarm(farm);
        setSelectedFarmId(farmId);
      }
    },
    [farms]
  );

  return (
    <FarmContext.Provider
      value={{
        farms,
        selectedFarm,
        loading,
        switchFarm,
        refreshFarms: loadFarms,
      }}
    >
      {children}
    </FarmContext.Provider>
  );
}
