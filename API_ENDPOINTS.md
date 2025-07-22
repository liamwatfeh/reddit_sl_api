# Reddit Comment Analysis API - Endpoint Documentation

This document provides the complete curl request structures for all endpoints in the Reddit Comment Analysis API with background job queue system.

## 🔥 **BACKGROUND JOB ENDPOINTS** (New Async System)

### **1. Submit Subreddit Analysis Job**

```bash
curl -X POST "http://localhost:8000/analyze-subreddit" \
  -H "accept: application/json" \
  -H "X-API-Key: z12PLfCDJlbNDgAKi4uolswQVzeJWmmZQYjEsoQ857g" \
  -H "Content-Type: application/json" \
  -d '{
    "subreddit": "technology",
    "sort": "hot",
    "time": "week",
    "limit": 25,
    "model": "gpt-4.1-2025-04-14",
    "system_prompt": "Analyze the following Reddit comment for sentiment (positive/negative/neutral), main theme, and purchase intent (high/medium/low/none). Focus on technology adoption patterns."
  }'
```

### **2. Submit Search Analysis Job**

```bash
curl -X POST "http://localhost:8000/analyze-search" \
  -H "accept: application/json" \
  -H "X-API-Key: z12PLfCDJlbNDgAKi4uolswQVzeJWmmZQYjEsoQ857g" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "artificial intelligence",
    "sort": "relevance",
    "time": "week",
    "limit": 25,
    "nsfw": false,
    "model": "gpt-4.1-2025-04-14",
    "system_prompt": "CUSTOM: Focus on investment sentiment and financial implications. Identify buy/sell signals and price predictions."
  }'
```

### **3. Check Job Status**

```bash
curl -X GET "http://localhost:8000/jobs/{job_id}/status" \
  -H "accept: application/json" \
  -H "X-API-Key: z12PLfCDJlbNDgAKi4uolswQVzeJWmmZQYjEsoQ857g"
```

### **4. Cancel Running Job**

```bash
curl -X DELETE "http://localhost:8000/jobs/{job_id}" \
  -H "accept: application/json" \
  -H "X-API-Key: z12PLfCDJlbNDgAKi4uolswQVzeJWmmZQYjEsoQ857g"
```

### **5. Get Job Queue Statistics**

```bash
curl -X GET "http://localhost:8000/jobs/queue/stats" \
  -H "accept: application/json" \
  -H "X-API-Key: z12PLfCDJlbNDgAKi4uolswQVzeJWmmZQYjEsoQ857g"
```

## 📊 **UTILITY ENDPOINTS**

### **6. Health Check** (No Auth Required)

```bash
curl -X GET "http://localhost:8000/health" \
  -H "accept: application/json"
```

### **7. API Status & Configuration**

```bash
curl -X GET "http://localhost:8000/status" \
  -H "accept: application/json" \
  -H "X-API-Key: z12PLfCDJlbNDgAKi4uolswQVzeJWmmZQYjEsoQ857g"
```

## 🔧 **LEGACY ENDPOINT** (Synchronous - Not Recommended)

### **8. Legacy Synchronous Analysis** (DEPRECATED)

```bash
curl -X POST "http://localhost:8000/analyze-reddit-comments" \
  -H "accept: application/json" \
  -H "X-API-Key: z12PLfCDJlbNDgAKi4uolswQVzeJWmmZQYjEsoQ857g" \
  -H "Content-Type: application/json" \
  -d '{
    "keywords": ["technology", "AI"],
    "subreddits": ["technology", "artificial"],
    "timeframe": "week",
    "limit": 10,
    "model": "gpt-4.1-2025-04-14",
    "system_prompt": "Analyze for sentiment and themes."
  }'
```

## 🎯 **CONFIGURATION OPTIONS**

### **Subreddit Analysis Parameters:**

- `subreddit`: Target subreddit (no "r/" prefix)
- `sort`: `"hot"`, `"new"`, `"top"`, `"rising"`
- `time`: `"hour"`, `"day"`, `"week"`, `"month"`, `"year"`
- `limit`: 1-100 posts
- `model`: AI model to use
- `system_prompt`: Custom analysis instructions

### **Search Analysis Parameters:**

- `query`: Search terms
- `sort`: `"relevance"`, `"hot"`, `"top"`, `"new"`, `"comments"`
- `time`: `"hour"`, `"day"`, `"week"`, `"month"`, `"year"`, `"all"`
- `limit`: 1-100 posts
- `nsfw`: true/false
- `model`: AI model to use
- `system_prompt`: Custom analysis instructions

## 🔄 **TYPICAL WORKFLOW**

1. **Submit Job**: Use `/analyze-subreddit` or `/analyze-search`
2. **Get Job ID**: API returns job_id and status_url
3. **Poll Status**: Check `/jobs/{job_id}/status` for progress
4. **Retrieve Results**: When status is "completed", results are in the response

## 📋 **RESPONSE EXAMPLES**

### Job Submission Response:

```json
{
  "job_id": "job_6f2b0aaa45a5",
  "status": "pending",
  "message": "Subreddit analysis job for r/technology has been queued for processing",
  "estimated_completion_time": "2025-07-22T15:54:24.426632",
  "status_url": "http://localhost:8000/jobs/job_6f2b0aaa45a5/status",
  "created_at": "2025-07-22T15:51:24.426710"
}
```

### Job Status Response (Completed):

```json
{
  "job_id": "job_6f2b0aaa45a5",
  "status": "completed",
  "created_at": "2025-07-22T15:51:24.426144",
  "started_at": "2025-07-22T15:51:24.428345",
  "completed_at": "2025-07-22T15:51:26.263583",
  "processing_time": 1.835238,
  "progress": 100.0,
  "progress_message": "Analysis completed successfully",
  "result": {
    "comment_analyses": [...],
    "metadata": {...}
  },
  "error": null,
  "error_details": null
}
```

### Queue Statistics Response:

```json
{
  "total_jobs": 2,
  "running_jobs": 0,
  "available_slots": 50,
  "max_concurrent_jobs": 50,
  "status_breakdown": {
    "completed": 1,
    "failed": 1
  },
  "result_ttl_hours": 24.0
}
```

## ✅ **CONFIRMED WORKING FEATURES**

1. **✅ Custom System Prompts**: Fully configurable via `system_prompt` parameter
2. **✅ Background Processing**: Jobs run asynchronously with progress tracking
3. **✅ Real-time Status**: Check progress and get results via status endpoint
4. **✅ Job Management**: Cancel jobs and view queue statistics
5. **✅ Security**: API key authentication on all protected endpoints
6. **✅ Error Handling**: Detailed error responses with debug information

## 🚀 **PRODUCTION READY FEATURES**

- **Async Job Queue**: No more HTTP timeouts on large requests
- **Progress Tracking**: Real-time updates on analysis progress
- **Job Cancellation**: Stop long-running jobs if needed
- **Result Caching**: Results stored for 24 hours after completion
- **Concurrent Processing**: Up to 50 concurrent analysis jobs
- **Automatic Cleanup**: Expired results automatically removed
- **Graceful Shutdown**: Proper cleanup on server restart

---

**Note**: Replace `z12PLfCDJlbNDgAKi4uolswQVzeJWmmZQYjEsoQ857g` with your actual API key and `localhost:8000` with your production server URL.
