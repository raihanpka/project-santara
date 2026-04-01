// Package domain contains the core business entities and logic for the simulation.
// This layer MUST NOT depend on any other layers (Domain Isolation principle).
package domain

import (
	"errors"
	"sync"
	"time"

	"github.com/google/uuid"
)

// Domain errors (error slugs as per AGENTS.md guidelines)
var (
	ErrAgentDead           = errors.New("agent is dead")
	ErrAgentHungry         = errors.New("agent is too hungry to perform action")
	ErrAgentExhausted      = errors.New("agent health too low")
	ErrInsufficientCash    = errors.New("insufficient cash")
	ErrInsufficientCrop    = errors.New("insufficient crop in inventory")
	ErrInvalidCropType     = errors.New("invalid crop type")
	ErrInvalidActionType   = errors.New("invalid action type")
	ErrAgentAlreadyThinking = errors.New("agent is already in thinking state")
)

// AgentStatus represents the current state of an agent
type AgentStatus string

const (
	AgentStatusIdle     AgentStatus = "idle"
	AgentStatusThinking AgentStatus = "thinking"
	AgentStatusActing   AgentStatus = "acting"
	AgentStatusDead     AgentStatus = "dead"
)

// CropType represents types of agricultural products
type CropType string

const (
	CropTypeRice      CropType = "rice"
	CropTypeCorn      CropType = "corn"
	CropTypeCassava   CropType = "cassava"
	CropTypeSoybean   CropType = "soybean"
	CropTypePeanut    CropType = "peanut"
	CropTypeVegetable CropType = "vegetable"
	CropTypeFruit     CropType = "fruit"
)

// ActionType represents the types of actions an agent can take
type ActionType string

const (
	ActionTypeIdle    ActionType = "idle"
	ActionTypeMove    ActionType = "move"
	ActionTypePlant   ActionType = "plant"
	ActionTypeHarvest ActionType = "harvest"
	ActionTypeSell    ActionType = "sell"
	ActionTypeBuy     ActionType = "buy"
	ActionTypeEat     ActionType = "eat"
	ActionTypeRest    ActionType = "rest"
)

// Coordinates represents a geographic location
type Coordinates struct {
	Latitude  float64
	Longitude float64
}

// Inventory represents crop quantities held by an agent
type Inventory map[CropType]float64

// Agent represents a farmer agent in the simulation.
// This is a pure domain entity with business logic methods.
type Agent struct {
	mu sync.RWMutex

	ID       uuid.UUID
	Name     string
	RegionID uuid.UUID
	Status   AgentStatus

	// Economic attributes
	Cash      float64
	Inventory Inventory
	LandSize  float64 // hectares

	// Health/survival attributes
	Health float64 // 0-100
	Hunger float64 // 0-100

	// Location
	Location Coordinates

	// Timestamps
	CreatedAt time.Time
	UpdatedAt time.Time

	// Metadata
	Properties map[string]string
}

// NewAgent creates a new Agent with default values
func NewAgent(name string, regionID uuid.UUID, location Coordinates) *Agent {
	now := time.Now().UTC()
	return &Agent{
		ID:         uuid.New(),
		Name:       name,
		RegionID:   regionID,
		Status:     AgentStatusIdle,
		Cash:       0,
		Inventory:  make(Inventory),
		LandSize:   1.0,
		Health:     100,
		Hunger:     0,
		Location:   location,
		CreatedAt:  now,
		UpdatedAt:  now,
		Properties: make(map[string]string),
	}
}

// IsAlive returns true if the agent is not dead
func (a *Agent) IsAlive() bool {
	a.mu.RLock()
	defer a.mu.RUnlock()
	return a.Status != AgentStatusDead
}

// CanAct returns true if the agent can perform actions
func (a *Agent) CanAct() bool {
	a.mu.RLock()
	defer a.mu.RUnlock()
	return a.Status != AgentStatusDead && a.Status != AgentStatusThinking
}

// Eat consumes food from inventory to reduce hunger.
// Returns the amount of hunger reduced.
func (a *Agent) Eat(cropType CropType, amount float64) (float64, error) {
	a.mu.Lock()
	defer a.mu.Unlock()

	if a.Status == AgentStatusDead {
		return 0, ErrAgentDead
	}

	available, ok := a.Inventory[cropType]
	if !ok || available < amount {
		return 0, ErrInsufficientCrop
	}

	// Consume the crop
	a.Inventory[cropType] -= amount

	// Reduce hunger (1kg food = 20 hunger points reduced)
	hungerReduction := amount * 20
	oldHunger := a.Hunger
	a.Hunger = max(0, a.Hunger-hungerReduction)
	actualReduction := oldHunger - a.Hunger

	a.UpdatedAt = time.Now().UTC()
	return actualReduction, nil
}

// Rest recovers health. Agent must not be too hungry.
func (a *Agent) Rest() (float64, error) {
	a.mu.Lock()
	defer a.mu.Unlock()

	if a.Status == AgentStatusDead {
		return 0, ErrAgentDead
	}

	if a.Hunger > 70 {
		return 0, ErrAgentHungry
	}

	// Recover health (base 10 points per rest)
	healthRecovery := 10.0
	oldHealth := a.Health
	a.Health = min(100, a.Health+healthRecovery)
	actualRecovery := a.Health - oldHealth

	a.UpdatedAt = time.Now().UTC()
	return actualRecovery, nil
}

