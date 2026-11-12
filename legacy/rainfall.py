import os
import matplotlib
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

# Create directory for plots
if not os.path.exists('./plots'):
    os.makedirs('./plots')

# Load data
def load_data():
    rooftop_data = pd.read_csv(r'C:\Users\Bibek\Downloads\Building_Rooftop_Area_Data.csv')
    rainfall_data = pd.read_csv(r'C:\Users\Bibek\Downloads\Precipitation_Data.csv')
    rainfall_data['DateTime'] = pd.to_datetime(rainfall_data['DateTime'])
    return rooftop_data, rainfall_data

# Calculate rainwater potential
def calculate_water_collection(rooftop_data, rainfall_data):
    daily_rainfall = rainfall_data.groupby(rainfall_data['DateTime'].dt.date)['Rainfall (mm/hr)'].sum().reset_index()
    daily_rainfall.columns = ['Date', 'Daily_Rainfall_mm']
    daily_rainfall['Month'] = pd.to_datetime(daily_rainfall['Date']).dt.month
    daily_rainfall['Season'] = daily_rainfall['Month'].map({
        12: 'Winter', 1: 'Winter', 2: 'Winter',
        3: 'Spring', 4: 'Spring', 5: 'Spring',
        6: 'Summer', 7: 'Summer', 8: 'Summer',
        9: 'Autumn', 10: 'Autumn', 11: 'Autumn'
    })
    total_rainfall = daily_rainfall['Daily_Rainfall_mm'].sum()
    rooftop_data['Total_Collection_L'] = rooftop_data['Rooftop Area (m²)'] * total_rainfall * 0.9 / 1000
    return rooftop_data, daily_rainfall

# Monthly and seasonal rainfall
def plot_monthly_seasonal_rainfall(daily_rainfall):
    monthly_totals = daily_rainfall.groupby('Month')['Daily_Rainfall_mm'].sum().reset_index()
    seasonal_totals = daily_rainfall.groupby('Season')['Daily_Rainfall_mm'].sum().reset_index()

    # Monthly rainfall
    plt.figure(figsize=(10, 6))
    sns.barplot(x='Month', y='Daily_Rainfall_mm', data=monthly_totals, palette='Blues_d')
    plt.title('Total Rainfall by Month')
    plt.xlabel('Month')
    plt.ylabel('Rainfall (mm)')
    plt.tight_layout()
    plt.savefig('./plots/monthly_rainfall.png')
    plt.show()

    # Seasonal contribution pie chart
    plt.figure(figsize=(8, 8))
    plt.pie(seasonal_totals['Daily_Rainfall_mm'], labels=seasonal_totals['Season'], autopct='%1.1f%%', colors=sns.color_palette('coolwarm', 4))
    plt.title('Seasonal Contribution to Total Rainfall')
    plt.savefig('./plots/seasonal_contribution.png')
    plt.show()

# Rainfall distribution
def plot_rainfall_distribution(daily_rainfall):
    # Histogram
    plt.figure(figsize=(10, 6))
    sns.histplot(daily_rainfall['Daily_Rainfall_mm'], bins=20, kde=True, color='skyblue')
    plt.title('Rainfall Distribution')
    plt.xlabel('Rainfall (mm)')
    plt.ylabel('Frequency')
    plt.tight_layout()
    plt.savefig('./plots/rainfall_distribution.png')
    plt.show()

    # Boxplot for outliers
    plt.figure(figsize=(6, 4))
    sns.boxplot(y='Daily_Rainfall_mm', data=daily_rainfall, color='lightgreen')
    plt.title('Rainfall Outliers')
    plt.tight_layout()
    plt.savefig('./plots/rainfall_boxplot.png')
    plt.show()

# Efficiency simulation
def efficiency_simulation(rooftop_data, daily_rainfall):
    results = {}
    coefficients = [0.9, 0.8, 0.7, 0.6]
    for coeff in coefficients:
        total_rainfall = daily_rainfall['Daily_Rainfall_mm'].sum()
        results[f'Coefficient {coeff}'] = rooftop_data['Rooftop Area (m²)'].sum() * total_rainfall * coeff / 1000

    # Plot efficiency results
    plt.figure(figsize=(8, 5))
    sns.barplot(x=list(results.keys()), y=list(results.values()), palette='viridis')
    plt.title('Rainwater Collection Efficiency at Different Coefficients')
    plt.xlabel('Runoff Coefficient')
    plt.ylabel('Total Collection (L)')
    plt.tight_layout()
    plt.savefig('./plots/efficiency_simulation.png')
    plt.show()

# Top buildings by collection potential
def plot_top_buildings(rooftop_data, top_n=10):
    top_buildings = rooftop_data.nlargest(top_n, 'Total_Collection_L')

    plt.figure(figsize=(12, 6))
    sns.barplot(x='Building ID', y='Total_Collection_L', data=top_buildings, palette='Greens_d')
    plt.title(f'Top {top_n} Buildings by Collection Potential')
    plt.xlabel('Building ID')
    plt.ylabel('Total Collection (L)')
    plt.tight_layout()
    plt.savefig('./plots/top_buildings.png')
    plt.show()

# Cumulative rainfall trend
def plot_cumulative_rainfall(daily_rainfall):
    daily_rainfall['Cumulative_Rainfall_mm'] = daily_rainfall['Daily_Rainfall_mm'].cumsum()

    plt.figure(figsize=(12, 6))
    plt.plot(daily_rainfall['Date'], daily_rainfall['Cumulative_Rainfall_mm'], color='blue')
    plt.title('Cumulative Rainfall Over Time')
    plt.xlabel('Date')
    plt.ylabel('Cumulative Rainfall (mm)')
    plt.grid()
    plt.tight_layout()
    plt.savefig('./plots/cumulative_rainfall.png')
    plt.show()

# Main function
def main():
    rooftop_data, rainfall_data = load_data()
    rooftop_data, daily_rainfall = calculate_water_collection(rooftop_data, rainfall_data)

    # Save intermediate results
    rooftop_data.to_csv('./rainwater_potential.csv', index=False)
    daily_rainfall.to_csv('./daily_rainfall.csv', index=False)

    # Perform analyses
    plot_monthly_seasonal_rainfall(daily_rainfall)
    plot_rainfall_distribution(daily_rainfall)
    efficiency_simulation(rooftop_data, daily_rainfall)
    plot_top_buildings(rooftop_data)
    plot_cumulative_rainfall(daily_rainfall)

    print("Analysis completed. Results saved in './plots' and CSV files.")

if __name__ == "__main__":
    main()
