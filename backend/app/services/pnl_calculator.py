"""P&L Calculator service for calculating profit/loss on trade exits.

This module provides P&L calculation functionality for individual exits
and weighted average P&L across multiple exits in a trade group.

Requirements: 2.1, 2.2, 2.4
"""
from dataclasses import dataclass
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class ExitPnL:
    """P&L result for a single exit.
    
    Attributes:
        pnl_percent: P&L as a percentage of entry price
        pnl_absolute: P&L in absolute terms (price difference * quantity)
        quantity: Quantity exited
    """
    pnl_percent: float
    pnl_absolute: float
    quantity: float


@dataclass
class WeightedPnL:
    """Weighted average P&L result across multiple exits.
    
    Attributes:
        total_pnl_percent: Weighted average P&L percentage
        total_pnl_absolute: Sum of all absolute P&L values
        total_quantity: Total quantity across all exits
        exits_breakdown: List of individual exit P&L results
    """
    total_pnl_percent: float
    total_pnl_absolute: float
    total_quantity: float
    exits_breakdown: List[ExitPnL]


class PnLCalculator:
    """Service for calculating P&L on trade exits.
    
    Provides methods for calculating P&L on individual exits and
    weighted average P&L across multiple exits in a trade group.
    
    Requirements: 2.1, 2.2, 2.4
    """
    
    @staticmethod
    def calculate_exit_pnl(
        entry_price: float,
        exit_price: float,
        direction: str,
        quantity: float
    ) -> ExitPnL:
        """
        Calculate P&L for a single exit.
        
        For longs: ((exit_price - entry_price) / entry_price) * 100
        For shorts: ((entry_price - exit_price) / entry_price) * 100
        
        Args:
            entry_price: The entry price of the position
            exit_price: The exit price for this exit
            direction: 'long' or 'short'
            quantity: The quantity being exited
            
        Returns:
            ExitPnL with pnl_percent, pnl_absolute, and quantity
            
        Raises:
            ValueError: If entry_price is zero or negative, or if direction is invalid
            
        Requirements: 2.1, 2.2
        """
        if entry_price <= 0:
            raise ValueError(f"entry_price must be positive, got {entry_price}")
        
        if quantity < 0:
            raise ValueError(f"quantity must be non-negative, got {quantity}")
        
        direction_lower = direction.lower()
        if direction_lower not in ('long', 'short'):
            raise ValueError(f"direction must be 'long' or 'short', got {direction}")
        
        # Calculate P&L percentage based on direction
        if direction_lower == 'long':
            # For longs: profit when exit > entry
            pnl_percent = ((exit_price - entry_price) / entry_price) * 100
        else:
            # For shorts: profit when entry > exit
            pnl_percent = ((entry_price - exit_price) / entry_price) * 100
        
        # Calculate absolute P&L (price difference * quantity)
        if direction_lower == 'long':
            pnl_absolute = (exit_price - entry_price) * quantity
        else:
            pnl_absolute = (entry_price - exit_price) * quantity
        
        return ExitPnL(
            pnl_percent=pnl_percent,
            pnl_absolute=pnl_absolute,
            quantity=quantity
        )
    
    @staticmethod
    def calculate_weighted_pnl(
        exits: List[dict],
        entry_price: float,
        direction: str
    ) -> WeightedPnL:
        """
        Calculate weighted average P&L across all exits.
        
        The total P&L equals the sum of (individual_pnl * quantity) divided by total_quantity.
        
        Args:
            exits: List of exit dictionaries with 'exit_price' and 'quantity' keys
            entry_price: The entry price of the position
            direction: 'long' or 'short'
            
        Returns:
            WeightedPnL with total_pnl_percent, total_pnl_absolute, total_quantity, exits_breakdown
            
        Raises:
            ValueError: If entry_price is zero or negative, or if direction is invalid
            
        Requirements: 2.4
        """
        if entry_price <= 0:
            raise ValueError(f"entry_price must be positive, got {entry_price}")
        
        direction_lower = direction.lower()
        if direction_lower not in ('long', 'short'):
            raise ValueError(f"direction must be 'long' or 'short', got {direction}")
        
        if not exits:
            return WeightedPnL(
                total_pnl_percent=0.0,
                total_pnl_absolute=0.0,
                total_quantity=0.0,
                exits_breakdown=[]
            )
        
        exits_breakdown = []
        total_quantity = 0.0
        total_pnl_absolute = 0.0
        weighted_pnl_sum = 0.0
        
        for exit_data in exits:
            exit_price = exit_data.get('exit_price')
            quantity = exit_data.get('quantity', 0)
            
            if exit_price is None or quantity <= 0:
                logger.warning(f"Skipping invalid exit data: {exit_data}")
                continue
            
            # Calculate individual exit P&L
            exit_pnl = PnLCalculator.calculate_exit_pnl(
                entry_price=entry_price,
                exit_price=exit_price,
                direction=direction,
                quantity=quantity
            )
            
            exits_breakdown.append(exit_pnl)
            total_quantity += quantity
            total_pnl_absolute += exit_pnl.pnl_absolute
            weighted_pnl_sum += exit_pnl.pnl_percent * quantity
        
        # Calculate weighted average P&L percentage
        if total_quantity > 0:
            total_pnl_percent = weighted_pnl_sum / total_quantity
        else:
            total_pnl_percent = 0.0
        
        return WeightedPnL(
            total_pnl_percent=total_pnl_percent,
            total_pnl_absolute=total_pnl_absolute,
            total_quantity=total_quantity,
            exits_breakdown=exits_breakdown
        )
