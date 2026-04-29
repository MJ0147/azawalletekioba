# Wallet Dashboard with Forecast Service Integration

## Overview
The wallet dashboard now integrates the forecast service to display real-time market charts and predictions for stocks, crypto, sentiment analysis, and cloud metrics alongside wallet information.

## Changes Made

### 1. Frontend Component Updates

#### **WalletView.tsx** (`frontend/components/WalletView.tsx`)
- Enhanced React component with forecast data integration
- Added fetching of forecast data from `/api/dashboard/forecast` endpoint
- Displays 4 interactive charts using Chart.js:
  - **Stock Forecast Chart**: Shows actual vs predicted stock prices (AAPL)
  - **Crypto Forecast Chart**: Shows actual vs predicted crypto prices (BTC)
  - **Market Sentiment**: Bar chart showing sentiment score (0-100)
  - **Cloud Metrics**: CPU usage metrics from cloud providers
- Auto-refreshes data every 60 seconds
- Shows loading states and error handling
- Displays latest prediction values in highlighted boxes
- Responsive grid layout for different screen sizes

#### **package.json** (`frontend/package.json`)
Added dependencies:
- `chart.js@^4.4.0` - Charting library
- `react-chartjs-2@^5.2.0` - React wrapper for Chart.js

### 2. Backend Endpoint Updates

#### **app.py** (`frontend/app.py`)
Added/Enhanced endpoints:

1. **GET `/wallet-dashboard`** (HTML Response)
   - Renders the wallet dashboard HTML template
   - Passes forecast data and wallet configuration
   - Returns formatted HTML page

2. **GET `/api/wallet/dashboard`** (JSON Response)
   - Returns wallet info and forecast data as JSON
   - Includes Solana and TON wallet addresses
   - Includes UTC timestamp
   - Structure:
   ```json
   {
     "wallet": {
       "chains": ["solana", "ton"],
       "solana_wallet": "...",
       "ton_wallet": "..."
     },
     "forecast": {
       "stocks": {...},
       "crypto": {...},
       "sentiment": {...},
       "cloud": {...}
     },
     "timestamp": "2026-04-24T..."
   }
   ```

3. **GET `/api/dashboard/forecast`** (JSON Response)
   - Returns raw forecast data
   - Used by React component to fetch chart data

### 3. HTML Template

#### **wallet_dashboard.html** (`frontend/templates/wallet_dashboard.html`)
- Responsive HTML dashboard with integrated Chart.js visualizations
- Features:
  - Wallet information display (Solana & TON addresses)
  - 4 interactive charts with predictions
  - Prediction boxes highlighting next predicted values
  - Auto-refresh every 60 seconds
  - Responsive grid layout (mobile-friendly)
  - Modern styling with Tailwind-like CSS
  - Real-time timestamp updates

## How It Works

### Data Flow
1. **Frontend Component** (WalletView.tsx)
   - On mount, fetches `/api/dashboard/forecast`
   - Processes forecast data into chart datasets
   - Displays charts using Chart.js
   - Auto-refreshes data every 60 seconds

2. **Backend Forecast Service** (agent.py)
   - Fetches stock data from Yahoo Finance
   - Fetches crypto data from Binance API
   - Fetches sentiment data from SoSoValue API
   - Fetches cloud metrics from Azure/DigitalOcean
   - Generates predictions using trend analysis
   - Provides fallback data if any service is unavailable

3. **Endpoint Routes**
   - `/wallet-dashboard` → HTML dashboard view
   - `/api/wallet/dashboard` → Wallet + Forecast JSON
   - `/api/dashboard/forecast` → Forecast data only

## Environment Variables Used

```bash
# Wallet Configuration
SOLANA_MERCHANT_WALLET=<solana-wallet-address>
TON_MERCHANT_WALLET=<ton-wallet-address>

# Forecast Data Sources
AGENT_STOCK_SYMBOL=AAPL          # Stock symbol (default: AAPL)
AGENT_CRYPTO_SYMBOL=BTCUSDT      # Crypto symbol (default: BTCUSDT)
DASHBOARD_STOCK_SYMBOL=AAPL      # Alternative config
DASHBOARD_CRYPTO_SYMBOL=BTCUSDT  # Alternative config

# Cloud Provider Metrics
CLOUD_PROVIDER=azure             # azure, digitalocean, or auto
AZURE_ACCESS_TOKEN=<token>
AZURE_VM_RESOURCE_ID=<resource-id>
DO_TOKEN=<digitalocean-token>
DO_DROPLET_ID=<droplet-id>
```

