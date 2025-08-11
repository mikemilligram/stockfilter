import os
import json
from flask import Flask, render_template, request, jsonify, send_file
from flask_pymongo import PyMongo
from dotenv import load_dotenv
from io import StringIO
import csv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configure MongoDB
db_name = os.getenv("MONGO_DB", "stockfinder")
mongo_host = os.getenv("MONGO_HOST", "")
mongo_port = os.getenv("MONGO_PORT", "27017")
mongo_user = os.getenv("MONGO_USER", "")
mongo_password = os.getenv("MONGO_PASSWORD", "")

# Build MongoDB URI
if mongo_user and mongo_password:
    mongo_uri = f"mongodb://{mongo_user}:{mongo_password}@{mongo_host}:{mongo_port}"
else:
    mongo_uri = f"mongodb://{mongo_host}:{mongo_port}"

# Ensure the URI includes the database name
if not mongo_uri.endswith('/'):
    mongo_uri += '/'
if not mongo_uri.endswith(f'/{db_name}'):
    mongo_uri += db_name

app.config["MONGO_URI"] = mongo_uri
print(f"Connecting to MongoDB at {mongo_host}:{mongo_port}")  # For debugging without exposing credentials

try:
    mongo = PyMongo(app)
    # Test the connection
    collections = mongo.db.list_collection_names()
    print(f"Successfully connected to MongoDB. Available collections: {collections}")
except Exception as e:
    print(f"Error connecting to MongoDB: {e}")
    print("Please check your MongoDB server is running and your MONGO_URI is correct")
    raise

# Load field mappings
with open('config/field_mapping.json', 'r') as f:
    FIELD_MAPPINGS = json.load(f)['mappings']

def get_nested_value(obj, path):
    """Get a value from a nested dictionary using dot notation path."""
    current = obj
    for part in path.split('.'):
        if isinstance(current, dict):
            if part in current:
                current = current[part]
            else:
                return None
        else:
            return None
    return current

def build_initial_query(criteria):
    """Build initial MongoDB query for fundamentals collection."""
    query = {}
    
    # Handle revenue criteria (mandatory minimum)
    if not (criteria.get('revenue', {}).get('min')):
        raise ValueError("Minimum revenue is required")
        
    revenue_field = FIELD_MAPPINGS['revenue']['mongodb_field']
    revenue_query = {'$gte': float(criteria['revenue']['min'])}
    if criteria['revenue'].get('max'):
        revenue_query['$lte'] = float(criteria['revenue']['max'])
    query[revenue_field] = revenue_query
    
    # Handle ROE criteria (percentage)
    if criteria.get('roe', {}).get('min'):
        roe_field = FIELD_MAPPINGS['return_on_equity']['mongodb_field']
        min_roe = convert_percentage_to_decimal(criteria['roe']['min'])
        query[roe_field] = {'$gte': min_roe}
    
    return query

def merge_fundamentals_and_historicals(fundamentals: list) -> list:
    for fund in fundamentals:
        symbol = f"{fund['General']['Code']}.{fund['General']['Code']}"
        symbol2 = fund['General']['PrimaryTicker']
        historicals = mongo.db.historicals.find_one({'Symbol': symbol})
        if historicals:
            fund['EOD'] = historicals.get('EOD')
            continue
        historicals = mongo.db.historicals.find_one({'Symbol': symbol2})
        if historicals:
            fund['EOD'] = historicals.get('EOD')
    
    return fundamentals

