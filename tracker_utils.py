"""
Utility functions for saving and loading tracker data.
Automatically loads from outputs/ directories instead of tracker_data.json.
"""
import json
import os
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

TRACKER_FILE = "tracker_data.json"
OUTPUTS_BASE = "outputs"


def load_tracker_data() -> List[Dict]:
    """Load tracker data automatically from outputs/ directories."""
    all_data = []
    
    if not os.path.isdir(OUTPUTS_BASE):
        return []
    
    # Scan all output directories
    for date_dir in sorted(os.listdir(OUTPUTS_BASE), reverse=True):
        output_dir = os.path.join(OUTPUTS_BASE, date_dir)
        if not os.path.isdir(output_dir):
            continue
        
        extract_date = date_dir
        
        # Load duplicate analysis data (overview.json)
        overview_path = os.path.join(output_dir, "overview.json")
        if os.path.isfile(overview_path):
            try:
                with open(overview_path, 'r', encoding='utf-8') as f:
                    overview = json.load(f)
                
                source_file = overview.get("source_file", "")
                manifest_path = os.path.join(output_dir, "manifest.json")
                if os.path.isfile(manifest_path):
                    with open(manifest_path, 'r', encoding='utf-8') as mf:
                        manifest = json.load(mf)
                        source_file = manifest.get("source_file", source_file)
                
                # Get modification time for timestamp
                mtime = os.path.getmtime(overview_path)
                dt = datetime.fromtimestamp(mtime)
                
                duplicate_entry = {
                    "analysis_type": "duplicate",
                    "extract_date": extract_date,
                    "source_file": source_file,
                    "total_products": overview.get("total_rows", 0),
                    "outer_duplicates": overview.get("outer_duplicates", 0),
                    "outer_unique_duplicated": overview.get("outer_unique_duplicated", 0),
                    "inner_duplicates": overview.get("inner_duplicates", 0),
                    "inner_unique_duplicated": overview.get("inner_unique_duplicated", 0),
                    "cross_duplicates": overview.get("cross_total_records", 0),
                    "timestamp": dt.isoformat(),
                    "date": extract_date,
                    "time": dt.strftime("%H:%M:%S")
                }
                all_data.append(duplicate_entry)
            except Exception as e:
                print(f"Error loading duplicate data from {output_dir}: {e}")
        
        # Load quality analysis data (quality_overview.json + quality_by_entity.xlsx)
        quality_overview_path = os.path.join(output_dir, "quality_overview.json")
        quality_by_entity_path = os.path.join(output_dir, "quality_by_entity.xlsx")
        
        if os.path.isfile(quality_overview_path):
            try:
                with open(quality_overview_path, 'r', encoding='utf-8') as f:
                    quality_overview = json.load(f)
                
                source_file = ""
                manifest_path = os.path.join(output_dir, "manifest.json")
                if os.path.isfile(manifest_path):
                    with open(manifest_path, 'r', encoding='utf-8') as mf:
                        manifest = json.load(mf)
                        source_file = manifest.get("source_file", "")
                
                # Get modification time for timestamp
                mtime = os.path.getmtime(quality_overview_path)
                dt = datetime.fromtimestamp(mtime)
                
                # Load entity metrics from quality_by_entity.xlsx if available
                entity_metrics = []
                if os.path.isfile(quality_by_entity_path):
                    try:
                        entity_df = pd.read_excel(quality_by_entity_path)
                        for _, row in entity_df.iterrows():
                            entity_metrics.append({
                                "legal_entity": row.get("Legal Entity", ""),
                                "total_products": int(row.get("Total Products", 0)) if pd.notna(row.get("Total Products")) else 0,
                                "valid_gtins": int(row.get("Valid GTINs", 0)) if pd.notna(row.get("Valid GTINs")) else 0,
                                "invalid_gtins": int(row.get("Invalid GTINs", 0)) if pd.notna(row.get("Invalid GTINs")) else 0,
                                "generic_gtins": int(row.get("Generic GTINs", 0)) if pd.notna(row.get("Generic GTINs")) else 0,
                                "placeholder_gtins": int(row.get("Placeholder GTINs (999...99)", 0)) if pd.notna(row.get("Placeholder GTINs (999...99)")) else 0,
                                "compliance_rate": float(row.get("Compliance Rate (%)", 0)) if pd.notna(row.get("Compliance Rate (%)")) else 0
                            })
                    except Exception as e:
                        print(f"Error loading entity metrics from {quality_by_entity_path}: {e}")
                
                quality_entry = {
                    "analysis_type": "quality",
                    "extract_date": extract_date,
                    "source_file": source_file,
                    "legal_entities": quality_overview.get("legal_entities", []),
                    "total_products": quality_overview.get("total_rows", 0),
                    "total_valid": quality_overview.get("total_valid", 0),
                    "total_invalid": quality_overview.get("total_invalid", 0),
                    "total_generic": quality_overview.get("total_generic", 0),
                    "total_placeholder": quality_overview.get("total_placeholder", 0),
                    "compliance_rate": quality_overview.get("compliance_rate", 0),
                    "entity_metrics": entity_metrics,
                    "timestamp": dt.isoformat(),
                    "date": extract_date,
                    "time": dt.strftime("%H:%M:%S")
                }
                all_data.append(quality_entry)
            except Exception as e:
                print(f"Error loading quality data from {output_dir}: {e}")
    
    # Sort by timestamp (most recent first)
    return sorted(all_data, key=lambda x: x.get("timestamp", ""), reverse=True)


def has_tracker_entry_for(extract_date: str, source_file: str, analysis_type: str) -> bool:
    """Return True if an entry already exists for this extract_date + source_file + analysis_type."""
    data = load_tracker_data()
    for entry in data:
        if (entry.get("analysis_type") == analysis_type
            and entry.get("extract_date") == extract_date
            and entry.get("source_file") == source_file):
            return True
    return False


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
