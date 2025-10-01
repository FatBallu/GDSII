#!/usr/bin/env python3
"""
GDSII 3D Renderer with Interactive Measurement Tool
"""

import os
import numpy as np
import trimesh
from shapely.geometry import Polygon
import plotly.graph_objects as go
import klayout.db as db
import dash
from dash import dcc, html, Output, Input

from GDSII_Reader import LayerReader  # your module

# ---------------------------
# 0) Config
# ---------------------------
gds_file = "csmc0153.gds"
layers_def = "layers_def.csv"
layers_color = "layer_color.csv"
layers_map = "layer_mapping.txt"

default_thickness = 0.5
color_palette = [
    'lightblue', 'orange', 'green', 'red', 'purple',
    'cyan', 'magenta', 'yellow', 'pink', 'lime'
]

z_scale = 100.0  # exaggerate vertical scale

# ---------------------------
# 1) Load mapping/colors
# ---------------------------
lr = LayerReader(
    layer_def_file=layers_def,
    layer_color_file=layers_color,
    layer_mapping_file=layers_map,
)

ld_to_key = {}
bottom_top = {}
layer_colors = {}
for key, info in lr.layers.items():
    ln, dt = info.get('name_gdsii_num'), info.get('purpose_gdsii_num')
    if ln is not None and dt is not None:
        ld_to_key[(ln, dt)] = key
        
    b, t = info.get('bottom'), info.get('top')
    color = info.get('color')
    if b is not None and t is not None:
        z0 = float(b) * z_scale
        height = float(t - b) * z_scale
        if height == 0.0:
            height = 1.0
    else:
        z0 = 0.0
        height = 1.0
    bottom_top[key] = (z0, height)
    layer_colors[key] = color

# bottom_top = {}
# layer_colors = {}
# for key, info in lr.layers.items():
#     b, t = info.get('bottom'), info.get('top')
#     color = info.get('color')
#     if b is not None and t is not None:
#         z0 = float(b) * z_scale
#         height = float(t - b) * z_scale
#         if height == 0.0:
#             height = 1.0
#     else:
#         z0 = 0.0
#         height = 1.0
#     bottom_top[key] = (z0, height)
#     layer_colors[key] = color

# ---------------------------
# 2) Load GDS, pick a cell
# ---------------------------
layout = db.Layout()
layout.read(gds_file)
cell_dict = {t.name.upper(): t for t in layout.each_cell()}
cell = cell_dict.get("OAI31D0", layout.top_cell())

# ---------------------------
# 3) Helper: KLayout polygon -> numpy array
# ---------------------------
def klayout_polygon_to_numpy(poly: db.Polygon) -> np.ndarray:
    coords = [(p.x, p.y) for p in poly.each_point_hull()]
    if len(coords) < 3:
        return np.empty((0, 2))
    arr = np.array(coords, dtype=float)
    if not np.allclose(arr[0], arr[-1]):
        arr = np.vstack([arr, arr[0]])
    return arr

# ---------------------------
# 4) Build 3D Mesh Figure
# ---------------------------
def build_figure():
    fig = go.Figure()
    trace_index = 0

    for li in layout.layer_indexes():
        info = layout.get_info(li)
        ld = (info.layer, info.datatype)
        layer_key = ld_to_key.get(ld)
        if layer_key is None:
            continue

        z0, height = bottom_top.get(layer_key, (0.0, 0.0))
        if height == 0.0:
            continue

        color = layer_colors.get(layer_key) or color_palette[trace_index % len(color_palette)]
        layer_name = lr.layers[layer_key].get('name') or f"{info.layer}/{info.datatype}"

        meshes = []
        for shape in cell.each_shape(li):
            if not shape.is_polygon():
                continue
            coords = klayout_polygon_to_numpy(shape.polygon)
            if coords.shape[0] < 3:
                continue
            shp_poly = Polygon(coords)
            if not shp_poly.is_valid or shp_poly.area == 0:
                continue
            try:
                solid = trimesh.creation.extrude_polygon(shp_poly, height=height, engine="earcut")
            except Exception:
                continue
            solid.apply_translation((0.0, 0.0, float(z0)))
            meshes.append(solid)

        if not meshes:
            continue

        layer_mesh = trimesh.util.concatenate(meshes)
        v = layer_mesh.vertices
        f = layer_mesh.faces

        fig.add_trace(go.Mesh3d(
            x=v[:, 0], y=v[:, 1], z=v[:, 2],
            i=f[:, 0], j=f[:, 1], k=f[:, 2],
            color=color,
            opacity=0.6,
            name=f"{layer_name} ({info.layer}/{info.datatype})",
            showlegend=True
        ))
        trace_index += 1

    fig.update_layout(
        scene=dict(
            aspectmode='data',
            camera=dict(
                projection=dict(type='orthographic'),
                eye=dict(x=1.5, y=1.5, z=1.0)
            ),
            xaxis=dict(title='X'),
            yaxis=dict(title='Y'),
            zaxis=dict(title='Layer Height')
        ),
        showlegend=True,
        margin=dict(l=0, r=0, t=30, b=0)
    )
    return fig

# ---------------------------
# 5) Dash App with Measurement Tool
# ---------------------------
app = dash.Dash(__name__)
fig = build_figure()

app.layout = html.Div([
    dcc.Graph(id="graph", figure=fig, style={"height": "90vh"}),
    html.Div(id="output", style={"fontSize": 20, "marginTop": "10px"})
])

clicked_points = []

@app.callback(
    Output("graph", "figure"),
    Output("output", "children"),
    Input("graph", "clickData"),
    prevent_initial_call=True
)
def measure(clickData):
    global clicked_points, fig
    if clickData is None:
        return fig, ""
    pt = clickData["points"][0]
    x, y, z = pt["x"], pt["y"], pt["z"]
    clicked_points.append((x, y, z))

    if len(clicked_points) == 2:
        (x1, y1, z1), (x2, y2, z2) = clicked_points
        dist = np.sqrt((x2-x1)**2 + (y2-y1)**2 + (z2-z1)**2)

        # Add measurement line
        fig.add_trace(go.Scatter3d(
            x=[x1, x2], y=[y1, y2], z=[z1, z2],
            mode="lines+markers+text",
            line=dict(color="red", width=5),
            marker=dict(size=5, color="red"),
            text=[None, f"{dist:.2f}"],
            textposition="top center",
            name="Measurement"
        ))

        clicked_points = []
        return fig, f"Distance: {dist:.2f} units"

    return fig, "First point selected..."

if __name__ == "__main__":
    app.run(debug=True)
