import os
import io
import json
import requests
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.ticker import MaxNLocator
from flask import Flask, request, jsonify, send_file
from datetime import datetime
from matplotlib import cm

app = Flask(__name__)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

def fetch_weather_data(lat, lon):
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m,precipitation,wind_speed_10m,wind_direction_10m",
        "timezone": "auto"
    }
    res = requests.get(OPEN_METEO_URL, params=params)
    data = res.json()
    hourly = data["hourly"]
    df = pd.DataFrame(hourly)
    df["time"] = pd.to_datetime(df["time"])
    df["date"] = df["time"].dt.date
    df["hour"] = df["time"].dt.hour
    df["day"] = df["time"].dt.day_name()
    return df

def get_best_spray_times(df, max_wind_speed=10):
    today = datetime.now().date()
    df["safe"] = df["wind_speed_10m"] <= max_wind_speed
    df["color"] = df["safe"].map({True: "#d4edda", False: "#f8d7da"})

    today_df = df[df["date"] == today]
    week_df = df[df["safe"]].groupby("date").apply(lambda x: x.nsmallest(1, "wind_speed_10m")).reset_index(drop=True)

    def extract_time(row):
        return {
            "day": row["day"],
            "date": row["date"].strftime('%Y-%m-%d'),
            "time": f"{int(row['hour']):02d}:00",
            "wind_speed": round(row["wind_speed_10m"], 1),
            "color": row["color"]
        }

    return {
        "today": [extract_time(row) for _, row in today_df[today_df["safe"]].nsmallest(1, "wind_speed_10m").iterrows()],
        "week": [extract_time(row) for _, row in week_df.iterrows()]
    }

def plot_weather(df, y, ylabel, title):
    fig = Figure(figsize=(3, 2), dpi=150)
    ax = fig.subplots()
    ax.plot(df["time"], df[y], linewidth=1.5)
    ax.set_title(title, fontsize=10)
    ax.set_xlabel("Time", fontsize=8)
    ax.set_ylabel(ylabel, fontsize=8)
    ax.tick_params(axis='both', labelsize=6)
    ax.xaxis.set_major_locator(MaxNLocator(4))
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    buf.seek(0)
    return buf

def plot_wind_rose(directions):
    fig = Figure(figsize=(2.5, 2.5), dpi=100)
    ax = fig.add_subplot(111, polar=True)
    bins = range(0, 361, 30)
    hist, bin_edges = pd.cut(directions, bins, right=False, labels=bins[:-1], retbins=True)
    hist_counts = pd.Series(hist).value_counts().sort_index()
    theta = [d * (3.14 / 180) for d in bin_edges[:-1]]
    values = hist_counts.values.tolist()
    values += [values[0]]
    theta += [theta[0]]
    ax.plot(theta, values, color="tab:blue")
    ax.fill(theta, values, color="skyblue", alpha=0.5)
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_xticks([i * (3.14 / 180) * 45 for i in range(8)])
    ax.set_xticklabels(['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'])
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    buf.seek(0)
    return buf

@app.route("/")
def index():
    return send_file("templates/index.html")

@app.route("/get_weather_data", methods=["POST"])
def get_weather_data():
    lat = request.json["lat"]
    lon = request.json["lon"]
    df = fetch_weather_data(lat, lon)

    data = {
        "temperature_plot": plot_weather(df, "temperature_2m", "°C", "Temperature").read(),
        "wind_plot": plot_weather(df, "wind_speed_10m", "m/s", "Wind Speed").read(),
        "precipitation_plot": plot_weather(df, "precipitation", "mm", "Precipitation").read(),
        "wind_rose_plot": plot_wind_rose(df["wind_direction_10m"]).read(),
        "spray_times": get_best_spray_times(df)
    }

    return jsonify({
        "temperature_plot": data["temperature_plot"].decode("latin1"),
        "wind_plot": data["wind_plot"].decode("latin1"),
        "precipitation_plot": data["precipitation_plot"].decode("latin1"),
        "wind_rose_plot": data["wind_rose_plot"].decode("latin1"),
        "spray_times": data["spray_times"]
    })

if __name__ == "__main__":
    app.run(debug=True)