// Move changes the agent's location
func (a *Agent) Move(newLocation Coordinates) error {
	a.mu.Lock()
	defer a.mu.Unlock()

	if a.Status == AgentStatusDead {
		return ErrAgentDead
	}

	if a.Health < 10 {
		return ErrAgentExhausted
	}

	// Moving costs energy (increases hunger slightly)
	a.Hunger = min(100, a.Hunger+2)
	a.Location = newLocation
	a.UpdatedAt = time.Now().UTC()

	return nil
}

// AddInventory adds crops to the agent's inventory
func (a *Agent) AddInventory(cropType CropType, amount float64) {
	a.mu.Lock()
	defer a.mu.Unlock()

	if _, ok := a.Inventory[cropType]; !ok {
		a.Inventory[cropType] = 0
	}
	a.Inventory[cropType] += amount
	a.UpdatedAt = time.Now().UTC()
}

// RemoveInventory removes crops from inventory
func (a *Agent) RemoveInventory(cropType CropType, amount float64) error {
	a.mu.Lock()
	defer a.mu.Unlock()

	available, ok := a.Inventory[cropType]
	if !ok || available < amount {
		return ErrInsufficientCrop
	}

	a.Inventory[cropType] -= amount
	a.UpdatedAt = time.Now().UTC()
	return nil
}

// AddCash adds money to the agent's balance
func (a *Agent) AddCash(amount float64) {
	a.mu.Lock()
	defer a.mu.Unlock()

	a.Cash += amount
	a.UpdatedAt = time.Now().UTC()
}

// SpendCash removes money from the agent's balance
func (a *Agent) SpendCash(amount float64) error {
	a.mu.Lock()
	defer a.mu.Unlock()

	if a.Cash < amount {
		return ErrInsufficientCash
	}

	a.Cash -= amount
	a.UpdatedAt = time.Now().UTC()
	return nil
}

// SetThinking marks the agent as waiting for LLM decision
func (a *Agent) SetThinking() error {
	a.mu.Lock()
	defer a.mu.Unlock()

	if a.Status == AgentStatusDead {
		return ErrAgentDead
	}

	if a.Status == AgentStatusThinking {
		return ErrAgentAlreadyThinking
	}

	a.Status = AgentStatusThinking
	a.UpdatedAt = time.Now().UTC()
	return nil
}

// SetIdle returns the agent to idle state
func (a *Agent) SetIdle() {
	a.mu.Lock()
	defer a.mu.Unlock()

	if a.Status != AgentStatusDead {
		a.Status = AgentStatusIdle
		a.UpdatedAt = time.Now().UTC()
	}
}

// SetActing marks the agent as executing an action
func (a *Agent) SetActing() {
	a.mu.Lock()
	defer a.mu.Unlock()

	if a.Status != AgentStatusDead {
		a.Status = AgentStatusActing
		a.UpdatedAt = time.Now().UTC()
	}
}

// Kill marks the agent as dead
func (a *Agent) Kill() {
	a.mu.Lock()
	defer a.mu.Unlock()

	a.Status = AgentStatusDead
	a.Health = 0
	a.UpdatedAt = time.Now().UTC()
}

// Tick applies per-tick effects (hunger increase, health decay)
// This should be called once per simulation tick.
func (a *Agent) Tick(hungerRate, healthDecayRate float64) {
	a.mu.Lock()
	defer a.mu.Unlock()

	if a.Status == AgentStatusDead {
		return
	}

	// Increase hunger
	a.Hunger = min(100, a.Hunger+hungerRate)

	// If very hungry, health decays
	if a.Hunger > 80 {
		a.Health = max(0, a.Health-healthDecayRate)
	}

	// Check for death
	if a.Health <= 0 {
		a.Status = AgentStatusDead
		a.Health = 0
	}

	a.UpdatedAt = time.Now().UTC()
}

// Clone creates a deep copy of the agent (for thread-safe reading)
func (a *Agent) Clone() *Agent {
	a.mu.RLock()
	defer a.mu.RUnlock()

	inventoryCopy := make(Inventory)
	for k, v := range a.Inventory {
		inventoryCopy[k] = v
	}

	propsCopy := make(map[string]string)
	for k, v := range a.Properties {
		propsCopy[k] = v
	}

	return &Agent{
		ID:         a.ID,
		Name:       a.Name,
		RegionID:   a.RegionID,
		Status:     a.Status,
		Cash:       a.Cash,
		Inventory:  inventoryCopy,
		LandSize:   a.LandSize,
		Health:     a.Health,
		Hunger:     a.Hunger,
		Location:   a.Location,
		CreatedAt:  a.CreatedAt,
		UpdatedAt:  a.UpdatedAt,
		Properties: propsCopy,
	}
}

// GetInventoryValue calculates the total value of inventory at given prices
func (a *Agent) GetInventoryValue(prices map[CropType]float64) float64 {
	a.mu.RLock()
	defer a.mu.RUnlock()

	var total float64
	for crop, qty := range a.Inventory {
		if price, ok := prices[crop]; ok {
			total += qty * price
		}
	}
	return total
}

// NeedsDecision returns true if the agent should query the LLM for a decision
func (a *Agent) NeedsDecision() bool {
	a.mu.RLock()
	defer a.mu.RUnlock()

	// Don't need decision if dead or already thinking
	if a.Status == AgentStatusDead || a.Status == AgentStatusThinking {
		return false
	}

	// Need decision in critical situations
	if a.Hunger > 50 || a.Health < 50 {
		return true
	}

	// Need decision if idle with options
	if a.Status == AgentStatusIdle {
		return true
	}

	return false
}
