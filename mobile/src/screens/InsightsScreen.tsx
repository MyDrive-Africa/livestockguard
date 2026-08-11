import React, { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  Alert,
  ActivityIndicator,
} from 'react-native';
import { api } from '../services/api';
import { useFarm } from '../context/FarmContext';

// ─── Types ───────────────────────────────────────────────────────────────────

interface Anomaly {
  id: string;
  farm_id: string;
  animal_id: string | null;
  animal_name: string | null;
  anomaly_type: string;
  severity: string;
  status: string;
  description: string;
  evidence: Record<string, any>;
  detected_at: string;
  resolved_at: string | null;
}

interface Suggestion {
  id: string;
  farm_id: string;
  anomaly_id: string | null;
  category: string;
  priority: string;
  title: string;
  description: string;
  recommended_action: string;
  evidence: Record<string, any> | null;
  status: string;
  created_at: string;
  expires_at: string | null;
}

interface InsightsDashboardData {
  anomalies_active: number;
  anomalies_high: number;
  suggestions_pending: number;
  suggestions_high: number;
  latest_report_date: string | null;
  latest_report_summary: string | null;
  anomalies: Anomaly[];
  suggestions: Suggestion[];
}

interface InsightsScreenProps {
  role: string;
}

// ─── Component ───────────────────────────────────────────────────────────────

