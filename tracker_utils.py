"""
Utility functions for saving and loading tracker data.
"""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

TRACKER_FILE = "tracker_data.json"


def load_tracker_data() -> List[Dict]:
    """Load tracker data from JSON file."""
    if not os.path.exists(TRACKER_FILE):
        return []
    
    try:
        with open(TRACKER_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def save_tracker_data(data: Dict) -> bool:
    """Save a new entry to tracker data."""
    try:
        # Load existing data
        existing_data = load_tracker_data()
        
        # Add timestamp
        data["timestamp"] = datetime.now().isoformat()
        data["date"] = datetime.now().strftime("%Y-%m-%d")
        data["time"] = datetime.now().strftime("%H:%M:%S")
        
        # Append new entry
        existing_data.append(data)
        
        # Save back to file
        with open(TRACKER_FILE, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, indent=2, ensure_ascii=False)
        
        return True
    except Exception as e:
        print(f"Error saving tracker data: {e}")
        return False


def get_quality_tracker_data(legal_entity: Optional[str] = None) -> List[Dict]:
    """Get quality tracker data, optionally filtered by legal entity."""
    data = load_tracker_data()
    quality_data = [entry for entry in data if entry.get("analysis_type") == "quality"]
    
    if legal_entity:
        quality_data = [entry for entry in quality_data 
                       if legal_entity in entry.get("legal_entities", [])]
    
    return sorted(quality_data, key=lambda x: x.get("timestamp", ""))


def get_duplicate_tracker_data() -> List[Dict]:
    """Get duplicate tracker data (global, not filtered by legal entity)."""
    data = load_tracker_data()
    duplicate_data = [entry for entry in data if entry.get("analysis_type") == "duplicate"]
    return sorted(duplicate_data, key=lambda x: x.get("timestamp", ""))
