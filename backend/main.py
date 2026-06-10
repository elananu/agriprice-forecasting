from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.units import inch
import pandas as pd
import numpy as np
import pickle
import os
import shutil
import subprocess
import requests
import io
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="AgriPrice Forecasting API", version="3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

MODELS_FOLDER    = "ml_models/"
PROCESSED_FOLDER = "data/processed/"
RAW_FOLDER       = "data/raw/"
WEATHER_API_KEY  = os.getenv("WEATHER_API_KEY", "7a16369a8a2dc7766bc9f92103d58dc4")

COMMODITIES = ['coconut','onion','tomato','rice','banana',
               'wheat','potato','garlic','chilli','turmeric','sugarcane']

CITIES = {
    'Chennai':   {'lat': 13.08, 'lon': 80.27, 'factor': 1.0},
    'Mumbai':    {'lat': 19.07, 'lon': 72.87, 'factor': 1.08},
    'Delhi':     {'lat': 28.70, 'lon': 77.10, 'factor': 1.12},
    'Bangalore': {'lat': 12.97, 'lon': 77.59, 'factor': 0.95},
    'Kolkata':   {'lat': 22.57, 'lon': 88.36, 'factor': 1.05},
}

SEASONS = {
    1: 'Winter', 2: 'Winter', 3: 'Summer',
    4: 'Summer', 5: 'Summer', 6: 'Monsoon',
    7: 'Monsoon', 8: 'Monsoon', 9: 'Monsoon',
    10: 'Post-Monsoon', 11: 'Post-Monsoon', 12: 'Winter'
}

FESTIVALS = [
    {'name': 'Pongal',    'month': 1,  'impact': 1.15},
    {'name': 'Holi',      'month': 3,  'impact': 1.10},
    {'name': 'Diwali',    'month': 10, 'impact': 1.20},
    {'name': 'Christmas', 'month': 12, 'impact': 1.08},
]

# ── Helper Functions ──

def load_model(commodity):
    path = MODELS_FOLDER + f"{commodity.lower()}_model.pkl"
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"Model not found for {commodity}.")
    with open(path, 'rb') as f:
        return pickle.load(f)

def get_predictions(commodity, days=7):
    model    = load_model(commodity)
    filepath = PROCESSED_FOLDER + f"{commodity.lower()}_clean.csv"
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail=f"Data not found for {commodity}")

    df = pd.read_csv(filepath)
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)

    last_prices   = df['price'].tolist()
    last_date     = df['date'].iloc[-1]
    current_price = last_prices[-1]

    predictions = []
    for i in range(1, days + 1):
        future_date = last_date + timedelta(days=i)
        lag1  = last_prices[-1]
        lag2  = last_prices[-2]
        lag3  = last_prices[-3]
        roll3 = np.mean([lag1, lag2, lag3])

        feature_df = pd.DataFrame([[
            future_date.day, future_date.month, future_date.year,
            future_date.dayofweek, future_date.timetuple().tm_yday,
            lag1, lag2, lag3, roll3
        ]], columns=[
            'day', 'month', 'year', 'dayofweek', 'dayofyear',
            'price_lag1', 'price_lag2', 'price_lag3', 'price_roll3'
        ])

        predicted_price = round(model.predict(feature_df)[0], 2)
        predictions.append({
            "date"          : future_date.strftime('%Y-%m-%d'),
            "price"         : predicted_price,
            "price_ton"     : round(predicted_price * 1000, 2),
            "price_quintal" : round(predicted_price * 100, 2),
        })
        last_prices.append(predicted_price)

    return current_price, predictions

def get_weather_impact(temp, humidity):
    impacts = []
    if temp > 35:     impacts.append("⚠️ High heat may reduce yield — expect price rise")
    elif temp < 20:   impacts.append("✅ Cool weather good for crops — prices may stabilize")
    if humidity > 80: impacts.append("⚠️ High humidity — fungal disease risk")
    elif humidity < 40: impacts.append("⚠️ Drought risk — prices may rise")
    return " | ".join(impacts) if impacts else "✅ Normal conditions — stable prices expected"

