from flask import Flask, request, jsonify
from flask_cors import CORS
import ee
import os
import json

app = Flask(__name__)
CORS(app)
# Initialize Earth Engine using a service account
def initialize_earth_engine():
    try:
        
        
        # Check if the file exists, if not use the environment variable
        
        service_account_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
        
        if not service_account_json:
            raise ValueError("GOOGLE_APPLICATION_CREDENTIALS_JSON environment variable not set or file not found.")

        # Convert the JSON string to a dictionary
        service_account_info = json.loads(service_account_json)

        # Authenticate with Earth Engine using the service account
        credentials = ee.ServiceAccountCredentials(
            email=None, 
            key_data=json.dumps(service_account_info)
        )
        ee.Initialize(credentials)

        print("Earth Engine API initialized successfully!")

    except Exception as e:
        print(f"Error initializing Earth Engine API: {e}")
        raise e

# Initialize Earth Engine when the app starts
initialize_earth_engine()

@app.route("/")
def home():
    return "Welcome to the Deforestation Checker API!"

@app.route("/check-deforestation", methods=["POST"])
def check_deforestation():
    
    geojson = request.get_json()

    if not geojson:
        return jsonify({"error": "GeoJSON data is required"}), 400
    geometry = geojson['features'][0]['geometry']
    roi = ee.Geometry(geometry)

    
    # Load the JRC Global Forest Change (2020) dataset
    jrc = ee.Image('UMD/hansen/global_forest_change_2023_v1_11').select('treecover2000').clip(roi)
    
    # Forest is defined where tree cover is > 30% in 2000
    baseline_forest_mask = jrc.gt(98.5).rename('BaselineForest')

    # Load the Dynamic World dataset (2023) and focus on tree cover
    dynamic_world = ee.ImageCollection('GOOGLE/DYNAMICWORLD/V1') \
                        .filterDate('2021-01-01', '2024-12-31') \
                        .filterBounds(roi) \
                        .median() \
                        .select('trees') \
                        .clip(roi)

    # Recent forest is defined where tree cover probability > 50% in 2023
    recent_forest_mask = dynamic_world.gt(98.5).rename('RecentForest')

    # Detect deforestation: areas in baselineForestMask but not in recentForestMask
    deforestation_mask = baseline_forest_mask.And(recent_forest_mask.Not()).rename('Deforestation')

    # Convert deforestation raster mask to vector polygons
    deforestation_polygons = deforestation_mask.updateMask(deforestation_mask).reduceToVectors(
        reducer=ee.Reducer.countEvery(),
        geometry=roi,
        scale=30,
        maxPixels=1e9,
        bestEffort=True
    )

    # Check if deforestation polygons exist
    deforestation_size = deforestation_polygons.size().getInfo()
    deforestation_data = deforestation_polygons.getInfo()
    # Prepare response
    if deforestation_size == 0:
        deforestationArray = {"status": True}
    else:
        deforestationArray = {"status": False, "details":deforestation_data}
    result = {
        "deforestation" : deforestationArray
    }
    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True)
