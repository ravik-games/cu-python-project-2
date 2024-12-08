import time
import json
import requests
from flask import Flask, render_template, jsonify, make_response, request
import credentials # Hidden file with API key

app = Flask(__name__)

# Web interface logic
@app.route('/')
def main_page():
    return render_template('main.html')


@app.route('/favicon.ico')
def favicon():
    return '', 204


# Additional logic for weather api
# This function is needed for the first task
def get_location_by_geoposition(latitude = 55.4424, longitude = 37.3636, _retry_count = 0):
    location_url = "http://dataservice.accuweather.com/locations/v1/cities/geoposition/search"

    response = requests.get(url = location_url, params = {
        "apikey": credentials.api_key,
        "q": f"{latitude},{longitude}",
        "language": "ru-RU",
    })

    if response.status_code != 200 or response.json() is None:
        print(f"Error occurred while getting geoposititon: {response.status_code}, {response.text}.")
        # Retry or abort
        if retry_request(_retry_count):
            get_location_by_geoposition(latitude, longitude, _retry_count + 1)
        else:
            return None

    location_key = response.json()["Key"]
    return location_key


# Returns current key params of weather. Also, response is stored in /temp folder
def get_current_weather(location_key = None, _retry_count = 0):
    if location_key is None:
        return None

    weather_url = f"http://dataservice.accuweather.com/currentconditions/v1/{location_key}"

    response = requests.get(url = weather_url, params={
        "apikey": credentials.api_key,
        "language": "ru-RU",
        "details": "true"
    })

    if response.status_code != 200 or response.json() is None:
        print(f"Error occurred while getting current weather: {response.status_code}, {response.text}.")
        # Retry or abort
        if retry_request(_retry_count):
            get_current_weather(location_key, _retry_count + 1)
        else:
            return None

    # Get 1-hour forecast for precipitation probability
    forecast = get_hour_prediction(location_key)
    if forecast is None:
        return None

    # Print extracted data from response to temp/last_response.json and temp/last_extracted_data.json
    raw_response = response.json()[0]

    wind = raw_response["Wind"]["Speed"]["Metric"]["Value"]
    if raw_response["Wind"]["Speed"]["Metric"]["Unit"] == "km/h":
        wind = "%.2f" % (wind * 5/18)

    data = {
        "temperature": raw_response["Temperature"]["Metric"]["Value"],
        "humidity": raw_response["RelativeHumidity"],
        "windSpeed": wind,
        "precipitationProbability": forecast[0]["PrecipitationProbability"],
    }
    with open(file="temp/last_response.json", encoding="UTF-8", mode="w") as file:
        json.dump(raw_response, file, ensure_ascii=False, indent=4)

    with open(file="temp/last_extracted_data.json", mode="w") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)

    return data


def get_hour_prediction(location_key, _retry_count = 0):
    forecast_url = f"http://dataservice.accuweather.com/forecasts/v1/hourly/1hour/{location_key}"

    response = requests.get(url = forecast_url, params = {
        "apikey": credentials.api_key,
        "language": "ru-RU",
        "details": "true"
    })

    if response.status_code != 200 or response.json() is None:
        print(f"Error occurred while getting current weather: {response.status_code}, {response.text}.")
        # Retry or abort
        if retry_request(_retry_count):
            get_hour_prediction(location_key, _retry_count + 1)
        else:
            return None

    return response.json()


def get_weather_type(temperature: float, humidity: float, wind_speed: float, precipitation_probability: float):
    precipitation_probability = precipitation_probability / 100 # Convert to 0 to 1
    if temperature < -10 or temperature > 35:
        return "Плохая погода"
    elif humidity < 40 or humidity > 90:
        return "Плохая погода"
    elif wind_speed > 12:
        return "Плохая погода"
    elif precipitation_probability > 0.9:
        return "Плохая погода"
    # Normal weather
    elif temperature < 10 or temperature > 30:
        return "Нормальная погода"
    elif humidity < 50 or humidity > 70:
        return "Нормальная погода"
    elif wind_speed > 8:
        return "Нормальная погода"
    elif precipitation_probability > 0.6:
        return "Нормальная погода"
    else:
        return "Хорошая погода"


def get_location_by_city(city_name, _retry_count = 0):
    city_url = "http://dataservice.accuweather.com/locations/v1/cities/search"

    response = requests.get(url=city_url, params={
        "apikey": credentials.api_key,
        "q": city_name,
        "language": "ru-RU",
    })

    if response.status_code != 200 or response.json() is None:
        print(f"Error occurred while getting city location: {response.status_code}, {response.text}.")
        # Retry or abort
        if retry_request(_retry_count):
            get_location_by_city(city_name, _retry_count + 1)
        else:
            return None

    location_key = response.json()[0]["Key"]
    return location_key


@app.route('/get_weather_data', methods=['POST'])
def get_weather_data():
    latitude = float(request.form['latitude'])
    longitude = float(request.form['longitude'])

    location_key = get_location_by_geoposition(latitude, longitude)
    weather_data = get_current_weather(location_key)
    if weather_data is None:
        return jsonify({})

    weather_data["weather_type"] = get_weather_type(float(weather_data["temperature"]),
                                                    float(weather_data["humidity"]),
                                                    float(weather_data["windSpeed"]),
                                                    float(weather_data["precipitationProbability"]))
    return jsonify(weather_data)


@app.route('/check_weather_type', methods=['POST'])
def check_weather_type():
    temperature = float(request.form['temperature'])
    humidity = float(request.form['humidity'])
    wind_speed = float(request.form['windSpeed'])
    precipitation = float(request.form['precipitation'])

    weather_type = get_weather_type(temperature, humidity, wind_speed, precipitation)
    return jsonify({'weather_type': weather_type})


@app.route('/get_weather_in_points', methods=['POST'])
def get_weather_in_points():
    if bool(request.form['city']):
        first_point = get_location_by_city(request.form['city-1'])
        second_point = get_location_by_city(request.form['city-2'])
    else:
        first_point = get_location_by_geoposition(float(request.form['latitude-1']), float(request.form['longitude-1']))
        second_point = get_location_by_geoposition(float(request.form['latitude-2']), float(request.form['longitude-2']))

    first_weather = get_current_weather(first_point)
    second_weather = get_current_weather(second_point)

    if first_weather is None or second_weather is None:
        return jsonify({})

    first_weather["weather_type"] = get_weather_type(float(first_weather["temperature"]),
                                                    float(first_weather["humidity"]),
                                                    float(first_weather["windSpeed"]),
                                                    float(first_weather["precipitationProbability"]))

    second_weather["weather_type"] = get_weather_type(float(second_weather["temperature"]),
                                                     float(second_weather["humidity"]),
                                                     float(second_weather["windSpeed"]),
                                                     float(second_weather["precipitationProbability"]))

    return jsonify([first_weather, second_weather])




# Error handlers
def retry_request(retry_count = 0, retry_limit = 3):
    # If retry count exceeds 5, abort GET request and return None
    if retry_count >= retry_limit:
        print(f"Retry limit exceeded. Aborting...")
        return False
    # Else try again after small delay, may be better luck next time
    print(f"Retrying... ({retry_count + 1}/{retry_limit})")
    time.sleep(0.5)  # Wait 500ms before next request
    return True


@app.errorhandler(404)
def not_found(error):
    if error is None:
        error = "Object not found"
    return make_response(jsonify({'error': error}), 404)


@app.errorhandler(400)
def bad_request(error):
    if error is None:
        error = "Invalid request"
    return make_response(jsonify({'error': error}), 400)


if __name__ == '__main__':
    app.run()
