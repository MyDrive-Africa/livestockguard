use axum::{extract::Json, routing::post, Router};
use serde::{Deserialize, Serialize};
use std::net::SocketAddr;
use tracing::info;

mod decoder;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Position {
    pub latitude: f64,
    pub longitude: f64,
    pub altitude: f32,
    pub hdop: f32,
    pub timestamp: chrono::DateTime<chrono::Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeviceTelemetry {
    pub device_id: String,
    pub positions: Vec<Position>,
    pub battery_mv: u16,
    pub temperature_c: f32,
    pub signal_rssi: i16,
    pub sequence_number: u32,
}

#[derive(Debug, Clone, Deserialize)]
struct Config {
    mqtt_host: String,
    mqtt_port: u16,
    webhook_port: u16,
    database_url: String,
}

impl Config {
    fn from_env() -> Self {
        Self {
            mqtt_host: std::env::var("MQTT_HOST").unwrap_or_else(|_| "localhost".into()),
            mqtt_port: std::env::var("MQTT_PORT")
                .unwrap_or_else(|_| "1883".into())
                .parse()
                .unwrap_or(1883),
            webhook_port: std::env::var("WEBHOOK_PORT")
                .unwrap_or_else(|_| "8001".into())
                .parse()
                .unwrap_or(8001),
            database_url: std::env::var("DATABASE_URL")
                .unwrap_or_else(|_| "postgres://localhost/livestockguard".into()),
        }
    }
}

#[derive(Debug, Deserialize)]
struct LoRaWANPayload {
    dev_eui: String,
    port: u8,
    payload_hex: String,
    rssi: i16,
    snr: f32,
}

#[derive(Debug, Deserialize)]
struct SatellitePayload {
    device_id: String,
    payload_hex: String,
    timestamp: String,
}

async fn handle_lorawan(Json(payload): Json<LoRaWANPayload>) -> &'static str {
    info!(
        dev_eui = %payload.dev_eui,
        port = payload.port,
        "Received LoRaWAN uplink"
    );

    match decoder::decode_uplink(&payload.payload_hex) {
        Ok(telemetry) => {
            info!(device_id = %telemetry.device_id, "Decoded telemetry");
            // TODO: Store in TimescaleDB and publish to MQTT
            "OK"
        }
        Err(e) => {
            tracing::error!(error = %e, "Failed to decode uplink");
            "DECODE_ERROR"
        }
    }
}

async fn handle_satellite(Json(payload): Json<SatellitePayload>) -> &'static str {
    info!(
        device_id = %payload.device_id,
        "Received satellite message"
    );

    match decoder::decode_uplink(&payload.payload_hex) {
        Ok(telemetry) => {
            info!(device_id = %telemetry.device_id, "Decoded satellite telemetry");
            // TODO: Store in TimescaleDB and publish to MQTT
            "OK"
        }
        Err(e) => {
            tracing::error!(error = %e, "Failed to decode satellite payload");
            "DECODE_ERROR"
        }
    }
}

async fn spawn_mqtt_handler(config: &Config) {
    info!(
        host = %config.mqtt_host,
        port = config.mqtt_port,
        "MQTT handler configured (connection deferred)"
    );
    // TODO: Connect to EMQX and subscribe to device topics
}

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt()
        .with_env_filter("livestockguard_ingestion=debug,info")
        .init();

    let config = Config::from_env();
    info!("Starting LivestockGuard ingestion service");

    spawn_mqtt_handler(&config).await;

    let app = Router::new()
        .route("/lorawan", post(handle_lorawan))
        .route("/satellite", post(handle_satellite));

    let addr = SocketAddr::from(([0, 0, 0, 0], config.webhook_port));
    info!(%addr, "Webhook server listening");

    let listener = tokio::net::TcpListener::bind(addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}
