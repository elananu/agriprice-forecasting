import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
import pickle
import os

# Paths
PROCESSED_FOLDER = "data/processed/"
MODELS_FOLDER = "ml_models/"

def prepare_features(df):
    """Create ML features from date and price data"""
    df = df.copy()
    
    # Extract date features
    df['day']        = df['date'].dt.day
    df['month']      = df['date'].dt.month
    df['year']       = df['date'].dt.year
    df['dayofweek']  = df['date'].dt.dayofweek
    df['dayofyear']  = df['date'].dt.dayofyear
    
    # Lag features — previous prices as input
    df['price_lag1'] = df['price'].shift(1)  # yesterday's price
    df['price_lag2'] = df['price'].shift(2)  # 2 days ago
    df['price_lag3'] = df['price'].shift(3)  # 3 days ago
    
    # Rolling average — trend over last 3 days
    df['price_roll3'] = df['price'].shift(1).rolling(3).mean()
    
    # Drop rows with NaN (from lag/rolling)
    df = df.dropna()
    
    return df

def train_model(commodity_name):
    """Train ML model for a specific commodity"""
    print(f"\n🌾 Training model for: {commodity_name}")
    
    # Load commodity data
    filename = f"{commodity_name.lower()}_clean.csv"
    filepath = PROCESSED_FOLDER + filename
    
    if not os.path.exists(filepath):
        print(f"❌ File not found: {filepath}")
        return None
    
    df = pd.read_csv(filepath)
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)
    
    # Prepare features
    df = prepare_features(df)
    
    # Define input (X) and output (y)
    feature_cols = ['day', 'month', 'year', 'dayofweek', 
                    'dayofyear', 'price_lag1', 'price_lag2', 
                    'price_lag3', 'price_roll3']
    
    X = df[feature_cols]
    y = df['price']
    
    # Split into train and test
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    
    # Train Random Forest model
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    
    # Evaluate model
    y_pred = model.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    r2  = r2_score(y_test, y_pred)
    
    print(f"   ✅ Training complete!")
    print(f"   📊 MAE (Mean Absolute Error) : ₹{mae:.2f}")
    print(f"   📊 R2 Score                  : {r2:.2f} (1.0 = perfect)")
    
    # Save model
    model_path = MODELS_FOLDER + f"{commodity_name.lower()}_model.pkl"
    with open(model_path, 'wb') as f:
        pickle.dump(model, f)
    print(f"   💾 Model saved: {model_path}")
    
    return model, df, feature_cols

def predict_next_7_days(commodity_name):
    """Predict prices for next 7 days"""
    print(f"\n🔮 Predicting next 7 days for: {commodity_name}")
    
    # Load saved model
    model_path = MODELS_FOLDER + f"{commodity_name.lower()}_model.pkl"
    with open(model_path, 'rb') as f:
        model = pickle.load(f)
    
    # Load latest data
    filepath = PROCESSED_FOLDER + f"{commodity_name.lower()}_clean.csv"
    df = pd.read_csv(filepath)
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)
    
    # Get last 3 prices for lag features
    last_prices = df['price'].tolist()
    last_date   = df['date'].iloc[-1]
    
    predictions = []
    
    for i in range(1, 366):
        future_date = last_date + pd.Timedelta(days=i)
        
        lag1      = last_prices[-1]
        lag2      = last_prices[-2]
        lag3      = last_prices[-3]
        roll3     = np.mean([lag1, lag2, lag3])
        
        features = [[
            future_date.day,
            future_date.month,
            future_date.year,
            future_date.dayofweek,
            future_date.dayofyear,
            lag1, lag2, lag3, roll3
        ]]
        
        predicted_price = model.predict(features)[0]
        predictions.append({
            'date'            : future_date.strftime('%Y-%m-%d'),
            'predicted_price' : round(predicted_price, 2)
        })
        
        # Add predicted price for next iteration
        last_prices.append(predicted_price)
    
    return predictions

def show_predictions(commodity_name, predictions):
    """Display predictions nicely"""
    print(f"\n📅 Price Forecast for {commodity_name}:")
    print("-" * 35)
    
    first_price = predictions[0]['predicted_price']
    last_price  = predictions[-1]['predicted_price']
    trend       = "📈 Rising" if last_price > first_price else "📉 Falling"
    
    for p in predictions:
        print(f"   {p['date']}  →  ₹{p['predicted_price']}/kg")
    
    print("-" * 35)
    print(f"   Trend: {trend}")
    
    if trend == "📈 Rising":
        print("   💡 Recommendation: Good time to SELL soon!")
    else:
        print("   💡 Recommendation: Good time to BUY now!")

# ── Main ──
if __name__ == "__main__":
    print("🤖 AgriPrice ML Model Training Started...\n")
    
    commodities = ['Coconut', 'Onion', 'Tomato', 'Rice', 'Banana']
    
    # Train models for all commodities
    for commodity in commodities:
        result = train_model(commodity)
    
    print("\n" + "="*50)
    print("🔮 PRICE PREDICTIONS FOR NEXT 7 DAYS")
    print("="*50)
    
    # Show predictions for all commodities
    for commodity in commodities:
        predictions = predict_next_7_days(commodity)
        show_predictions(commodity, predictions)
    
    print("\n✅ Phase 3 Complete! ML Models trained and predictions ready.")