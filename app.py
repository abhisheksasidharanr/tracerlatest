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

def calculate_area_in_hectares(roi):   
    
    # Calculate the area of the polygon in square meters
    area_square_meters = roi.area().getInfo()
    
    # Convert area to hectares (1 hectare = 10,000 square meters)
    area_hectares = area_square_meters / 10000
    
    # Round the area to 2 decimal places
    area_hectares_rounded = round(area_hectares, 2)
    
    return area_hectares_rounded
# Function for cloud masking Sentinel-2 data
# Function to mask cloudy or invalid pixels (optional, based on the dataset)
def mask_clouds(image):
    return image.updateMask(image.mask())
    
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
    area = calculate_area_in_hectares(roi)
    
    # # Load the JRC Global Forest Change (2020) dataset
    # jrc = ee.Image('UMD/hansen/global_forest_change_2023_v1_11').select('treecover2000').clip(roi)
    
    # # Forest is defined where tree cover is > 30% in 2000
    # baseline_forest_mask = jrc.gt(98.5).rename('BaselineForest')

    # # Load the Dynamic World dataset (2023) and focus on tree cover
    # dynamic_world = ee.ImageCollection('GOOGLE/DYNAMICWORLD/V1') \
    #                     .filterDate('2021-01-01', '2024-12-31') \
    #                     .filterBounds(roi) \
    #                     .median() \
    #                     .select('trees') \
    #                     .clip(roi)

    # # Recent forest is defined where tree cover probability > 50% in 2023
    # recent_forest_mask = dynamic_world.gt(98.5).rename('RecentForest')

    # # Detect deforestation: areas in baselineForestMask but not in recentForestMask
    # deforestation_mask = baseline_forest_mask.And(recent_forest_mask.Not()).rename('Deforestation')

    # # Convert deforestation raster mask to vector polygons
    # deforestation_polygons = deforestation_mask.updateMask(deforestation_mask).reduceToVectors(
    #     reducer=ee.Reducer.countEvery(),
    #     geometry=roi,
    #     scale=30,
    #     maxPixels=1e9,
    #     bestEffort=True
    # )

    # # Check if deforestation polygons exist
    # deforestation_size = deforestation_polygons.size().getInfo()
    # deforestation_data = deforestation_polygons.getInfo()

    # Load JRC Forest Cover 2020 dataset
    jrc2020 = ee.ImageCollection('JRC/GFC2020/V2').mosaic()    
    
    
    # Clip JRC forest cover data to the ROI
    jrc2020Clipped = jrc2020.clip(roi)
    
    # Load Dynamic World V1 data for the period after Dec 31, 2020 (2021 onwards)
    dynamicWorld = ee.ImageCollection('GOOGLE/DYNAMICWORLD/V1') \
        .filterBounds(roi) \
        .filterDate('2021-01-01', '2024-12-31') \
        .select('trees')  # Select the classification band   
    
    
    # Preprocess Dynamic World data (masking clouds if necessary)
    dynamicWorldPreprocessed = dynamicWorld.map(mask_clouds)
    
    # Calculate the mode of the Dynamic World data after 2020 (most frequent classification)
    dynamicWorldModeAfter = dynamicWorldPreprocessed.mode()
    
    # Load Dynamic World V1 data for the period before 2020 (2018-2020)
    dynamicWorldBefore2020 = ee.ImageCollection('GOOGLE/DYNAMICWORLD/V1') \
        .filterBounds(roi) \
        .filterDate('2020-01-01', '2020-12-31') \
        .select('trees')  # Select the classification band
    
    # Calculate the mode of the Dynamic World data before 2020 (most frequent classification)
    dynamicWorldModeBefore = dynamicWorldBefore2020.mode()
    
    # Compute the change by subtracting the pre-2020 mode from the post-2020 mode
    dynamicWorldChange = dynamicWorldModeAfter.subtract(dynamicWorldModeBefore)
    
    # Set a threshold for detecting significant change
    threshold = 10  # Adjust based on classification changes
    significantChange = dynamicWorldChange.abs().gt(threshold)
    
    # Detect deforestation by overlaying the change detection with the JRC forest map (1 = forest cover)
    deforestation = significantChange.And(jrc2020Clipped.eq(1))
    
    # Vectorize the deforestation areas
    deforestationVectors = deforestation.reduceToVectors(
        reducer=ee.Reducer.countEvery(),
        geometryType='polygon',
        maxPixels=1e8,
        scale=30  # Define a reasonable scale for vectorization
    )
    # Convert the result to GeoJSON for viewing
    deforestation_polygons_geojson = deforestationVectors.getInfo()
    
    # Prepare response based on the presence of deforestation polygons
    if len(deforestation_polygons_geojson['features']) > 0:
        deforestationArray = {"status": False, "details": deforestation_polygons_geojson}
    else:
        deforestationArray = {"status": True, "details": deforestation_polygons_geojson}

    #protected area check    
    # Load the WDPA dataset
    wdpa = ee.FeatureCollection('WCMC/WDPA/current/polygons')

    # Filter the WDPA dataset to get polygons that intersect with the ROI
    intersecting_areas = wdpa.filterBounds(roi)

    # Count the number of intersecting features
    intersecting_count = intersecting_areas.size().getInfo()
    if intersecting_count==0:
        protectedAreaArray = {"status":True}
    else:
        protectedAreaArray = {"status":False}

    #Onland Check
    
    # Load the JRC Global Surface Water dataset
    water = ee.Image("JRC/GSW1_4/GlobalSurfaceWater").select('occurrence')
    
    # Create a water mask: values greater than 0 indicate the presence of water
    water_mask = water.gt(0)
    
    # Clip the water mask to the ROI (Region of Interest)
    water_in_polygon = water_mask.clip(roi)
    
    # Calculate water presence
    stats = water_in_polygon.reduceRegion(
        reducer=ee.Reducer.sum(),
        geometry=roi,
        scale=30,  # Typical scale for GSW
        maxPixels=1e13
    )
    
    # Get water pixels count (handle None case)
    water_pixels = stats.get('occurrence')
    water_pixels = water_pixels.getInfo() if water_pixels else 0
    
    # Get water geometry (handle case where no geometry exists)
    water_as_polygon = water_in_polygon.geometry()
    
    
    # Evaluate the result and return
    if water_pixels > 0:
        water_vectors = water_in_polygon.reduceToVectors(
            geometryType='polygon',
            reducer=ee.Reducer.countEvery(),
            scale=30,
            maxPixels=1e13,
            geometry=roi
        )
        waterData = water_vectors.getInfo()
        onLandArray = {"status": False, "polygon": waterData}
    else:
        onLandArray = {"status": True, "polygon": None}

    #check for builtuparea   

    # Load the Open Buildings dataset
    open_buildings = ee.FeatureCollection('GOOGLE/Research/open-buildings/v3/polygons')

    # Filter buildings that intersect the ROI
    buildings_inside_polygon = open_buildings.filterBounds(roi)
    building_data = buildings_inside_polygon.getInfo()
    count = buildings_inside_polygon.size().getInfo()
    if count==0:
        builtupArea = {"status": True}
    else:
        builtupArea = {"status": False, "polygon":building_data}


    # Load the SRTM dataset
    srtm = ee.Image('USGS/SRTMGL1_003')   
    # Clip the DEM to the polygon
    clipped_dem = srtm.clip(roi)
    
    # Calculate the mean elevation within the polygon
    mean_elevation = clipped_dem.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=roi,
        scale=30,  # Adjust the scale as needed for your resolution
        maxPixels=1e9
    ).get('elevation')
    
    # Fetch and print the result
    mean_elevation_value = mean_elevation.getInfo()
    
    result = {
        "polygon":geometry['coordinates'],"area":area, "deforestation" : deforestationArray, "protectedArea":protectedAreaArray, "onLand":onLandArray, "builtupArea": builtupArea, "altitude":mean_elevation_value
    }
    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True)
