#!/bin/bash

echo "🧪 Testing /analyze-search endpoint with enhanced modern_comment_analyzer..."

curl -X POST "http://localhost:8000/analyze-search" \
-H "Content-Type: application/json" \
-H "X-API-Key: z12PLfCDJlbNDgAKi4uolswQVzeJWmmZQYjEsoQ857g" \
-d '{
  "query": "durable backpack recommendations",
  "sort": "relevance",
  "time": "month",
  "limit":1,
  "nsfw": false,
  "model": "gpt-4.1-2025-04-14",
  "system_prompt": "Find comments about durable products people recommend buying",
  "output_format": "json",
  "max_quote_length": 300
}' | jq '.' 