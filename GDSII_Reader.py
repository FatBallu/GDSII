#!/usr/bin/env python3
"""
GDSII Reader
"""

import csv
import os
from typing import Dict, List, Optional, Tuple

import klayout.db as db


class LayerReader:
    """
    A class to read and manage layer information from CSV and mapping files.
    """
    
    def __init__(self, layer_def_file, 
                       layer_color_file,
                       layer_mapping_file):
        self.layer_def_file = layer_def_file
        self.layer_color_file = layer_color_file
        self.layer_mapping_file = layer_mapping_file
        
        self.layers ={}

        
        self._load_layer_mapping()
        self._load_layer_def()
        self._load_layer_color()

    
    def _load_layer_mapping(self):
        self.layer_mapping = {}
        """Load layer mapping from layer_mapping.txt file."""
        if not os.path.exists(self.layer_mapping_file):
            print(f"Warning: {self.layer_mapping_file} not found")
            return
        
        try:
            with open(self.layer_mapping_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    
                    parts = line.split()
                    if len(parts) >= 4:
                        name = parts[0]
                        purpose = parts[1]
                        layer_number = int(parts[2])
                        datatype = int(parts[3])
                        
                        self.layer_mapping[(name, purpose)] = (layer_number, datatype)
                    else:
                        print(f"Warning: Invalid line format at line {line_num}: {line}")
        
        except Exception as e:
            print(f"Error reading {self.layer_mapping_file}: {e}")

    def _load_layer_def(self):
        """Load layer definitions from CSV and populate self.layers mapping.

        Builds: self.layers[layer] = {
            'name': name,
            'purpose': purpose,
            'name_gdsii_num': layer_number,
            'purpose_gdsii_num': datatype,
            'description': description (optional)
        }
        """
        if not os.path.exists(self.layer_def_file):
            print(f"Warning: {self.layer_def_file} not found")
            return
        try:
            with open(self.layer_def_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Column renamed from 'ascell' to 'layer'; keep backward compatibility
                    layer_key = (row.get('layer') or row.get('ascell') or '').strip()
                    name = (row.get('name') or '').strip()
                    purpose = (row.get('purpose') or '').strip()
                    description = (row.get('description') or '').strip()
                    if not layer_key or not name or not purpose:
                        continue
                    # Lookup GDSII numbers (layer, datatype)
                    layer_number, datatype = None, None
                    key = (name, purpose)
                    if key in self.layer_mapping:
                        layer_number, datatype = self.layer_mapping[key]
                    else:
                        print(f"Warning: No mapping found for {name}.{purpose}")
                        continue
                    # Populate entry
                    self.layers[layer_key] = {
                        'name': name,
                        'purpose': purpose,
                        'name_gdsii_num': layer_number,
                        'purpose_gdsii_num': datatype,
                        'description': description,
                    }
        except Exception as e:
            print(f"Error reading {self.layer_def_file}: {e}")

    def _load_layer_color(self):
        """Load color/bottom/top from layer_color CSV and merge into self.layers."""
        if not os.path.exists(self.layer_color_file):
            # Optional file
            return
        try:
            with open(self.layer_color_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    layer_key = (row.get('layer') or '').strip()
                    color = (row.get('color') or '').strip()
                    bottom = row.get('bottom')
                    top = row.get('top')
                    if not layer_key:
                        continue
                    # Normalize numeric fields
                    try:
                        bottom_val = int(float(bottom)) if bottom not in (None, '') else None
                    except Exception:
                        bottom_val = None
                    try:
                        top_val = int(float(top)) if top not in (None, '') else None
                    except Exception:
                        top_val = None
                    if layer_key not in self.layers:
                        # If a layer appears only in color file, create a minimal entry
                        self.layers[layer_key] = {
                            'name': '',
                            'purpose': '',
                            'name_gdsii_num': None,
                            'purpose_gdsii_num': None,
                            'description': '',
                        }
                    self.layers[layer_key]['color'] = color
                    self.layers[layer_key]['bottom'] = bottom_val
                    self.layers[layer_key]['top'] = top_val
        except Exception as e:
            print(f"Error reading {self.layer_color_file}: {e}")

    def get_klayoutlayer_index(self, layer_key):
        name_gdsii_num = self.layers[layer_key]['name_gdsii_num']
        purpose_gdsii_num = self.layers[layer_key]['purpose_gdsii_num']
        return '%d/%d'%(name_gdsii_num,purpose_gdsii_num)

    def gen_layer2index(self):
        layer2index = {}
        for k,v in self.layers.items():
            layer2index[k]='%d/%d'%(v['name_gdsii_num'],v['purpose_gdsii_num'])
        return layer2index



if __name__ == "__main__":
    # Simple test for LayerReader
    # layers = LayerReader(
    #     layer_def_file="layers_def.csv",
    #     layer_color_file="layer_color.csv",
    #     layer_mapping_file="layer_mapping.txt",
    # )
    
    
    gds_file = "csmc0153.gds"
    layout = db.Layout()
    layout.read(gds_file)
    gds2klayout_index = {k.to_s() :v for k,v in zip(layout.layer_infos(),layout.layer_indexes())}
    cell_dict = {t.name.upper():t for t in layout.each_cell()}
    cell1 = cell_dict["OAI31D0"]
    
    #get shape data by:
    for gds_layer,klayout_index in gds2klayout_index.items():
        print('gds layer %s'%gds_layer)
        shapes = list(cell1.each_shape(klayout_index))
        print(shapes)
        
        


    # name2gds2 = {k : '%d/%d'%(v[0],v[1]) for k,v in tech.output_map.items()}

    

