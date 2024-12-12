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


    # Load the JRC Global Forest Change (GFC) 2020 dataset
    jrc2020 = ee.ImageCollection('JRC/GFC2020/V2').mosaic()
    
    # Clip to region of interest (ROI)
    jrc2020_clipped = jrc2020.clip(roi)
    
    # Load Sentinel-1 data (GRD product)
    sentinel1 = ee.ImageCollection('COPERNICUS/S1_GRD') \
        .filterBounds(roi) \
        .filterDate('2021-01-01', '2023-12-31') \
        .filter(ee.Filter.eq('instrumentMode', 'IW')) \
        .select('VV')
    
    # Load Sentinel-2 data (Surface Reflectance)
    sentinel2 = ee.ImageCollection('COPERNICUS/S2') \
        .filterBounds(roi) \
        .filterDate('2021-01-01', '2023-12-31') \
        .select('B8')
    
    # Preprocess Sentinel-1 data (Example: No preprocessing in this example)
    sentinel1_preprocessed = sentinel1.map(lambda image: image)
    
    # Preprocess Sentinel-2 data (Example: No preprocessing in this example)
    sentinel2_preprocessed = sentinel2.map(lambda image: image)
    
    # Calculate change detection metrics (Median subtraction, assuming it's a proxy for change)
    sentinel1_change = sentinel1_preprocessed.median().subtract(sentinel1_preprocessed.median())
    sentinel2_change = sentinel2_preprocessed.median().subtract(sentinel2_preprocessed.median())
    
    # Define thresholds for detecting significant changes
    threshold1 = 3  # Sentinel-1 threshold (adjust as needed)
    threshold2 = 0.3  # Sentinel-2 threshold (adjust as needed)
    
    # Create a mask for significant changes
    significant_change = sentinel1_change.abs().gt(threshold1).And(
        sentinel2_change.abs().gt(threshold2)
    )
    
    # Detect deforestation: overlay significant change with the JRC forest cover map (1 = forest cover)
    deforestation = significant_change.And(jrc2020_clipped.eq(1))
    deforestation_size = deforestation.size().getInfo()
    deforestation_data = deforestation.getInfo()
    
    # Prepare response
    if deforestation_size == 0:
        deforestationArray = {"status": True}
    else:
        deforestationArray = {"status": False, "details":deforestation_data}

    

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
    # Load the MODIS Land Cover dataset and select the LC_Type1 band
    modis_land_cover = ee.ImageCollection('MODIS/006/MCD12Q1').select('LC_Type1')

    # Get the most recent land cover image and clip it to the ROI
    land_cover_image = modis_land_cover.sort('system:time_start', False).first().clip(roi)

    # Reduce the image to extract land cover type within the polygon
    land_cover = land_cover_image.reduceRegion(
        reducer=ee.Reducer.mode(),
        geometry=roi,
        scale=500,
        maxPixels=1e6
    )

    # Get the dominant land cover type
    land_cover_type = land_cover.get('LC_Type1')

    # Check if the land cover type corresponds to land
    is_on_land = ee.Algorithms.If(
        land_cover_type,
        ee.Number(land_cover_type).neq(0).And(ee.Number(land_cover_type).neq(17)),
        False
    )

    # Evaluate the result and return
    if is_on_land.getInfo() ==1:
        onLandArray = {"status": True}
    else:
        onLandArray = {"status": False}

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

    
    result = {
        "polygon":geometry['coordinates'],"area":area, "deforestation" : deforestationArray, "protectedArea":protectedAreaArray, "onLand":onLandArray, "builtupArea": builtupArea
    }
    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True)
