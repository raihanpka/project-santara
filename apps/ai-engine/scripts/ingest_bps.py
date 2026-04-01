#!/usr/bin/env python3
"""BPS (Badan Pusat Statistik) data ingestion script for Santara knowledge graph.

This script parses CSV data from Indonesian Statistics Bureau and ingests
economic/demographic data (regions, population, agricultural statistics)
into the Neo4j knowledge graph.

Usage:
    python -m scripts.ingest_bps --input data/bps_regions.csv --type regions
    python -m scripts.ingest_bps --input data/bps_agriculture.csv --type agriculture
    python -m scripts.ingest_bps --input data/ --pattern "*.csv"
"""

import argparse
import asyncio
import csv
import sys
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_settings
from src.domain.schemas import (
    CropType,
    Farmer,
    Market,
    MarketType,
    Region,
)
from src.infrastructure.neo4j_client import Neo4jClient
from src.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


class DataType(str, Enum):
    """Types of BPS data files."""

    REGIONS = "regions"
    AGRICULTURE = "agriculture"
    POPULATION = "population"
    MARKETS = "markets"
    PRICES = "prices"


# Default column mappings for BPS CSV formats
COLUMN_MAPPINGS = {
    DataType.REGIONS: {
        "kode": "code",
        "nama": "name",
        "nama_wilayah": "name",
        "kode_wilayah": "code",
        "level": "level",
        "tingkat": "level",
        "latitude": "latitude",
        "lat": "latitude",
        "longitude": "longitude",
        "lon": "longitude",
        "lng": "longitude",
        "populasi": "population",
        "jumlah_penduduk": "population",
        "luas": "area_km2",
        "luas_wilayah": "area_km2",
        "parent_code": "parent_code",
        "kode_induk": "parent_code",
    },
    DataType.AGRICULTURE: {
        "kode_wilayah": "region_code",
        "komoditas": "crop_type",
        "jenis_tanaman": "crop_type",
        "produksi": "production_kg",
        "luas_panen": "harvest_area_ha",
        "produktivitas": "productivity",
        "harga": "price_per_kg",
    },
    DataType.MARKETS: {
        "nama": "name",
        "nama_pasar": "name",
        "kode_wilayah": "region_code",
        "latitude": "latitude",
        "lat": "latitude",
        "longitude": "longitude",
        "lon": "longitude",
        "lng": "longitude",
        "tipe": "market_type",
        "jenis": "market_type",
        "volume_harian": "daily_volume",
    },
    DataType.PRICES: {
        "kode_wilayah": "region_code",
        "komoditas": "crop_type",
        "harga": "price",
        "harga_per_kg": "price",
        "tanggal": "date",
    },
}

# Crop type mappings from Indonesian to enum
CROP_MAPPINGS = {
    "padi": CropType.RICE,
    "beras": CropType.RICE,
    "jagung": CropType.CORN,
    "singkong": CropType.CASSAVA,
    "ubi kayu": CropType.CASSAVA,
    "kedelai": CropType.SOYBEAN,
    "kacang tanah": CropType.PEANUT,
    "sayuran": CropType.VEGETABLE,
    "buah": CropType.FRUIT,
}


