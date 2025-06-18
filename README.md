# Stock Filter Web Application

A Flask web application for filtering and analyzing stock data from MongoDB, featuring growth calculations and customizable filters. This application is designed to work with financial data collected by the [stockfinder](https://github.com/mikemilligram/stockfinder) project.

## Prerequisites

This application expects a MongoDB database populated with stock fundamentals data gathered using the stockfinder project.

## Features

- Filter stocks based on multiple criteria:
  - Revenue range
  - Return on Equity (ROE)
  - Revenue growth rate (user-specified period)
  - Earnings growth rate (user-specified period)
- Export results to CSV

## Setup

### Environment Configuration

1. Create a `.env` file from `.env.example`:
```bash
cp .env.example .env
```

2. Configure your MongoDB connection settings in `.env`:
```ini
# MongoDB Connection Settings
MONGO_HOST=localhost
```

See [Environment Variables](#environment-variables) section for all available configuration options.

### Docker Deployment

#### Production
1. Build and start the application:
```bash
docker-compose up --build
```

The application will be available at http://localhost:5000

#### Development
For development with hot-reload and debug features:

1. Build and start using the development compose file:
```bash
docker-compose -f docker-compose.dev.yml up --build
```

Development mode features:
- Code hot-reload (changes reflect immediately)
- Debug logs

The development server will be available at http://localhost:5000

## Configuration

### Environment Variables

| Variable | Purpose | Default Value |
|----------|---------|---------------|
| MONGO_HOST | MongoDB server hostname | None |
| MONGO_PORT | MongoDB server port | 27017 |
| MONGO_DB | MongoDB database name | stockfinder |
| MONGO_USER | MongoDB username for authentication | None |
| MONGO_PASSWORD | MongoDB password for authentication | None |
| FLASK_ENV | Flask environment mode | production |
