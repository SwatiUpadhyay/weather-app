from flask import Flask, render_template, request
import requests
from dotenv import load_dotenv
import os
from pymongo import MongoClient
from bson.objectid import ObjectId

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Load API key
API_KEY = os.getenv("WEATHER_API_KEY")
if not API_KEY:
    raise ValueError("❌ WEATHER_API_KEY not found in .env file")

# Setup MongoDB connection
try:
    MONGO_URI = os.getenv("MONGO_URI")
    if not MONGO_URI:
        raise ValueError("❌ MONGO_URI not found in .env file")

    client = MongoClient(MONGO_URI)
    db = client['weather-db']
    collection = db['searches']
    print("✅ Connected to MongoDB")
except Exception as e:
    print("❌ MongoDB connection error:", e)
    collection = None  # Fail gracefully

@app.route('/', methods=['GET', 'POST'])
def index():
    weather_data = None
    forecast_data = None
    error = None

    if request.method == 'POST':
        city = request.form.get('city')
        if city:
            try:
                current_url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units=metric"
                forecast_url = f"https://api.openweathermap.org/data/2.5/forecast?q={city}&appid={API_KEY}&units=metric"

                current_response = requests.get(current_url)
                forecast_response = requests.get(forecast_url)

                if current_response.status_code == 200 and forecast_response.status_code == 200:
                    current = current_response.json()
                    forecast = forecast_response.json()

                    weather_data = {
                        'city': city,
                        'temperature': current['main']['temp'],
                        'description': current['weather'][0]['description'],
                        'icon': current['weather'][0]['icon']
                    }

                    forecast_data = []
                    for entry in forecast['list']:
                        if "12:00:00" in entry['dt_txt']:
                            forecast_data.append({
                                'date': entry['dt_txt'].split(' ')[0],
                                'temp': entry['main']['temp'],
                                'desc': entry['weather'][0]['description'],
                                'icon': entry['weather'][0]['icon']
                            })

                    if collection is not None:
                        try:
                            collection.insert_one({
                                'city': city,
                                'temperature': weather_data['temperature'],
                                'description': weather_data['description'],
                                'icon': weather_data['icon'],
                                'forecast': forecast_data
                            })
                            print("✅ Data inserted into MongoDB for:", city)
                        except Exception as e:
                            print("❌ MongoDB insert error:", e)
                else:
                    error = "City not found. Please try again."
            except Exception as e:
                print("❌ Unexpected error:", e)
                error = "Something went wrong. Please try again later."

    # READ: Fetch saved data
    saved_searches = []
    if collection is not None:
        try:
            saved_searches = list(collection.find().sort('_id', -1))
            for s in saved_searches:
                s['_id'] = str(s['_id'])  # convert ObjectId to string
        except Exception as e:
            print("❌ Error reading from MongoDB:", e)

    return render_template('index.html', weather=weather_data, forecast=forecast_data, error=error, saved=saved_searches)

@app.route('/delete', methods=['POST'])
def delete():
    doc_id = request.form.get('id')
    try:
        collection.delete_one({'_id': ObjectId(doc_id)})
        print(f"🗑️ Deleted search with ID: {doc_id}")
    except Exception as e:
        print("❌ Delete error:", e)
    return index()

@app.route('/update', methods=['POST'])
def update():
    doc_id = request.form.get('id')
    new_city = request.form.get('new_city')

    if new_city:
        try:
            current_url = f"https://api.openweathermap.org/data/2.5/weather?q={new_city}&appid={API_KEY}&units=metric"
            forecast_url = f"https://api.openweathermap.org/data/2.5/forecast?q={new_city}&appid={API_KEY}&units=metric"

            current_response = requests.get(current_url)
            forecast_response = requests.get(forecast_url)

            if current_response.status_code == 200 and forecast_response.status_code == 200:
                current = current_response.json()
                forecast = forecast_response.json()

                weather_data = {
                    'city': new_city,
                    'temperature': current['main']['temp'],
                    'description': current['weather'][0]['description'],
                    'icon': current['weather'][0]['icon'],
                    'forecast': [
                        {
                            'date': entry['dt_txt'].split(' ')[0],
                            'temp': entry['main']['temp'],
                            'desc': entry['weather'][0]['description'],
                            'icon': entry['weather'][0]['icon']
                        }
                        for entry in forecast['list'] if "12:00:00" in entry['dt_txt']
                    ]
                }

                collection.update_one({'_id': ObjectId(doc_id)}, {'$set': weather_data})
                print(f"✏️ Updated search with new data for city: {new_city}")
            else:
                print("❌ Failed to update: new city not found.")
        except Exception as e:
            print("❌ Update error:", e)
    return index()

if __name__ == '__main__':
    print("Loaded API KEY:", API_KEY)
    app.run(debug=True)