class BPSIngester:
    """Ingests BPS statistical data into Neo4j."""

    def __init__(self, neo4j_client: Neo4jClient) -> None:
        """Initialize the ingester.

        Args:
            neo4j_client: Connected Neo4j client instance
        """
        self._client = neo4j_client
        self._stats = {
            "regions_created": 0,
            "farmers_created": 0,
            "markets_created": 0,
            "markets_updated": 0,
            "rows_processed": 0,
            "rows_skipped": 0,
        }
        self._regions: dict[str, Region] = {}  # code -> Region

    async def ingest_file(
        self,
        file_path: Path,
        data_type: DataType,
    ) -> dict[str, int]:
        """Ingest a CSV file into Neo4j.

        Args:
            file_path: Path to CSV file
            data_type: Type of data in the file

        Returns:
            Statistics dict with counts of created entities
        """
        logger.info("bps_ingest_start", file=str(file_path), data_type=data_type.value)

        with open(file_path, encoding="utf-8-sig", newline="") as f:
            # Detect delimiter
            sample = f.read(4096)
            f.seek(0)
            delimiter = ";" if ";" in sample else ","

            reader = csv.DictReader(f, delimiter=delimiter)
            rows = list(reader)

        if not rows:
            logger.warning("bps_empty_file", file=str(file_path))
            return self._stats

        # Normalize column names
        column_mapping = COLUMN_MAPPINGS.get(data_type, {})
        normalized_rows = [self._normalize_row(row, column_mapping) for row in rows]

        # Process based on data type
        if data_type == DataType.REGIONS:
            await self._process_regions(normalized_rows)
        elif data_type == DataType.AGRICULTURE:
            await self._process_agriculture(normalized_rows)
        elif data_type == DataType.MARKETS:
            await self._process_markets(normalized_rows)
        elif data_type == DataType.PRICES:
            await self._process_prices(normalized_rows)
        else:
            logger.warning("bps_unknown_type", data_type=data_type.value)

        logger.info(
            "bps_ingest_complete",
            file=str(file_path),
            stats=self._stats,
        )
        return self._stats

    def _normalize_row(
        self,
        row: dict[str, Any],
        mapping: dict[str, str],
    ) -> dict[str, Any]:
        """Normalize a CSV row using column mappings."""
        normalized: dict[str, Any] = {}
        for key, value in row.items():
            # Lowercase and strip the key
            clean_key = key.lower().strip()
            # Map to standard name if available
            standard_key = mapping.get(clean_key, clean_key)
            # Clean the value
            clean_value = value.strip() if isinstance(value, str) else value
            normalized[standard_key] = clean_value
        return normalized

    async def _process_regions(self, rows: list[dict[str, Any]]) -> None:
        """Process region data from BPS."""
        # First pass: create all regions
        for row in rows:
            self._stats["rows_processed"] += 1

            code = row.get("code", "")
            name = row.get("name", "")

            if not code or not name:
                self._stats["rows_skipped"] += 1
                continue

            # Parse coordinates
            try:
                latitude = float(row.get("latitude", 0) or 0)
                longitude = float(row.get("longitude", 0) or 0)
            except (ValueError, TypeError):
                latitude, longitude = 0.0, 0.0

            # Parse level (default to 3 = kecamatan)
            try:
                level = int(row.get("level", 3) or 3)
            except (ValueError, TypeError):
                level = 3

            # Parse population
            try:
                population = int(float(row.get("population", 0) or 0))
            except (ValueError, TypeError):
                population = 0

            # Parse area
            try:
                area_km2 = float(row.get("area_km2", 0) or 0)
            except (ValueError, TypeError):
                area_km2 = 0.0

            region = Region(
                id=uuid4(),
                name=name,
                code=code,
                level=level,
                center_latitude=latitude,
                center_longitude=longitude,
                population=population,
                area_km2=area_km2,
            )

            await self._client.create_region(region)
            self._regions[code] = region
            self._stats["regions_created"] += 1

    async def _process_agriculture(self, rows: list[dict[str, Any]]) -> None:
        """Process agricultural statistics to create farmers."""
        for row in rows:
            self._stats["rows_processed"] += 1

            region_code = row.get("region_code", "")
            crop_type_str = row.get("crop_type", "").lower()

            # Get region
            region = await self._get_region_by_code(region_code)
            if not region:
                self._stats["rows_skipped"] += 1
                continue

            # Map crop type
            crop_type = CROP_MAPPINGS.get(crop_type_str)
            if not crop_type:
                self._stats["rows_skipped"] += 1
                continue

            # Parse production data
            try:
                production_kg = float(row.get("production_kg", 0) or 0)
                harvest_area_ha = float(row.get("harvest_area_ha", 0) or 0)
            except (ValueError, TypeError):
                production_kg, harvest_area_ha = 0.0, 1.0

            # Estimate number of farmers (1 farmer per 2 hectares average)
            estimated_farmers = max(1, int(harvest_area_ha / 2))

            # Create representative farmers
            for i in range(min(estimated_farmers, 10)):  # Cap at 10 per row
                # Add some variation to location
                lat_offset = (hash(f"{region_code}{i}") % 100 - 50) / 1000
                lon_offset = (hash(f"{i}{region_code}") % 100 - 50) / 1000

                farmer = Farmer(
                    id=uuid4(),
                    name=f"Petani {crop_type.value.title()} {region.name[:20]} #{i + 1}",
                    region_id=region.id,
                    latitude=region.center_latitude + lat_offset,
                    longitude=region.center_longitude + lon_offset,
                    land_size=harvest_area_ha / max(estimated_farmers, 1),
                    cash=500000.0,  # Default starting cash (IDR)
                    inventory={crop_type: production_kg / max(estimated_farmers, 1)},
                    health=100.0,
                    hunger=0.0,
                )

                await self._client.create_farmer(farmer)
                self._stats["farmers_created"] += 1

    async def _process_markets(self, rows: list[dict[str, Any]]) -> None:
        """Process market data from BPS."""
        for row in rows:
            self._stats["rows_processed"] += 1

            name = row.get("name", "")
            region_code = row.get("region_code", "")

            if not name:
                self._stats["rows_skipped"] += 1
                continue

            # Get region
            region = await self._get_region_by_code(region_code)
            if not region:
                # Create a default region
                region = Region(
                    id=uuid4(),
                    name=f"Area untuk {name}",
                    code=f"AUTO-{uuid4().hex[:8]}",
                    level=3,
                    center_latitude=0.0,
                    center_longitude=0.0,
                )
                await self._client.create_region(region)
                self._regions[region.code] = region

            # Parse coordinates
            try:
                latitude = float(row.get("latitude", 0) or region.center_latitude)
                longitude = float(row.get("longitude", 0) or region.center_longitude)
            except (ValueError, TypeError):
                latitude = region.center_latitude
                longitude = region.center_longitude

            # Parse market type
            market_type_str = row.get("market_type", "local").lower()
            if "induk" in market_type_str or "regional" in market_type_str:
                market_type = MarketType.REGIONAL
            elif "kabupaten" in market_type_str or "district" in market_type_str:
                market_type = MarketType.DISTRICT
            else:
                market_type = MarketType.LOCAL

            # Parse volume
            try:
                daily_volume = float(row.get("daily_volume", 1000) or 1000)
            except (ValueError, TypeError):
                daily_volume = 1000.0

            # Default prices
            default_prices = {
                CropType.RICE: 12000.0,
                CropType.CORN: 5000.0,
                CropType.CASSAVA: 3000.0,
                CropType.SOYBEAN: 10000.0,
                CropType.PEANUT: 15000.0,
                CropType.VEGETABLE: 8000.0,
                CropType.FRUIT: 10000.0,
            }

            market = Market(
                id=uuid4(),
                name=name,
                market_type=market_type,
                region_id=region.id,
                latitude=latitude,
                longitude=longitude,
                prices=default_prices,
                demand={crop: 100.0 for crop in CropType},
                supply={crop: 50.0 for crop in CropType},
                daily_volume=daily_volume,
            )

            await self._client.create_market(market)
            self._stats["markets_created"] += 1

    async def _process_prices(self, rows: list[dict[str, Any]]) -> None:
        """Process price data to update market prices."""
        # Group prices by region
        prices_by_region: dict[str, dict[CropType, float]] = {}

        for row in rows:
            self._stats["rows_processed"] += 1

            region_code = row.get("region_code", "")
            crop_type_str = row.get("crop_type", "").lower()
            crop_type = CROP_MAPPINGS.get(crop_type_str)

            if not region_code or not crop_type:
                self._stats["rows_skipped"] += 1
                continue

            try:
                price = float(row.get("price", 0) or 0)
            except (ValueError, TypeError):
                self._stats["rows_skipped"] += 1
                continue

            if region_code not in prices_by_region:
                prices_by_region[region_code] = {}
            prices_by_region[region_code][crop_type] = price

        # Update markets with new prices
        # Note: This would require fetching markets by region, which would
        # need additional Neo4j queries. For now, log the collected prices.
        logger.info(
            "bps_prices_collected",
            regions_count=len(prices_by_region),
        )

    async def _get_region_by_code(self, code: str) -> Region | None:
        """Get a region by code, checking cache first."""
        if code in self._regions:
            return self._regions[code]

        region = await self._client.get_region_by_code(code)
        if region:
            self._regions[code] = region
        return region


