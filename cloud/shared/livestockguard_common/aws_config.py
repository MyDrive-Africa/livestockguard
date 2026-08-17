"""
AWS-aware configuration loader for LivestockGuard services.

Provides a unified interface for loading secrets and configuration that works
across all environments:

  - AWS (Cloud9/ECS): Reads from Secrets Manager + SSM Parameter Store via IAM role.
  - Local development: Falls back to environment variables / .env files.

Usage:
    from livestockguard_common.aws_config import (
        load_jwt_secret,
        load_database_url,
        load_ses_config,
        load_sms_config,
        load_firebase_config,
    )

All loaders follow the same pattern: check if running on AWS infrastructure,
and if so, fetch from AWS services. Otherwise, read from environment variables
with sensible development defaults.
"""

import json
import logging
import os
from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)


# ─── AWS Environment Detection ─────────────────────────────────────────────────

def is_aws_environment() -> bool:
    """
    Detect if running on AWS infrastructure (Cloud9, ECS, EC2).

    Checks for standard AWS environment indicators:
      - AWS_EXECUTION_ENV: Set by Lambda/ECS
      - ECS_CONTAINER_METADATA_URI: Set in ECS Fargate containers
      - /sys/hypervisor/uuid: Present on EC2 instances (starts with 'ec2')
      - USE_AWS_CONFIG: Explicit opt-in env var for testing

    Returns:
        True if running on AWS, False for local development.
    """
    # Explicit override for testing or manual control
    explicit = os.environ.get("USE_AWS_CONFIG", "").lower()
    if explicit in ("1", "true", "yes"):
        return True
    if explicit in ("0", "false", "no"):
        return False

    return (
        os.environ.get("AWS_EXECUTION_ENV") is not None
        or os.environ.get("ECS_CONTAINER_METADATA_URI") is not None
        or os.environ.get("ECS_CONTAINER_METADATA_URI_V4") is not None
        or _is_ec2_instance()
    )


def _is_ec2_instance() -> bool:
    """Check if running on an EC2 instance via hypervisor UUID."""
    try:
        with open("/sys/hypervisor/uuid", "r") as f:
            return f.read(3).lower() == "ec2"
    except (FileNotFoundError, PermissionError, OSError):
        return False


# ─── AWS Client Factories (Lazy, Cached) ───────────────────────────────────────

@lru_cache()
def _get_secrets_client():
    """Get a cached Secrets Manager client."""
    import boto3
    region = os.environ.get("AWS_REGION", "af-south-1")
    return boto3.client("secretsmanager", region_name=region)


@lru_cache()
def _get_ssm_client():
    """Get a cached SSM Parameter Store client."""
    import boto3
    region = os.environ.get("AWS_REGION", "af-south-1")
    return boto3.client("ssm", region_name=region)


# ─── Low-Level Fetch Functions ─────────────────────────────────────────────────

def get_secret(secret_name: str) -> dict:
    """
    Fetch a JSON secret from AWS Secrets Manager.

    Args:
        secret_name: Secret name without prefix (e.g., 'jwt-secret').
                     Automatically prefixed with 'livestockguard/'.

    Returns:
        Parsed JSON dict from the secret value.

    Raises:
        botocore.exceptions.ClientError: If secret not found or access denied.
    """
    client = _get_secrets_client()
    full_name = f"livestockguard/{secret_name}"
    logger.debug(f"Fetching secret: {full_name}")
    response = client.get_secret_value(SecretId=full_name)
    return json.loads(response["SecretString"])


def get_parameter(param_name: str) -> str:
    """
    Fetch a config value from SSM Parameter Store.

    Args:
        param_name: Parameter name without prefix (e.g., 'ses-sender-email').
                    Automatically prefixed with '/livestockguard/'.

    Returns:
        String value of the parameter.

    Raises:
        botocore.exceptions.ClientError: If parameter not found or access denied.
    """
    client = _get_ssm_client()
    full_name = f"/livestockguard/{param_name}"
    logger.debug(f"Fetching parameter: {full_name}")
    response = client.get_parameter(Name=full_name, WithDecryption=True)
    return response["Parameter"]["Value"]


# ─── High-Level Config Loaders ─────────────────────────────────────────────────

def load_jwt_secret() -> str:
    """
    Load the JWT signing secret.

    AWS: Reads from Secrets Manager (livestockguard/jwt-secret).
    Local: Falls back to JWT_SECRET env var.

    Returns:
        JWT secret string for signing/verifying tokens.
    """
    if is_aws_environment():
        try:
            secret = get_secret("jwt-secret")
            logger.info("JWT secret loaded from AWS Secrets Manager")
            return secret["value"]
        except Exception as e:
            logger.error(f"Failed to load JWT secret from AWS: {e}")
            raise
    return os.environ.get("JWT_SECRET", "dev_secret_change_in_production")


def load_database_url(driver: str = "postgresql+asyncpg") -> str:
    """
    Load the PostgreSQL connection URL.

    AWS: Reads credentials from Secrets Manager (livestockguard/postgres)
         and constructs the connection string.
    Local: Falls back to DATABASE_URL env var.

    Args:
        driver: SQLAlchemy driver prefix. Use 'postgresql+asyncpg' for
                async services (api_gateway) or 'postgresql' for asyncpg
                direct connections (mqtt_writer).

    Returns:
        Full database connection URL string.
    """
    if is_aws_environment():
        try:
            db = get_secret("postgres")
            url = (
                f"{driver}://{db['username']}:{db['password']}"
                f"@{db['host']}:{db['port']}/{db['dbname']}"
            )
            logger.info(f"Database URL loaded from AWS Secrets Manager (host={db['host']})")
            return url
        except Exception as e:
            logger.error(f"Failed to load database URL from AWS: {e}")
            raise

    default_url = (
        f"{driver}://livestockguard:livestockguard_dev@localhost:5432/livestockguard"
    )
    return os.environ.get("DATABASE_URL", default_url)