## Forecast Data Structure

```python
{
  "stocks": {
    "labels": ["2026-04-24 10:00", "2026-04-24 11:00", ...],
    "actual": [145.23, 146.50, ...],
    "predicted": [146.00, 147.20, ...]
  },
  "crypto": {
    "labels": ["2026-04-24 10:00", "2026-04-24 11:00", ...],
    "actual": [32000, 32200, ...],
    "predicted": [32300, 32400, ...]
  },
  "sentiment": {
    "labels": ["Sentiment"],
    "values": [65]  # 0-100 score
  },
  "cloud": {
    "labels": ["2026-04-24 10:00", ...],
    "values": [45.2, 48.1, ...]  # CPU % usage
  }
}
```

## Features

✅ **Real-time Data**: Auto-refreshes forecast every 60 seconds
✅ **Multiple Data Sources**: Stocks, crypto, sentiment, and cloud metrics
✅ **Predictions**: Displays predicted future values alongside actual data
✅ **Interactive Charts**: Line charts for trends, bar chart for sentiment
✅ **Error Handling**: Graceful fallbacks if data sources unavailable
✅ **Responsive Design**: Works on desktop, tablet, and mobile
✅ **Wallet Integration**: Displays configured Solana and TON wallets
✅ **Multiple Access Methods**: HTML page + JSON API for flexibility

## API Endpoints

| Endpoint | Method | Response | Purpose |
|----------|--------|----------|---------|
| `/wallet-dashboard` | GET | HTML | Wallet dashboard page with embedded charts |
| `/api/wallet/dashboard` | GET | JSON | Wallet info + forecast data |
| `/api/dashboard/forecast` | GET | JSON | Forecast data only |
| `/dashboard` | GET | HTML | Alternative dashboard view |

## Installation

1. Install dependencies:
```bash
cd frontend
npm install
```

2. Set environment variables:
```bash
export SOLANA_MERCHANT_WALLET=your_wallet_address
export TON_MERCHANT_WALLET=your_ton_wallet
export AI_ASSISTANT_URL=http://localhost:8005
```

3. Run the frontend:
```bash
npm run dev      # Development
npm run build    # Production build
npm start        # Production server
```

## Usage

### HTML Dashboard
- Navigate to `/wallet-dashboard` in browser
- View real-time wallet info and forecast charts
- Charts auto-refresh every 60 seconds

### React Component
- Import `WalletView` component
- Component automatically fetches and displays forecast data
- Embedded in any React application

### JSON API
- Use `/api/wallet/dashboard` for programmatic access
- Perfect for mobile apps or external dashboards
- Returns structured JSON with all forecast data

## Testing

To test the endpoints:

```bash
# Get wallet dashboard JSON
curl http://localhost:3000/api/wallet/dashboard

# Get forecast data
curl http://localhost:3000/api/dashboard/forecast

# View HTML dashboard
curl http://localhost:3000/wallet-dashboard
```

## Performance Considerations

- Forecast data is computed on-demand (not cached)
- Each API call fetches fresh data from external services
- Fallback data provided if any service is unavailable
- Client-side caching: React component refreshes every 60 seconds
- Chart.js handles efficient rendering of multiple datasets

## Browser Compatibility

- Modern browsers (Chrome, Firefox, Safari, Edge)
- Chart.js 4.4.0+
- React 18.3.1+
- Requires JavaScript enabled

## Future Enhancements

- [ ] Add historical trend data (7-day, 30-day views)
- [ ] Implement WebSocket for real-time updates
- [ ] Add more prediction models (ARIMA, ML-based)
- [ ] Store historical forecast accuracy
- [ ] Add user preferences for displayed metrics
- [ ] Implement alerts for price predictions
- [ ] Add export to CSV functionality
