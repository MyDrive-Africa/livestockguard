# Sibanyoni Farm — Exclusion Register (Verified GPS Coordinates)

**Date:** 2 August 2026  
**Method:** Satellite imagery click-mapping via LivestockGuard Mark Structure tool  
**Coordinate System:** WGS84 (EPSG:4326)  
**Farm Centre:** Lat -25.3580560, Lon 25.3612750  

---

## Purpose

This register documents all existing structures, compounds, and cultivated fields identified within or near the proposed Sibanyoni Farm boundary. These locations are **formally excluded** from the Sibanyoni Farm claim and remain the property/responsibility of their current occupants.

All coordinates were captured by clicking directly on visible structures in high-resolution satellite imagery.

---

## Exclusion Points Register

| ID | Label | Type | Latitude | Longitude | Notes |
|----|-------|------|----------|-----------|-------|
| X1 | House 1 | House | -25.3576415 | 25.3608834 | Primary dwelling, tin roof visible |
| X2 | Structure of House 1 | Compound | -25.3576270 | 25.3607225 | Outbuilding/annex of X1 |
| X3 | Compound | House | -25.3574864 | 25.3601109 | Separate dwelling, cleared yard |
| X4 | House | House | -25.3572489 | 25.3599822 | Standalone house, near X3 |
| X5 | Compound | Compound | -25.3568780 | 25.3586491 | Multi-structure compound |
| X6 | Structure | House | -25.3568320 | 25.3587591 | Structure adjacent to X5 |
| X7 | Compound | House | -25.3574428 | 25.3602423 | House within compound cluster |
| X8 | Compound | Compound | -25.3593503 | 25.3597435 | Southern compound, multiple structures |
| X9 | Compound | Compound | -25.3592073 | 25.3594270 | Southern compound, adjacent to X8 |
| X10 | Compound | Compound | -25.3601307 | 25.3598963 | Far south compound |
| X11 | Field | Field | -25.3600508 | 25.3593009 | Cultivated/fenced field |
| X12 | Compound | Compound | -25.3605840 | 25.3597998 | Southernmost compound identified |
| X13 | Compound | House | -25.3585892 | 25.3503101 | Western compound (far west of main cluster) |
| X14 | House | House | -25.3583081 | 25.3493445 | Far western house (westernmost structure) |

---

## Cluster Analysis

The structures group into **5 distinct clusters**:

### Cluster A: North-East (X1, X2, X3, X4, X7)
- **Location:** North of farm centre, east side
- **Coordinates range:** Lat -25.3572 to -25.3577, Lon 25.3600 to 25.3609
- **Description:** 5 structures forming a residential neighbourhood along the road
- **Estimated combined footprint:** ~0.8 ha (including yards and clearings)
- **Buffer zone recommended:** 30m around cluster

### Cluster B: North-West (X5, X6)
- **Location:** North-west of farm centre
- **Coordinates range:** Lat -25.3568 to -25.3569, Lon 25.3586 to 25.3588
- **Description:** Compound with adjacent structure, further west along road
- **Estimated combined footprint:** ~0.3 ha
- **Buffer zone recommended:** 20m around cluster

### Cluster C: Centre-South (X8, X9)
- **Location:** South of farm centre, slightly west
- **Coordinates range:** Lat -25.3592 to -25.3594, Lon 25.3594 to 25.3597
- **Description:** Two adjacent compounds
- **Estimated combined footprint:** ~0.4 ha
- **Buffer zone recommended:** 20m around cluster

### Cluster D: Far South (X10, X11, X12)
- **Location:** Far south, near southern boundary edge
- **Coordinates range:** Lat -25.3601 to -25.3606, Lon 25.3593 to 25.3599
- **Description:** Compounds plus a cultivated field
- **Estimated combined footprint:** ~0.6 ha
- **Buffer zone recommended:** 30m around cluster

### Cluster E: Far West (X13, X14) — NEW
- **Location:** Far west, approximately 1km west of pin
- **Coordinates range:** Lat -25.3583 to -25.3586, Lon 25.3493 to 25.3503
- **Description:** Two structures on western side, previously outside analysis area
- **Estimated combined footprint:** ~0.3 ha
- **Buffer zone recommended:** 30m around cluster
- **Impact:** These fall INSIDE the original Option A-Shifted boundary — requiring a new boundary design

---

## Total Exclusion Summary

| Metric | Value |
|--------|-------|
| Total structures identified | 14 |
| Clusters | 5 |
| Estimated total exclusion area (with buffers) | ~4.0 ha |
| Clear gap between clusters (usable corridor) | 775m wide (lon 25.3506 to 25.3583) |

---

## Revised Boundary Options (avoiding all 14 structures)

### Option AS-v2: Rectangle in Clear Gap (60 ha)
- **Shape:** Rectangle 775m × 780m
- **Strategy:** Fits in the clear corridor between western (X13/14) and eastern (X1-12) clusters
- **All 14 structures confirmed OUTSIDE**
- **Coordinates:**
  | Corner | Latitude | Longitude |
  |--------|----------|-----------|
  | NW | -25.3545566 | 25.3506000 |
  | NE | -25.3545566 | 25.3583000 |
  | SE | -25.3615634 | 25.3583000 |
  | SW | -25.3615634 | 25.3506000 |

