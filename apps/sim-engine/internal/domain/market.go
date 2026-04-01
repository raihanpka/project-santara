package domain

import (
	"errors"
	"sync"
	"time"

	"github.com/google/uuid"
)

// Market domain errors
var (
	ErrMarketClosed        = errors.New("market is closed")
	ErrInsufficientSupply  = errors.New("insufficient supply at market")
	ErrExceedsDailyVolume  = errors.New("transaction exceeds daily volume limit")
	ErrInvalidPrice        = errors.New("invalid price")
)

// MarketType represents the classification of a market
type MarketType string

const (
	MarketTypeLocal    MarketType = "local"
	MarketTypeDistrict MarketType = "district"
	MarketTypeRegional MarketType = "regional"
)

// PriceList maps crop types to their prices
type PriceList map[CropType]float64

// Market represents a trading location in the simulation.
// This is a pure domain entity with business logic methods.
type Market struct {
	mu sync.RWMutex

	ID         uuid.UUID
	Name       string
	RegionID   uuid.UUID
	MarketType MarketType

	// Location
	Location Coordinates

	// Economic attributes
	Prices      PriceList // Current prices per crop (per kg)
	Demand      PriceList // Current demand levels
	Supply      PriceList // Current supply levels
	DailyVolume float64   // Max daily trading volume (kg)

	// Daily tracking (resets each day/tick cycle)
	TodayVolume float64

	// Timestamps
	CreatedAt time.Time
	UpdatedAt time.Time

	// Metadata
	Properties map[string]string
}

// NewMarket creates a new Market with default values
func NewMarket(name string, regionID uuid.UUID, marketType MarketType, location Coordinates) *Market {
	now := time.Now().UTC()

	defaultVolume := 1000.0
	switch marketType {
	case MarketTypeDistrict:
		defaultVolume = 5000.0
	case MarketTypeRegional:
		defaultVolume = 20000.0
	}

	return &Market{
		ID:          uuid.New(),
		Name:        name,
		RegionID:    regionID,
		MarketType:  marketType,
		Location:    location,
		Prices:      make(PriceList),
		Demand:      make(PriceList),
		Supply:      make(PriceList),
		DailyVolume: defaultVolume,
		TodayVolume: 0,
		CreatedAt:   now,
		UpdatedAt:   now,
		Properties:  make(map[string]string),
	}
}

// GetPrice returns the current price for a crop type
func (m *Market) GetPrice(cropType CropType) (float64, bool) {
	m.mu.RLock()
	defer m.mu.RUnlock()

	price, ok := m.Prices[cropType]
	return price, ok
}

// SetPrice sets the price for a crop type
func (m *Market) SetPrice(cropType CropType, price float64) error {
	if price < 0 {
		return ErrInvalidPrice
	}

	m.mu.Lock()
	defer m.mu.Unlock()

	m.Prices[cropType] = price
	m.UpdatedAt = time.Now().UTC()
	return nil
}

// SetPrices sets multiple prices at once
func (m *Market) SetPrices(prices PriceList) {
	m.mu.Lock()
	defer m.mu.Unlock()

	for crop, price := range prices {
		if price >= 0 {
			m.Prices[crop] = price
		}
	}
	m.UpdatedAt = time.Now().UTC()
}

// CanTrade checks if a trade of given volume can be executed
func (m *Market) CanTrade(volume float64) bool {
	m.mu.RLock()
	defer m.mu.RUnlock()

	return m.TodayVolume+volume <= m.DailyVolume
}

// ExecuteSale records a sale transaction (farmer selling to market)
// Returns the total revenue for the seller
func (m *Market) ExecuteSale(cropType CropType, quantity float64) (float64, error) {
	m.mu.Lock()
	defer m.mu.Unlock()

	if m.TodayVolume+quantity > m.DailyVolume {
		return 0, ErrExceedsDailyVolume
	}

	price, ok := m.Prices[cropType]
	if !ok {
		// Use default price if not set
		price = m.getDefaultPrice(cropType)
		m.Prices[cropType] = price
	}

	// Calculate revenue
	revenue := quantity * price

	// Update market state
	m.TodayVolume += quantity
	m.Supply[cropType] += quantity

	// Price adjustment: more supply = lower price (simple supply/demand)
	priceAdjustment := 1.0 - (quantity / m.DailyVolume * 0.1)
	m.Prices[cropType] = max(price*0.5, price*priceAdjustment) // Floor at 50% of current price

	m.UpdatedAt = time.Now().UTC()
	return revenue, nil
}

// ExecutePurchase records a purchase transaction (farmer buying from market)
// Returns the total cost for the buyer
func (m *Market) ExecutePurchase(cropType CropType, quantity float64) (float64, error) {
	m.mu.Lock()
	defer m.mu.Unlock()

	// Check supply
	supply, ok := m.Supply[cropType]
	if !ok || supply < quantity {
		return 0, ErrInsufficientSupply
	}

	if m.TodayVolume+quantity > m.DailyVolume {
		return 0, ErrExceedsDailyVolume
	}

	price, ok := m.Prices[cropType]
	if !ok {
		price = m.getDefaultPrice(cropType)
		m.Prices[cropType] = price
	}

	// Calculate cost
	cost := quantity * price

	// Update market state
	m.TodayVolume += quantity
	m.Supply[cropType] -= quantity

	// Price adjustment: less supply = higher price
	priceAdjustment := 1.0 + (quantity / m.DailyVolume * 0.1)
	m.Prices[cropType] = min(price*2.0, price*priceAdjustment) // Cap at 200% of current price

	m.UpdatedAt = time.Now().UTC()
	return cost, nil
}