export default function InsightsScreen({ role }: InsightsScreenProps) {
  const { selectedFarm } = useFarm();
  const [data, setData] = useState<InsightsDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canAction = role === 'admin' || role === 'farm_owner';

  const fetchInsights = useCallback(async () => {
    if (!selectedFarm) return;
    try {
      setError(null);
      const resp = await api.get(`/api/v1/insights/dashboard?farm_id=${selectedFarm.id}`);
      setData(resp.data);
    } catch (err: any) {
      console.warn('Failed to fetch insights:', err);
      setError('Unable to load insights. Pull to retry.');
    } finally {
      setLoading(false);
    }
  }, [selectedFarm]);

  useEffect(() => {
    setLoading(true);
    fetchInsights();
  }, [fetchInsights]);

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchInsights();
    setRefreshing(false);
  };

  const handleAcknowledge = async (anomalyId: string) => {
    try {
      await api.put(`/api/v1/insights/anomalies/${anomalyId}/acknowledge`);
      await fetchInsights();
    } catch {
      Alert.alert('Error', 'Failed to acknowledge anomaly.');
    }
  };

  const handleDismissAnomaly = async (anomalyId: string) => {
    try {
      await api.put(`/api/v1/insights/anomalies/${anomalyId}/dismiss`);
      await fetchInsights();
    } catch {
      Alert.alert('Error', 'Failed to dismiss anomaly.');
    }
  };

  const handleAcceptSuggestion = async (suggestionId: string) => {
    try {
      await api.put(`/api/v1/insights/suggestions/${suggestionId}/accept`);
      await fetchInsights();
    } catch {
      Alert.alert('Error', 'Failed to accept suggestion.');
    }
  };

  const handleDismissSuggestion = async (suggestionId: string) => {
    try {
      await api.put(`/api/v1/insights/suggestions/${suggestionId}/dismiss`);
      await fetchInsights();
    } catch {
      Alert.alert('Error', 'Failed to dismiss suggestion.');
    }
  };

  // ─── Loading ────────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color="#22c55e" />
        <Text style={styles.loadingText}>Loading insights...</Text>
      </View>
    );
  }

  // ─── Error ──────────────────────────────────────────────────────────────────

  if (error && !data) {
    return (
      <ScrollView
        style={styles.container}
        contentContainerStyle={styles.centered}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#22c55e" />}
      >
        <Text style={styles.errorText}>{error}</Text>
      </ScrollView>
    );
  }

  // ─── Main ───────────────────────────────────────────────────────────────────

  return (
    <ScrollView
      style={styles.container}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#22c55e" />}
    >
      <Text style={styles.title}>Farm Intelligence</Text>
      <Text style={styles.farmName}>{selectedFarm?.name || 'No farm selected'}</Text>

      {/* Summary Cards */}
      <View style={styles.summaryRow}>
        <View style={styles.summaryCard}>
          <Text style={styles.summaryIcon}>⚠️</Text>
          <Text style={styles.summaryValue}>{data?.anomalies_active ?? 0}</Text>
          <Text style={styles.summaryLabel}>Anomalies</Text>
          {(data?.anomalies_high ?? 0) > 0 && (
            <Text style={styles.summaryHighlight}>{data?.anomalies_high} high</Text>
          )}
        </View>
        <View style={styles.summaryCard}>
          <Text style={styles.summaryIcon}>💡</Text>
          <Text style={styles.summaryValue}>{data?.suggestions_pending ?? 0}</Text>
          <Text style={styles.summaryLabel}>Suggestions</Text>
          {(data?.suggestions_high ?? 0) > 0 && (
            <Text style={styles.summaryHighlight}>{data?.suggestions_high} high</Text>
          )}
        </View>
      </View>

      {/* Latest Report */}
      {data?.latest_report_date && (
        <View style={styles.reportCard}>
          <View style={styles.reportHeader}>
            <Text style={styles.reportIcon}>📄</Text>
            <Text style={styles.reportTitle}>Latest Report</Text>
            <Text style={styles.reportDate}>{formatDate(data.latest_report_date)}</Text>
          </View>
          <Text style={styles.reportSummary}>{data.latest_report_summary}</Text>
        </View>
      )}

      {/* Anomalies */}
      <Text style={styles.sectionTitle}>
        Active Anomalies {data && data.anomalies.length > 0 ? `(${data.anomalies.length})` : ''}
      </Text>

      {(!data || data.anomalies.length === 0) ? (
        <View style={styles.emptyCard}>
          <Text style={styles.emptyText}>No active anomalies</Text>
        </View>
      ) : (
        data.anomalies.map((anomaly) => (
          <View
            key={anomaly.id}
            style={[styles.itemCard, { borderLeftColor: severityColor(anomaly.severity) }]}
          >
            <View style={styles.cardHeader}>
              <Text style={styles.itemType}>
                {severityEmoji(anomaly.severity)} {formatAnomalyType(anomaly.anomaly_type)}
              </Text>
              <View style={[styles.badge, { backgroundColor: severityBgColor(anomaly.severity) }]}>
                <Text style={[styles.badgeText, { color: severityColor(anomaly.severity) }]}>
                  {anomaly.severity}
                </Text>
              </View>
            </View>

            {anomaly.animal_name && (
              <Text style={styles.animalName}>🐄 {anomaly.animal_name}</Text>
            )}

            <Text style={styles.itemDescription}>{anomaly.description}</Text>
            <Text style={styles.timestamp}>Detected: {formatDateTime(anomaly.detected_at)}</Text>

            {canAction && (
              <View style={styles.actionRow}>
                <TouchableOpacity
                  style={styles.btnPrimary}
                  onPress={() => handleAcknowledge(anomaly.id)}
                  accessibilityLabel={`Acknowledge anomaly for ${anomaly.animal_name || 'farm'}`}
                >
                  <Text style={styles.btnPrimaryText}>Acknowledge</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={styles.btnOutline}
                  onPress={() => handleDismissAnomaly(anomaly.id)}
                  accessibilityLabel={`Dismiss anomaly for ${anomaly.animal_name || 'farm'}`}
                >
                  <Text style={styles.btnOutlineText}>Dismiss</Text>
                </TouchableOpacity>
              </View>
            )}
          </View>
        ))
      )}

      {/* Suggestions */}
      <Text style={styles.sectionTitle}>
        Suggestions {data && data.suggestions.length > 0 ? `(${data.suggestions.length})` : ''}
      </Text>

      {(!data || data.suggestions.length === 0) ? (
        <View style={styles.emptyCard}>
          <Text style={styles.emptyText}>No pending suggestions</Text>
        </View>
      ) : (
        data.suggestions.map((suggestion) => (
          <View
            key={suggestion.id}
            style={[styles.itemCard, { borderLeftColor: priorityColor(suggestion.priority) }]}
          >
            <View style={styles.cardHeader}>
              <View style={[styles.badge, { backgroundColor: categoryBgColor(suggestion.category) }]}>
                <Text style={styles.categoryText}>
                  {categoryEmoji(suggestion.category)} {suggestion.category}
                </Text>
              </View>
              <View style={[styles.badge, { backgroundColor: priorityBgColor(suggestion.priority) }]}>
                <Text style={[styles.badgeText, { color: priorityColor(suggestion.priority) }]}>
                  {suggestion.priority}
                </Text>
              </View>
            </View>

            <Text style={styles.suggestionTitle}>{suggestion.title}</Text>
            <Text style={styles.itemDescription}>{suggestion.description}</Text>

            <View style={styles.recommendedBox}>
              <Text style={styles.recommendedLabel}>Recommended:</Text>
              <Text style={styles.recommendedText}>{suggestion.recommended_action}</Text>
            </View>

            {canAction && (
              <View style={styles.actionRow}>
                <TouchableOpacity
                  style={styles.btnAccept}
                  onPress={() => handleAcceptSuggestion(suggestion.id)}
                  accessibilityLabel={`Accept suggestion: ${suggestion.title}`}
                >
                  <Text style={styles.btnPrimaryText}>Accept</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={styles.btnOutline}
                  onPress={() => handleDismissSuggestion(suggestion.id)}
                  accessibilityLabel={`Dismiss suggestion: ${suggestion.title}`}
                >
                  <Text style={styles.btnOutlineText}>Dismiss</Text>
                </TouchableOpacity>
              </View>
            )}
          </View>
        ))
      )}

      <View style={{ height: 40 }} />
    </ScrollView>
  );
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function severityColor(severity: string): string {
  switch (severity) {
    case 'high': return '#ef4444';
    case 'medium': return '#f59e0b';
    default: return '#6b7280';
  }
}

