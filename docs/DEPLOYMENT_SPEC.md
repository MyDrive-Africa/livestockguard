# LivestockGuard Deployment & Go-to-Market Specification

## Regulatory Compliance (South Africa)

### ICASA Type Approval
- Required for all radio-emitting devices (collars + ear-tags)
- Certification: ICASA Form 252 + test reports from accredited lab
- Timeline: 8-12 weeks, budget R50K per device variant
- LoRa: EU868 approved for SA under ISM exemption (≤25mW ERP)

### POPIA (Protection of Personal Information Act)
- Farm location data classified as personal information
- Data residency: All PII stored in AWS af-south-1 (Cape Town)
- Consent: Explicit opt-in during onboarding, granular data sharing controls
- Right to delete: Full data purge within 30 days of request
- Information Officer: Designated per organisation
- PAIA manual: Published on website

### RICA (SIM Registration)
- All cellular SIMs registered to LivestockGuard (Pty) Ltd
- Bulk registration agreement with Vodacom Business
- Device-to-SIM mapping maintained in asset register

### SAMIC Integration
- South African Meat Industry Company animal identification
- 15-digit SAMIC ID linked to device in system
- Supports national traceability requirements for disease control
- API integration for ID validation and reporting

## Infrastructure (AWS af-south-1)

### Architecture
- **Compute**: ECS Fargate (auto-scaling, no EC2 management)
- **Database**: RDS PostgreSQL 15 (Multi-AZ) + TimescaleDB extension
- **Cache**: ElastiCache Redis 7 (cluster mode)
- **MQTT**: EMQX on EC2 (c6g.xlarge × 2, clustered)
- **Storage**: S3 (firmware binaries, exports, backups)
- **CDN**: CloudFront for dashboard + map tiles
- **Monitoring**: CloudWatch + Grafana + PagerDuty

### Cost Estimate (10,000 devices)
| Component | Monthly Cost (ZAR) |
|-----------|-------------------|
| ECS Fargate (6 services) | R8,000 |
| RDS Multi-AZ (db.r6g.large) | R12,000 |
| ElastiCache | R4,000 |
| EMQX EC2 instances | R6,000 |
| Data transfer + S3 | R5,000 |
| Monitoring + misc | R5,000 |
| **Total** | **~R40,000/month** |

## Pricing Model

### Hardware (once-off, excl. VAT)
| Product | Price | Target |
|---------|-------|--------|
| SmartCollar (LTE-M + GPS) | R2,499 | High-value cattle, horses |
| SmartTag (LoRaWAN) | R499 | Sheep, goats, bulk herds |
| SmartTag Pro (LTE-M, no GPS) | R1,299 | Cattle in cellular areas |
| Farm Gateway (LoRa + LTE) | R4,999 | 1 per farm (solar-powered) |

### Subscription (per device/month)
| Plan | Price | Includes |
|------|-------|----------|
| Basic | R29/month | 15-min updates, geofence alerts, app access |
| Standard | R59/month | 5-min updates, analytics, SMS alerts (50/month) |
| Premium | R99/month | 1-min updates, satellite backup, WhatsApp, API access |

## Go-to-Market Strategy

### Phase 1: Pilot (Months 1-6)
- 5 commercial farms in Gauteng/Free State
- 200 devices deployed (mix of collars + tags)
- Free hardware, subscription waived during pilot
- Weekly on-site support, rapid iteration

### Phase 2: Early Adopters (Months 7-12)
- Target: 100 paying customers, 5000 devices
- Channels: Agricultural shows (Nampo, Royal Show), farming co-ops
- Referral programme: 1 month free per referral
- Insurance partnership discount (Hollard Agri)

### Phase 3: Scale (Year 2-3)
- National expansion: all 9 provinces
- Channel partners: Agri retailers (TWK, Senwes, NWK)
- Enterprise tier for large commercial operations (1000+ head)
- Integration with farm management platforms (Agitrack, FarmRanger)

## Partnerships

| Partner | Role |
|---------|------|
| Vodacom Business | IoT connectivity, SIM management, co-marketing |
| Hollard Agri Insurance | Reduced premiums for monitored livestock |
| AgriSA / RPO | Industry body endorsement, member access |
| SAPS Stock Theft Unit | Real-time alert sharing (opt-in) |
| Africa's Talking | SMS/USSD infrastructure |
| ChirpStack | LoRaWAN network server (open-source) |

## Team Structure (Initial - 12 people)

| Role | Count | Focus |
|------|-------|-------|
| Firmware Engineer | 2 | Embedded C, hardware bring-up |
| Backend Engineer | 3 | Rust + Python services |
| Frontend/Mobile Dev | 2 | React + React Native |
| Hardware/RF Engineer | 1 | PCB design, antenna, certification |
| DevOps/SRE | 1 | Infrastructure, CI/CD, monitoring |
| Product Manager | 1 | Roadmap, customer feedback |
| Field Technician | 1 | Installations, support |
| BD / Sales | 1 | Partnerships, enterprise sales |

## 5-Year Scaling Roadmap

| Year | Devices | Revenue (ARR) | Key Milestone |
|------|---------|---------------|---------------|
| 1 | 5,000 | R3M | Product-market fit, first insurance partner |
| 2 | 25,000 | R15M | National coverage, SAPS integration live |
| 3 | 100,000 | R60M | Neighbouring countries (NAM, BWA, MOZ) |
| 4 | 250,000 | R150M | Series B, wildlife/game monitoring vertical |
| 5 | 500,000 | R300M | Pan-African, predictive health AI features |