def filter_results(results, criteria):
    """Apply additional filtering criteria to the results."""
    filtered_results = []

    # Get revenue growth criteria
    revenue_growth = criteria.get('revenueGrowth', {})
    revenue_growth_min = revenue_growth.get('min')
    revenue_growth_years = revenue_growth.get('years')

    # Get earnings growth criteria
    earnings_growth = criteria.get('earningsGrowth', {})
    earnings_growth_min = earnings_growth.get('min')
    earnings_growth_years = earnings_growth.get('years')

    # Convert growth requirements to decimals
    min_revenue_growth = convert_percentage_to_decimal(revenue_growth_min) if revenue_growth_min is not None else None
    min_earnings_growth = convert_percentage_to_decimal(earnings_growth_min) if earnings_growth_min is not None else None

    for result in results:
        include_result = True
        financials = get_nested_value(result, FIELD_MAPPINGS['financials']['mongodb_field'])

        # Calculate and attach revenue growth if criteria provided
        if revenue_growth_years is not None:
            revenue_growth_value = calculate_growth(financials, 'totalRevenue', revenue_growth_years)
            result['revenue_growth'] = revenue_growth_value
            if min_revenue_growth is not None:
                if revenue_growth_value is None or revenue_growth_value < min_revenue_growth:
                    include_result = False
                    continue
        else:
            result['revenue_growth'] = None

        # Calculate and attach earnings growth if criteria provided
        if earnings_growth_years is not None:
            earnings_growth_value = calculate_growth(financials, 'ebit', earnings_growth_years)
            result['earnings_growth'] = earnings_growth_value
            if min_earnings_growth is not None:
                if earnings_growth_value is None or earnings_growth_value < min_earnings_growth:
                    include_result = False
                    continue
        else:
            result['earnings_growth'] = None

        if include_result:
            filtered_results.append(result)

    return filtered_results

def transform_result(result, criteria):
    """Transform MongoDB result to application format using field mappings."""
    transformed = {}
    
    fields = ['name', 'isin', 'code', 'exchange', 'country', 'revenue', 'return_on_equity', 'currency_symbol']
    
    for field in fields:
        if field in FIELD_MAPPINGS:
            value = get_nested_value(result, FIELD_MAPPINGS[field]['mongodb_field'])
            transformed[field] = value

    # Add revenue_growth and earnings_growth as percentages rounded to 1 decimal
    def pct(val):
        return f"{round(val * 100, 1)}%" if val is not None else None
    transformed['revenue_growth'] = pct(result.get('revenue_growth'))
    transformed['earnings_growth'] = pct(result.get('earnings_growth'))
    
    # Add share price information
    years = criteria.get('revenueGrowth', {}).get('years') #TODO either use same value for entire form or add dedicated form field for share prices
    eod = result.get('EOD')
    
    # Get most recent share price (max $years)
    if eod and isinstance(eod, dict):
        # Find the most recent date
        most_recent_date = max(eod.keys())
        most_recent_price = eod[most_recent_date].get('close') if isinstance(eod[most_recent_date], dict) else None
        transformed['recent_share_price'] = most_recent_price
        transformed['recent_share_price_date'] = most_recent_date
    else:
        transformed['recent_share_price'] = None
        transformed['recent_share_price_date'] = None

    # Get oldest share price (max $years ago)
    if eod and isinstance(eod, dict):
        dates = sorted(eod.keys())  # Sort dates in ascending order
        oldest_price = None
        oldest_date = None
        
        if dates:
            most_recent_year = int(dates[-1][:4])
            target_year = most_recent_year - years if years else most_recent_year
            
            for date in dates:
                year = int(date[:4])
                if year >= target_year:
                    oldest_price = eod[date].get('close') if isinstance(eod[date], dict) else None
                    oldest_date = date
                    break
                    
        transformed['oldest_share_price'] = oldest_price
        transformed['oldest_share_price_date'] = oldest_date
    else:
        transformed['oldest_share_price'] = None
        transformed['oldest_share_price_date'] = None
        
    # Calculate share price increase
    if transformed['recent_share_price'] and transformed['oldest_share_price']:
        try:
            years_between = int(transformed['recent_share_price_date'][:4]) - int(transformed['oldest_share_price_date'][:4])
            if years_between > 0:
                total_growth = ((transformed['recent_share_price'] - transformed['oldest_share_price']) / transformed['oldest_share_price']) * 100
                transformed['share_price_growth'] = f"{round(total_growth, 1)}%"
            else:
                transformed['share_price_growth'] = None
        except:
            transformed['share_price_growth'] = None
    else:
        transformed['share_price_growth'] = None
        
    # Calculate share price growth per annum if share price data is available
    if transformed['recent_share_price'] and transformed['oldest_share_price']:
        try:
            years_between = float(transformed['recent_share_price_date'][:4]) - float(transformed['oldest_share_price_date'][:4])
            if years_between > 0:
                growth_per_annum = get_growth_rate(transformed['oldest_share_price'], transformed['recent_share_price'], years_between) * 100
                transformed['share_price_growth_pa'] = f"{round(growth_per_annum, 1)}%"
            else:
                transformed['share_price_growth_pa'] = None
        except:
            transformed['share_price_growth_pa'] = None
    else:
        transformed['share_price_growth_pa'] = None
    
    return transformed

