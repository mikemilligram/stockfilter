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

def transform_result(result):
    """Transform MongoDB result to application format using field mappings."""
    transformed = {}
    
    fields = ['name', 'code', 'exchange', 'country', 'revenue', 'return_on_equity', 'currency_symbol']
    
    for field in fields:
        if field in FIELD_MAPPINGS:
            value = get_nested_value(result, FIELD_MAPPINGS[field]['mongodb_field'])
            transformed[field] = value

    # Add revenue_growth and earnings_growth as percentages rounded to 1 decimal
    def pct(val):
        return f"{round(val * 100, 1)}%" if val is not None else None
    transformed['revenue_growth'] = pct(result.get('revenue_growth'))
    transformed['earnings_growth'] = pct(result.get('earnings_growth'))
    
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
                
            # Execute query on fundamentals collection
            fundamentals = list(mongo.db.fundamentals.find(initial_query))
            
            # Apply additional filtering criteria
            filtered_results = filter_results(fundamentals, criteria)
            
            # Transform results using field mappings
            transformed_results = [transform_result(result) for result in filtered_results]
                
            return jsonify({
                "success": True, 
                "data": transformed_results,
                "fieldOrder": ['name', 'code', 'exchange', 'country', 'revenue', 'return_on_equity', 'revenue_growth', 'earnings_growth']
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
