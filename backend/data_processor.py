import pandas as pd
import os
import glob

# Paths
RAW_FOLDER = "data/raw/"
PROCESSED_FOLDER = "data/processed/"

def load_all_datasets():
    """Automatically loads ALL csv files from raw folder"""
    all_files = glob.glob(RAW_FOLDER + "*.csv")
    
    if not all_files:
        print("❌ No CSV files found in data/raw/")
        return None
    
    print(f"✅ Found {len(all_files)} file(s): {all_files}")
    
    dataframes = []
    for file in all_files:
        df = pd.read_csv(file)
        print(f"   Loaded: {file} → {len(df)} rows")
        dataframes.append(df)
    
    # Combine all files into one
    combined = pd.concat(dataframes, ignore_index=True)
    return combined

def clean_data(df):
    """Clean and prepare the data"""
    print("\n🔄 Cleaning data...")
    
    # Step 1 - Remove duplicates
    df = df.drop_duplicates()
    print(f"   After removing duplicates: {len(df)} rows")
    
    # Step 2 - Fix date format
    df['date'] = pd.to_datetime(df['date'])
    
    # Step 3 - Remove empty rows
    df = df.dropna()
    print(f"   After removing empty rows: {len(df)} rows")
    
    # Step 4 - Make commodity names consistent
    df['commodity'] = df['commodity'].str.strip().str.title()
    df['market'] = df['market'].str.strip().str.title()
    df['state'] = df['state'].str.strip().str.title()
    
    # Step 5 - Sort by date
    df = df.sort_values(['commodity', 'date'])
    
    print("✅ Data cleaned successfully!")
    return df

def save_processed_data(df):
    """Save cleaned data to processed folder"""
    
    # Save combined file
    combined_path = PROCESSED_FOLDER + "all_commodities_clean.csv"
    df.to_csv(combined_path, index=False)
    print(f"\n✅ Saved combined file: {combined_path}")
    
    # Save separate file for each commodity
    commodities = df['commodity'].unique()
    for commodity in commodities:
        commodity_df = df[df['commodity'] == commodity]
        filename = f"{commodity.lower()}_clean.csv"
        path = PROCESSED_FOLDER + filename
        commodity_df.to_csv(path, index=False)
        print(f"   Saved: {path} → {len(commodity_df)} rows")

def show_summary(df):
    """Show a summary of the data"""
    print("\n📊 DATA SUMMARY:")
    print(f"   Total records  : {len(df)}")
    print(f"   Commodities    : {list(df['commodity'].unique())}")
    print(f"   Date range     : {df['date'].min()} to {df['date'].max()}")
    print(f"   Markets        : {list(df['market'].unique())}")
    print("\n💰 Average Prices:")
    avg = df.groupby('commodity')['price'].mean().round(2)
    for commodity, price in avg.items():
        print(f"   {commodity}: ₹{price}/kg")

# ── Main ──
if __name__ == "__main__":
    print("🌾 AgriPrice Data Processor Starting...\n")
    
    df = load_all_datasets()
    
    if df is not None:
        df_clean = clean_data(df)
        save_processed_data(df_clean)
        show_summary(df_clean)
        print("\n✅ Phase 2 Complete! Data is ready for ML training.")