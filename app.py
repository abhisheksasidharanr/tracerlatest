from flask import Flask, request, jsonify
import ee

# Initialize Earth Engine
ee.Initialize()

app = Flask(__name__)

@app.route('/check-deforestation', methods=['POST'])
def check_deforestation():
    data = request.json
    geojson = data['geojson']
    
    # Convert GeoJSON to Earth Engine Geometry
    roi = ee.Geometry.Polygon(geojson['features'][0]['geometry']['coordinates'])
    
    # Load JRC and Dynamic World datasets
    jrc = ee.Image('UMD/hansen/global_forest_change_2023_v1_11').select('treecover2000').clip(roi)
    dynamic_world = ee.ImageCollection('GOOGLE/DYNAMICWORLD/V1').filterDate('2021-01-01', '2024-12-31').filterBounds(roi).median().select('trees').clip(roi)
    
    # Forest masks
    baseline_forest_mask = jrc.gt(30)
    recent_forest_mask = dynamic_world.gt(50)
    
    # Deforestation detection
    deforestation_mask = baseline_forest_mask.And(recent_forest_mask.Not())
    deforestation_polygons = deforestation_mask.reduceToVectors({
        'geometryType': 'polygon',
        'scale': 30,
        'maxPixels': 1e9
    })
    
    deforestation_count = deforestation_polygons.size().getInfo()
    if deforestation_count == 0:
        return jsonify({'isDeforestationFree': True})
    else:
        polygons = deforestation_polygons.getInfo()
        return jsonify({'isDeforestationFree': False, 'deforestationPolygons': polygons})

if __name__ == '__main__':
    app.run(debug=True)
