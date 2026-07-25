use geo::{Contains, Polygon, Coord, LineString};
use serde::{Deserialize, Serialize};
use tracing::info;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Geofence {
    pub id: String,
    pub name: String,
    pub farm_id: String,
    pub fence_type: FenceDirection,
    pub polygon: Vec<[f64; 2]>, // [[lng, lat], ...]
    pub active: bool,
}

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum FenceDirection {
    Inclusion,
    Exclusion,
}

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum FenceStatus {
    Inside,
    Outside,
    Breached,
    Compliant,
}

/// Evaluate whether a point is inside or outside a geofence polygon.
/// Returns the fence status based on fence direction:
/// - Inclusion fence: Inside = Compliant, Outside = Breached
/// - Exclusion fence: Inside = Breached, Outside = Compliant
pub fn evaluate_point(geofence: &Geofence, lat: f64, lng: f64) -> FenceStatus {
    if !geofence.active {
        return FenceStatus::Compliant;
    }

    let coords: Vec<Coord<f64>> = geofence
        .polygon
        .iter()
        .map(|p| Coord { x: p[0], y: p[1] })
        .collect();

    if coords.len() < 3 {
        return FenceStatus::Compliant;
    }

    let line_string = LineString::new(coords);
    let polygon = Polygon::new(line_string, vec![]);

    let point = geo::Point::new(lng, lat);
    let is_inside = polygon.contains(&point);

    match (geofence.fence_type, is_inside) {
        (FenceDirection::Inclusion, true) => FenceStatus::Compliant,
        (FenceDirection::Inclusion, false) => FenceStatus::Breached,
        (FenceDirection::Exclusion, true) => FenceStatus::Breached,
        (FenceDirection::Exclusion, false) => FenceStatus::Compliant,
    }
}

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt()
        .with_env_filter("livestockguard_geofence_engine=debug,info")
        .init();

    info!("Starting LivestockGuard geofence engine");

    // TODO: Subscribe to position updates via MQTT/Redis
    // and evaluate against active geofences

    // Example usage
    let fence = Geofence {
        id: "fence-001".to_string(),
        name: "Main Paddock".to_string(),
        farm_id: "farm-001".to_string(),
        fence_type: FenceDirection::Inclusion,
        polygon: vec![
            [149.10, -35.30],
            [149.15, -35.30],
            [149.15, -35.25],
            [149.10, -35.25],
            [149.10, -35.30],
        ],
        active: true,
    };

    let status = evaluate_point(&fence, -35.28, 149.12);
    info!(?status, "Evaluated point against fence");

    // Keep running
    tokio::signal::ctrl_c().await.unwrap();
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_square_fence(fence_type: FenceDirection, active: bool) -> Geofence {
        // Square from (26.20, -29.11) to (26.22, -29.13)
        Geofence {
            id: "test-fence".to_string(),
            name: "Test Paddock".to_string(),
            farm_id: "farm-1".to_string(),
            fence_type,
            polygon: vec![
                [26.20, -29.11],
                [26.22, -29.11],
                [26.22, -29.13],
                [26.20, -29.13],
                [26.20, -29.11], // closed ring
            ],
            active,
        }
    }

    // ─── Inclusion Fence Tests ───────────────────────

    #[test]
    fn test_inclusion_point_inside_is_compliant() {
        let fence = make_square_fence(FenceDirection::Inclusion, true);
        let status = evaluate_point(&fence, -29.12, 26.21); // center
        assert_eq!(status, FenceStatus::Compliant);
    }

    #[test]
    fn test_inclusion_point_outside_is_breached() {
        let fence = make_square_fence(FenceDirection::Inclusion, true);
        let status = evaluate_point(&fence, -29.15, 26.21); // south of fence
        assert_eq!(status, FenceStatus::Breached);
    }

    #[test]
    fn test_inclusion_point_far_outside() {
        let fence = make_square_fence(FenceDirection::Inclusion, true);
        let status = evaluate_point(&fence, -30.0, 27.0); // way outside
        assert_eq!(status, FenceStatus::Breached);
    }

    // ─── Exclusion Fence Tests ───────────────────────

    #[test]
    fn test_exclusion_point_inside_is_breached() {
        let fence = make_square_fence(FenceDirection::Exclusion, true);
        let status = evaluate_point(&fence, -29.12, 26.21); // center
        assert_eq!(status, FenceStatus::Breached);
    }

    #[test]
    fn test_exclusion_point_outside_is_compliant() {
        let fence = make_square_fence(FenceDirection::Exclusion, true);
        let status = evaluate_point(&fence, -29.15, 26.21); // south of fence
        assert_eq!(status, FenceStatus::Compliant);
    }

    // ─── Inactive Fence Tests ────────────────────────

    #[test]
    fn test_inactive_fence_always_compliant() {
        let fence = make_square_fence(FenceDirection::Inclusion, false);
        // Even outside an inclusion fence, inactive = compliant
        let status = evaluate_point(&fence, -29.15, 26.21);
        assert_eq!(status, FenceStatus::Compliant);
    }

    #[test]
    fn test_inactive_exclusion_fence_always_compliant() {
        let fence = make_square_fence(FenceDirection::Exclusion, false);
        // Even inside an exclusion fence, inactive = compliant
        let status = evaluate_point(&fence, -29.12, 26.21);
        assert_eq!(status, FenceStatus::Compliant);
    }

    // ─── Edge Cases ──────────────────────────────────

    #[test]
    fn test_too_few_vertices_is_compliant() {
        let fence = Geofence {
            id: "bad".to_string(),
            name: "Bad".to_string(),
            farm_id: "f".to_string(),
            fence_type: FenceDirection::Inclusion,
            polygon: vec![[26.0, -29.0], [26.1, -29.0]], // only 2 points
            active: true,
        };
        let status = evaluate_point(&fence, -29.0, 26.05);
        assert_eq!(status, FenceStatus::Compliant);
    }

    #[test]
    fn test_empty_polygon_is_compliant() {
        let fence = Geofence {
            id: "empty".to_string(),
            name: "Empty".to_string(),
            farm_id: "f".to_string(),
            fence_type: FenceDirection::Inclusion,
            polygon: vec![],
            active: true,
        };
        let status = evaluate_point(&fence, -29.12, 26.21);
        assert_eq!(status, FenceStatus::Compliant);
    }

    #[test]
    fn test_point_on_boundary_inclusion() {
        // Point exactly on polygon edge — geo crate may or may not include it
        // Just ensure it doesn't panic
        let fence = make_square_fence(FenceDirection::Inclusion, true);
        let status = evaluate_point(&fence, -29.11, 26.21); // on north edge
        // Either Compliant or Breached is acceptable, just no panic
        assert!(status == FenceStatus::Compliant || status == FenceStatus::Breached);
    }

    // ─── Multiple Fences ─────────────────────────────

    #[test]
    fn test_evaluate_multiple_fences() {
        let inclusion = make_square_fence(FenceDirection::Inclusion, true);
        let exclusion = Geofence {
            id: "dam-zone".to_string(),
            name: "Dam Exclusion".to_string(),
            farm_id: "farm-1".to_string(),
            fence_type: FenceDirection::Exclusion,
            polygon: vec![
                [26.208, -29.118],
                [26.212, -29.118],
                [26.212, -29.122],
                [26.208, -29.122],
                [26.208, -29.118],
            ],
            active: true,
        };

        // Point inside inclusion AND inside exclusion
        let lat = -29.12;
        let lng = 26.21;
        let s1 = evaluate_point(&inclusion, lat, lng);
        let s2 = evaluate_point(&exclusion, lat, lng);

        assert_eq!(s1, FenceStatus::Compliant); // inside inclusion = ok
        assert_eq!(s2, FenceStatus::Breached); // inside exclusion = breach
    }

    // ─── Serialization ───────────────────────────────

    #[test]
    fn test_fence_direction_serialization() {
        let json = serde_json::to_string(&FenceDirection::Inclusion).unwrap();
        assert_eq!(json, "\"inclusion\"");

        let json = serde_json::to_string(&FenceDirection::Exclusion).unwrap();
        assert_eq!(json, "\"exclusion\"");
    }

    #[test]
    fn test_fence_status_serialization() {
        let json = serde_json::to_string(&FenceStatus::Breached).unwrap();
        assert_eq!(json, "\"breached\"");

        let json = serde_json::to_string(&FenceStatus::Compliant).unwrap();
        assert_eq!(json, "\"compliant\"");
    }

    #[test]
    fn test_geofence_deserialization() {
        let json = r#"{
            "id": "f1",
            "name": "Test",
            "farm_id": "farm-1",
            "fence_type": "inclusion",
            "polygon": [[26.0, -29.0], [26.1, -29.0], [26.1, -29.1], [26.0, -29.1], [26.0, -29.0]],
            "active": true
        }"#;
        let fence: Geofence = serde_json::from_str(json).unwrap();
        assert_eq!(fence.id, "f1");
        assert_eq!(fence.fence_type, FenceDirection::Inclusion);
        assert_eq!(fence.polygon.len(), 5);
        assert!(fence.active);
    }
}