function severityBgColor(severity: string): string {
  switch (severity) {
    case 'high': return '#451a1a';
    case 'medium': return '#451a00';
    default: return '#1f2937';
  }
}

function severityEmoji(severity: string): string {
  switch (severity) {
    case 'high': return '🔴';
    case 'medium': return '🟡';
    default: return '⚪';
  }
}

function priorityColor(priority: string): string {
  switch (priority) {
    case 'high': return '#ef4444';
    case 'medium': return '#f59e0b';
    default: return '#6b7280';
  }
}

function priorityBgColor(priority: string): string {
  switch (priority) {
    case 'high': return '#451a1a';
    case 'medium': return '#451a00';
    default: return '#1f2937';
  }
}

function categoryEmoji(category: string): string {
  switch (category) {
    case 'health': return '🏥';
    case 'security': return '🔒';
    case 'operational': return '📋';
    case 'maintenance': return '🔧';
    default: return '📌';
  }
}

function categoryBgColor(category: string): string {
  switch (category) {
    case 'health': return '#14532d';
    case 'security': return '#1e1b4b';
    case 'operational': return '#1c1917';
    case 'maintenance': return '#172554';
    default: return '#1f2937';
  }
}

function formatAnomalyType(type: string): string {
  return type.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatDate(dateStr: string): string {
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-ZA', { day: 'numeric', month: 'short', year: 'numeric' });
  } catch {
    return dateStr;
  }
}

