#!/usr/bin/env python3
"""OpenStreetMap data ingestion script for Santara knowledge graph.

This script parses OpenStreetMap (OSM) data in GeoJSON format and ingests
geographic entities (markets, regions, roads) into the Neo4j knowledge graph.

Usage:
    python -m scripts.ingest_osm --input data/osm_export.geojson
    python -m scripts.ingest_osm --input data/ --pattern "*.geojson"
"""

import argparse
import asyncio
import json
import sys
from math import atan2, cos, radians, sin, sqrt
from pathlib import Path
from typing import Any
from uuid import uuid4

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_settings
from src.domain.schemas import (
    ConnectedTo,
    CropType,
    Market,
    MarketType,
    Region,
)
from src.infrastructure.neo4j_client import Neo4jClient
from src.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points in kilometers."""
    r = 6371  # Earth's radius in km

    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return r * c


class OSMIngester:
    """Ingests OpenStreetMap data into Neo4j."""

    def __init__(self, neo4j_client: Neo4jClient) -> None:
        """Initialize the ingester.

        Args:
            neo4j_client: Connected Neo4j client instance
        """
        self._client = neo4j_client
        self._stats = {
            "markets_created": 0,
            "regions_created": 0,
            "connections_created": 0,
            "features_skipped": 0,
        }
        self._regions: dict[str, Region] = {}  # code -> Region
        self._markets: list[Market] = []

    async def ingest_file(self, file_path: Path) -> dict[str, int]:
        """Ingest a GeoJSON file into Neo4j.

        Args:
            file_path: Path to GeoJSON file

        Returns:
            Statistics dict with counts of created entities
        """
        logger.info("osm_ingest_start", file=str(file_path))

        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)

        if data.get("type") == "FeatureCollection":
            features = data.get("features", [])
        elif data.get("type") == "Feature":
            features = [data]
        else:
            logger.warning("osm_unknown_format", file=str(file_path))
            return self._stats

        # Process features by type
        for feature in features:
            await self._process_feature(feature)

        # Create connections between nearby markets
        await self._create_market_connections()

        logger.info(
            "osm_ingest_complete",
            file=str(file_path),
            stats=self._stats,
        )
        return self._stats

    async def _process_feature(self, feature: dict[str, Any]) -> None:
        """Process a single GeoJSON feature."""
        geometry = feature.get("geometry", {})
        properties = feature.get("properties", {})
        feature_type = geometry.get("type", "")

        # Extract tags/properties
        tags = properties.get("tags", properties)
        osm_type = tags.get("amenity") or tags.get("shop") or tags.get("landuse")
        name = tags.get("name") or tags.get("name:en") or tags.get("name:id")

        # Handle Points (markets, shops)
        if feature_type == "Point" and osm_type in ("marketplace", "market", "supermarket"):
            await self._create_market_from_feature(feature, tags)
        # Handle Polygons (regions, administrative boundaries)
        elif feature_type in ("Polygon", "MultiPolygon") and tags.get("admin_level"):
            await self._create_region_from_feature(feature, tags)
        else:
            self._stats["features_skipped"] += 1

    async def _create_market_from_feature(
        self,
        feature: dict[str, Any],
        tags: dict[str, Any],
    ) -> None:
        """Create a Market from an OSM feature."""
        geometry = feature.get("geometry", {})
        coords = geometry.get("coordinates", [0, 0])

        # GeoJSON uses [longitude, latitude]
        longitude, latitude = coords[0], coords[1]

        name = tags.get("name") or tags.get("name:id") or f"Market {uuid4().hex[:8]}"

        # Determine market type from tags
        market_type = MarketType.LOCAL
        if tags.get("shop") == "supermarket":
            market_type = MarketType.DISTRICT
        elif "pasar" in name.lower() and "induk" in name.lower():
            market_type = MarketType.REGIONAL

        # Find or create a region for this market
        region_id = await self._get_or_create_default_region(latitude, longitude)

        # Set default prices for common crops
        default_prices = {
            CropType.RICE: 12000.0,  # IDR per kg
            CropType.CORN: 5000.0,
            CropType.CASSAVA: 3000.0,
            CropType.SOYBEAN: 10000.0,
        }

        market = Market(
            id=uuid4(),
            name=name,
            market_type=market_type,
            region_id=region_id,
            latitude=latitude,
            longitude=longitude,
            prices=default_prices,
            demand={crop: 100.0 for crop in CropType},
            supply={crop: 50.0 for crop in CropType},
            daily_volume=1000.0 if market_type == MarketType.LOCAL else 5000.0,
            properties={
                "osm_id": tags.get("@id"),
                "opening_hours": tags.get("opening_hours"),
            },
        )

        await self._client.create_market(market)
        self._markets.append(market)
        self._stats["markets_created"] += 1

    async def _create_region_from_feature(
        self,
        feature: dict[str, Any],
        tags: dict[str, Any],
    ) -> None:
        """Create a Region from an OSM administrative boundary."""
        geometry = feature.get("geometry", {})
        name = tags.get("name") or tags.get("name:id") or "Unknown Region"
        admin_level = int(tags.get("admin_level", 3))
        code = tags.get("ref") or tags.get("ISO3166-2") or f"REG-{uuid4().hex[:8]}"

        # Calculate centroid from polygon
        center_lat, center_lon = self._calculate_centroid(geometry)

        # Map OSM admin_level to our level system
        # OSM: 2=country, 4=province, 5=kabupaten, 6=kecamatan, 7=kelurahan
        level_map = {2: 1, 4: 1, 5: 2, 6: 3, 7: 4, 8: 5}
        level = level_map.get(admin_level, 3)

        region = Region(
            id=uuid4(),
            name=name,
            code=code,
            level=level,
            center_latitude=center_lat,
            center_longitude=center_lon,
            population=int(tags.get("population", 0)),
            area_km2=float(tags.get("area", 0)),
        )

        await self._client.create_region(region)
        self._regions[code] = region
        self._stats["regions_created"] += 1

    def _calculate_centroid(self, geometry: dict[str, Any]) -> tuple[float, float]:
        """Calculate the centroid of a polygon geometry."""
        geo_type = geometry.get("type", "")
        coords = geometry.get("coordinates", [])

        if not coords:
            return 0.0, 0.0

        points: list[tuple[float, float]] = []

        if geo_type == "Polygon":
            # First ring is exterior
            points = [(c[1], c[0]) for c in coords[0]]  # lat, lon
        elif geo_type == "MultiPolygon":
            # Use first polygon
            if coords and coords[0]:
                points = [(c[1], c[0]) for c in coords[0][0]]

        if not points:
            return 0.0, 0.0

        avg_lat = sum(p[0] for p in points) / len(points)
        avg_lon = sum(p[1] for p in points) / len(points)
        return avg_lat, avg_lon

    async def _get_or_create_default_region(
        self,
        latitude: float,
        longitude: float,
    ) -> Any:
        """Get or create a default region for entities without region assignment."""
        # Try to find existing region containing this point
        for region in self._regions.values():
            # Simple bounding box check (not precise but fast)
            if abs(region.center_latitude - latitude) < 0.5 and abs(
                region.center_longitude - longitude
            ) < 0.5:
                return region.id

        # Create a default region
        code = f"DEFAULT-{len(self._regions)}"
        if code not in self._regions:
            region = Region(
                id=uuid4(),
                name=f"Area {len(self._regions) + 1}",
                code=code,
                level=3,
                center_latitude=latitude,
                center_longitude=longitude,
            )
            await self._client.create_region(region)
            self._regions[code] = region
            self._stats["regions_created"] += 1

        return self._regions[code].id

    async def _create_market_connections(self, max_distance_km: float = 50.0) -> None:
        """Create CONNECTED_TO relationships between nearby markets."""
        for i, market1 in enumerate(self._markets):
            for market2 in self._markets[i + 1 :]:
                distance = haversine_distance(
                    market1.latitude,
                    market1.longitude,
                    market2.latitude,
                    market2.longitude,
                )

                if distance <= max_distance_km:
                    # Estimate travel time (assume 30 km/h average)
                    travel_time = distance / 30.0

                    await self._client.create_connection(
                        source_id=market1.id,
                        target_id=market2.id,
                        distance_km=distance,
                        travel_time_hours=travel_time,
                        road_quality=0.7,  # Default assumption
                    )
                    self._stats["connections_created"] += 1


async def main() -> None:
    """Main entry point for OSM ingestion."""
    parser = argparse.ArgumentParser(
        description="Ingest OpenStreetMap data into Santara Neo4j graph"
    )
    parser.add_argument(
        "--input",
        "-i",
        type=str,
        required=True,
        help="Input GeoJSON file or directory",
    )
    parser.add_argument(
        "--pattern",
        "-p",
        type=str,
        default="*.geojson",
        help="Glob pattern for files when input is a directory",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing data before ingestion",
    )

    args = parser.parse_args()
    input_path = Path(args.input)

    # Initialize Neo4j client
    client = Neo4jClient()
    await client.connect()
    await client.apply_schema_constraints()

    if args.clear:
        logger.warning("clearing_database")
        await client.clear_database()

    try:
        ingester = OSMIngester(client)

        if input_path.is_file():
            await ingester.ingest_file(input_path)
        elif input_path.is_dir():
            files = list(input_path.glob(args.pattern))
            logger.info("osm_batch_ingest", file_count=len(files))
            for file_path in files:
                await ingester.ingest_file(file_path)
        else:
            logger.error("osm_input_not_found", path=str(input_path))
            sys.exit(1)

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
