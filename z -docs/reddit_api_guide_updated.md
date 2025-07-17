# Complete Reddit Comment Analysis API Implementation Guide

## Table of Contents
1. [Project Overview](#project-overview)
2. [System Architecture](#system-architecture)
3. [Data Models and Schemas](#data-models-and-schemas)
4. [Reddit Data Collection Service](#reddit-data-collection-service)
5. [Data Cleaning Pipeline](#data-cleaning-pipeline)
6. [AI Agent Implementation](#ai-agent-implementation)
7. [Result Processing and Combination](#result-processing-and-combination)
8. [FastAPI Implementation](#fastapi-implementation)
9. [Error Handling Strategy](#error-handling-strategy)
10. [Complete Implementation Steps](#complete-implementation-steps)

---

## Project Overview

### Purpose
Build a production-ready Reddit comment analysis API that provides two distinct endpoints for analyzing Reddit discussions about BMW motorcycles (or any topic). The system uses a Reddit scraper service available through RapidAPI to extract meaningful quotes from Reddit comments, analyzes sentiment, identifies themes, and detects purchase intent.

### Key Features
- **Dual Endpoints**: Subreddit browsing vs. search-based analysis
- **Cell-Based Data Processing**: Handles Reddit's complex cell-based response format
- **Intelligent Comment Filtering**: AI agent identifies only relevant comments
- **Scalable Architecture**: Handles pagination and concurrent processing
- **Flexible Configuration**: User-configurable analysis parameters
- **Production Ready**: Comprehensive error handling and logging

### Technology Stack
- **FastAPI**: REST API framework
- **Pydantic AI**: AI agent framework
- **Pydantic**: Data validation and serialization
- **Gemini 2.5 Pro**: Large language model for analysis
- **Reddit Scraper (RapidAPI)**: Reddit data collection service
- **AsyncIO**: Concurrent processing

---

## System Architecture

### Dual Endpoint Design

#### Endpoint 1: `/analyze-subreddit`
- **Purpose**: Analyze posts from a specific subreddit
- **Use Case**: "Get top 50 posts from r/motorcycles this week"
- **API Used**: `subreddit/search`
- **Parameters**: subreddit name, sort method, time filter, post limit

#### Endpoint 2: `/analyze-search`
- **Purpose**: Search and analyze posts across all Reddit
- **Use Case**: "Find 50 posts about 'BMW R12' anywhere on Reddit"
- **API Used**: `posts/search-posts`
- **Parameters**: search query, sort method, time filter, post limit

### Data Flow Architecture

```
User Request → Data Collection → Cell Processing → Comment Extraction → AI Analysis → Result Combination → Response

Phase 1: Data Collection
├── Subreddit Collection (subreddit/search)
└── Search Collection (posts/search-posts)

Phase 2: Dual Format Processing & Extraction
├── Cell-Based Processing (subreddit/search)
│   ├── Filter Ads and Recommendations
│   ├── Parse Cell Structure
│   └── Extract Post Data from Cells
└── Flat Object Processing (posts/search-posts)
    ├── Extract SubredditPost Objects
    ├── Handle Content Formats
    └── Direct Field Mapping

Phase 3: Comment Extraction
├── Comment Tree Fetching (posts/comments)
└── Data Cleaning Pipeline

Phase 4: AI Analysis
├── Concurrent Agent Processing
├── Comment Filtering & Analysis
└── Individual Result Generation

Phase 5: Result Combination
├── Stack All Comment Analyses
├── Generate Metadata
└── Format Final Response
```

### Reddit API Dual Response Architecture

Reddit's API uses **two different response formats** depending on the endpoint:

#### Format 1: Cell-Based Structure (subreddit/search)
Posts are represented as `CellGroup` containing multiple `cells` of different types:
- **MetadataCell**: Author, creation date, subreddit info
- **TitleCell**: Post title
- **ActionCell**: Score, comment count, voting data
- **LegacyVideoCell/ImageCell**: Media content
- **AdMetadataCell**: Advertisement content (filtered out)
- **MarginCell**: UI spacing (ignored)

#### Format 2: Flat Object Structure (posts/search-posts)
Posts are represented as `SubredditPost` objects with direct field access:
- **id**: Post ID (e.g., "t3_1dyxu5j")
- **postTitle**: Post title
- **authorInfo**: Author information object
- **score**: Post score
- **commentCount**: Number of comments
- **content**: Post content with multiple formats (markdown, html, preview)

---

## Data Models and Schemas

### Core Data Models

```python
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime

class CommentAnalysis(BaseModel):
    """Individual comment analysis result"""
    post_id: str
    post_url: str  # URL to original Reddit post for verification
    quote: str  # Comment text (potentially shortened with ellipses)
    sentiment: str  # "positive", "negative", "neutral"
    theme: str  # e.g., "performance", "price", "design", "experience"
    purchase_intent: str  # "high", "medium", "low", "none"
    date: datetime  # Comment creation date
    source: str = "reddit"  # Hardcoded to "reddit"
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class PostWithComments(BaseModel):
    """Post with all its comments after cleaning"""
    post_id: str
    post_title: str
    post_content: str
    post_author: str
    post_score: int
    post_date: datetime
    subreddit: str
    permalink: str
    url: str
    comments: List[Dict[str, Any]]
    
class AnalysisMetadata(BaseModel):
    """Metadata about the analysis process"""
    total_posts_analyzed: int
    total_comments_found: int
    relevant_comments_extracted: int
    irrelevant_posts: int
    analysis_timestamp: datetime
    processing_time_seconds: float
    model_used: str
    api_calls_made: int
    collection_method: str  # "subreddit" or "search"
    cell_parsing_errors: int  # New field for cell parsing issues

class UnifiedAnalysisResponse(BaseModel):
    """Final response returned to user"""
    comment_analyses: List[CommentAnalysis]
    metadata: AnalysisMetadata
```

### Request Schemas

```python
class SubredditAnalysisRequest(BaseModel):
    """Request schema for /analyze-subreddit endpoint"""
    # Subreddit browsing parameters
    subreddit: str  # e.g., "motorcycles", "BMW", "advrider"
    sort: str = "hot"  # "hot", "new", "top", "controversial", "rising"
    time: str = "week"  # "all", "year", "month", "week", "day", "hour"
    limit: int = 50  # Number of posts to analyze
    
    # Model configuration
    model: str = "gemini-2.5-pro"
    api_key: str  # LLM API key
    
    # Analysis configuration
    system_prompt: str = """You are an expert social media analyst specializing in automotive discussions, particularly BMW motorcycles. Your task is to analyze Reddit discussions to identify only the most relevant and insightful comments worth highlighting."""
    
    # Output configuration
    output_format: str = "json"
    max_quote_length: int = 200

class SearchAnalysisRequest(BaseModel):
    """Request schema for /analyze-search endpoint"""
    # Search parameters
    query: str  # Search query, e.g., "BMW R 12 GS"
    sort: str = "relevance"  # "relevance", "hot", "top", "new", "comments"
    time: str = "week"  # "all", "year", "month", "week", "day", "hour"
    limit: int = 50  # Number of posts to analyze
    nsfw: bool = False  # Include NSFW content
    
    # Model configuration
    model: str = "gemini-2.5-pro"
    api_key: str  # LLM API key
    
    # Analysis configuration
    system_prompt: str = """You are an expert social media analyst specializing in automotive discussions, particularly BMW motorcycles. Your task is to analyze Reddit discussions to identify only the most relevant and insightful comments worth highlighting."""
    
    # Output configuration
    output_format: str = "json"
    max_quote_length: int = 200
```

---

## Reddit Data Collection Service

### RapidAPI Reddit Scraper Configuration

This implementation uses a Reddit scraper service through RapidAPI. The API requires specific headers and base URL:

- **Base URL**: `https://reddit-com.p.rapidapi.com`
- **Headers**: `x-rapidapi-key` and `x-rapidapi-host`
- **Endpoints**: `/subreddit/search`, `/posts/search-posts`, `/posts/comments`

### Dual Response Format Handling

The Reddit API uses two different response formats:
- **subreddit/search**: Cell-based structure requiring complex parsing
- **posts/search-posts**: Flat object structure with direct field access

### 4.1: Cell-Based Data Extraction (subreddit/search)

```python
import re
from datetime import datetime
from typing import Dict, Any, List, Optional

def extract_posts_from_reddit_response(api_response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract actual posts from Reddit API cell-based response, filtering out ads and recommendations
    """
    posts = []
    
    for item in api_response.get("data", []):
        # Only process CellGroup items (actual posts)
        if item.get("__typename") != "CellGroup":
            continue
            
        # Skip ads (they have adPayload)
        if item.get("adPayload") is not None:
            continue
            
        # Extract post ID from groupId (format: "t3_postid")
        group_id = item.get("groupId", "")
        if not group_id.startswith("t3_"):
            continue
            
        # Convert cell structure to flat post object
        post_data = extract_post_from_cells(group_id, item.get("cells", []))
        if post_data:
            posts.append(post_data)
    
    return posts

def extract_post_from_cells(group_id: str, cells: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Extract post information from Reddit cell structure
    """
    post_data = {
        "id": group_id.replace("t3_", ""),  # Remove t3_ prefix
        "title": "",
        "selftext": "",
        "author": "",
        "score": 0,
        "num_comments": 0,
        "created_utc": None,
        "permalink": "",
        "url": "",
        "subreddit": "motorcycles"  # Default, will be updated if found
    }
    
    for cell in cells:
        cell_type = cell.get("__typename", "")
        
        if cell_type == "MetadataCell":
            # Extract author and creation date
            author_name = cell.get("authorName", "")
            if author_name.startswith("u/"):
                post_data["author"] = author_name[2:]  # Remove u/ prefix
            
            created_at = cell.get("createdAt")
            if created_at:
                try:
                    # Convert ISO format to Unix timestamp
                    dt = datetime.fromisoformat(created_at.replace("+0000", "+00:00"))
                    post_data["created_utc"] = int(dt.timestamp())
                except Exception as e:
                    print(f"Error parsing date {created_at}: {e}")
                    
        elif cell_type == "TitleCell":
            # Extract post title
            post_data["title"] = cell.get("title", "")
            
        elif cell_type == "ActionCell":
            # Extract score and comment count
            post_data["score"] = cell.get("score", 0)
            post_data["num_comments"] = cell.get("commentCount", 0)
            
        elif cell_type in ["LegacyVideoCell", "ImageCell"]:
            # For media posts, extract subreddit if available
            subreddit_visual = cell.get("subredditVisualName", "")
            if subreddit_visual:
                post_data["subreddit"] = subreddit_visual
    
    # Generate permalink and URL
    if post_data["id"] and post_data["subreddit"]:
        post_data["permalink"] = f"/r/{post_data['subreddit']}/comments/{post_data['id']}/"
        post_data["url"] = f"https://www.reddit.com{post_data['permalink']}"
    
    # Return post only if we have essential data
    return post_data if post_data["title"] and post_data["id"] else None
```

### 4.2: Flat Object Data Extraction (posts/search-posts)

```python
def extract_posts_from_search_response(api_response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract posts from search API flat object response
    """
    posts = []
    
    for item in api_response.get("data", []):
        # Only process SubredditPost items
        if item.get("__typename") != "SubredditPost":
            continue
            
        # Convert SubredditPost to our standard format
        post_data = extract_search_post_data(item)
        if post_data:
            posts.append(post_data)
    
    return posts

def extract_search_post_data(post_item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Extract post information from SubredditPost object
    """
    # Extract post ID (remove t3_ prefix if present)
    post_id = post_item.get("id", "")
    if post_id.startswith("t3_"):
        post_id = post_id[3:]
    
    # Extract content with fallback handling
    content = ""
    content_obj = post_item.get("content")
    if content_obj:
        # Try markdown first, then preview, then html
        content = (content_obj.get("markdown") or 
                  content_obj.get("preview") or 
                  content_obj.get("html", ""))
    
    # Extract author name
    author_info = post_item.get("authorInfo", {})
    author_name = author_info.get("name", "")
    
    # Extract subreddit name
    subreddit_info = post_item.get("subreddit", {})
    subreddit_name = subreddit_info.get("name", "")
    
    # Convert creation date
    created_utc = None
    created_at = post_item.get("createdAt")
    if created_at:
        try:
            dt = datetime.fromisoformat(created_at.replace("+0000", "+00:00"))
            created_utc = int(dt.timestamp())
        except Exception as e:
            print(f"Error parsing date {created_at}: {e}")
    
    post_data = {
        "id": post_id,
        "title": post_item.get("postTitle", ""),
        "selftext": content,
        "author": author_name,
        "score": post_item.get("score", 0),
        "num_comments": post_item.get("commentCount", 0),
        "created_utc": created_utc,
        "permalink": post_item.get("permalink", ""),
        "url": post_item.get("url", ""),
        "subreddit": subreddit_name
    }
    
    # Return post only if we have essential data
    return post_data if post_data["title"] and post_data["id"] else None
```

### Common Utility Functions

```python
import re
from datetime import datetime
from typing import Dict, Any, List, Optional

def extract_posts_from_reddit_response(api_response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract actual posts from Reddit API cell-based response, filtering out ads and recommendations
    """
    posts = []
    
    for item in api_response.get("data", []):
        # Only process CellGroup items (actual posts)
        if item.get("__typename") != "CellGroup":
            continue
            
        # Skip ads (they have adPayload)
        if item.get("adPayload") is not None:
            continue
            
        # Extract post ID from groupId (format: "t3_postid")
        group_id = item.get("groupId", "")
        if not group_id.startswith("t3_"):
            continue
            
        # Convert cell structure to flat post object
        post_data = extract_post_from_cells(group_id, item.get("cells", []))
        if post_data:
            posts.append(post_data)
    
    return posts

def extract_post_from_cells(group_id: str, cells: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Extract post information from Reddit cell structure
    """
    post_data = {
        "id": group_id.replace("t3_", ""),  # Remove t3_ prefix
        "title": "",
        "selftext": "",
        "author": "",
        "score": 0,
        "num_comments": 0,
        "created_utc": None,
        "permalink": "",
        "url": "",
        "subreddit": "motorcycles"  # Default, will be updated if found
    }
    
    for cell in cells:
        cell_type = cell.get("__typename", "")
        
        if cell_type == "MetadataCell":
            # Extract author and creation date
            author_name = cell.get("authorName", "")
            if author_name.startswith("u/"):
                post_data["author"] = author_name[2:]  # Remove u/ prefix
            
            created_at = cell.get("createdAt")
            if created_at:
                try:
                    # Convert ISO format to Unix timestamp
                    dt = datetime.fromisoformat(created_at.replace("+0000", "+00:00"))
                    post_data["created_utc"] = int(dt.timestamp())
                except Exception as e:
                    print(f"Error parsing date {created_at}: {e}")
                    
        elif cell_type == "TitleCell":
            # Extract post title
            post_data["title"] = cell.get("title", "")
            
        elif cell_type == "ActionCell":
            # Extract score and comment count
            post_data["score"] = cell.get("score", 0)
            post_data["num_comments"] = cell.get("commentCount", 0)
            
        elif cell_type in ["LegacyVideoCell", "ImageCell"]:
            # For media posts, extract subreddit if available
            subreddit_visual = cell.get("subredditVisualName", "")
            if subreddit_visual:
                post_data["subreddit"] = subreddit_visual
    
    # Generate permalink and URL
    if post_data["id"] and post_data["subreddit"]:
        post_data["permalink"] = f"/r/{post_data['subreddit']}/comments/{post_data['id']}/"
        post_data["url"] = f"https://www.reddit.com{post_data['permalink']}"
    
    # Return post only if we have essential data
    return post_data if post_data["title"] and post_data["id"] else None

def extract_pagination_token(api_response: Dict[str, Any]) -> Optional[str]:
    """
    Extract pagination token from Reddit API response
    """
    return api_response.get("meta", {}).get("nextPage")

def filter_content_types(api_response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Filter out ads and recommendations from API response
    """
    filtered_data = []
    
    for item in api_response.get("data", []):
        # Keep only CellGroup items without ads
        if (item.get("__typename") == "CellGroup" and 
            item.get("adPayload") is None):
            filtered_data.append(item)
    
    return {
        **api_response,
        "data": filtered_data
    }
```

### Base Data Collector Class

```python
import httpx
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime

class BaseRedditDataCollector:
    """Base class for Reddit data collection via RapidAPI with cell-based processing"""
    
    def __init__(self, rapidapi_key: str):
        self.base_url = "https://reddit-com.p.rapidapi.com"
        self.api_key = rapidapi_key
        self.client = httpx.AsyncClient(
            headers={
                'x-rapidapi-key': rapidapi_key,
                'x-rapidapi-host': 'reddit-com.p.rapidapi.com'
            },
            timeout=30.0
        )
    
    async def fetch_comment_tree(self, post_id: str) -> Dict[str, Any]:
        """Fetch comment tree for a specific post"""
        try:
            response = await self.client.get(
                f"{self.base_url}/posts/comments",
                params={"postId": post_id, "sort": "confidence"}
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching comments for post {post_id}: {e}")
            return {"comments": []}
    
    async def paginate_posts(
        self, 
        initial_response: Dict[str, Any], 
        limit: int, 
        fetch_func,
        extraction_func  # New parameter for extraction method
    ) -> List[Dict[str, Any]]:
        """
        Generic pagination logic for both endpoints with configurable extraction
        """
        all_posts = []
        current_response = initial_response
        
        while len(all_posts) < limit and current_response:
            # Extract posts using the provided extraction function
            posts = extraction_func(current_response)
            
            # Add posts to our collection
            for post in posts:
                if len(all_posts) >= limit:
                    break
                all_posts.append(post)
            
            # Check if we have enough posts or if there's no next page
            if len(all_posts) >= limit:
                break
                
            next_page = extract_pagination_token(current_response)
            if not next_page:
                break
            
            # Fetch next page
            try:
                current_response = await fetch_func(next_page)
                await asyncio.sleep(0.1)  # Rate limiting
            except Exception as e:
                print(f"Error during pagination: {e}")
                break
        
        return all_posts[:limit]
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
```

### Subreddit Data Collector

```python
class SubredditDataCollector(BaseRedditDataCollector):
    """Collects posts from specific subreddits with cell-based processing"""
    
    async def collect_subreddit_posts(
        self, 
        subreddit: str, 
        sort: str = "hot", 
        time: str = "week", 
        limit: int = 50
    ) -> List[PostWithComments]:
        """
        Collect posts from a specific subreddit with pagination and cell processing
        """
        posts_with_comments = []
        cell_parsing_errors = 0
        
        try:
            # Initial API call
            initial_response = await self._fetch_subreddit_page(subreddit, sort, time, None)
            
            # Paginate to get all posts with cell-based extraction
            all_posts = await self.paginate_posts(
                initial_response, 
                limit, 
                lambda next_page: self._fetch_subreddit_page(subreddit, sort, time, next_page),
                extract_posts_from_reddit_response  # Use cell-based extraction
            )
            
            # Fetch comments for each post
            for post in all_posts:
                try:
                    # Clean the post data
                    clean_post = clean_reddit_post_updated(post)
                    
                    # Fetch comment tree
                    comment_tree_response = await self.fetch_comment_tree(clean_post["post_id"])
                    
                    # Clean the comments using updated posts/comments format
                    clean_comments = clean_posts_comments_response(comment_tree_response)
                    
                    # Combine into PostWithComments
                    post_with_comments = PostWithComments(
                        post_id=clean_post["post_id"],
                        post_title=clean_post["post_title"],
                        post_content=clean_post["post_content"],
                        post_author=clean_post["post_author"],
                        post_score=clean_post["post_score"],
                        post_date=clean_post["post_date"],
                        subreddit=clean_post["subreddit"],
                        permalink=clean_post["permalink"],
                        url=clean_post["url"],
                        comments=clean_comments
                    )
                    
                    posts_with_comments.append(post_with_comments)
                    
                except Exception as e:
                    print(f"Error processing post {post.get('id', 'unknown')}: {e}")
                    cell_parsing_errors += 1
                    continue
        
        except Exception as e:
            print(f"Error collecting subreddit posts: {e}")
            raise
        
        return posts_with_comments
    
    async def _fetch_subreddit_page(
        self, 
        subreddit: str, 
        sort: str, 
        time: str, 
        next_page: Optional[str]
    ) -> Dict[str, Any]:
        """Fetch a single page of subreddit posts"""
        params = {
            "query": f"r/{subreddit}",
            "sort": sort,
            "time": time
        }
        
        if next_page:
            params["nextPage"] = next_page
        
        response = await self.client.get(f"{self.base_url}/subreddit/search", params=params)
        response.raise_for_status()
        return response.json()
```

### Search Data Collector

```python
class SearchDataCollector(BaseRedditDataCollector):
    """Collects posts from Reddit search results with flat object processing"""
    
    async def collect_search_posts(
        self, 
        query: str, 
        sort: str = "relevance", 
        time: str = "week", 
        limit: int = 50,
        nsfw: bool = False
    ) -> List[PostWithComments]:
        """
        Collect posts from Reddit search results with pagination and flat object processing
        """
        posts_with_comments = []
        processing_errors = 0
        
        try:
            # Initial API call
            initial_response = await self._fetch_search_page(query, sort, time, nsfw, None)
            
            # Paginate to get all posts with flat object extraction
            all_posts = await self.paginate_posts(
                initial_response, 
                limit, 
                lambda next_page: self._fetch_search_page(query, sort, time, nsfw, next_page),
                extract_posts_from_search_response  # Use flat object extraction
            )
            
            # Fetch comments for each post
            for post in all_posts:
                try:
                    # Clean the post data (uses same cleaner as subreddit posts)
                    clean_post = clean_reddit_post_updated(post)
                    
                    # Fetch comment tree
                    comment_tree_response = await self.fetch_comment_tree(clean_post["post_id"])
                    
                    # Clean the comments using updated posts/comments format
                    clean_comments = clean_posts_comments_response(comment_tree_response)
                    
                    # Combine into PostWithComments
                    post_with_comments = PostWithComments(
                        post_id=clean_post["post_id"],
                        post_title=clean_post["post_title"],
                        post_content=clean_post["post_content"],
                        post_author=clean_post["post_author"],
                        post_score=clean_post["post_score"],
                        post_date=clean_post["post_date"],
                        subreddit=clean_post["subreddit"],
                        permalink=clean_post["permalink"],
                        url=clean_post["url"],
                        comments=clean_comments
                    )
                    
                    posts_with_comments.append(post_with_comments)
                    
                except Exception as e:
                    print(f"Error processing post {post.get('id', 'unknown')}: {e}")
                    processing_errors += 1
                    continue
        
        except Exception as e:
            print(f"Error collecting search posts: {e}")
            raise
        
        return posts_with_comments
    
    async def _fetch_search_page(
        self, 
        query: str, 
        sort: str, 
        time: str, 
        nsfw: bool, 
        next_page: Optional[str]
    ) -> Dict[str, Any]:
        """Fetch a single page of search results"""
        params = {
            "query": query,
            "sort": sort,
            "time": time,
            "nsfw": nsfw
        }
        
        if next_page:
            params["nextPage"] = next_page
        
        response = await self.client.get(f"{self.base_url}/posts/search-posts", params=params)
        response.raise_for_status()
        return response.json()
```

---

## Data Cleaning Pipeline

### Dual Format Processing

The data cleaning pipeline handles two different input formats and converts both to the same standardized `PostWithComments` output:

- **Cell-based input** (from subreddit/search): Requires complex parsing and extraction
- **Flat object input** (from posts/search-posts): Direct field mapping

### 5.1: Cell-Based Post Cleaning

```python
from datetime import datetime
from typing import Dict, Any

def clean_reddit_post_updated(extracted_post: Dict[str, Any]) -> Dict[str, Any]:
    """
    Takes an extracted post object (from cell parsing or flat object) and returns a clean, minimal post schema.
    This function works with both extraction formats since they're normalized to the same structure.
    """
    return {
        "post_id": extracted_post.get("id", ""),
        "post_title": extracted_post.get("title", ""),
        "post_content": extracted_post.get("selftext", ""),
        "post_author": extracted_post.get("author", ""),
        "post_score": extracted_post.get("score", 0),
        "post_date": (
            datetime.utcfromtimestamp(extracted_post["created_utc"])
            if extracted_post.get("created_utc") else
            datetime.utcnow()
        ),
        "subreddit": extracted_post.get("subreddit", ""),
        "permalink": extracted_post.get("permalink", ""),
        "url": extracted_post.get("url", ""),
    }
```

### 5.2: Content Format Handling

```python
def extract_post_content(content_obj: Dict[str, Any]) -> str:
    """
    Extract text content from various Reddit content formats
    """
    if not content_obj:
        return ""
    
    # Priority order: markdown > preview > html > empty
    content_formats = ["markdown", "preview", "html"]
    
    for format_name in content_formats:
        content = content_obj.get(format_name, "")
        if content and content.strip():
            # Clean HTML tags if present
            if format_name == "html":
                import re
                content = re.sub(r'<[^>]+>', '', content)
                content = content.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
            return content.strip()
    
    return ""

def normalize_author_name(author_info: Dict[str, Any]) -> str:
    """
    Extract author name from different author formats
    """
    if not author_info:
        return ""
    
    # Handle both direct name and nested authorInfo structures
    name = author_info.get("name", "")
    if not name and isinstance(author_info, str):
        name = author_info
    
    # Remove u/ prefix if present
    if name.startswith("u/"):
        name = name[2:]
    
    return name if name and name not in ["[deleted]", "[removed]"] else ""
```

### 5.3: Comment Tree Cleaner Implementation

```python
def clean_posts_comments_response(api_response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Takes a posts/comments API response and returns a cleaned, nested comment tree.
    Handles the commentForest.trees structure from the posts/comments endpoint.
    """
    # Extract comment forest from API response
    comment_forest = api_response.get("data", {}).get("commentForest", {})
    trees = comment_forest.get("trees", [])
    
    if not trees:
        return []
    
    # Build a dict of all comments keyed by id
    comments = {}
    for tree in trees:
        # Skip "more comments" placeholders (they have node: null)
        if not tree.get("node"):
            continue
            
        node = tree["node"]
        comment_id = node.get("id")
        
        if not comment_id:
            continue
        
        # Extract comment content with fallback handling
        content = extract_comment_content(node.get("content", {}))
        
        # Extract author name
        author_info = node.get("authorInfo", {})
        author_name = author_info.get("name", "")
        
        # Handle deleted/removed comments
        if node.get("isRemoved") or not content.strip():
            content = "[deleted]"
        
        # Convert creation date
        created_at = node.get("createdAt")
        comment_date = datetime.utcnow()
        if created_at:
            try:
                comment_date = datetime.fromisoformat(created_at.replace("+0000", "+00:00"))
            except Exception:
                pass
                
        comments[comment_id] = {
            "id": comment_id,
            "author": author_name if author_name and author_name not in ["[deleted]", "[removed]"] else "unknown",
            "body": content,
            "score": node.get("score", 0),
            "date": comment_date,
            "depth": tree.get("depth", 0),
            "parentId": tree.get("parentId"),
            "children": []
        }
    
    # Build nested structure by attaching children to parents
    roots = []
    for comment in comments.values():
        parent_id = comment["parentId"]
        if parent_id and parent_id in comments:
            comments[parent_id]["children"].append(comment)
        else:
            roots.append(comment)
    
    return roots

def extract_comment_content(content_obj: Dict[str, Any]) -> str:
    """
    Extract text content from Reddit comment content object
    """
    if not content_obj:
        return ""
    
    # Priority order: markdown > preview > html > empty
    content_formats = ["markdown", "preview", "html"]
    
    for format_name in content_formats:
        content = content_obj.get(format_name, "")
        if content and content.strip():
            # Clean HTML tags if present
            if format_name == "html":
                import re
                content = re.sub(r'<[^>]+>', '', content)
                content = content.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
                content = content.replace('&#39;', "'").replace('&quot;', '"')
            return content.strip()
    
    return ""

def clean_reddit_comment_tree_legacy(raw_comment_trees: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Legacy comment cleaner for backward compatibility.
    Takes a Reddit comment 'forest' and returns a cleaned, nested comment tree.
    """
    if not raw_comment_trees:
        return []
    
    # Build a dict of all comments keyed by id
    comments = {}
    for comment in raw_comment_trees:
        node = comment.get("node", comment)
        comment_id = node.get("id")
        
        if not comment_id:
            continue
            
        comments[comment_id] = {
            "id": comment_id,
            "author": node.get("authorInfo", {}).get("name", "unknown"),
            "body": node.get("content", {}).get("markdown", "") or node.get("body", ""),
            "score": node.get("score", 0),
            "date": (
                datetime.fromisoformat(node["createdAt"])
                if "createdAt" in node and node["createdAt"]
                else datetime.utcnow()
            ),
            "depth": comment.get("depth", 0),
            "parentId": comment.get("parentId"),
            "children": []
        }
    
    # Attach each comment to its parent's 'children'
    roots = []
    for comment in comments.values():
        parent_id = comment["parentId"]
        if parent_id and parent_id in comments:
            comments[parent_id]["children"].append(comment)
        else:
            roots.append(comment)
    
    return roots

def build_post_with_comments(clean_post: Dict[str, Any], clean_comments: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Combine a cleaned post and its comments tree into a single structure.
    """
    post_with_comments = clean_post.copy()
    post_with_comments["comments"] = clean_comments
    return post_with_comments
```

### 5.4: Data Validation and Error Handling

```python
def validate_cell_structure(cells: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Validate that required cells are present and well-formed (for cell-based responses)
    """
    validation_result = {
        "is_valid": True,
        "errors": [],
        "warnings": [],
        "required_cells_found": {
            "MetadataCell": False,
            "TitleCell": False,
            "ActionCell": False
        }
    }
    
    for cell in cells:
        cell_type = cell.get("__typename", "")
        
        if cell_type in validation_result["required_cells_found"]:
            validation_result["required_cells_found"][cell_type] = True
        
        # Validate cell-specific requirements
        if cell_type == "MetadataCell":
            if not cell.get("authorName"):
                validation_result["warnings"].append("MetadataCell missing authorName")
            if not cell.get("createdAt"):
                validation_result["warnings"].append("MetadataCell missing createdAt")
                
        elif cell_type == "TitleCell":
            if not cell.get("title"):
                validation_result["errors"].append("TitleCell missing title")
                validation_result["is_valid"] = False
    
    # Check if all required cells are present
    missing_required = [
        cell_type for cell_type, found in validation_result["required_cells_found"].items()
        if not found
    ]
    
    if missing_required:
        validation_result["errors"].extend([f"Missing required cell: {ct}" for ct in missing_required])
        validation_result["is_valid"] = False
    
    return validation_result

def validate_search_post_structure(post: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate that required fields are present in search post response
    """
    validation_result = {
        "is_valid": True,
        "errors": [],
        "warnings": []
    }
    
    # Check required fields
    required_fields = ["id", "postTitle", "authorInfo", "subreddit"]
    for field in required_fields:
        if not post.get(field):
            validation_result["errors"].append(f"Missing required field: {field}")
            validation_result["is_valid"] = False
    
    # Check nested required fields
    if post.get("authorInfo") and not post["authorInfo"].get("name"):
        validation_result["warnings"].append("Author info missing name")
    
    if post.get("subreddit") and not post["subreddit"].get("name"):
        validation_result["warnings"].append("Subreddit info missing name")
    
    return validation_result

def validate_comment_structure(comment_node: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate that required fields are present in comment node
    """
    validation_result = {
        "is_valid": True,
        "errors": [],
        "warnings": []
    }
    
    # Check required fields
    required_fields = ["id", "content", "authorInfo", "score"]
    for field in required_fields:
        if field not in comment_node:
            validation_result["errors"].append(f"Missing required field: {field}")
            validation_result["is_valid"] = False
    
    # Check nested required fields
    if comment_node.get("content"):
        content = comment_node["content"]
        if not any(content.get(fmt) for fmt in ["markdown", "preview", "html"]):
            validation_result["warnings"].append("Comment content missing text in all formats")
    
    if comment_node.get("authorInfo") and not comment_node["authorInfo"].get("name"):
        validation_result["warnings"].append("Author info missing name")
    
    # Check for removed/deleted content
    if comment_node.get("isRemoved") or comment_node.get("isAdminTakedown"):
        validation_result["warnings"].append("Comment appears to be removed or taken down")
    
    return validation_result
```

---

## AI Agent Implementation

### Comment Filtering Agent

```python
from pydantic_ai import Agent
from typing import List
import asyncio

class CommentFilteringAgent:
    """AI agent that filters and analyzes Reddit comments"""
    
    def __init__(self, model: str, api_key: str, system_prompt: str, max_quote_length: int = 200):
        self.max_quote_length = max_quote_length
        self.agent = Agent(
            model=model,
            result_type=List[CommentAnalysis],
            system_prompt=system_prompt,
            # Configure API key based on model
            api_key=api_key
        )
    
    async def analyze_post_for_comments(self, post_data: PostWithComments) -> List[CommentAnalysis]:
        """
        Analyze a post and its comments to extract relevant comment analyses
        """
        try:
            # Prepare the analysis prompt
            analysis_prompt = self._build_analysis_prompt(post_data)
            
            # Run the agent
            result = await self.agent.run(analysis_prompt)
            
            # Ensure all analyses have correct metadata
            for analysis in result:
                analysis.post_id = post_data.post_id
                analysis.post_url = post_data.url  # Add post URL for verification
                analysis.source = "reddit"
                
                # Truncate quote if too long
                if len(analysis.quote) > self.max_quote_length:
                    analysis.quote = analysis.quote[:self.max_quote_length-3] + "..."
            
            return result
            
        except Exception as e:
            print(f"Error analyzing post {post_data.post_id}: {e}")
            return []  # Return empty list if analysis fails
    
    def _build_analysis_prompt(self, post_data: PostWithComments) -> str:
        """Build the prompt for the AI agent"""
        # Flatten comments for analysis
        comment_text = self._format_comments_for_analysis(post_data.comments)
        
        return f"""
        Analyze this Reddit discussion and extract only the most relevant comments:
        
        POST INFORMATION:
        Title: {post_data.post_title}
        Content: {post_data.post_content}
        Author: {post_data.post_author}
        Score: {post_data.post_score}
        Subreddit: {post_data.subreddit}
        
        COMMENTS ({len(post_data.comments)} total):
        {comment_text}
        
        FILTERING CRITERIA - Only extract comments that:
        1. Contain meaningful insights about the topic
        2. Express clear opinions, experiences, or intentions
        3. Provide context that would be valuable for analysis
        4. Are substantive (not just "lol", "ok", "this", etc.)
        
        QUOTE EXTRACTION:
        - If a comment is longer than {self.max_quote_length} characters, extract the most important parts
        - Use ellipses (...) to indicate omitted text
        - Preserve the core meaning while keeping it concise
        
        OUTPUT REQUIREMENTS:
        - Return a list of CommentAnalysis objects
        - If no comments are worth highlighting, return an empty list
        - Each quote should be substantial and meaningful
        - Sentiment: "positive", "negative", or "neutral"
        - Theme: one of "performance", "price", "design", "experience", "reliability", "comparison", "purchase"
        - Purchase intent: "high", "medium", "low", or "none"
        - Post URL will be automatically added for verification
        
        Remember: Quality over quantity. Better to return 3 excellent quotes than 10 mediocre ones.
        """
    
    def _format_comments_for_analysis(self, comments: List[Dict[str, Any]]) -> str:
        """Format comments for AI analysis"""
        formatted_comments = []
        
        def process_comment(comment: Dict[str, Any], depth: int = 0):
            """Recursively process comments and their children"""
            indent = "  " * depth
            comment_text = comment.get("body", "").strip()
            
            if len(comment_text) > 10 and comment_text.lower() not in ['deleted', '[removed]', '[deleted]']:
                formatted_comments.append(f"""
{indent}Comment (Score: {comment.get('score', 0)}, Author: {comment.get('author', 'unknown')}):
{indent}{comment_text}
{indent}---""")
            
            # Process child comments
            for child in comment.get("children", []):
                process_comment(child, depth + 1)
        
        # Process all top-level comments
        for comment in comments:
            process_comment(comment)
        
        return "\n".join(formatted_comments[:100])  # Limit to first 100 comments for token efficiency
```

### Agent Orchestrator

```python
class ConcurrentCommentAnalysisOrchestrator:
    """Orchestrates concurrent comment analysis across multiple posts"""
    
    def __init__(self, model: str, api_key: str, system_prompt: str, max_concurrent_agents: int = 5):
        self.max_concurrent = max_concurrent_agents
        # Create ONE agent instance that will be reused
        self.filtering_agent = CommentFilteringAgent(
            model=model,
            api_key=api_key,
            system_prompt=system_prompt
        )
    
    async def analyze_posts_for_comments(
        self, 
        posts: List[PostWithComments]
    ) -> List[List[CommentAnalysis]]:
        """
        Analyze all posts concurrently using the same agent instance
        """
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def analyze_with_semaphore(post: PostWithComments) -> List[CommentAnalysis]:
            async with semaphore:
                try:
                    return await self.filtering_agent.analyze_post_for_comments(post)
                except Exception as e:
                    print(f"Error analyzing post {post.post_id}: {e}")
                    return []
        
        # Run all analyses concurrently
        tasks = [analyze_with_semaphore(post) for post in posts]
        results = await asyncio.gather(*tasks)
        
        return results
    
    def get_agent_info(self) -> Dict[str, Any]:
        """Get information about the agent configuration"""
        return {
            "agent_class": "CommentFilteringAgent",
            "model": self.filtering_agent.agent.model,
            "concurrent_executions": self.max_concurrent,
            "reuses_same_instance": True
        }
```

---

## Result Processing and Combination

### Results Stacker

```python
import time
from typing import List

class ResultsStacker:
    """Combines individual comment analyses into unified response"""
    
    def stack_comment_analyses(
        self, 
        individual_results: List[List[CommentAnalysis]],
        posts_analyzed: List[PostWithComments],
        processing_start_time: float,
        model_used: str,
        api_calls_made: int,
        collection_method: str,
        cell_parsing_errors: int = 0
    ) -> UnifiedAnalysisResponse:
        """
        Stack all comment analyses into unified response
        """
        # Flatten all comment analyses into single list
        all_comment_analyses = []
        for post_results in individual_results:
            all_comment_analyses.extend(post_results)
        
        # Calculate metadata
        total_posts = len(posts_analyzed)
        total_comments = sum(len(post.comments) for post in posts_analyzed)
        relevant_comments = len(all_comment_analyses)
        irrelevant_posts = sum(1 for results in individual_results if len(results) == 0)
        processing_time = time.time() - processing_start_time
        
        metadata = AnalysisMetadata(
            total_posts_analyzed=total_posts,
            total_comments_found=total_comments,
            relevant_comments_extracted=relevant_comments,
            irrelevant_posts=irrelevant_posts,
            analysis_timestamp=datetime.now(),
            processing_time_seconds=round(processing_time, 2),
            model_used=model_used,
            api_calls_made=api_calls_made,
            collection_method=collection_method,
            cell_parsing_errors=cell_parsing_errors
        )
        
        return UnifiedAnalysisResponse(
            comment_analyses=all_comment_analyses,
            metadata=metadata
        )
```

---

## FastAPI Implementation

### Complete FastAPI Application

```python
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
import time
import logging
from contextlib import asynccontextmanager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variables for data collectors
subreddit_collector = None
search_collector = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI"""
    global subreddit_collector, search_collector
    
    # Startup
    logger.info("Starting Reddit Comment Analysis API...")
    
    # Initialize data collectors
    rapidapi_key = "your-rapidapi-key"  # This should come from environment
    
    subreddit_collector = SubredditDataCollector(rapidapi_key)
    search_collector = SearchDataCollector(rapidapi_key)
    
    yield
    
    # Shutdown
    logger.info("Shutting down Reddit Comment Analysis API...")
    if subreddit_collector:
        await subreddit_collector.close()
    if search_collector:
        await search_collector.close()

app = FastAPI(
    title="Reddit Comment Analysis API",
    description="Analyze Reddit discussions with AI-powered comment filtering and cell-based data processing",
    version="2.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add trusted host middleware
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])

@app.post("/analyze-subreddit", response_model=UnifiedAnalysisResponse)
async def analyze_subreddit(request: SubredditAnalysisRequest):
    """
    Analyze Reddit discussions from a specific subreddit using comment-level filtering with cell-based processing
    """
    processing_start_time = time.time()
    cell_parsing_errors = 0
    
    try:
        logger.info(f"Starting subreddit analysis for r/{request.subreddit}")
        
        # Phase 1: Subreddit Data Collection with Cell Processing
        posts_with_comments = await subreddit_collector.collect_subreddit_posts(
            subreddit=request.subreddit,
            sort=request.sort,
            time=request.time,
            limit=request.limit
        )
        
        logger.info(f"Collected {len(posts_with_comments)} posts from r/{request.subreddit}")
        
        # Phase 2: Concurrent Comment Analysis
        orchestrator = ConcurrentCommentAnalysisOrchestrator(
            model=request.model,
            api_key=request.api_key,
            system_prompt=request.system_prompt,
            max_concurrent_agents=5
        )
        
        individual_results = await orchestrator.analyze_posts_for_comments(posts_with_comments)
        
        # Phase 3: Stack Results
        stacker = ResultsStacker()
        final_response = stacker.stack_comment_analyses(
            individual_results=individual_results,
            posts_analyzed=posts_with_comments,
            processing_start_time=processing_start_time,
            model_used=request.model,
            api_calls_made=len(posts_with_comments) + 1,
            collection_method="subreddit",
            cell_parsing_errors=cell_parsing_errors
        )
        
        logger.info(f"Subreddit analysis completed: {final_response.metadata.relevant_comments_extracted} comments extracted")
        
        return final_response
        
    except Exception as e:
        logger.error(f"Subreddit analysis failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Subreddit analysis failed: {str(e)}")

@app.post("/analyze-search", response_model=UnifiedAnalysisResponse)
async def analyze_search(request: SearchAnalysisRequest):
    """
    Analyze Reddit discussions from search results across all Reddit using comment-level filtering with cell-based processing
    """
    processing_start_time = time.time()
    cell_parsing_errors = 0
    
    try:
        logger.info(f"Starting search analysis for query: {request.query}")
        
        # Phase 1: Search Data Collection with Cell Processing
        posts_with_comments = await search_collector.collect_search_posts(
            query=request.query,
            sort=request.sort,
            time=request.time,
            limit=request.limit,
            nsfw=request.nsfw
        )
        
        logger.info(f"Collected {len(posts_with_comments)} posts for query: {request.query}")
        
        # Phase 2: Concurrent Comment Analysis
        orchestrator = ConcurrentCommentAnalysisOrchestrator(
            model=request.model,
            api_key=request.api_key,
            system_prompt=request.system_prompt,
            max_concurrent_agents=5
        )
        
        individual_results = await orchestrator.analyze_posts_for_comments(posts_with_comments)
        
        # Phase 3: Stack Results
        stacker = ResultsStacker()
        final_response = stacker.stack_comment_analyses(
            individual_results=individual_results,
            posts_analyzed=posts_with_comments,
            processing_start_time=processing_start_time,
            model_used=request.model,
            api_calls_made=len(posts_with_comments) + 1,
            collection_method="search",
            cell_parsing_errors=cell_parsing_errors
        )
        
        logger.info(f"Search analysis completed: {final_response.metadata.relevant_comments_extracted} comments extracted")
        
        return final_response
        
    except Exception as e:
        logger.error(f"Search analysis failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Search analysis failed: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "analysis_type": "comment_level_with_cell_processing",
        "endpoints": ["/analyze-subreddit", "/analyze-search"],
        "timestamp": datetime.now().isoformat()
    }

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Reddit Comment Analysis API with Cell-Based Processing",
        "version": "2.0.0",
        "documentation": "/docs",
        "health": "/health"
    }
```

---

## Error Handling Strategy

### Custom Exception Classes

```python
class RedditAPIError(Exception):
    """Base exception for Reddit API errors"""
    pass

class DataCollectionError(RedditAPIError):
    """Error during data collection phase"""
    pass

class CellParsingError(RedditAPIError):
    """Error during cell-based data parsing"""
    pass

class SearchPostParsingError(RedditAPIError):
    """Error during search post data parsing"""
    pass

class CommentParsingError(RedditAPIError):
    """Error during comment parsing"""
    pass

class CommentAnalysisError(RedditAPIError):
    """Error during comment analysis phase"""
    pass

class ResultProcessingError(RedditAPIError):
    """Error during result processing phase"""
    pass
```

### Error Handling Middleware

```python
from fastapi import Request
from fastapi.responses import JSONResponse
import traceback

@app.exception_handler(DataCollectionError)
async def data_collection_exception_handler(request: Request, exc: DataCollectionError):
    return JSONResponse(
        status_code=500,
        content={
            "error": "Data Collection Error",
            "detail": str(exc),
            "phase": "data_collection"
        }
    )

@app.exception_handler(CellParsingError)
async def cell_parsing_exception_handler(request: Request, exc: CellParsingError):
    return JSONResponse(
        status_code=500,
        content={
            "error": "Cell Parsing Error",
            "detail": str(exc),
            "phase": "cell_parsing"
        }
    )

@app.exception_handler(SearchPostParsingError)
async def search_post_parsing_exception_handler(request: Request, exc: SearchPostParsingError):
    return JSONResponse(
        status_code=500,
        content={
            "error": "Search Post Parsing Error",
            "detail": str(exc),
            "phase": "search_post_parsing"
        }
    )

@app.exception_handler(CommentParsingError)
async def comment_parsing_exception_handler(request: Request, exc: CommentParsingError):
    return JSONResponse(
        status_code=500,
        content={
            "error": "Comment Parsing Error",
            "detail": str(exc),
            "phase": "comment_parsing"
        }
    )

@app.exception_handler(CommentAnalysisError)
async def comment_analysis_exception_handler(request: Request, exc: CommentAnalysisError):
    return JSONResponse(
        status_code=500,
        content={
            "error": "Comment Analysis Error",
            "detail": str(exc),
            "phase": "comment_analysis"
        }
    )

@app.exception_handler(ResultProcessingError)
async def result_processing_exception_handler(request: Request, exc: ResultProcessingError):
    return JSONResponse(
        status_code=500,
        content={
            "error": "Result Processing Error",
            "detail": str(exc),
            "phase": "result_processing"
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unexpected error: {str(exc)}")
    logger.error(traceback.format_exc())
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "detail": "An unexpected error occurred",
            "phase": "unknown"
        }
    )
```

---

## Complete Implementation Steps

### Step 1: Project Setup
```bash
# Create project directory
mkdir reddit-comment-analyzer
cd reddit-comment-analyzer

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install fastapi[all] uvicorn pydantic-ai google-generativeai httpx asyncio python-dotenv
```

### Step 2: Directory Structure
```
reddit-comment-analyzer/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── reddit_collectors.py
│   │   ├── data_cleaners.py
│   │   ├── cell_extractors.py
│   │   └── comment_analyzer.py
│   ├── agents/
│   │   ├── __init__.py
│   │   └── filtering_agent.py
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py
│   └── core/
│       ├── __init__.py
│       ├── config.py
│       └── exceptions.py
├── tests/
├── requirements.txt
└── .env
```

### Step 3: Environment Configuration
```bash
# .env file
RAPIDAPI_REDDIT_KEY=your-rapidapi-key-here
GEMINI_API_KEY=your-gemini-key-here
LOG_LEVEL=INFO
MAX_CONCURRENT_AGENTS=5
```

### Step 4: Implementation Order
1. **Implement schemas.py** - All Pydantic models
2. **Implement cell_extractors.py** - Cell-based data extraction functions
3. **Implement data_cleaners.py** - Updated post and comment cleaning functions
5. **Implement reddit_collectors.py** - Data collection services with dual format processing (cell-based for subreddit, flat object for search)
5. **Implement filtering_agent.py** - AI agent for comment analysis
6. **Implement comment_analyzer.py** - Orchestrator and results stacker
7. **Implement routes.py** - FastAPI endpoints
8. **Implement main.py** - FastAPI application
9. **Add error handling and logging**
10. **Test and validate with real API responses**

### Step 5: Testing
```python
# test_main.py
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_cell_extraction():
    # Test cell-based data extraction
    sample_response = {
        "data": [
            {
                "__typename": "CellGroup",
                "groupId": "t3_test123",
                "cells": [
                    {"__typename": "TitleCell", "title": "Test Post"},
                    {"__typename": "MetadataCell", "authorName": "u/testuser"},
                    {"__typename": "ActionCell", "score": 100}
                ]
            }
        ]
    }
    
    from app.services.cell_extractors import extract_posts_from_reddit_response
    posts = extract_posts_from_reddit_response(sample_response)
    assert len(posts) == 1
    assert posts[0]["title"] == "Test Post"
    assert posts[0]["author"] == "testuser"

def test_search_post_extraction():
    # Test flat object data extraction  
    sample_response = {
        "data": [
            {
                "__typename": "SubredditPost",
                "id": "t3_test123",
                "postTitle": "Test Post Title",
                "authorInfo": {"name": "testuser"},
                "score": 100,
                "commentCount": 50,
                "subreddit": {"name": "motorcycles"}
            }
        ]
    }
    
    from app.services.search_extractors import extract_posts_from_search_response
    posts = extract_posts_from_search_response(sample_response)
    assert len(posts) == 1
    assert posts[0]["title"] == "Test Post Title"
    assert posts[0]["author"] == "testuser"
    assert posts[0]["subreddit"] == "motorcycles"

def test_comment_extraction():
    # Test posts/comments response processing
    sample_comment_response = {
        "data": {
            "commentForest": {
                "trees": [
                    {
                        "depth": 0,
                        "parentId": None,
                        "node": {
                            "id": "t1_test123",
                            "content": {
                                "markdown": "This is a test comment",
                                "preview": "This is a test comment"
                            },
                            "authorInfo": {"name": "testuser"},
                            "score": 50,
                            "createdAt": "2024-07-09T10:48:29.125000+0000"
                        }
                    }
                ]
            }
        }
    }
    
    from app.services.data_cleaners import clean_posts_comments_response
    comments = clean_posts_comments_response(sample_comment_response)
    assert len(comments) == 1
    assert comments[0]["body"] == "This is a test comment"
    assert comments[0]["author"] == "testuser"
    assert comments[0]["score"] == 50

def test_subreddit_analysis():
    request_data = {
        "subreddit": "motorcycles",
        "sort": "hot",
        "time": "week",
        "limit": 10,
        "model": "gemini-2.5-pro",
        "api_key": "test-key",
        "system_prompt": "Test prompt"
    }
    
    response = client.post("/analyze-subreddit", json=request_data)
    assert response.status_code == 200
    # Add more assertions based on expected response structure
```

### Step 6: Deployment
```bash
# Run locally
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Or use Docker
# Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## Key Implementation Notes

### Dual Format Processing Considerations
- **Performance**: Flat object processing (search) is faster than cell parsing (subreddit)
- **Reliability**: Both formats have different failure modes and validation requirements
- **Maintainability**: Separate processors allow independent updates for each format
- **Debugging**: Format-specific logging helps identify issues quickly

### Security Considerations
- Validate all user inputs and cell data
- Implement proper API key management
- Add request rate limiting
- Use HTTPS in production
- Implement proper CORS policies
- Sanitize extracted cell content

### Monitoring and Logging
- Add comprehensive logging throughout cell processing
- Implement health checks with cell parsing status
- Add metrics collection for cell parsing performance
- Monitor API usage and cell parsing success rates

### Scalability Features
- Design for horizontal scaling with stateless cell processing
- Use message queues for high-volume cell processing
- Implement database storage for processed results
- Add load balancing support
- Cache processed cell data when appropriate

This updated implementation guide provides everything needed to build a production-ready Reddit comment analysis API that properly handles Reddit's cell-based response format, with dual endpoints, intelligent comment filtering, and comprehensive error handling for cell processing scenarios.
