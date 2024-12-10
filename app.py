from flask import Flask, request, jsonify
import ee
import os
import json

app = Flask(__name__)

# Initialize Earth Engine using a service account
def initialize_earth_engine():
    try:
        # Retrieve the service account credentials from the environment variable
        service_account_json = '''{
  "type": "service_account",
  "project_id": "ee-abhisheksasidharanr",
  "private_key_id": "9332dd99f683a6d41ea162c051c52627e5d75463",
  "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvwIBADANBgkqhkiG9w0BAQEFAASCBKkwggSlAgEAAoIBAQCvYFcC11Ivgw0E\nhuF1HVH0EgsVOvdzMaR0F0OLXvNxzaAl/MgSVH+JbZAKt8ptfWvbd5z41UHen3zv\nbB1afr61h/U+5p5gWtpyDkfIVJDDGyadQQwvMJ0Qc5eOUlDG/7263tfRfcB7q9f9\nnP1QTJkXVpLiG54VXMNTk4++cq+b1Lklf0nP38XJZ+0TAfRs09+Htk4Yh/gc0NPo\n8Gd6sYeNK3Q1dU5fLyrAT+AUswif+LHTjbnEQrvX2DgQRsIDCwJLI/RCrvFNWAif\nauZOMpiFsIFe0rfkqFOUS8J5R6H0JsYS12Kf7dNy8ocBJKoyAisGI19VpeXcCLIL\nVLbCFMtnAgMBAAECggEAFZfPOXZ+ftgWvGXJEQI9AB1P8ltncpj8TnOQ1EeqwhUs\ncJDuUgdyXomNZdcZnEqILaZNaaaEQjSxOB9qgSUVi8SuJwJTzLmoUh5nqzGc/ftz\n+9exotvMSDrF6yGVIt4DznmNPr90zs//5juJRZ+bbTAHzMF+wNLs6neYMr2XLqCZ\nYgIHIU1br57+6wOrL9lre26AC8L6jUMVtHe+W49OG4nJimgExAxGYUGR0EcHo/FP\nnOW90QbPcnq2krPz81Dza1AmwpwGMfGqbrV7cgF8+f3TJUuTUumWCWbbA3VMebk1\nZfov9P/4nz6ACkgqOFnP5ixkX2x4uGxNNJsVv/rEjQKBgQDvUaXnnVvhl5Hx3LBg\ne66ysuXUTTmmorKd6zRlsr/x2SGotBX466Fyca6gwtMPTh9tVQyocNmGYjRbf32K\ns8esw1Xar8HgmDlGiRp+mrFdgSDJEQELaXoL3wlaTPLPdA+MhGGSVwaMCe/Ofx4w\n2Spz3X1kjtBL7QoPHSG4QAX/8wKBgQC7mbbyPMdiBlblv9olN/w+ZW0MUPni36LM\niIJyOnvzfUspyxXPLkjVzO0co03Lh6LJl73F+AFUQYk991VOfhk8uSLlJOswZwl6\nur2UM8C22AkPpXWmSi2RYXxeABs7TNvC/zXs5++j3NZZPha5CTBezED9a8q1o4S+\nAYmRT7gXvQKBgQDqg2r8/aGU/i9g/+7CjVDTAiXfldFhrls0DtEouzIGr8yhAd/q\nLhTmDeqe1Gt4uwhm3gnqYbN3UXKXGuaN7cBEVqIiC0sEaIbvzNhuqe4Wf7v97DDG\n2xRi36vNlkv16Hh4LR1kBu1+expIkx6lpZlJMwl2adBKJr1NtDFf2TVH6wKBgQCd\n/ZmGLkuYMVCTktxLxfeIMPECk1uvhrnbWQfK3Zgv+pAHdYI7hnZOoJP8L0fAJc2h\ny0pGZFPyOnMznY3ZWfc1HZHWux3bGJtyIbyxCFi/Y/dVlvoa/pObwSb1H0/PxC27\n7iTjDH3UWZKne9O1J5j17Ty6cEI6cKjFQBQ0LZgTXQKBgQCQMUmKV3IhppV+mkDC\ndqnJlxH7aSBgWF+dLzJJBc0Z04XpFFi8jpUaSF/aedO4BSlHBnJjWt0r86X6qINs\n8XjR0Mlmx0F7SZuqDLkzhFZCExiNZE/mzPTZ3P008xPCij8Nf0F8EUj0PodmgWZt\nyvJ2kxqw2YS57Vt8INZvxRjhTg==\n-----END PRIVATE KEY-----\n",
  "client_email": "earth-engine-service-account@ee-abhisheksasidharanr.iam.gserviceaccount.com",
  "client_id": "110619773534188793927",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/earth-engine-service-account%40ee-abhisheksasidharanr.iam.gserviceaccount.com",
  "universe_domain": "googleapis.com"
}'''
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
