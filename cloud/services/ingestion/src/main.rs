//! LivestockGuard Ingestion Service
//!
//! High-throughput telemetry ingestion for GPS collar devices. This service
//! accepts binary-encoded position reports from multiple transport layers
//! (LoRaWAN webhooks, satellite gateways, direct MQTT) and decodes them into
//! structured telemetry for storage in TimescaleDB.
//!
//! # Architecture
//!
//! ```text
//! LoRaWAN Gateway ──► POST /lorawan ──┐
//!                                      ├──► Binary Decoder ──► TimescaleDB
//! Satellite Modem ──► POST /satellite ─┘                  └──► Redis pub/sub
//! MQTT (EMQX) ─────► Subscribe lg/dev/+/pos ─────────────────►
//! ```
//!
//! # Performance Target
//!
//! Designed to sustain 5,000 messages/sec using Tokio's multi-threaded runtime.
//!
//! # Binary Protocol
//!
//! All transports use the same binary frame format with CRC-16/CCITT integrity.
//! See [`decoder::decode_uplink`] for the full frame specification.

use axum::{extract::Json, routing::post, Router};
use serde::{Deserialize, Serialize};
use std::net::SocketAddr;
use tracing::info;

mod decoder;

/// A single GPS position fix from a collar device.
///
/// Coordinates use WGS84 datum. Latitude and longitude are stored as
/// floating-point degrees (not the integer microdegrees used in the wire
/// protocol — conversion happens during decoding).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Position {
    /// Latitude in decimal degrees (negative = south).
    pub latitude: f64,
    /// Longitude in decimal degrees (negative = west).
    pub longitude: f64,
    /// Altitude above sea level in metres.
    pub altitude: f32,
    /// Horizontal Dilution of Precision (lower = better accuracy).
    pub hdop: f32,
    /// UTC timestamp of the fix.
    pub timestamp: chrono::DateTime<chrono::Utc>,
}

/// Decoded telemetry payload from a GPS collar device.
///
/// Contains one or more position fixes along with device health metrics.
/// A batch of positions is common when the device was offline and stored
/// fixes locally before transmitting.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeviceTelemetry {
    /// Unique device identifier in format `"LG-XXXXXXXX"` (hex-encoded u32).
    pub device_id: String,
    /// One or more GPS position fixes (oldest first).
    pub positions: Vec<Position>,
    /// Battery voltage in millivolts (typical range: 3000–4200 mV).
    pub battery_mv: u16,
    /// Ambient temperature in degrees Celsius (offset-decoded from wire format).
    pub temperature_c: f32,
    /// Radio signal strength in dBm (negative values; closer to 0 = stronger).
    pub signal_rssi: i16,
    /// Rolling sequence number for detecting missed messages (wraps at u16::MAX).
    pub sequence_number: u32,
}

/// Service configuration loaded from environment variables.
///
/// All fields have sensible defaults for local development. In production,
/// these are set via Docker Compose environment or ECS task definitions.
#[derive(Debug, Clone, Deserialize)]
struct Config {
    /// EMQX broker hostname (default: `"localhost"`).
    mqtt_host: String,
    /// EMQX broker port (default: `1883`).
    mqtt_port: u16,
    /// Port for the HTTP webhook server (default: `8001`).
    webhook_port: u16,
    /// PostgreSQL+TimescaleDB connection string.
    database_url: String,
}

impl Config {
    /// Load configuration from environment variables with development defaults.
    ///
    /// # Environment Variables
    ///
    /// - `MQTT_HOST` — EMQX broker host (default: `"localhost"`)
    /// - `MQTT_PORT` — EMQX broker port (default: `1883`)
    /// - `WEBHOOK_PORT` — HTTP listener port (default: `8001`)
    /// - `DATABASE_URL` — PostgreSQL connection string
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

/// Incoming LoRaWAN uplink payload as forwarded by a network server (e.g., TTN, Chirpstack).
#[derive(Debug, Deserialize)]
struct LoRaWANPayload {
    /// Device EUI (Extended Unique Identifier) — 16-char hex string.
    dev_eui: String,
    /// LoRaWAN FPort number indicating the application payload type.
    port: u8,
    /// Hex-encoded binary payload containing the LivestockGuard frame.
    payload_hex: String,
    /// Received Signal Strength Indicator from the gateway (dBm).
    rssi: i16,
    /// Signal-to-Noise Ratio at the gateway (dB).
    snr: f32,
}

/// Incoming satellite uplink payload (e.g., from Swarm, Iridium SBD).
#[derive(Debug, Deserialize)]
struct SatellitePayload {
    /// Device identifier as registered with the satellite provider.
    device_id: String,
    /// Hex-encoded binary payload containing the LivestockGuard frame.
    payload_hex: String,
    /// ISO 8601 timestamp from the satellite gateway.
    timestamp: String,
}

/// Handle an incoming LoRaWAN webhook.
///
/// Decodes the binary payload and logs the result. Once the TimescaleDB
/// integration is complete, decoded positions will be persisted and
/// published to Redis for real-time dashboard updates.
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

/// Handle an incoming satellite message webhook.
///
/// Satellite links (Swarm, Iridium) use the same binary frame as LoRaWAN
/// but arrive via a different transport with their own metadata format.
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

/// Initialize the MQTT subscriber for direct device connections.
///
/// Subscribes to `lg/dev/+/pos` on EMQX to receive binary position
/// reports from devices connected via LTE-M/NB-IoT cellular.
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
