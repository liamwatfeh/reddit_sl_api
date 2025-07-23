#!/bin/bash

echo "🧪 Testing /analyze-subreddit endpoint with enhanced modern_comment_analyzer..."

curl -X POST "http://localhost:8000/analyze-subreddit" \
-H "Content-Type: application/json" \
-H "X-API-Key: z12PLfCDJlbNDgAKi4uolswQVzeJWmmZQYjEsoQ857g" \
-d '{
  "subreddit": "BuyItForLife",
  "sort": "top",
  "time": "month",
  "limit": 1,
  "model": "gpt-4.1-2025-04-14",
  "system_prompt": "Find comments about durable products people recommend buying",
  "output_format": "json",
  "max_quote_length": 300
}' | jq '.' 