def load_redis_url() -> str:
    """
    Load the Redis connection URL.

    AWS: Reads from Parameter Store (/livestockguard/redis-url).
    Local: Falls back to REDIS_URL env var.

    Returns:
        Redis connection URL string.
    """
    if is_aws_environment():
        try:
            return get_parameter("redis-url")
        except Exception as e:
            logger.warning(f"Failed to load Redis URL from AWS, using env fallback: {e}")

    return os.environ.get("REDIS_URL", "redis://localhost:6379/0")


def load_ses_config() -> dict:
    """
    Load Amazon SES email configuration.

    AWS: Reads sender email and recipients from Parameter Store.
    Local: Falls back to SES_SENDER_EMAIL and ALERT_EMAIL_RECIPIENTS env vars.

    Returns:
        Dict with keys: sender_email, region, recipients.
    """
    if is_aws_environment():
        try:
            return {
                "sender_email": get_parameter("ses-sender-email"),
                "region": get_parameter("aws-region"),
                "recipients": [
                    e.strip()
                    for e in get_parameter("email-recipients").split(",")
                    if e.strip()
                ],
            }
        except Exception as e:
            logger.warning(f"Failed to load SES config from AWS: {e}")

    return {
        "sender_email": os.environ.get("SES_SENDER_EMAIL", "alerts@livestockguard.co.za"),
        "region": os.environ.get("AWS_REGION", "af-south-1"),
        "recipients": [
            e.strip()
            for e in os.environ.get("ALERT_EMAIL_RECIPIENTS", "").split(",")
            if e.strip()
        ],
    }


def load_sms_config() -> dict:
    """
    Load Africa's Talking SMS configuration.

    AWS: Reads API key + username from Secrets Manager, recipients from Parameter Store.
    Local: Falls back to AT_API_KEY, AT_USERNAME, ALERT_SMS_RECIPIENTS env vars.

    Returns:
        Dict with keys: api_key, username, recipients, sender_id.
    """
    if is_aws_environment():
        try:
            creds = get_secret("africastalking")
            recipients_str = get_parameter("sms-recipients")
            return {
                "api_key": creds["api_key"],
                "username": creds["username"],
                "sender_id": creds.get("sender_id", "LGGUARD"),
                "recipients": [
                    p.strip() for p in recipients_str.split(",") if p.strip()
                ],
            }
        except Exception as e:
            logger.warning(f"Failed to load SMS config from AWS: {e}")

    return {
        "api_key": os.environ.get("AT_API_KEY", ""),
        "username": os.environ.get("AT_USERNAME", "sandbox"),
        "sender_id": os.environ.get("AT_SENDER_ID", "LGGUARD"),
        "recipients": [
            p.strip()
            for p in os.environ.get("ALERT_SMS_RECIPIENTS", "").split(",")
            if p.strip()
        ],
    }


def load_firebase_config() -> Optional[dict]:
    """
    Load Firebase Cloud Messaging service account credentials.

    AWS: Reads full service account JSON from Secrets Manager.
    Local: Reads from the file path in FIREBASE_CREDENTIALS_FILE env var.

    Returns:
        Dict of Firebase service account credentials, or None if not configured.
    """
    if is_aws_environment():
        try:
            creds = get_secret("firebase-credentials")
            logger.info("Firebase credentials loaded from AWS Secrets Manager")
            return creds
        except Exception as e:
            logger.warning(f"Failed to load Firebase config from AWS: {e}")
            return None

    creds_file = os.environ.get(
        "FIREBASE_CREDENTIALS_FILE", "./config/firebase-credentials.json"
    )
    if os.path.exists(creds_file):
        with open(creds_file) as f:
            return json.load(f)

    logger.debug("Firebase credentials file not found — FCM disabled")
    return None


def load_webhook_urls() -> list[str]:
    """
    Load webhook notification URLs.

    AWS: Reads from Secrets Manager (livestockguard/webhooks).
    Local: Falls back to WEBHOOK_URLS env var (comma-separated).

    Returns:
        List of webhook URL strings.
    """
    if is_aws_environment():
        try:
            data = get_secret("webhooks")
            return data.get("urls", [])
        except Exception as e:
            logger.warning(f"Failed to load webhook URLs from AWS: {e}")

    urls = os.environ.get("WEBHOOK_URLS", "")
    return [u.strip() for u in urls.split(",") if u.strip()]


def load_mqtt_config() -> dict:
    """
    Load MQTT broker configuration.

    AWS: Reads broker host from Parameter Store.
    Local: Falls back to MQTT_BROKER and MQTT_PORT env vars.

    Returns:
        Dict with keys: broker, port.
    """
    if is_aws_environment():
        try:
            broker = get_parameter("mqtt-broker")
            port = int(get_parameter("mqtt-port"))
            return {"broker": broker, "port": port}
        except Exception as e:
            logger.warning(f"Failed to load MQTT config from AWS: {e}")

    return {
        "broker": os.environ.get("MQTT_BROKER", "localhost"),
        "port": int(os.environ.get("MQTT_PORT", "1883")),
    }