def detect_data_type(file_path: Path) -> DataType:
    """Attempt to auto-detect the data type from file content."""
    filename = file_path.stem.lower()

    if "region" in filename or "wilayah" in filename:
        return DataType.REGIONS
    elif "agri" in filename or "pertanian" in filename or "tanaman" in filename:
        return DataType.AGRICULTURE
    elif "market" in filename or "pasar" in filename:
        return DataType.MARKETS
    elif "price" in filename or "harga" in filename:
        return DataType.PRICES

    # Default to regions
    return DataType.REGIONS


async def main() -> None:
    """Main entry point for BPS data ingestion."""
    parser = argparse.ArgumentParser(
        description="Ingest BPS statistical data into Santara Neo4j graph"
    )
    parser.add_argument(
        "--input",
        "-i",
        type=str,
        required=True,
        help="Input CSV file or directory",
    )
    parser.add_argument(
        "--type",
        "-t",
        type=str,
        choices=[t.value for t in DataType],
        help="Type of data in the file (auto-detected if not specified)",
    )
    parser.add_argument(
        "--pattern",
        "-p",
        type=str,
        default="*.csv",
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
        ingester = BPSIngester(client)

        if input_path.is_file():
            data_type = DataType(args.type) if args.type else detect_data_type(input_path)
            await ingester.ingest_file(input_path, data_type)
        elif input_path.is_dir():
            files = list(input_path.glob(args.pattern))
            logger.info("bps_batch_ingest", file_count=len(files))
            for file_path in files:
                data_type = DataType(args.type) if args.type else detect_data_type(file_path)
                await ingester.ingest_file(file_path, data_type)
        else:
            logger.error("bps_input_not_found", path=str(input_path))
            sys.exit(1)

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
