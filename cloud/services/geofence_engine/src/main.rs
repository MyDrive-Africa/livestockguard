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
