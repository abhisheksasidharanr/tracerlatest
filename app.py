from flask import Flask, request, jsonify
import ee
import os
import json

app = Flask(__name__)

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
    # try:
    #     # Get GeoJSON polygon from the request
    #     data = request.json
    #     if "features" not in data:
    #         return jsonify({"error": "GeoJSON polygon is required."}), 400

    #     # Convert GeoJSON to Earth Engine Geometry
    #     roi = ee.Geometry.Polygon(data['features'][0]['geometry']['coordinates'])
        
    #     # Load the JRC Global Forest Change dataset
    #     jrc = ee.Image('UMD/hansen/global_forest_change_2023_v1_11').select('treecover2000').clip(roi)
        
    #     # Define forest in 2000 where tree cover >30%
    #     baseline_forest_mask = jrc.gt(30).rename('BaselineForest')
        
    #     # Load the Dynamic World dataset for recent tree cover
    #     dynamic_world = ee.ImageCollection('GOOGLE/DYNAMICWORLD/V1') \
    #         .filterDate('2021-01-01', '2024-12-31') \
    #         .filterBounds(roi) \
    #         .median() \
    #         .select('trees') \
    #         .clip(roi)
        
    #     # Define forest in 2023 where tree cover >50%
    #     recent_forest_mask = dynamic_world.gt(50).rename('RecentForest')
        
    #     # Detect deforestation: areas in baselineForestMask but not in recentForestMask
    #     deforestation_mask = baseline_forest_mask.And(recent_forest_mask.Not()).rename('Deforestation')
        
    #     # Convert deforestation raster mask to vector polygons
    #     deforestation_polygons = ee.Reducer.toVectors({
    #         'geometryType': 'polygon',
    #         'scale': 30,
    #         'maxPixels': 1e9,
    #         'bestEffort': True
    #     })(deforestation_mask)
        
    #     # Get the count of deforestation polygons
    #     # Convert deforestation mask to a feature collection
    #     deforestation_fc = deforestation_mask.reduceToImage(['sum'], 30).gt(0).selfMask().reduceToVectors(geometry=roi, scale=30, maxPixels=1e9)
        
    #     # Get the count of deforestation polygons
    #     deforestation_count = deforestation_fc.size().getInfo()
        
    #     # Prepare the result
    #     if deforestation_count == 0:
    #         result = {
    #             "status": "Deforestation-Free",
    #             "message": "No deforestation detected within the provided polygon.",
    #         }
    #     else:
    #         result = {
    #             "status": "Deforestation Detected",
    #             "message": f"Deforestation polygons found: {deforestation_count}",
    #             "polygons": deforestation_polygons.getInfo(),
    #         }
        
    #     return jsonify(result)

    # except Exception as e:
    #     return jsonify({"error": str(e)}), 500

    

    roi = ee.Geometry.Polygon([
        [[35.30311547038008, -0.36029597397167934],
         [35.30534706828047, -0.357806932879987],
         [35.30680618998457, -0.3590943680120164],
         [35.304917914838086, -0.3610684348620916],
         [35.30311547038008, -0.36029597397167934]]
    ])

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

    # Prepare response
    if deforestation_size == 0:
        response = {"message": "Deforestation-Free: No deforestation detected within the ROI."}
    else:
        response = {"message": "Deforestation Happened: Deforestation polygons exist within the ROI."}

    return response


if __name__ == "__main__":
    app.run(debug=True)
