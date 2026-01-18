#!/usr/bin/env python3
"""
Helper script to list all available component keys from components_mapping.json
Useful for Jenkins integration and manual component selection.
"""

import json
import os
import sys
from pathlib import Path


def main():
    # Get project root (parent of scripts/)
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    mapping_file = project_root / "config" / "components_mapping.json"
    
    if not mapping_file.exists():
        print(f"Error: {mapping_file} not found", file=sys.stderr)
        sys.exit(1)
    
    try:
        with open(mapping_file, "r", encoding="utf-8") as f:
            mappings = json.load(f)
        
        # Extract unique component keys
        component_keys = set()
        for mapping in mappings:
            if "component_key" in mapping:
                component_keys.add(mapping["component_key"])
        
        # Sort and print
        sorted_keys = sorted(component_keys)
        
        print(f"Available component keys ({len(sorted_keys)} total):\n")
        for key in sorted_keys:
            print(f"  {key}")
        
        print(f"\nComma-separated list:")
        print(",".join(sorted_keys))
        
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {mapping_file}: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

