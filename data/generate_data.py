import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

# Set random seed for determinism
np.random.seed(42)

# Ensure directory exists
output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)))
os.makedirs(output_dir, exist_ok=True)

# Constants
START_DATE = datetime(2026, 1, 1)
END_DATE = datetime(2026, 8, 18)
REGIONS = ['West', 'East', 'North', 'South']
CHANNELS = ['online', 'retail', 'wholesale']
PRODUCTS = [f'SKU-{i:03d}' for i in range(1, 11)]
SKU_NEW = 'SKU-NEW'
SKU_NEW_START = datetime(2026, 7, 28)

def generate_sales_data():
    date_range = pd.date_range(start=START_DATE, end=END_DATE, freq='D')
    
    records = []
    order_id_counter = 100000
    
    # Base prices for products
    base_prices = {sku: np.random.uniform(20.0, 150.0) for sku in PRODUCTS}
    base_prices[SKU_NEW] = 75.0
    
    for current_date in date_range:
        is_weekend = current_date.weekday() >= 5
        weekend_multiplier = 0.8 if is_weekend else 1.0
        
        # Determine if we are in the West region drop period (Aug 11-17, 2026)
        is_west_drop_week = (datetime(2026, 8, 11) <= current_date <= datetime(2026, 8, 17))
        
        # Base daily transactions per region
        for region in REGIONS:
            # We add a slight random variation to the base number of transactions
            num_transactions = int(np.random.normal(loc=15, scale=3) * weekend_multiplier)
            if num_transactions < 1:
                num_transactions = 1
                
            for _ in range(num_transactions):
                sku = np.random.choice(PRODUCTS)
                channel = np.random.choice(CHANNELS)
                
                # Base values
                base_price = base_prices[sku]
                units = int(np.random.normal(loc=5, scale=2))
                if units < 1: units = 1
                discount = np.random.choice([0.0, 0.05, 0.1])
                
                # Apply West Region Drop (Scenario 1)
                if region == 'West' and is_west_drop_week:
                    base_price = base_price * 0.92  # 8% drop in price
                    units = int(units * 0.85)       # 15% drop in volume
                    if units < 1: units = 1
                    discount = discount + 0.15      # Increase discount significantly to ensure target drop
                
                # Add regular noise
                noise_price = np.random.uniform(0.95, 1.05)
                final_price = round(base_price * noise_price, 2)
                
                records.append({
                    'order_id': f"ORD-{order_id_counter}",
                    'date': current_date.strftime('%Y-%m-%d'),
                    'product_id': sku,
                    'region': region,
                    'units': units,
                    'unit_price': final_price,
                    'discount': round(discount, 2),
                    'channel': channel
                })
                order_id_counter += 1
                
        # Handle SKU-NEW (Scenario 3)
        if current_date >= SKU_NEW_START:
            num_new = np.random.randint(2, 5) # 2-4 tx per day
            for _ in range(num_new):
                records.append({
                    'order_id': f"ORD-{order_id_counter}",
                    'date': current_date.strftime('%Y-%m-%d'),
                    'product_id': SKU_NEW,
                    'region': 'East',
                    'units': int(np.random.normal(loc=3, scale=1)) or 1,
                    'unit_price': round(base_prices[SKU_NEW] * np.random.uniform(0.95, 1.05), 2),
                    'discount': 0.0,
                    'channel': 'online'
                })
                order_id_counter += 1
                
    df = pd.DataFrame(records)
    return df

def generate_marketing_spend():
    weeks = pd.date_range(start=START_DATE, end=END_DATE, freq='W-MON')
    mkt_channels = ['online', 'social', 'email', 'search']
    
    records = []
    for week in weeks:
        is_july = week.month == 7
        for region in REGIONS:
            for channel in mkt_channels:
                base_spend = np.random.uniform(1000, 5000)
                
                # Spike in East social channel around July 2026
                if region == 'East' and channel == 'social' and is_july:
                    base_spend *= 3.5
                    
                spend = round(base_spend, 2)
                impressions = int(spend * np.random.uniform(10, 20))
                clicks = int(impressions * np.random.uniform(0.01, 0.05))
                
                records.append({
                    'week_start': week.strftime('%Y-%m-%d'),
                    'channel': channel,
                    'region': region,
                    'spend': spend,
                    'impressions': impressions,
                    'clicks': clicks
                })
    return pd.DataFrame(records)

def generate_customer_events():
    # Jan 2026 through June 2026 ONLY
    months = pd.date_range(start=START_DATE, end=datetime(2026, 6, 30), freq='MS')
    
    records = []
    
    pii_comments = [
        "john.doe@email.com complained about delivery",
        "Sarah Smith (555-0192) said the product was great",
        "Contact Mike at mike.jones@company.com",
        "Great service",
        "A bit too expensive"
    ]
    
    for month in months:
        for region in REGIONS:
            active = int(np.random.uniform(5000, 10000))
            churn = int(active * np.random.uniform(0.02, 0.05))
            nps = int(np.random.uniform(30, 70))
            
            # Scenario 2: Ambiguous churn movement in East, May-June
            if region == 'East' and month.month in [5, 6]:
                churn = int(active * np.random.uniform(0.06, 0.09)) # Uptick
                nps = nps - 15 # NPS decline (correlating but could be seasonal)
                
            comment = np.random.choice(pii_comments) if np.random.random() > 0.5 else ""
            
            records.append({
                'month': month.strftime('%Y-%m-%d'),
                'region': region,
                'active_customers': active,
                'churned_customers': churn,
                'nps_score': nps,
                'nps_comment': comment
            })
    return pd.DataFrame(records)

