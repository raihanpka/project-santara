"""Application configuration using Pydantic Settings for type-safe env var parsing."""

from enum import Enum
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProvider(str, Enum):
    """Supported LLM providers."""

    GEMINI = "gemini"
    ANTHROPIC = "anthropic"
    OPENAI = "openai"


class LogFormat(str, Enum):
    """Log output formats."""

    JSON = "json"
    CONSOLE = "console"


# =============================================================================
# Localization Configuration (Web UI configurable in future)
# =============================================================================

class LocaleConfig(BaseModel):
    """Localization settings for the simulation.

    This configuration is designed to be:
    1. Loaded from environment variables (current)
    2. Persisted to database for web UI configuration (future)
    3. Serializable to JSON for API responses

    To adapt for a different country/region:
    - Change currency_code, currency_symbol
    - Update admin_level_names for local terminology
    - Adjust default_prices for local market rates
    """

    # Regional Identity
    country_code: str = Field(
        default="ID",
        description="ISO 3166-1 alpha-2 country code",
    )
    country_name: str = Field(
        default="Indonesia",
        description="Full country name for display",
    )
    language_code: str = Field(
        default="id",
        description="ISO 639-1 language code",
    )

    # Currency
    currency_code: str = Field(
        default="IDR",
        description="ISO 4217 currency code",
    )
    currency_symbol: str = Field(
        default="Rp",
        description="Currency symbol for display",
    )
    currency_decimal_places: int = Field(
        default=0,
        ge=0,
        le=4,
        description="Decimal places for currency display",
    )

    # Administrative Levels (customize for local government structure)
    # Level 1 = highest (e.g., Province/State), Level 5 = lowest (e.g., Village)
    admin_level_names: dict[int, str] = Field(
        default={
            1: "Province",
            2: "Regency/City",  # Kabupaten/Kota
            3: "District",       # Kecamatan
            4: "Sub-district",   # Kelurahan/Desa
            5: "Neighborhood",   # RW/RT
        },
        description="Names for administrative levels",
    )

    # Default Prices (per kg in local currency)
    # These serve as baseline prices - actual prices are dynamic
    default_crop_prices: dict[str, float] = Field(
        default={
            "rice": 12000.0,
            "corn": 5000.0,
            "cassava": 3000.0,
            "soybean": 10000.0,
            "peanut": 15000.0,
            "vegetable": 8000.0,
            "fruit": 10000.0,
        },
        description="Default prices per crop type in local currency",
    )

    # Simulation Defaults
    default_agent_cash: float = Field(
        default=500000.0,
        description="Default starting cash for new agents",
    )
    default_land_size_ha: float = Field(
        default=1.0,
        gt=0,
        description="Default land size in hectares",
    )

    # Market Classification Keywords (for data ingestion)
    regional_market_keywords: list[str] = Field(
        default=["induk", "regional", "wholesale", "grosir"],
        description="Keywords identifying regional/wholesale markets",
    )
    district_market_keywords: list[str] = Field(
        default=["kabupaten", "district", "kota", "city"],
        description="Keywords identifying district-level markets",
    )

    def format_currency(self, amount: float) -> str:
        """Format an amount in local currency."""
        if self.currency_decimal_places == 0:
            return f"{self.currency_symbol} {amount:,.0f}"
        return f"{self.currency_symbol} {amount:,.{self.currency_decimal_places}f}"

    def get_admin_level_name(self, level: int) -> str:
        """Get the name for an administrative level."""
        return self.admin_level_names.get(level, f"Level {level}")


