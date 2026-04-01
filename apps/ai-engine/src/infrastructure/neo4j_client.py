"""Neo4j client for the Santara knowledge graph.

This module provides the infrastructure adapter for Neo4j, implementing
the repository interfaces defined in the domain layer.
"""

import asyncio
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator
from uuid import UUID

from neo4j import AsyncDriver, AsyncGraphDatabase, AsyncSession
from neo4j.exceptions import Neo4jError, ServiceUnavailable

from src.config import get_settings
from src.domain.repositories import (
    EntityNotFoundError,
    GraphConnectionError,
)
from src.domain.schemas import (
    CommunityNode,
    ConnectedTo,
    CropType,
    Farmer,
    GraphSnapshot,
    Market,
    Region,
    RelationshipType,
    TradesWith,
)
from src.logging import get_logger

logger = get_logger(__name__)


class Neo4jClient:
    """Async Neo4j client with connection pooling and schema management.

    This client provides:
    - Connection lifecycle management
    - Schema constraint initialization
    - CRUD operations for graph entities
    - Community detection queries for graph pruning
    """

    def __init__(
        self,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
    ) -> None:
        """Initialize Neo4j client.

        Args:
            uri: Neo4j Bolt URI (defaults to settings)
            user: Neo4j username (defaults to settings)
            password: Neo4j password (defaults to settings)
        """
        settings = get_settings()
        self._uri = uri or settings.neo4j_uri
        self._user = user or settings.neo4j_user
        self._password = password or settings.neo4j_password
        self._driver: AsyncDriver | None = None
        self._initialized = False

    async def connect(self) -> None:
        """Establish connection to Neo4j."""
        if self._driver is not None:
            return

        try:
            self._driver = AsyncGraphDatabase.driver(
                self._uri,
                auth=(self._user, self._password),
                max_connection_pool_size=50,
                connection_acquisition_timeout=30.0,
            )
            # Verify connectivity
            await self._driver.verify_connectivity()
            logger.info("neo4j_connected", uri=self._uri)
        except ServiceUnavailable as e:
            logger.error("neo4j_connection_failed", uri=self._uri, error=str(e))
            raise GraphConnectionError(
                f"Failed to connect to Neo4j at {self._uri}",
                original_error=e,
            ) from e

    async def close(self) -> None:
        """Close the Neo4j connection."""
        if self._driver is not None:
            await self._driver.close()
            self._driver = None
            logger.info("neo4j_disconnected")

    @asynccontextmanager
    async def session(self, database: str = "neo4j") -> AsyncGenerator[AsyncSession, None]:
        """Get a Neo4j session context manager.

        Args:
            database: Database name to use

        Yields:
            AsyncSession for executing queries
        """
        if self._driver is None:
            await self.connect()
        assert self._driver is not None

        session = self._driver.session(database=database)
        try:
            yield session
        finally:
            await session.close()

    # =========================================================================
    # Schema Management
    # =========================================================================

    async def apply_schema_constraints(self) -> None:
        """Apply database schema constraints and indexes.

        Creates:
        - Uniqueness constraints on node IDs
        - Indexes for common query patterns
        """
        if self._initialized:
            return

        constraints = [
            # Node uniqueness constraints
            "CREATE CONSTRAINT farmer_id IF NOT EXISTS FOR (f:Farmer) REQUIRE f.id IS UNIQUE",
            "CREATE CONSTRAINT market_id IF NOT EXISTS FOR (m:Market) REQUIRE m.id IS UNIQUE",
            "CREATE CONSTRAINT region_id IF NOT EXISTS FOR (r:Region) REQUIRE r.id IS UNIQUE",
            "CREATE CONSTRAINT region_code IF NOT EXISTS FOR (r:Region) REQUIRE r.code IS UNIQUE",
            # Indexes for geospatial queries
            "CREATE INDEX farmer_location IF NOT EXISTS FOR (f:Farmer) ON (f.latitude, f.longitude)",
            "CREATE INDEX market_location IF NOT EXISTS FOR (m:Market) ON (m.latitude, m.longitude)",
            # Indexes for common lookups
            "CREATE INDEX farmer_region IF NOT EXISTS FOR (f:Farmer) ON (f.region_id)",
            "CREATE INDEX market_region IF NOT EXISTS FOR (m:Market) ON (m.region_id)",
            "CREATE INDEX farmer_status IF NOT EXISTS FOR (f:Farmer) ON (f.status)",
        ]

        async with self.session() as session:
            for constraint in constraints:
                try:
                    await session.run(constraint)
                    logger.debug("schema_constraint_applied", query=constraint[:50])
                except Neo4jError as e:
                    # Constraint might already exist
                    logger.warning("schema_constraint_warning", query=constraint[:50], error=str(e))

        self._initialized = True
        logger.info("neo4j_schema_initialized", constraints_count=len(constraints))

    async def clear_database(self) -> None:
        """Clear all nodes and relationships (use with caution)."""
        async with self.session() as session:
            await session.run("MATCH (n) DETACH DELETE n")
            logger.warning("neo4j_database_cleared")

    # =========================================================================
    # Farmer Operations
    # =========================================================================

    async def create_farmer(self, farmer: Farmer) -> Farmer:
        """Create a new Farmer node in the graph."""
        query = """
        CREATE (f:Farmer {
            id: $id,
            name: $name,
            region_id: $region_id,
            status: $status,
            cash: $cash,
            inventory: $inventory,
            land_size: $land_size,
            health: $health,
            hunger: $hunger,
            latitude: $latitude,
            longitude: $longitude,
            created_at: datetime(),
            updated_at: datetime()
        })
        RETURN f
        """
        params = {
            "id": str(farmer.id),
            "name": farmer.name,
            "region_id": str(farmer.region_id),
            "status": farmer.status.value,
            "cash": farmer.cash,
            "inventory": {k.value: v for k, v in farmer.inventory.items()},
            "land_size": farmer.land_size,
            "health": farmer.health,
            "hunger": farmer.hunger,
            "latitude": farmer.latitude,
            "longitude": farmer.longitude,
        }

        async with self.session() as session:
            result = await session.run(query, params)
            record = await result.single()
            if record is None:
                raise GraphConnectionError("Failed to create farmer")
            logger.info("farmer_created", farmer_id=str(farmer.id), name=farmer.name)
            return farmer

    async def get_farmer(self, farmer_id: UUID) -> Farmer | None:
        """Get a Farmer by ID."""
        query = "MATCH (f:Farmer {id: $id}) RETURN f"

        async with self.session() as session:
            result = await session.run(query, {"id": str(farmer_id)})
            record = await result.single()
            if record is None:
                return None
            return self._record_to_farmer(record["f"])

    async def get_farmers_by_region(self, region_id: UUID) -> list[Farmer]:
        """Get all Farmers in a region."""
        query = "MATCH (f:Farmer {region_id: $region_id}) RETURN f"

        async with self.session() as session:
            result = await session.run(query, {"region_id": str(region_id)})
            records = await result.values()
            return [self._record_to_farmer(r[0]) for r in records]

    async def get_farmers_nearby(
        self,
        latitude: float,
        longitude: float,
        radius_km: float,
    ) -> list[Farmer]:
        """Get Farmers within a radius using Haversine distance."""
        # Approximate degree distance (1 degree ~ 111km at equator)
        degree_radius = radius_km / 111.0

        query = """
        MATCH (f:Farmer)
        WHERE abs(f.latitude - $lat) <= $deg_radius
          AND abs(f.longitude - $lon) <= $deg_radius
        WITH f,
             point({latitude: f.latitude, longitude: f.longitude}) AS p1,
             point({latitude: $lat, longitude: $lon}) AS p2
        WHERE point.distance(p1, p2) <= $radius_m
        RETURN f
        """

        async with self.session() as session:
            result = await session.run(
                query,
                {
                    "lat": latitude,
                    "lon": longitude,
                    "deg_radius": degree_radius,
                    "radius_m": radius_km * 1000,
                },
            )
            records = await result.values()
            return [self._record_to_farmer(r[0]) for r in records]

    async def update_farmer(self, farmer: Farmer) -> Farmer:
        """Update a Farmer node."""
        query = """
        MATCH (f:Farmer {id: $id})
        SET f.name = $name,
            f.status = $status,
            f.cash = $cash,
            f.inventory = $inventory,
            f.health = $health,
            f.hunger = $hunger,
            f.latitude = $latitude,
            f.longitude = $longitude,
            f.updated_at = datetime()
        RETURN f
        """
        params = {
            "id": str(farmer.id),
            "name": farmer.name,
            "status": farmer.status.value,
            "cash": farmer.cash,
            "inventory": {k.value: v for k, v in farmer.inventory.items()},
            "health": farmer.health,
            "hunger": farmer.hunger,
            "latitude": farmer.latitude,
            "longitude": farmer.longitude,
        }

        async with self.session() as session:
            result = await session.run(query, params)
            record = await result.single()
            if record is None:
                raise EntityNotFoundError("Farmer", str(farmer.id))
            logger.debug("farmer_updated", farmer_id=str(farmer.id))
            return farmer

    async def delete_farmer(self, farmer_id: UUID) -> bool:
        """Delete a Farmer and all its relationships."""
        query = "MATCH (f:Farmer {id: $id}) DETACH DELETE f RETURN count(f) as deleted"

        async with self.session() as session:
            result = await session.run(query, {"id": str(farmer_id)})
            record = await result.single()
            deleted = record["deleted"] > 0 if record else False
            if deleted:
                logger.info("farmer_deleted", farmer_id=str(farmer_id))
            return deleted

    def _record_to_farmer(self, node: Any) -> Farmer:
        """Convert a Neo4j node to a Farmer domain entity."""
        props = dict(node)
        inventory = {}
        if props.get("inventory"):
            for k, v in props["inventory"].items():
                try:
                    inventory[CropType(k)] = float(v)
                except ValueError:
                    pass

        return Farmer(
            id=UUID(props["id"]),
            name=props["name"],
            region_id=UUID(props["region_id"]),
            status=props.get("status", "idle"),
            cash=float(props.get("cash", 0)),
            inventory=inventory,
            land_size=float(props.get("land_size", 1.0)),
            health=float(props.get("health", 100)),
            hunger=float(props.get("hunger", 0)),
            latitude=float(props["latitude"]),
            longitude=float(props["longitude"]),
        )

    # =========================================================================
    # Market Operations
    # =========================================================================

    async def create_market(self, market: Market) -> Market:
        """Create a new Market node in the graph."""
        query = """
        CREATE (m:Market {
            id: $id,
            name: $name,
            market_type: $market_type,
            region_id: $region_id,
            latitude: $latitude,
            longitude: $longitude,
            prices: $prices,
            demand: $demand,
            supply: $supply,
            daily_volume: $daily_volume,
            created_at: datetime(),
            updated_at: datetime()
        })
        RETURN m
        """
        params = {
            "id": str(market.id),
            "name": market.name,
            "market_type": market.market_type.value,
            "region_id": str(market.region_id),
            "latitude": market.latitude,
            "longitude": market.longitude,
            "prices": {k.value: v for k, v in market.prices.items()},
            "demand": {k.value: v for k, v in market.demand.items()},
            "supply": {k.value: v for k, v in market.supply.items()},
            "daily_volume": market.daily_volume,
        }

        async with self.session() as session:
            result = await session.run(query, params)
            record = await result.single()
            if record is None:
                raise GraphConnectionError("Failed to create market")
            logger.info("market_created", market_id=str(market.id), name=market.name)
            return market

    async def get_market(self, market_id: UUID) -> Market | None:
        """Get a Market by ID."""
        query = "MATCH (m:Market {id: $id}) RETURN m"

        async with self.session() as session:
            result = await session.run(query, {"id": str(market_id)})
            record = await result.single()
            if record is None:
                return None
            return self._record_to_market(record["m"])

    async def get_markets_nearby(
        self,
        latitude: float,
        longitude: float,
        radius_km: float,
    ) -> list[Market]:
        """Get Markets within a radius."""
        degree_radius = radius_km / 111.0

        query = """
        MATCH (m:Market)
        WHERE abs(m.latitude - $lat) <= $deg_radius
          AND abs(m.longitude - $lon) <= $deg_radius
        WITH m,
             point({latitude: m.latitude, longitude: m.longitude}) AS p1,
             point({latitude: $lat, longitude: $lon}) AS p2
        WHERE point.distance(p1, p2) <= $radius_m
        RETURN m
        ORDER BY point.distance(p1, p2)
        """

        async with self.session() as session:
            result = await session.run(
                query,
                {
                    "lat": latitude,
                    "lon": longitude,
                    "deg_radius": degree_radius,
                    "radius_m": radius_km * 1000,
                },
            )
            records = await result.values()
            return [self._record_to_market(r[0]) for r in records]

    async def update_market(self, market: Market) -> Market:
        """Update a Market node."""
        query = """
        MATCH (m:Market {id: $id})
        SET m.name = $name,
            m.prices = $prices,
            m.demand = $demand,
            m.supply = $supply,
            m.daily_volume = $daily_volume,
            m.updated_at = datetime()
        RETURN m
        """
        params = {
            "id": str(market.id),
            "name": market.name,
            "prices": {k.value: v for k, v in market.prices.items()},
            "demand": {k.value: v for k, v in market.demand.items()},
            "supply": {k.value: v for k, v in market.supply.items()},
            "daily_volume": market.daily_volume,
        }

        async with self.session() as session:
            result = await session.run(query, params)
            record = await result.single()
            if record is None:
                raise EntityNotFoundError("Market", str(market.id))
            return market

    def _record_to_market(self, node: Any) -> Market:
        """Convert a Neo4j node to a Market domain entity."""
        props = dict(node)

        def parse_crop_dict(d: dict | None) -> dict[CropType, float]:
            if not d:
                return {}
            result = {}
            for k, v in d.items():
                try:
                    result[CropType(k)] = float(v)
                except ValueError:
                    pass
            return result

        return Market(
            id=UUID(props["id"]),
            name=props["name"],
            market_type=props.get("market_type", "local"),
            region_id=UUID(props["region_id"]),
            latitude=float(props["latitude"]),
            longitude=float(props["longitude"]),
            prices=parse_crop_dict(props.get("prices")),
            demand=parse_crop_dict(props.get("demand")),
            supply=parse_crop_dict(props.get("supply")),
            daily_volume=float(props.get("daily_volume", 1000)),
        )

    # =========================================================================
    # Region Operations
    # =========================================================================

    async def create_region(self, region: Region) -> Region:
        """Create a new Region node."""
        query = """
        CREATE (r:Region {
            id: $id,
            name: $name,
            code: $code,
            level: $level,
            parent_id: $parent_id,
            center_latitude: $center_latitude,
            center_longitude: $center_longitude,
            population: $population,
            area_km2: $area_km2,
            created_at: datetime(),
            updated_at: datetime()
        })
        RETURN r
        """
        params = {
            "id": str(region.id),
            "name": region.name,
            "code": region.code,
            "level": region.level,
            "parent_id": str(region.parent_id) if region.parent_id else None,
            "center_latitude": region.center_latitude,
            "center_longitude": region.center_longitude,
            "population": region.population,
            "area_km2": region.area_km2,
        }

        async with self.session() as session:
            result = await session.run(query, params)
            record = await result.single()
            if record is None:
                raise GraphConnectionError("Failed to create region")
            logger.info("region_created", region_id=str(region.id), name=region.name)
            return region

    async def get_region(self, region_id: UUID) -> Region | None:
        """Get a Region by ID."""
        query = "MATCH (r:Region {id: $id}) RETURN r"

        async with self.session() as session:
            result = await session.run(query, {"id": str(region_id)})
            record = await result.single()
            if record is None:
                return None
            return self._record_to_region(record["r"])

    async def get_region_by_code(self, code: str) -> Region | None:
        """Get a Region by administrative code."""
        query = "MATCH (r:Region {code: $code}) RETURN r"

        async with self.session() as session:
            result = await session.run(query, {"code": code})
            record = await result.single()
            if record is None:
                return None
            return self._record_to_region(record["r"])

    def _record_to_region(self, node: Any) -> Region:
        """Convert a Neo4j node to a Region domain entity."""
        props = dict(node)
        return Region(
            id=UUID(props["id"]),
            name=props["name"],
            code=props["code"],
            level=int(props.get("level", 3)),
            parent_id=UUID(props["parent_id"]) if props.get("parent_id") else None,
            center_latitude=float(props["center_latitude"]),
            center_longitude=float(props["center_longitude"]),
            population=int(props.get("population", 0)),
            area_km2=float(props.get("area_km2", 0)),
        )

    # =========================================================================
    # Relationship Operations
    # =========================================================================

    async def create_connection(
        self,
        source_id: UUID,
        target_id: UUID,
        distance_km: float,
        travel_time_hours: float = 0.0,
        road_quality: float = 0.5,
    ) -> ConnectedTo:
        """Create a CONNECTED_TO relationship between nodes."""
        query = """
        MATCH (a {id: $source_id}), (b {id: $target_id})
        MERGE (a)-[r:CONNECTED_TO]->(b)
        SET r.distance_km = $distance_km,
            r.travel_time_hours = $travel_time_hours,
            r.road_quality = $road_quality
        RETURN r
        """
        params = {
            "source_id": str(source_id),
            "target_id": str(target_id),
            "distance_km": distance_km,
            "travel_time_hours": travel_time_hours,
            "road_quality": road_quality,
        }

        async with self.session() as session:
            result = await session.run(query, params)
            record = await result.single()
            if record is None:
                raise EntityNotFoundError("Node", f"{source_id} or {target_id}")

        return ConnectedTo(
            source_id=source_id,
            target_id=target_id,
            distance_km=distance_km,
            travel_time_hours=travel_time_hours,
            road_quality=road_quality,
        )

    async def create_trade_relationship(
        self,
        farmer_id: UUID,
        market_id: UUID,
    ) -> TradesWith:
        """Create or update a TRADES_WITH relationship."""
        query = """
        MATCH (f:Farmer {id: $farmer_id}), (m:Market {id: $market_id})
        MERGE (f)-[r:TRADES_WITH]->(m)
        ON CREATE SET r.frequency = 1, r.total_volume = 0, r.trust_score = 0.5
        ON MATCH SET r.frequency = r.frequency + 1
        RETURN r
        """
        params = {
            "farmer_id": str(farmer_id),
            "market_id": str(market_id),
        }

        async with self.session() as session:
            result = await session.run(query, params)
            record = await result.single()
            if record is None:
                raise EntityNotFoundError("Farmer or Market", f"{farmer_id}, {market_id}")

            rel = record["r"]
            return TradesWith(
                source_id=farmer_id,
                target_id=market_id,
                frequency=rel.get("frequency", 1),
                total_volume=rel.get("total_volume", 0),
                trust_score=rel.get("trust_score", 0.5),
            )

    async def get_connections(self, node_id: UUID) -> list[ConnectedTo]:
        """Get all CONNECTED_TO relationships from a node."""
        query = """
        MATCH (a {id: $id})-[r:CONNECTED_TO]->(b)
        RETURN r, b.id as target_id
        """

        async with self.session() as session:
            result = await session.run(query, {"id": str(node_id)})
            records = await result.values()
            connections = []
            for rel, target_id in records:
                connections.append(
                    ConnectedTo(
                        source_id=node_id,
                        target_id=UUID(target_id),
                        distance_km=rel.get("distance_km", 0),
                        travel_time_hours=rel.get("travel_time_hours", 0),
                        road_quality=rel.get("road_quality", 0.5),
                    )
                )
            return connections

    async def get_trade_relationships(self, farmer_id: UUID) -> list[TradesWith]:
        """Get all TRADES_WITH relationships for a farmer."""
        query = """
        MATCH (f:Farmer {id: $id})-[r:TRADES_WITH]->(m:Market)
        RETURN r, m.id as market_id
        """

        async with self.session() as session:
            result = await session.run(query, {"id": str(farmer_id)})
            records = await result.values()
            trades = []
            for rel, market_id in records:
                trades.append(
                    TradesWith(
                        source_id=farmer_id,
                        target_id=UUID(market_id),
                        frequency=rel.get("frequency", 0),
                        total_volume=rel.get("total_volume", 0),
                        trust_score=rel.get("trust_score", 0.5),
                    )
                )
            return trades

    # =========================================================================
    # Community Detection (Graph Pruning)
    # =========================================================================

    async def detect_communities(self) -> list[CommunityNode]:
        """Detect communities using Label Propagation for graph summarization.

        This enables eager graph pruning to keep LLM prompts small.
        Uses Neo4j GDS (Graph Data Science) library if available,
        otherwise falls back to a simple region-based clustering.
        """
        # Try GDS community detection first
        try:
            return await self._detect_communities_gds()
        except Neo4jError:
            # Fall back to region-based clustering
            logger.warning("gds_unavailable", fallback="region_clustering")
            return await self._detect_communities_region()

    async def _detect_communities_gds(self) -> list[CommunityNode]:
        """Use Neo4j GDS Label Propagation for community detection."""
        # Project the graph
        project_query = """
        CALL gds.graph.project(
            'santara_graph',
            ['Farmer', 'Market', 'Region'],
            {
                CONNECTED_TO: {orientation: 'UNDIRECTED'},
                TRADES_WITH: {orientation: 'UNDIRECTED'}
            }
        )
        """

        # Run community detection
        detect_query = """
        CALL gds.labelPropagation.stream('santara_graph')
        YIELD nodeId, communityId
        WITH gds.util.asNode(nodeId) AS node, communityId
        RETURN communityId,
               count(*) as member_count,
               avg(node.latitude) as center_lat,
               avg(node.longitude) as center_lon,
               collect(DISTINCT labels(node)[0]) as node_types
        ORDER BY member_count DESC
        """

        # Clean up
        drop_query = "CALL gds.graph.drop('santara_graph', false)"

        async with self.session() as session:
            try:
                await session.run(project_query)
                result = await session.run(detect_query)
                records = await result.values()

                communities = []
                for community_id, count, lat, lon, _ in records:
                    communities.append(
                        CommunityNode(
                            community_id=str(community_id),
                            member_count=count,
                            center_latitude=lat or 0,
                            center_longitude=lon or 0,
                            dominant_crops=[],
                            average_price={},
                            summary=f"Community {community_id} with {count} nodes",
                        )
                    )
                return communities
            finally:
                await session.run(drop_query)

    async def _detect_communities_region(self) -> list[CommunityNode]:
        """Fallback: cluster by region for community summarization."""
        query = """
        MATCH (r:Region)
        OPTIONAL MATCH (f:Farmer {region_id: r.id})
        OPTIONAL MATCH (m:Market {region_id: r.id})
        WITH r,
             count(DISTINCT f) + count(DISTINCT m) as member_count,
             collect(DISTINCT f.inventory) as inventories
        WHERE member_count > 0
        RETURN r.id as community_id,
               r.name as name,
               member_count,
               r.center_latitude as center_lat,
               r.center_longitude as center_lon,
               inventories
        ORDER BY member_count DESC
        """

        async with self.session() as session:
            result = await session.run(query)
            records = await result.values()

            communities = []
            for community_id, name, count, lat, lon, inventories in records:
                # Aggregate crop types from inventories
                crop_counts: dict[str, int] = {}
                for inv in inventories:
                    if inv:
                        for crop in inv.keys():
                            crop_counts[crop] = crop_counts.get(crop, 0) + 1

                dominant_crops = []
                for crop in sorted(crop_counts, key=crop_counts.get, reverse=True)[:3]:  # type: ignore
                    try:
                        dominant_crops.append(CropType(crop))
                    except ValueError:
                        pass

                communities.append(
                    CommunityNode(
                        community_id=str(community_id),
                        member_count=count,
                        center_latitude=lat or 0,
                        center_longitude=lon or 0,
                        dominant_crops=dominant_crops,
                        average_price={},
                        summary=f"Region {name} with {count} entities",
                    )
                )
            return communities

    # =========================================================================
    # Graph Snapshot
    # =========================================================================

    async def get_snapshot(self) -> GraphSnapshot:
        """Get a full snapshot of the graph for serialization."""
        async with self.session() as session:
            # Get all farmers
            farmers_result = await session.run("MATCH (f:Farmer) RETURN f")
            farmers = [self._record_to_farmer(r["f"]) for r in await farmers_result.values()]

            # Get all markets
            markets_result = await session.run("MATCH (m:Market) RETURN m")
            markets = [self._record_to_market(r["m"]) for r in await markets_result.values()]

            # Get all regions
            regions_result = await session.run("MATCH (r:Region) RETURN r")
            regions = [self._record_to_region(r["r"]) for r in await regions_result.values()]

            # Get communities
            communities = await self.detect_communities()

        return GraphSnapshot(
            farmers=farmers,
            markets=markets,
            regions=regions,
            communities=communities,
        )


# =============================================================================
# Factory Function
# =============================================================================


async def create_neo4j_client() -> Neo4jClient:
    """Create and initialize a Neo4j client."""
    client = Neo4jClient()
    await client.connect()
    await client.apply_schema_constraints()
    return client