# ── Endpoints ──

@app.get("/")
def home():
    return {
        "message": "AgriPrice Forecasting API v3.0",
        "features": [
            "7/30/90/365-day forecasts",
            "multi-city pricing",
            "bulk pricing per ton/quintal",
            "live weather integration",
            "price alerts",
            "excel & pdf export",
            "seasonal analysis",
            "csv upload"
        ]
    }

@app.get("/commodities")
def get_commodities():
    available = [c for c in COMMODITIES
                 if os.path.exists(PROCESSED_FOLDER + f"{c}_clean.csv")]
    return {"commodities": available, "total": len(available)}

@app.get("/predict/{commodity}")
def predict_price(commodity: str, days: int = 7, city: str = "Chennai"):
    if commodity.lower() not in COMMODITIES:
        raise HTTPException(status_code=400, detail="Invalid commodity.")

    city_factor = CITIES.get(city, {}).get('factor', 1.0)
    current_price, predictions = get_predictions(commodity, days)

    for p in predictions:
        p['price']         = round(p['price'] * city_factor, 2)
        p['price_ton']     = round(p['price'] * 1000, 2)
        p['price_quintal'] = round(p['price'] * 100, 2)

    first_price = predictions[0]['price']
    last_price  = predictions[-1]['price']
    trend       = "rising" if last_price > first_price else "falling"
    change_pct  = round(((last_price - first_price) / first_price) * 100, 1)

    current_month  = datetime.now().month
    current_season = SEASONS[current_month]
    festival_alert = None
    for f in FESTIVALS:
        if f['month'] == current_month:
            festival_alert = f"🎉 {f['name']} season — expect {int((f['impact']-1)*100)}% price rise"

    if change_pct > 5:
        recommendation = "🔴 STRONG SELL — Prices rising sharply. Sell now for maximum profit!"
        action = "SELL"
    elif change_pct > 2:
        recommendation = "🟡 SELL — Prices going up. Good time to sell."
        action = "SELL"
    elif change_pct < -5:
        recommendation = "🟢 STRONG BUY — Prices falling sharply. Buy now for best deal!"
        action = "BUY"
    elif change_pct < -2:
        recommendation = "🟡 BUY — Prices going down. Good time to buy."
        action = "BUY"
    else:
        recommendation = "⚪ HOLD — Prices stable. Monitor before deciding."
        action = "HOLD"

    return {
        "commodity"       : commodity.title(),
        "city"            : city,
        "current_price"   : float(round(current_price * city_factor, 2)),
        "current_per_ton" : float(round(current_price * city_factor * 1000, 2)),
        "currency"        : "INR",
        "unit"            : "per_kg",
        "trend"           : trend,
        "change_pct"      : change_pct,
        "action"          : action,
        "recommendation"  : recommendation,
        "season"          : current_season,
        "festival_alert"  : festival_alert,
        "predictions"     : predictions,
        "forecast_days"   : days,
        "last_updated"    : datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

@app.get("/summary")
def get_summary(city: str = "Chennai"):
    city_factor = CITIES.get(city, {}).get('factor', 1.0)
    summary = []
    for commodity in COMMODITIES:
        try:
            filepath = PROCESSED_FOLDER + f"{commodity}_clean.csv"
            df = pd.read_csv(filepath)
            current = float(df['price'].iloc[-1]) * city_factor
            prev    = float(df['price'].iloc[-2]) * city_factor if len(df) > 1 else current
            change  = round(current - prev, 2)
            summary.append({
                "commodity"       : commodity.title(),
                "current_price"   : round(current, 2),
                "current_per_ton" : round(current * 1000, 2),
                "avg_price"       : round(float(df['price'].mean()) * city_factor, 2),
                "min_price"       : round(float(df['price'].min()) * city_factor, 2),
                "max_price"       : round(float(df['price'].max()) * city_factor, 2),
                "change"          : change,
                "change_pct"      : round((change / prev) * 100, 1) if prev else 0,
                "unit"            : "per_kg"
            })
        except:
            pass
    return {"summary": summary, "city": city, "total": len(summary)}

@app.get("/history/{commodity}")
def get_history(commodity: str):
    filepath = PROCESSED_FOLDER + f"{commodity.lower()}_clean.csv"
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Data not found")
    df = pd.read_csv(filepath)
    return {
        "commodity"     : commodity.title(),
        "history"       : df[['date', 'price']].to_dict(orient='records'),
        "total_records" : len(df)
    }

@app.get("/multicity/{commodity}")
def get_multicity(commodity: str):
    if commodity.lower() not in COMMODITIES:
        raise HTTPException(status_code=400, detail="Invalid commodity")
    filepath = PROCESSED_FOLDER + f"{commodity.lower()}_clean.csv"
    df = pd.read_csv(filepath)
    base_price = float(df['price'].iloc[-1])
    result = []
    min_factor = min(CITIES.values(), key=lambda x: x['factor'])['factor']
    max_factor = max(CITIES.values(), key=lambda x: x['factor'])['factor']
    for city, info in CITIES.items():
        price = round(base_price * info['factor'], 2)
        if info['factor'] == min_factor:
            rec = "Best to buy here"
        elif info['factor'] == max_factor:
            rec = "Best to sell here"
        else:
            rec = "Average market"
        result.append({
            "city"          : city,
            "price_per_kg"  : price,
            "price_per_ton" : round(price * 1000, 2),
            "price_quintal" : round(price * 100, 2),
            "recommendation": rec
        })
    result.sort(key=lambda x: x['price_per_kg'])
    return {"commodity": commodity.title(), "cities": result}

@app.get("/seasonal/{commodity}")
def get_seasonal(commodity: str):
    filepath = PROCESSED_FOLDER + f"{commodity.lower()}_clean.csv"
    df = pd.read_csv(filepath)
    df['date']   = pd.to_datetime(df['date'])
    df['month']  = df['date'].dt.month
    df['season'] = df['month'].map(SEASONS)
    seasonal = df.groupby('season')['price'].agg(['mean','min','max']).round(2).reset_index()
    seasonal.columns = ['season', 'avg_price', 'min_price', 'max_price']
    best_buy  = seasonal.loc[seasonal['avg_price'].idxmin(), 'season']
    best_sell = seasonal.loc[seasonal['avg_price'].idxmax(), 'season']
    return {
        "commodity"        : commodity.title(),
        "seasonal"         : seasonal.to_dict(orient='records'),
        "best_buy_season"  : best_buy,
        "best_sell_season" : best_sell,
        "current_season"   : SEASONS[datetime.now().month]
    }

@app.get("/weather")
def get_weather(city: str = "Chennai"):
    try:
        url  = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric"
        res  = requests.get(url, timeout=5)
        data = res.json()
        if res.status_code != 200:
            raise Exception("API error")
        return {
            "city"        : city,
            "temperature" : data['main']['temp'],
            "feels_like"  : data['main']['feels_like'],
            "humidity"    : data['main']['humidity'],
            "description" : data['weather'][0]['description'].title(),
            "wind_speed"  : data['wind']['speed'],
            "impact"      : get_weather_impact(data['main']['temp'], data['main']['humidity'])
        }
    except:
        return {
            "city"        : city,
            "temperature" : 32,
            "humidity"    : 75,
            "description" : "Data unavailable",
            "impact"      : "Weather data temporarily unavailable"
        }

@app.get("/alerts")
def get_alerts():
    alerts = []
    for commodity in COMMODITIES:
        try:
            _, predictions = get_predictions(commodity, 7)
            first      = predictions[0]['price']
            last       = predictions[-1]['price']
            change_pct = ((last - first) / first) * 100
            if abs(change_pct) >= 2:
                severity = "high" if abs(change_pct) >= 8 else "medium" if abs(change_pct) >= 4 else "low"
                alerts.append({
                    "commodity" : commodity.title(),
                    "type"      : "rise" if change_pct > 0 else "drop",
                    "severity"  : severity,
                    "change_pct": round(change_pct, 1),
                    "message"   : f"{commodity.title()} prices expected to {'rise' if change_pct > 0 else 'drop'} by {abs(round(change_pct,1))}% this week"
                })
        except:
            pass
    alerts.sort(key=lambda x: abs(x['change_pct']), reverse=True)
    return {"alerts": alerts, "total": len(alerts)}

@app.post("/upload")
async def upload_dataset(file: UploadFile = File(...)):
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files allowed")
    save_path = f"{RAW_FOLDER}{file.filename}"
    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    subprocess.run(["python", "backend/data_processor.py"])
    subprocess.run(["python", "ml_models/price_predictor.py"])
    return {"message": f"File '{file.filename}' uploaded and processed!", "filename": file.filename}

@app.get("/live/{commodity}")
def get_live_price(commodity: str):
    filepath = PROCESSED_FOLDER + f"{commodity.lower()}_clean.csv"
    df = pd.read_csv(filepath)
    base_price = float(df['price'].iloc[-1])
    live_price = round(base_price + np.random.uniform(-0.5, 0.5), 2)
    return {
        "commodity"  : commodity.title(),
        "live_price" : live_price,
        "timestamp"  : datetime.now().strftime('%H:%M:%S'),
        "unit"       : "per_kg"
    }

@app.get("/export/excel/{commodity}")
def export_excel(commodity: str, days: int = 30, city: str = "Chennai"):
    city_factor  = CITIES.get(city, {}).get('factor', 1.0)
    current_price, predictions = get_predictions(commodity, days)
    filepath = PROCESSED_FOLDER + f"{commodity.lower()}_clean.csv"
    hist_df  = pd.read_csv(filepath)

    for p in predictions:
        p['price']         = round(p['price'] * city_factor, 2)
        p['price_ton']     = round(p['price'] * 1000, 2)
        p['price_quintal'] = round(p['price'] * 100, 2)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        pred_df = pd.DataFrame(predictions)
        pred_df.columns = ['Date','Price/kg (Rs.)','Price/ton (Rs.)','Price/quintal (Rs.)']
        pred_df.to_excel(writer, sheet_name='Price Forecast', index=False)

        hist_df[['date','price']].rename(
            columns={'date':'Date','price':'Price/kg (Rs.)'}).to_excel(
            writer, sheet_name='Price History', index=False)

        summary_data = {
            'Metric': ['Commodity','City','Current Price/kg','Current Price/Ton',
                       'Forecast Period','Season','Generated On'],
            'Value':  [commodity.title(), city,
                       f'Rs.{round(current_price*city_factor,2)}',
                       f'Rs.{round(current_price*city_factor*1000,2)}',
                       f'{days} days', SEASONS[datetime.now().month],
                       datetime.now().strftime('%Y-%m-%d %H:%M')]
        }
        pd.DataFrame(summary_data).to_excel(writer, sheet_name='Summary', index=False)

    output.seek(0)
    filename = f"{commodity}_{city}_forecast_{datetime.now().strftime('%Y%m%d')}.xlsx"
    return StreamingResponse(
        output,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )

@app.get("/export/pdf/{commodity}")
def export_pdf(commodity: str, days: int = 7, city: str = "Chennai"):
    if commodity.lower() not in COMMODITIES:
        raise HTTPException(status_code=400, detail="Invalid commodity")

    city_factor   = CITIES.get(city, {}).get('factor', 1.0)
    current_price, predictions = get_predictions(commodity, days)
    current_price = round(current_price * city_factor, 2)

    for p in predictions:
        p['price'] = round(p['price'] * city_factor, 2)

    first      = predictions[0]['price']
    last       = predictions[-1]['price']
    change_pct = round(((last - first) / first) * 100, 1)
    trend      = "RISING" if change_pct > 0 else "FALLING"
    action     = "SELL — Prices going up" if change_pct > 0 else "BUY — Prices going down"

    buffer = io.BytesIO()
    doc    = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5*inch)
    styles = getSampleStyleSheet()
    story  = []

    # Title
    story.append(Paragraph("AgriPrice Market Intelligence Report", styles['Title']))
    story.append(Paragraph(f"{commodity.title()} — {city} Market", styles['Heading2']))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}  |  Season: {SEASONS[datetime.now().month]}", styles['Normal']))
    story.append(Spacer(1, 0.2*inch))

    # Summary Table
    story.append(Paragraph("Price Summary", styles['Heading3']))
    summary_data = [
        ['Metric', 'Value'],
        ['Commodity',          commodity.title()],
        ['Market City',        city],
        ['Current Price/kg',   f'Rs. {current_price}'],
        ['Current Price/Quintal', f'Rs. {round(current_price*100, 2)}'],
        ['Current Price/Ton',  f'Rs. {round(current_price*1000, 2):,.2f}'],
        ['Forecast Period',    f'{days} days'],
        ['Current Season',     SEASONS[datetime.now().month]],
        ['Price Trend',        f'{trend} ({change_pct}%)'],
        ['Recommended Action', action],
    ]
    t = Table(summary_data, colWidths=[3*inch, 3*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#10b981')),
        ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
        ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE',   (0,0), (-1,-1), 10),
        ('GRID',       (0,0), (-1,-1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f0fdf4')]),
        ('PADDING',    (0,0), (-1,-1), 8),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.2*inch))

    # Forecast Table
    story.append(Paragraph(f"{days}-Day Price Forecast", styles['Heading3']))
    pred_data = [['Date', 'Price/kg (Rs.)', 'Price/Quintal (Rs.)', 'Price/Ton (Rs.)']]
    for p in predictions[:days]:
        pred_data.append([
            p['date'],
            str(p['price']),
            str(round(p['price'] * 100, 2)),
            str(f"{round(p['price'] * 1000, 2):,.2f}")
        ])
    t2 = Table(pred_data, colWidths=[1.8*inch, 1.8*inch, 1.8*inch, 1.8*inch])
    t2.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,0), colors.HexColor('#1e3a5f')),
        ('TEXTCOLOR',     (0,0), (-1,0), colors.white),
        ('FONTNAME',      (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE',      (0,0), (-1,-1), 9),
        ('GRID',          (0,0), (-1,-1), 0.5, colors.grey),
        ('ROWBACKGROUNDS',(0,1), (-1,-1), [colors.white, colors.HexColor('#f0f9ff')]),
        ('PADDING',       (0,0), (-1,-1), 6),
    ]))
    story.append(t2)
    story.append(Spacer(1, 0.2*inch))

    # Disclaimer
    story.append(Paragraph("Disclaimer", styles['Heading3']))
    story.append(Paragraph(
        "This report is AI-generated based on historical price trends and machine learning models. "
        "Predictions are estimates only. Please verify with market sources before making business decisions.",
        styles['Normal']
    ))

    doc.build(story)
    buffer.seek(0)
    filename = f"{commodity}_{city}_report_{datetime.now().strftime('%Y%m%d')}.pdf"
    return StreamingResponse(
        buffer,
        media_type='application/pdf',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )

@app.on_event("startup")
async def startup_event():
    """Run data processing on startup if models don't exist"""
    import subprocess, sys
    models_exist = all(
        os.path.exists(f"ml_models/{c}_model.pkl")
        for c in COMMODITIES
    )
    if not models_exist:
        print("Running data processor...")
        subprocess.run([sys.executable, "backend/data_processor.py"])
        subprocess.run([sys.executable, "ml_models/price_predictor.py"])
        print("Models ready!")