def convert_percentage_to_decimal(value):
    """Convert a percentage value to its decimal representation."""
    if value is None:
        return None
    return float(value) / 100.0

def get_growth_rate(initial_value, final_value, years):
    """Calculate compound annual growth rate."""
    if initial_value <= 0 or final_value <= 0:
        return float('-inf')
    try:
        return (final_value / initial_value) ** (1.0 / years) - 1
    except:
        return float('-inf')

def get_value_for_year(financials, field):
    """
    Get the value for a specific field from the financials data for a given year.
    Converts string values to float.
    """
    if not financials:
        return None
    value = financials.get(field, None)
    if value is None:
        return None
    try:
        # Remove any commas and convert to float
        return float(str(value).replace(',', ''))
    except (ValueError, TypeError):
        print(f"Warning: Could not convert value '{value}' to float")
        return None

def calculate_growth(financials_data, field, years_back):
    """
    Calculate growth rate using the most recent data point and comparing it with data from years_back ago.
    financials_data is a dict mapping dates (YYYY-MM-DD) to financial data.
    """
    if not financials_data:
        return None

    # Sort dates in descending order (newest first)
    dates = sorted(financials_data.keys(), reverse=True)
    if len(dates) < 2:
        return None

    # Get the most recent year and the comparison year
    most_recent_year = int(dates[0][:4])
    target_year = most_recent_year - years_back

    # Find the actual dates we'll use
    recent_date = None
    old_date = None

    for date in dates:
        year = int(date[:4])
        if not recent_date and year == most_recent_year:
            recent_date = date
        if not old_date and year == target_year:
            old_date = date
        if recent_date and old_date:
            break

    if not (recent_date and old_date):
        return None

    recent_value = get_value_for_year(financials_data[recent_date], field)
    old_value = get_value_for_year(financials_data[old_date], field)

    if recent_value is None or old_value is None:
        return None

    return get_growth_rate(old_value, recent_value, years_back)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    try:
        criteria = request.json
        
        # Build initial MongoDB query for fundamentals collection
        try:
            initial_query = build_initial_query(criteria)
        except ValueError as e:
            return jsonify({"success": False, "error": str(e)}), 400
            
        try:
            # Ensure the fundamentals collection exists
            if 'fundamentals' not in mongo.db.list_collection_names():
                return jsonify({
                    "success": False, 
                    "error": "The fundamentals collection does not exist in the database"
                }), 500
                
            print(f"Fetching fundamentals from db...")
            # Execute query on fundamentals collection
            fundamentals = list(mongo.db.fundamentals.find(initial_query))
            
            # Apply additional filtering criteria
            print(f"Filtering based on criteria...")
            filtered_results = filter_results(fundamentals, criteria)
            
            print(f"Merge with historical EOD data...")
            merged_fundamentals = merge_fundamentals_and_historicals(filtered_results)
            
            # Transform results using field mappings
            print(f"Transform for output...")
            transformed_results = [transform_result(result, criteria) for result in merged_fundamentals]
            
            print(f"Complete.")
                
            return jsonify({
                "success": True, 
                "data": transformed_results,
                "fieldOrder": ['name', 'isin', 'code', 'exchange', 'country', 'revenue', 'return_on_equity', 'revenue_growth', 'earnings_growth', 'oldest_share_price_date', 'recent_share_price_date', 'oldest_share_price', 'recent_share_price', 'share_price_growth', 'share_price_growth_pa']
            })
        except Exception as e:
            return jsonify({
                "success": False, 
                "error": f"Database error: {str(e)}"
            }), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/export', methods=['POST'])
def export():
    try:
        results = request.json.get('data', [])
        field_order = request.json.get('fieldOrder')
        if not results:
            return jsonify({"success": False, "error": "No data to export"}), 400

        # Use fieldOrder if provided, else use keys from first result
        if field_order:
            fieldnames = field_order
        else:
            fieldnames = list(results[0].keys())

        # Create CSV in memory
        si = StringIO()
        writer = csv.DictWriter(si, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

        # Create response
        output = si.getvalue()
        si.close()

        return jsonify({
            "success": True,
            "csv": output
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