def generate_context_notes():
    records = [
        {
            'note_id': 'CN-001',
            'date': '2026-08-12',
            'region': 'West',
            'category': 'competitor_activity',
            'note': "Competitor XYZ launched 20%-off back-to-school promotion across West region stores, running Aug 10-20"
        },
        {
            'note_id': 'CN-002',
            'date': '2026-07-15',
            'region': 'North',
            'category': 'supply_chain',
            'note': "Supply chain delay at major North distribution center impacting fulfillment times."
        },
        {
            'note_id': 'CN-003',
            'date': '2026-06-05',
            'region': 'All',
            'category': 'product_launch',
            'note': "New loyalty program launched globally."
        },
        {
            'note_id': 'CN-004',
            'date': '2026-08-01',
            'region': 'All',
            'category': 'trend',
            'note': "Seasonal back-to-school trend beginning to show in early indicators."
        },
        {
            'note_id': 'CN-005',
            'date': '2026-05-20',
            'region': 'East',
            'category': 'pr',
            'note': "Positive PR mention in major East Coast lifestyle magazine."
        }
    ]
    return pd.DataFrame(records)

def main():
    print("Generating data...")
    df_sales = generate_sales_data()
    df_mkt = generate_marketing_spend()
    df_events = generate_customer_events()
    df_notes = generate_context_notes()
    
    df_sales.to_csv(os.path.join(output_dir, 'sales_transactions.csv'), index=False)
    df_mkt.to_csv(os.path.join(output_dir, 'marketing_spend.csv'), index=False)
    df_events.to_csv(os.path.join(output_dir, 'customer_events.csv'), index=False)
    df_notes.to_csv(os.path.join(output_dir, 'context_notes.csv'), index=False)
    
    print("Files saved successfully.")
    print(f"\nSummary Statistics:")
    print(f"Sales Transactions: {len(df_sales)} rows")
    print(f"Marketing Spend: {len(df_mkt)} rows")
    print(f"Customer Events: {len(df_events)} rows")
    print(f"Context Notes: {len(df_notes)} rows")
    
    # Assertions
    print("\nRunning assertions...")
    
    # Assertion 1: West revenue week of Aug 11 is at least 20% below prior 4-week avg
    df_sales['date'] = pd.to_datetime(df_sales['date'])
    df_sales['revenue'] = df_sales['units'] * df_sales['unit_price'] * (1 - df_sales['discount'])
    
    west_sales = df_sales[df_sales['region'] == 'West'].copy()
    west_sales.set_index('date', inplace=True)
    daily_west_rev = west_sales.resample('D')['revenue'].sum().fillna(0)
    
    # Target week: Aug 11 to Aug 17 (7 days)
    target_start = pd.Timestamp('2026-08-11')
    target_end = pd.Timestamp('2026-08-17')
    target_rev = daily_west_rev.loc[target_start:target_end].sum()
    
    # Prior 4 weeks: July 14 to Aug 10 (28 days)
    prior_start = target_start - pd.Timedelta(days=28)
    prior_end = target_start - pd.Timedelta(days=1)
    prior_rev = daily_west_rev.loc[prior_start:prior_end].sum()
    prior_weekly_avg = prior_rev / 4
    
    drop_pct = (prior_weekly_avg - target_rev) / prior_weekly_avg
    assert drop_pct >= 0.20, f"West revenue drop is only {drop_pct:.1%}, needs to be >= 20%"
    print(f"Assertion 1 passed: West revenue drop is {drop_pct:.1%}")
    
    # Assertion 2: SKU-NEW from July 28 only
    sku_new_dates = df_sales[df_sales['product_id'] == 'SKU-NEW']['date']
    assert sku_new_dates.min() >= pd.Timestamp('2026-07-28'), "SKU-NEW appears before July 28"
    assert len(sku_new_dates.unique()) > 10, "SKU-NEW has too few unique dates"
    print("Assertion 2 passed: SKU-NEW appears correctly")
    
    # Assertion 3: customer_events max month is June 2026
    df_events['month'] = pd.to_datetime(df_events['month'])
    assert df_events['month'].max() == pd.Timestamp('2026-06-01'), "Customer events max month is not June 2026"
    print("Assertion 3 passed: Customer events max month is June 2026")
    
    # Assertion 4: context_notes has CN-001
    assert 'CN-001' in df_notes['note_id'].values, "CN-001 is missing"
    assert "Competitor XYZ launched 20%-off back-to-school" in df_notes[df_notes['note_id'] == 'CN-001']['note'].iloc[0], "CN-001 text mismatch"
    print("Assertion 4 passed: Context notes are correct")
    
if __name__ == '__main__':
    main()
