import os
import numpy as np
import pandas as pd
import tensorflow as tf
from tensorflow import keras
from keras.preprocessing import image # type: ignore
from flask import Flask, request, render_template, jsonify
import requests
from io import BytesIO
from PIL import Image
import base64

# Initialize Flask application
app = Flask(__name__, template_folder=r'B:\final year projects\SoilSense-Crop-Recommendation-main\SoilSense-Crop-Recommendation-main\Frontend\templates')

# Paths to the model and CSV file
MODEL_PATH = r'B:\final year projects\SoilSense-Crop-Recommendation-main\SoilSense-Crop-Recommendation-main\Backend\soil_classification_model_mobilenet.h5'
CROP_CSV_PATH = r'B:\final year projects\SoilSense-Crop-Recommendation-main\SoilSense-Crop-Recommendation-main\Datasets\Crop_recommendation.csv'

# Weather API URL and Key
API_KEY = 'b95ec1dba49c758f63d36e1a685edb59'
WEATHER_API_URL = 'http://api.openweathermap.org/data/2.5/weather'

# Load the trained model
model = tf.keras.models.load_model(MODEL_PATH)

# Define class labels
class_labels = [
    'Alluvial soil', 'Black Soil', 'Cinder Soil', 'Clayey soil',
    'Laterite Soil', 'Loamy soil', 'Peat Soil', 'Red soil',
    'Sandy loam', 'Sandy soil', 'Yellow Soil'
]

# Load crop recommendations from the CSV file
def load_crop_recommendations():
    try:
        crop_data = pd.read_csv(CROP_CSV_PATH, skipinitialspace=True)
        crop_data.columns = crop_data.columns.str.strip().str.lower()  # Normalize column names

        # Check if required columns exist
        required_columns = {'soil type', 'crop type', 'temperature', 'humidity', 'nitrogen', 'phosphorous', 'potassium', 'fertilizer name'}
        if not required_columns.issubset(set(crop_data.columns)):
            print("Error: CSV file is missing required columns.")
            return {}

        # Organize data by soil type
        recommendations = {}
        for _, row in crop_data.iterrows():
            soil_type = row['soil type'].strip().lower()
            crop_details = {
                'crop_type': row['crop type'],
                'temperature': row['temperature'],  
                'humidity': row['humidity'],
                'nitrogen': row['nitrogen'],
                'phosphorous': row['phosphorous'],
                'potassium': row['potassium'],
                'fertilizer': row['fertilizer name']
            }
            if soil_type not in recommendations:
                recommendations[soil_type] = []
            recommendations[soil_type].append(crop_details)

        return recommendations
    except Exception as e:
        print(f"Error loading crop recommendations: {e}")
        return {}

# Get weather data for the given city
def get_weather_data(city):
    try:
        params = {'q': city, 'appid': API_KEY, 'units': 'metric'}
        response = requests.get(WEATHER_API_URL, params=params)
        weather_data = response.json()

        if weather_data.get('cod') == 200:
            return (
                weather_data['main'].get('temp'),
                weather_data['main'].get('humidity'),
                weather_data['weather'][0].get('description')
            )
        return None, None, None
    except Exception as e:
        print(f"Error fetching weather data: {e}")
        return None, None, None

# Load recommendations once at startup
crop_recommendations = load_crop_recommendations()

@app.route('/')
def home():
    return render_template('index.html')

# Process base64 image
def process_image_from_base64(base64_str):
    try:
        base64_str = base64_str.split(',')[1] if ',' in base64_str else base64_str
        img_data = base64.b64decode(base64_str)
        img = Image.open(BytesIO(img_data))
        img = img.resize((224, 224))  # Resize for model
        img_array = np.expand_dims(np.array(img) / 255.0, axis=0)
        return img_array
    except Exception as e:
        print(f"Error processing base64 image: {e}")
        return None

@app.route('/predict', methods=['POST'])
def predict():
    file = request.files.get('file')
    captured_image = request.form.get('captured_image')
    city = request.form.get('city')

    img_array = None

    if file and file.filename:
        os.makedirs('uploads', exist_ok=True)
        file_path = os.path.join('uploads', file.filename)
        file.save(file_path)

        img = image.load_img(file_path, target_size=(224, 224))
        img_array = np.expand_dims(image.img_to_array(img) / 255.0, axis=0)
    elif captured_image:
        img_array = process_image_from_base64(captured_image)

    if img_array is None:
        return render_template('index.html', error="Invalid image input")

    # Make prediction
    predictions = model.predict(img_array)
    predicted_class_index = np.argmax(predictions, axis=1)[0]
    predicted_class = class_labels[predicted_class_index].lower().strip()

    # Get crop recommendations
    soil_crops = crop_recommendations.get(predicted_class, [])
    if not soil_crops:
        return render_template('index.html', error=f"No data available for soil type: {predicted_class}")

    # Get weather data
    temperature, humidity, description = get_weather_data(city)

    return render_template(
        'index.html',
        soil_type=predicted_class.title(),
        crops=list({crop['crop_type'] for crop in soil_crops}),
        uploaded_image=file.filename if file else None,
        city=city,
        temperature=temperature,
        humidity=humidity,
        description=description
    )

@app.route('/crop_details', methods=['POST'])
def crop_details():
    crop_type = request.form.get('crop_type')
    soil_type = request.form.get('soil_type', '').lower()

    selected_crop = next(
        (crop for crop in crop_recommendations.get(soil_type, []) if crop['crop_type'] == crop_type), None
    )

    if not selected_crop:
        return jsonify({"error": "Crop details not found"}), 404

    return render_template(
        'index.html',
        crop_info={
            'Soil Type': soil_type.title(),
            'Crop Type': selected_crop['crop_type'],
            'Temperature': selected_crop['temperature'],
            'Humidity': selected_crop['humidity'],
            'Nitrogen': selected_crop['nitrogen'],
            'Phosphorous': selected_crop['phosphorous'],
            'Potassium': selected_crop['potassium'],
            'Fertilizer Name': selected_crop['fertilizer']
        }
    )

if __name__ == "__main__":
    app.run(debug=True)