// ResetDaily resets daily tracking counters
func (m *Market) ResetDaily() {
	m.mu.Lock()
	defer m.mu.Unlock()

	m.TodayVolume = 0
	m.UpdatedAt = time.Now().UTC()
}

// UpdatePrices adjusts prices based on supply and demand
// Called periodically to simulate market dynamics
func (m *Market) UpdatePrices() {
	m.mu.Lock()
	defer m.mu.Unlock()

	for crop := range m.Prices {
		supply := m.Supply[crop]
		demand := m.Demand[crop]

		if demand == 0 {
			demand = 100 // Default demand
		}

		// Price adjustment based on supply/demand ratio
		ratio := supply / demand
		var adjustment float64
		switch {
		case ratio < 0.5:
			adjustment = 1.1 // Low supply, increase price
		case ratio > 2.0:
			adjustment = 0.9 // High supply, decrease price
		default:
			adjustment = 1.0 // Stable
		}

		currentPrice := m.Prices[crop]
		newPrice := currentPrice * adjustment

		// Apply bounds
		minPrice := m.getDefaultPrice(crop) * 0.3
		maxPrice := m.getDefaultPrice(crop) * 3.0
		m.Prices[crop] = max(minPrice, min(maxPrice, newPrice))
	}

	m.UpdatedAt = time.Now().UTC()
}

// AddSupply adds supply to the market
func (m *Market) AddSupply(cropType CropType, quantity float64) {
	m.mu.Lock()
	defer m.mu.Unlock()

	if _, ok := m.Supply[cropType]; !ok {
		m.Supply[cropType] = 0
	}
	m.Supply[cropType] += quantity
	m.UpdatedAt = time.Now().UTC()
}

// AddDemand adds demand at the market
func (m *Market) AddDemand(cropType CropType, quantity float64) {
	m.mu.Lock()
	defer m.mu.Unlock()

	if _, ok := m.Demand[cropType]; !ok {
		m.Demand[cropType] = 0
	}
	m.Demand[cropType] += quantity
	m.UpdatedAt = time.Now().UTC()
}

// Clone creates a deep copy of the market (for thread-safe reading)
func (m *Market) Clone() *Market {
	m.mu.RLock()
	defer m.mu.RUnlock()

	pricesCopy := make(PriceList)
	for k, v := range m.Prices {
		pricesCopy[k] = v
	}

	demandCopy := make(PriceList)
	for k, v := range m.Demand {
		demandCopy[k] = v
	}

	supplyCopy := make(PriceList)
	for k, v := range m.Supply {
		supplyCopy[k] = v
	}

	propsCopy := make(map[string]string)
	for k, v := range m.Properties {
		propsCopy[k] = v
	}

	return &Market{
		ID:          m.ID,
		Name:        m.Name,
		RegionID:    m.RegionID,
		MarketType:  m.MarketType,
		Location:    m.Location,
		Prices:      pricesCopy,
		Demand:      demandCopy,
		Supply:      supplyCopy,
		DailyVolume: m.DailyVolume,
		TodayVolume: m.TodayVolume,
		CreatedAt:   m.CreatedAt,
		UpdatedAt:   m.UpdatedAt,
		Properties:  propsCopy,
	}
}

// getDefaultPrice returns the default price for a crop type (in IDR per kg)
func (m *Market) getDefaultPrice(cropType CropType) float64 {
	defaults := map[CropType]float64{
		CropTypeRice:      12000,
		CropTypeCorn:      5000,
		CropTypeCassava:   3000,
		CropTypeSoybean:   10000,
		CropTypePeanut:    15000,
		CropTypeVegetable: 8000,
		CropTypeFruit:     10000,
	}

	if price, ok := defaults[cropType]; ok {
		return price
	}
	return 5000 // Default fallback
}

// GetTotalSupplyValue calculates the total value of all supplies
func (m *Market) GetTotalSupplyValue() float64 {
	m.mu.RLock()
	defer m.mu.RUnlock()

	var total float64
	for crop, qty := range m.Supply {
		if price, ok := m.Prices[crop]; ok {
			total += qty * price
		}
	}
	return total
}

// Region represents an administrative area in the simulation.
type Region struct {
	mu sync.RWMutex

	ID       uuid.UUID
	Name     string
	Code     string // Administrative code
	Level    int    // 1=province, 2=kabupaten, 3=kecamatan, etc.
	ParentID *uuid.UUID

	// Geographic center
	Center Coordinates

	// Statistics
	Population int64
	AreaKm2    float64

	// Timestamps
	CreatedAt time.Time
	UpdatedAt time.Time
}

// NewRegion creates a new Region
func NewRegion(name, code string, level int, center Coordinates) *Region {
	now := time.Now().UTC()
	return &Region{
		ID:        uuid.New(),
		Name:      name,
		Code:      code,
		Level:     level,
		Center:    center,
		CreatedAt: now,
		UpdatedAt: now,
	}
}

// Clone creates a deep copy of the region
func (r *Region) Clone() *Region {
	r.mu.RLock()
	defer r.mu.RUnlock()

	var parentIDCopy *uuid.UUID
	if r.ParentID != nil {
		id := *r.ParentID
		parentIDCopy = &id
	}

	return &Region{
		ID:         r.ID,
		Name:       r.Name,
		Code:       r.Code,
		Level:      r.Level,
		ParentID:   parentIDCopy,
		Center:     r.Center,
		Population: r.Population,
		AreaKm2:    r.AreaKm2,
		CreatedAt:  r.CreatedAt,
		UpdatedAt:  r.UpdatedAt,
	}
}
