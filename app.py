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
def cloud_masking(image):
    # Sentinel-2 cloud mask based on QA60
    QA60 = image.select(['QA60'])
    cloud_mask = QA60.bitwiseAnd(1).eq(0)
    return image.updateMask(cloud_mask)
    
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


    # Clip JRC data to the ROI
    jrc2020_clipped = jrc2020.clip(roi)
    
    # Load Sentinel-2 data (B8 band for near-infrared)
    sentinel2 = ee.ImageCollection('COPERNICUS/S2') \
        .filterBounds(roi) \
        .filterDate('2021-01-01', ee.Date('2024-12-31')) \
        .select('B8')
    
    # Function for cloud masking Sentinel-2 data
    def cloud_masking(image):
        # Sentinel-2 cloud mask based on QA60
        QA60 = image.select(['QA60'])
        cloud_mask = QA60.bitwiseAnd(1).eq(0)
        return image.updateMask(cloud_mask)
    
    # Preprocess Sentinel-2 data with cloud masking
    sentinel2_preprocessed = sentinel2.map(cloud_masking)
    
    # Calculate the median of the post-2020 data (after Dec 31, 2020)
    sentinel2_median_after = sentinel2_preprocessed.median()
    
    # To compare, you can use pre-2020 data as well (Optional)
    sentinel2_before_2020 = ee.ImageCollection('COPERNICUS/S2') \
        .filterBounds(roi) \
        .filterDate('2018-01-01', '2020-12-31') \
        .select('B8')
    
    sentinel2_median_before = sentinel2_before_2020.median()
    
    # Compute the change between the two periods (2020 vs 2021-2024)
    sentinel2_change = sentinel2_median_after.subtract(sentinel2_median_before)
    
    # Threshold for detecting significant change (adjustable)
    threshold = 0.3
    significant_change = sentinel2_change.abs().gt(threshold)
    
    # Detect deforestation: overlay change detection with JRC forest map (1 = forest)
    deforestation = significant_change.And(jrc2020_clipped.eq(1))

    
    # Detect deforestation: overlay significant change with the JRC forest cover map (1 = forest cover)
    deforestation = significant_change.And(jrc2020_clipped.eq(1))
    # Use connectedComponents to identify connected regions (deforestation areas)
    deforestation_components = deforestation.connectedComponents(
        ee.Kernel.plus(1),  # Connectivity (4-connected pixels)
        maxSize=128
    )
    
    # Extract the labeled components (connected regions)
    deforestation_labeled = deforestation_components.select('labels')
    
    # Convert the labeled regions into polygons (vectorize)
    deforestation_polygons = deforestation_labeled.reduceToVectors(
        reducer=ee.Reducer.countEvery(),
        maxPixels=1e8
    )
    
    # Convert the result to GeoJSON (or similar) to view details
    deforestation_polygons_geojson = deforestation_polygons.getInfo()
    
    # Prepare response
    if len(deforestation_polygons_geojson['features']) == 0:
        deforestationArray = {"status": True, "details": deforestation_polygons_geojson}
    else:
        deforestationArray = {"status": False, "details": deforestation_polygons_geojson}

    

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