function formatDateTime(dateStr: string): string {
  try {
    const d = new Date(dateStr);
    return d.toLocaleString('en-ZA', {
      day: 'numeric',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return dateStr;
  }
}

// ─── Styles ──────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#111827',
    padding: 16,
    paddingTop: 60,
  },
  centered: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#111827',
    padding: 16,
  },
  loadingText: {
    color: '#9ca3af',
    fontSize: 14,
    marginTop: 12,
  },
  errorText: {
    color: '#f87171',
    fontSize: 14,
    textAlign: 'center',
  },
  title: {
    fontSize: 22,
    fontWeight: 'bold',
    color: '#ffffff',
    textAlign: 'center',
  },
  farmName: {
    fontSize: 13,
    color: '#9ca3af',
    textAlign: 'center',
    marginBottom: 20,
  },

  // Summary cards
  summaryRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 16,
  },
  summaryCard: {
    flex: 1,
    backgroundColor: '#1f2937',
    borderRadius: 12,
    padding: 16,
    alignItems: 'center',
    marginHorizontal: 4,
  },
  summaryIcon: {
    fontSize: 24,
    marginBottom: 4,
  },
  summaryValue: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#ffffff',
  },
  summaryLabel: {
    fontSize: 12,
    color: '#9ca3af',
    marginTop: 2,
  },
  summaryHighlight: {
    fontSize: 11,
    color: '#ef4444',
    fontWeight: '600',
    marginTop: 4,
  },

  // Report card
  reportCard: {
    backgroundColor: '#1f2937',
    borderRadius: 12,
    padding: 14,
    marginBottom: 20,
    borderLeftWidth: 3,
    borderLeftColor: '#3b82f6',
  },
  reportHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
  },
  reportIcon: {
    fontSize: 16,
    marginRight: 6,
  },
  reportTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#ffffff',
    flex: 1,
  },
  reportDate: {
    fontSize: 11,
    color: '#6b7280',
  },
  reportSummary: {
    fontSize: 13,
    color: '#d1d5db',
    lineHeight: 18,
  },

  // Section title
  sectionTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#ffffff',
    marginBottom: 10,
    marginTop: 8,
  },

  // Empty state
  emptyCard: {
    backgroundColor: '#14532d',
    borderRadius: 12,
    padding: 16,
    alignItems: 'center',
    marginBottom: 16,
  },
  emptyText: {
    color: '#86efac',
    fontSize: 14,
    fontWeight: '600',
  },

  // Item card (anomaly or suggestion)
  itemCard: {
    backgroundColor: '#1f2937',
    borderRadius: 12,
    padding: 14,
    marginBottom: 10,
    borderLeftWidth: 3,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  itemType: {
    color: '#ffffff',
    fontSize: 13,
    fontWeight: '600',
    flex: 1,
  },
  badge: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 8,
  },
  badgeText: {
    fontSize: 10,
    fontWeight: '700',
    textTransform: 'uppercase',
  },
  categoryText: {
    fontSize: 10,
    color: '#d1d5db',
    fontWeight: '600',
    textTransform: 'capitalize',
  },
  animalName: {
    color: '#9ca3af',
    fontSize: 12,
    marginBottom: 4,
  },
  itemDescription: {
    color: '#d1d5db',
    fontSize: 12,
    lineHeight: 17,
    marginBottom: 6,
  },
  timestamp: {
    color: '#6b7280',
    fontSize: 11,
  },

  // Suggestion-specific
  suggestionTitle: {
    color: '#ffffff',
    fontSize: 14,
    fontWeight: '600',
    marginTop: 8,
    marginBottom: 4,
  },
  recommendedBox: {
    backgroundColor: '#111827',
    borderRadius: 8,
    padding: 10,
    marginTop: 8,
  },
  recommendedLabel: {
    color: '#6b7280',
    fontSize: 10,
    fontWeight: '600',
    textTransform: 'uppercase',
    marginBottom: 4,
  },
  recommendedText: {
    color: '#d1d5db',
    fontSize: 12,
    lineHeight: 17,
  },

  // Action buttons
  actionRow: {
    flexDirection: 'row',
    marginTop: 10,
    gap: 8,
  },
  btnPrimary: {
    backgroundColor: '#1d4ed8',
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 8,
  },
  btnAccept: {
    backgroundColor: '#16a34a',
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 8,
  },
  btnOutline: {
    backgroundColor: 'transparent',
    borderWidth: 1,
    borderColor: '#374151',
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 8,
  },
  btnPrimaryText: {
    color: '#ffffff',
    fontSize: 12,
    fontWeight: '600',
  },
  btnOutlineText: {
    color: '#9ca3af',
    fontSize: 12,
    fontWeight: '600',
  },
});