# Preset configurations for common countries
LOCALE_PRESETS: dict[str, dict] = {
    "ID": {  # Indonesia
        "country_code": "ID",
        "country_name": "Indonesia",
        "language_code": "id",
        "currency_code": "IDR",
        "currency_symbol": "Rp",
        "currency_decimal_places": 0,
        "admin_level_names": {
            1: "Provinsi",
            2: "Kabupaten/Kota",
            3: "Kecamatan",
            4: "Kelurahan/Desa",
            5: "RW/RT",
        },
        "regional_market_keywords": ["induk", "grosir", "regional"],
        "district_market_keywords": ["kabupaten", "kota"],
    },
    "US": {  # United States
        "country_code": "US",
        "country_name": "United States",
        "language_code": "en",
        "currency_code": "USD",
        "currency_symbol": "$",
        "currency_decimal_places": 2,
        "admin_level_names": {
            1: "State",
            2: "County",
            3: "City/Township",
            4: "District",
            5: "Neighborhood",
        },
        "default_crop_prices": {
            "rice": 1.50,
            "corn": 0.20,
            "cassava": 0.80,
            "soybean": 0.40,
            "peanut": 1.20,
            "vegetable": 2.00,
            "fruit": 2.50,
        },
        "default_agent_cash": 5000.0,
        "regional_market_keywords": ["wholesale", "regional", "distribution"],
        "district_market_keywords": ["county", "municipal"],
    },
    "IN": {  # India
        "country_code": "IN",
        "country_name": "India",
        "language_code": "hi",
        "currency_code": "INR",
        "currency_symbol": "₹",
        "currency_decimal_places": 0,
        "admin_level_names": {
            1: "State",
            2: "District",
            3: "Tehsil/Taluka",
            4: "Block",
            5: "Village",
        },
        "default_crop_prices": {
            "rice": 40.0,
            "corn": 20.0,
            "cassava": 15.0,
            "soybean": 50.0,
            "peanut": 60.0,
            "vegetable": 30.0,
            "fruit": 50.0,
        },
        "default_agent_cash": 50000.0,
        "regional_market_keywords": ["mandi", "wholesale", "apmc"],
        "district_market_keywords": ["district", "tehsil"],
    },
    "PH": {  # Philippines
        "country_code": "PH",
        "country_name": "Philippines",
        "language_code": "tl",
        "currency_code": "PHP",
        "currency_symbol": "₱",
        "currency_decimal_places": 2,
        "admin_level_names": {
            1: "Region",
            2: "Province",
            3: "Municipality/City",
            4: "Barangay",
            5: "Purok/Sitio",
        },
        "default_crop_prices": {
            "rice": 45.0,
            "corn": 20.0,
            "cassava": 15.0,
            "soybean": 60.0,
            "peanut": 80.0,
            "vegetable": 40.0,
            "fruit": 50.0,
        },
        "default_agent_cash": 10000.0,
        "regional_market_keywords": ["trading", "regional", "wholesale"],
        "district_market_keywords": ["municipal", "public"],
    },
}


def get_locale_preset(country_code: str) -> LocaleConfig:
    """Get a locale preset by country code."""
    preset_data = LOCALE_PRESETS.get(country_code.upper(), LOCALE_PRESETS["ID"])
    return LocaleConfig(**preset_data)


# =============================================================================
# Main Settings
# =============================================================================


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # LLM Configuration
    llm_service: LLMProvider = Field(
        default=LLMProvider.GEMINI,
        description="Cloud LLM provider to use",
    )
    llm_model: str = Field(
        default="gemini-2.0-flash",
        description="Model identifier for the selected provider",
    )
    llm_api_key: str = Field(
        default="",
        description="API key for the LLM provider",
    )

    # Rate Limiting Configuration
    llm_max_concurrency: int = Field(
        default=5,
        ge=1,
        le=100,
        description="Maximum concurrent LLM requests",
    )
    llm_max_retries: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum retry attempts for failed requests",
    )
    llm_retry_min_wait: float = Field(
        default=1.0,
        ge=0.1,
        description="Minimum wait time (seconds) between retries",
    )
    llm_retry_max_wait: float = Field(
        default=60.0,
        ge=1.0,
        description="Maximum wait time (seconds) between retries",
    )

    # Neo4j Configuration
    neo4j_uri: str = Field(
        default="bolt://localhost:7687",
        description="Neo4j Bolt connection URI",
    )
    neo4j_user: str = Field(
        default="neo4j",
        description="Neo4j username",
    )
    neo4j_password: str = Field(
        default="",
        description="Neo4j password",
    )

    # Logging Configuration
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Logging level",
    )
    log_format: LogFormat = Field(
        default=LogFormat.JSON,
        description="Log output format",
    )

    # Server Configuration
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, ge=1, le=65535, description="Server port")
    grpc_port: int = Field(default=50051, ge=1, le=65535, description="gRPC server port")

    # Localization Configuration
    # Use LOCALE_COUNTRY env var to select a preset, or configure individually
    locale_country: str = Field(
        default="ID",
        description="Country code for locale preset (ID, US, IN, PH, etc.)",
    )

    # Override individual locale settings via env vars if needed
    locale_currency_code: str | None = Field(
        default=None,
        description="Override currency code from preset",
    )
    locale_currency_symbol: str | None = Field(
        default=None,
        description="Override currency symbol from preset",
    )

    def get_locale(self) -> LocaleConfig:
        """Get the locale configuration with any overrides applied."""
        locale = get_locale_preset(self.locale_country)

        # Apply overrides
        if self.locale_currency_code:
            locale.currency_code = self.locale_currency_code
        if self.locale_currency_symbol:
            locale.currency_symbol = self.locale_currency_symbol

        return locale


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings singleton."""
    return Settings()


@lru_cache
def get_locale() -> LocaleConfig:
    """Get cached locale configuration."""
    return get_settings().get_locale()

