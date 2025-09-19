#!/bin/bash

# Stock Symbols Daily Merger Script
# Downloads NASDAQ, AMEX, and NYSE ticker data and merges into symbols.csv

set -e  # Exit on any error

# Define URLs (convert GitHub URLs to raw URLs)
NASDAQ_URL="https://raw.githubusercontent.com/rreichel3/US-Stock-Symbols/main/nasdaq/nasdaq_full_tickers.json"
AMEX_URL="https://raw.githubusercontent.com/rreichel3/US-Stock-Symbols/main/amex/amex_full_tickers.json"
NYSE_URL="https://raw.githubusercontent.com/rreichel3/US-Stock-Symbols/main/nyse/nyse_full_tickers.json"

# Define temporary files
TEMP_DIR=$(mktemp -d)
NASDAQ_FILE="$TEMP_DIR/nasdaq.json"
AMEX_FILE="$TEMP_DIR/amex.json"
NYSE_FILE="$TEMP_DIR/nyse.json"
OUTPUT_FILE="symbols.csv"

# Function to cleanup temporary files
cleanup() {
    rm -rf "$TEMP_DIR"
}
trap cleanup EXIT

# Function to download file with retry
download_file() {
    local url=$1
    local output=$2
    local max_retries=3
    local retry=0
    
    while [ $retry -lt $max_retries ]; do
        echo "Downloading $url (attempt $((retry + 1))/$max_retries)..."
        if curl -s -L "$url" -o "$output"; then
            echo "Successfully downloaded $output"
            return 0
        else
            echo "Failed to download $url"
            retry=$((retry + 1))
            sleep 2
        fi
    done
    
    echo "Error: Failed to download $url after $max_retries attempts"
    return 1
}

# Function to convert JSON to CSV format
json_to_csv() {
    local json_file=$1
    local exchange=$2
    
    # Check if jq is available
    if ! command -v jq &> /dev/null; then
        echo "Error: jq is required but not installed. Please install jq."
        exit 1
    fi
    
    # Convert JSON array to CSV format
    # Assumes JSON structure like: [{"symbol": "AAPL", "name": "Apple Inc."}, ...]
    jq -r --arg exchange "$exchange" '
        .[] | 
        [.symbol // .ticker // .Symbol // .Ticker, 
         .name // .companyName // .Name // .company_name // "N/A", 
         $exchange] | 
        @csv
    ' "$json_file"
}

echo "Starting stock symbols merge process..."

# Download all files
download_file "$NASDAQ_URL" "$NASDAQ_FILE"
download_file "$AMEX_URL" "$AMEX_FILE"
download_file "$NYSE_URL" "$NYSE_FILE"

# Check if files were downloaded successfully
for file in "$NASDAQ_FILE" "$AMEX_FILE" "$NYSE_FILE"; do
    if [ ! -s "$file" ]; then
        echo "Error: $file is empty or was not downloaded properly"
        exit 1
    fi
done

echo "All files downloaded successfully. Converting to CSV format..."

# Create CSV header
echo "ticker,company_name,exchange" > "$OUTPUT_FILE"

# Convert each JSON file to CSV and append to output
echo "Processing NASDAQ data..."
json_to_csv "$NASDAQ_FILE" "NASDAQ" >> "$OUTPUT_FILE"

echo "Processing AMEX data..."
json_to_csv "$AMEX_FILE" "AMEX" >> "$OUTPUT_FILE"

echo "Processing NYSE data..."
json_to_csv "$NYSE_FILE" "NYSE" >> "$OUTPUT_FILE"

# Get counts for summary
nasdaq_count=$(json_to_csv "$NASDAQ_FILE" "NASDAQ" | wc -l)
amex_count=$(json_to_csv "$AMEX_FILE" "AMEX" | wc -l)
nyse_count=$(json_to_csv "$NYSE_FILE" "NYSE" | wc -l)
total_count=$((nasdaq_count + amex_count + nyse_count))

echo "Merge completed successfully!"
echo "Summary:"
echo "  NASDAQ symbols: $nasdaq_count"
echo "  AMEX symbols: $amex_count"
echo "  NYSE symbols: $nyse_count"
echo "  Total symbols: $total_count"
echo "  Output file: $OUTPUT_FILE"

# Display first few lines as preview
echo ""
echo "Preview of merged data:"
head -10 "$OUTPUT_FILE"

echo ""
echo "File saved as: $OUTPUT_FILE"
