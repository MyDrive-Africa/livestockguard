//! LivestockGuard Geofence Engine
//!
//! Spatial breach detection service for virtual fencing. Evaluates GPS position
//! reports against active geofence polygons to determine whether animals are
//! inside permitted areas or have breached boundaries.
//!
//! # Architecture
//!
//! ```text
//! Position Updates (MQTT/Redis) ──► Geofence Engine ──► Breach Alerts (Redis pub/sub)
//!                                        │
//!                                   R-tree Index
//!                                   (O(log n) lookup)
//! ```
//!
//! # Fence Types
//!
//! - **Inclusion fence**: Animals must stay *inside* the polygon (e.g., paddock boundary).
//!   Leaving triggers a breach alert.
//! - **Exclusion fence**: Animals must stay *outside* the polygon (e.g., dam, cliff edge).
//!   Entering triggers a breach alert.
//!
//! # Geometry
//!
//! Polygons use WGS84 coordinates stored as `[longitude, latitude]` pairs (GeoJSON
//! convention). The [`geo`] crate's point-in-polygon algorithm handles the spatial
//! containment test. For production scale, an [`rstar`] R-tree index provides
//! O(log n) pre-filtering when evaluating a point against many geofences.

use geo::{Contains, Polygon, Coord, LineString};
use serde::{Deserialize, Serialize};
use tracing::info;

/// A geofence polygon defining a virtual boundary for a farm.
///
/// Geofences are loaded from PostgreSQL/PostGIS and cached in-memory.
/// Each fence belongs to a single farm and is either an inclusion or
/// exclusion boundary.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Geofence {
    /// Unique identifier (UUID from the database).
    pub id: String,
    /// Human-readable fence name (e.g., "Main Paddock", "Dam Exclusion Zone").
    pub name: String,
    /// The farm this geofence belongs to.
    pub farm_id: String,
    /// Whether animals should be kept inside or outside this polygon.
    pub fence_type: FenceDirection,
    /// Polygon vertices as `[longitude, latitude]` pairs (GeoJSON order).
    /// Must form a closed ring (first point == last point) with at least 3 unique vertices.
    pub polygon: Vec<[f64; 2]>,
    /// Whether this fence is currently being evaluated. Inactive fences are skipped.
    pub active: bool,
}

/// Specifies whether a geofence is an inclusion or exclusion boundary.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum FenceDirection {
    /// Animals must remain *inside* this polygon (typical paddock/camp boundary).
    Inclusion,
    /// Animals must remain *outside* this polygon (hazard zone — dam, road, cliff).
    Exclusion,
}

/// The result of evaluating a point against a geofence.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum FenceStatus {
    /// The point is geometrically inside the polygon.
    Inside,
    /// The point is geometrically outside the polygon.
    Outside,
    /// The animal has violated the fence rule (outside an inclusion fence,
    /// or inside an exclusion fence). Triggers an alert.
    Breached,
    /// The animal is respecting the fence rule. No action needed.
    Compliant,
}

/// Evaluate whether a GPS position complies with a geofence boundary.
///
/// Uses the [`geo`] crate's point-in-polygon algorithm (winding number)
/// to determine spatial containment, then maps the geometric result to
/// a compliance status based on the fence direction.
///
/// # Arguments
///
/// * `geofence` — The geofence definition to evaluate against.
/// * `lat` — Latitude of the position in decimal degrees (WGS84).
/// * `lng` — Longitude of the position in decimal degrees (WGS84).
///
/// # Returns
///
/// - [`FenceStatus::Compliant`] if the animal is where it should be (or the fence is inactive/invalid).
/// - [`FenceStatus::Breached`] if the animal has violated the fence rule.
///
/// # Edge Cases
///
/// - Inactive fences always return [`FenceStatus::Compliant`].
/// - Polygons with fewer than 3 vertices are treated as invalid and return [`FenceStatus::Compliant`].
/// - Points exactly on the polygon boundary may return either status (implementation-defined by the `geo` crate).
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