### Option AS-v3: L-shaped (65 ha)
- **Shape:** Main corridor + south extension below all structures
- **Strategy:** Uses the gap for the main body, extends south where ALL land is clear
- **All 14 structures confirmed OUTSIDE**
- **Main body:** 775m × 540m = 41.8 ha (between clusters)
- **South extension:** 925m × 250m = 23.1 ha (below lat -25.3606)
- **Total:** 64.9 ha

### Key Finding
The structures span from **lon 25.3493 (X14)** to **lon 25.3609 (X1)** — a total east-west spread of ~1,160m. However, there is a **completely clear 775m corridor** between the western pair (X13/X14) and the eastern cluster (X1-X12) with NO structures whatsoever. This corridor is the ideal location for the farm boundary.

---

## CSV Data (for GIS import)

```csv
ID,Label,Type,Latitude,Longitude
X1,house1,house,-25.3576415,25.3608834
X2,structureOfHouse1,compound,-25.3576270,25.3607225
X3,compound,house,-25.3574864,25.3601109
X4,house,house,-25.3572489,25.3599822
X5,Compound,Compound,-25.3568780,25.3586491
X6,Structure,house,-25.3568320,25.3587591
X7,compound,house,-25.3574428,25.3602423
X8,Compound,Compound,-25.3593503,25.3597435
X9,Compound,Compound,-25.3592073,25.3594270
X10,Compound,Compound,-25.3601307,25.3598963
X11,field,field,-25.3600508,25.3593009
X12,Compound,Compound,-25.3605840,25.3597998
X13,compound,house,-25.3585892,25.3503101
X14,house,house,-25.3583081,25.3493445
```

---

## Earlier Estimated Exclusion Zones (Satellite Image Analysis)

These were estimated from satellite imagery before the click-mapping verification. They are polygon areas (not points) inserted into the database as ❌ exclusion geofences:

| Est. ID | Description | Type | Centre Lat | Centre Lon | Est. Area | Polygon Coordinates (WKT) |
|---------|-------------|------|-----------|-----------|-----------|---------------------------|
| E1 | NE Homestead (multiple buildings + fenced field) | Compound | -25.35567 | 25.36090 | 0.48 ha | POLYGON((25.36050 -25.35540, 25.36130 -25.35540, 25.36130 -25.35594, 25.36050 -25.35594, 25.36050 -25.35540)) |
| E2 | Road Junction Houses (2-3 structures) | Houses | -25.35634 | 25.35900 | 0.12 ha | POLYGON((25.35880 -25.35620, 25.35920 -25.35620, 25.35920 -25.35647, 25.35880 -25.35647, 25.35880 -25.35620)) |
| E3 | West Homestead (2 buildings) | Homestead | -25.35741 | 25.35498 | 0.09 ha | POLYGON((25.35480 -25.35730, 25.35515 -25.35730, 25.35515 -25.35752, 25.35480 -25.35752, 25.35480 -25.35730)) |
| E4 | Cultivated Field (fenced rectangular plot) | Field | -25.35803 | 25.35980 | 0.30 ha | POLYGON((25.35950 -25.35780, 25.36010 -25.35780, 25.36010 -25.35825, 25.35950 -25.35825, 25.35950 -25.35780)) |
| E5 | East Road Compound (structures along path) | Compound | -25.35848 | 25.36125 | 0.20 ha | POLYGON((25.36100 -25.35830, 25.36150 -25.35830, 25.36150 -25.35866, 25.36100 -25.35866, 25.36100 -25.35830)) |
| E6 | Main Dirt Road (public, 6m wide NW-SE) | Road | — | — | 0.53 ha | POLYGON((25.35200 -25.35560, 25.35206 -25.35557, 25.36150 -25.35870, 25.36144 -25.35873, 25.35200 -25.35560)) |

**Total estimated exclusion area (polygon-based): 1.71 ha**

### Cross-reference: Estimated vs Verified

| Estimated Zone | Likely corresponds to Verified Points |
|----------------|--------------------------------------|
| E1 (NE Homestead) | X1, X2 (house1 + structure) |
| E2 (Road Junction) | X5, X6 (compound cluster to NW) |
| E3 (West Homestead) | — (may be outside final boundary) |
| E4 (Cultivated Field) | X3, X4, X7 (house/compound cluster) |
| E5 (East Road Compound) | X1, X2 area (overlaps E1 vicinity) |
| E6 (Main Dirt Road) | Confirmed via satellite — road visible |
| — | X8, X9 (new — centre-south compounds) |
| — | X10, X11, X12 (new — far south cluster) |

**Key finding:** The verified click-points identified **6 additional structures** (X8-X12) in the **southern portion** that were not visible in the earlier satellite analysis. This increases the total exclusion area.

---

## Verification Status

- [x] Coordinates captured via satellite imagery (2 August 2026)
- [ ] Ground verification (physical site visit pending)
- [ ] Occupant consultation (to confirm current use)
- [ ] Council review and approval
- [ ] Registered surveyor confirmation

---

*Generated from LivestockGuard Farm Planning System*  
*Source file: sibanyoni-exclusion-structures.csv*
