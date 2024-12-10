from flask import Flask, request, jsonify
import ee
import os
import json

app = Flask(__name__)

# Initialize Earth Engine using a service account
def initialize_earth_engine():
    try:
        # Retrieve the service account credentials from the environment variable
        service_account_json = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')

        if not service_account_json:
            raise ValueError("GOOGLE_APPLICATION_CREDENTIALS environment variable not set.")

        # Convert the JSON string to a dictionary
        service_account_info = json.loads(service_account_json)

        # Authenticate with Earth Engine using the service account
        credentials = ee.ServiceAccountCredentials(email=None, key_data=json.dumps(service_account_info))
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
    try:
        # Get GeoJSON polygon from the request
        data = request.json
        if "polygon" not in data:
            return jsonify({"error": "GeoJSON polygon is required."}), 400

        polygon = data["polygon"]

        # Convert GeoJSON to Earth Engine Geometry
        roi = ee.Geometry.Polygon(polygon)

        # Load the JRC Global Forest Change dataset
        jrc = ee.Image('UMD/hansen/global_forest_change_2023_v1_11').select('treecover2000').clip(roi)

        # Define forest in 2000 where tree cover >30%
        baseline_forest_mask = jrc.gt(30).rename('BaselineForest')

        # Load the Dynamic World dataset for recent tree cover
        dynamic_world = ee.ImageCollection('GOOGLE/DYNAMICWORLD/V1') \
            .filterDate('2021-01-01', '2024-12-31') \
            .filterBounds(roi) \
            .median() \
            .select('trees') \
            .clip(roi)

        # Define forest in 2023 where tree cover >50%
        recent_forest_mask = dynamic_world.gt(50).rename('RecentForest')

        # Detect deforestation: areas in baselineForestMask but not in recentForestMask
        deforestation_mask = baseline_forest_mask.And(recent_forest_mask.Not()).rename('Deforestation')

        # Convert deforestation raster mask to vector polygons
        deforestation_polygons = deforestation_mask.updateMask(deforestation_mask) \
            .reduceToVectors({
                'reducer': ee.Reducer.countEvery(),
                'geometry': roi,
                'scale': 30,
                'maxPixels': 1e9,
                'bestEffort': True,
            })

        # Count the number of deforestation polygons
        deforestation_count = deforestation_polygons.size().getInfo()

        # Prepare the result
        if deforestation_count == 0:
            result = {
                "status": "Deforestation-Free",
                "message": "No deforestation detected within the provided polygon.",
            }
        else:
            result = {
                "status": "Deforestation Detected",
                "message": f"Deforestation polygons found: {deforestation_count}",
                "polygons": deforestation_polygons.getInfo(),
            }

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)
