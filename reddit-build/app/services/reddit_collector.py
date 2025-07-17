"""
Base Reddit Data Collector for RapidAPI integration.
Handles all Reddit API communication with authentication, rate limiting, and error handling.
"""

import asyncio
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.config import get_settings
from app.models.schemas import SubredditAnalysisRequest, SearchAnalysisRequest, PostWithComments
from app.services.cell_extractors import extract_posts_from_reddit_response
from app.services.search_extractors import extract_posts_from_search_response
from app.services.data_cleaners import clean_posts_comments_response, build_post_with_comments

logger = logging.getLogger(__name__)


class RedditAPIError(Exception):
    """Custom exception for Reddit API errors"""
    pass


class BaseRedditDataCollector:
    """
    Base collector for Reddit data via RapidAPI.
    Handles authentication, rate limiting, and data collection for both subreddit and search endpoints.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.base_url = "https://reddit-com.p.rapidapi.com"
        self.headers = {
            "X-RapidAPI-Key": self.settings.rapid_api_key,
            "X-RapidAPI-Host": self.settings.rapidapi_reddit_host,
            "User-Agent": "RedditAnalyzer/1.0",
            "Accept": "application/json"
        }
        self.client: Optional[httpx.AsyncClient] = None
        
    async def __aenter__(self):
        """Async context manager entry"""
        await self._init_client()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.client:
            await self.client.aclose()
    
    async def _init_client(self):
        """Initialize the HTTP client with proper configuration"""
        if not self.settings.rapid_api_key:
            raise RedditAPIError("RapidAPI key not configured. Please set RAPID_API_KEY in your environment.")
        
        self.client = httpx.AsyncClient(
            headers=self.headers,
            timeout=httpx.Timeout(self.settings.reddit_api_timeout),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
        )
        logger.info("Reddit API client initialized successfully")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError))
    )
    async def _make_request(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Make authenticated request to Reddit API with retry logic
        """
        if not self.client:
            await self._init_client()
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            # Apply rate limiting delay
            await asyncio.sleep(self.settings.reddit_api_rate_limit_delay)
            
            logger.info(f"Making request to: {endpoint} with params: {params}")
            response = await self.client.get(url, params=params)
            
            # Handle specific HTTP errors
            if response.status_code == 401:
                raise RedditAPIError("Authentication failed. Check your RapidAPI key.")
            elif response.status_code == 403:
                raise RedditAPIError("Access forbidden. Check API permissions.")
            elif response.status_code == 429:
                raise RedditAPIError("Rate limit exceeded. Please try again later.")
            elif response.status_code == 404:
                logger.warning(f"Resource not found: {endpoint}")
                return {"data": [], "meta": {}}
            
            response.raise_for_status()
            
            # Parse JSON response
            try:
                data = response.json()
                logger.info(f"Request successful. Response size: {len(str(data))}")
                return data
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                raise RedditAPIError(f"Invalid JSON response: {e}")
                
        except httpx.RequestError as e:
            logger.error(f"Request failed: {e}")
            raise RedditAPIError(f"Network request failed: {e}")
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
            raise RedditAPIError(f"HTTP {e.response.status_code}: {e.response.text}")
    
    async def fetch_subreddit_posts(
        self, 
        subreddit: str, 
        sort: str = "hot", 
        time: str = "week", 
        limit: int = 10,
        after: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fetch posts from a specific subreddit (cell-based response format)
        
        Args:
            subreddit: Subreddit name (e.g., "motorcycles")
            sort: Sort method ("hot", "new", "top", "controversial", "rising")
            time: Time filter ("all", "year", "month", "week", "day")
            limit: Number of posts to fetch (1-100)
            after: Pagination token for next page
            
        Returns:
            Raw Reddit API response with CellGroup structure
        """
        endpoint = f"/subreddit/{subreddit}"
        
        params = {
            "sort": sort,
            "t": time,
            "limit": min(limit, 100),  # API limit
        }
        
        if after:
            params["after"] = after
            
        try:
            response = await self._make_request(endpoint, params)
            logger.info(f"Fetched {len(response.get('data', []))} items from r/{subreddit}")
            return response
        except RedditAPIError as e:
            logger.error(f"Failed to fetch subreddit posts: {e}")
            raise
    
    async def fetch_search_posts(
        self, 
        query: str, 
        sort: str = "relevance", 
        time: str = "week", 
        limit: int = 10,
        nsfw: bool = False,
        after: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Search Reddit posts (flat object response format)
        
        Args:
            query: Search query string
            sort: Sort method ("relevance", "new", "hot", "top", "comments")
            time: Time filter ("all", "year", "month", "week", "day")
            limit: Number of posts to fetch (1-100)
            nsfw: Include NSFW content
            after: Pagination token for next page
            
        Returns:
            Raw Reddit API response with SubredditPost structure
        """
        endpoint = "/posts/search"
        
        params = {
            "q": query,
            "sort": sort,
            "t": time,
            "limit": min(limit, 100),  # API limit
            "include_over_18": "true" if nsfw else "false"
        }
        
        if after:
            params["after"] = after
            
        try:
            response = await self._make_request(endpoint, params)
            logger.info(f"Found {len(response.get('data', []))} search results for: {query}")
            return response
        except RedditAPIError as e:
            logger.error(f"Failed to search posts: {e}")
            raise
    
    async def fetch_comment_tree(self, post_id: str, sort: str = "best") -> Dict[str, Any]:
        """
        Fetch all comments for a specific post
        
        Args:
            post_id: Reddit post ID (without t3_ prefix)
            sort: Comment sort method ("best", "top", "new", "controversial", "old", "qa")
            
        Returns:
            Raw Reddit API response with comment tree structure
        """
        endpoint = f"/posts/{post_id}/comments"
        
        params = {
            "sort": sort,
            "limit": 500,  # Maximum comments per request
            "depth": 10    # Maximum nesting depth
        }
        
        try:
            response = await self._make_request(endpoint, params)
            comments_count = len(response.get("data", []))
            logger.info(f"Fetched {comments_count} comments for post {post_id}")
            return response
        except RedditAPIError as e:
            logger.error(f"Failed to fetch comments for post {post_id}: {e}")
            raise
    
    async def paginate_posts(
        self, 
        fetch_method, 
        total_limit: int = 50, 
        per_page: int = 25,
        **kwargs
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Handle pagination for large result sets
        
        Args:
            fetch_method: The method to call for fetching (fetch_subreddit_posts or fetch_search_posts)
            total_limit: Total number of posts to collect
            per_page: Posts per API request
            **kwargs: Additional arguments for the fetch method
            
        Returns:
            Tuple of (all_posts, metadata)
        """
        all_posts = []
        after_token = None
        requests_made = 0
        start_time = datetime.now()
        
        while len(all_posts) < total_limit:
            # Calculate remaining posts needed
            remaining = total_limit - len(all_posts)
            current_limit = min(per_page, remaining)
            
            try:
                # Fetch current page
                response = await fetch_method(
                    limit=current_limit,
                    after=after_token,
                    **kwargs
                )
                
                requests_made += 1
                posts = response.get("data", [])
                
                if not posts:
                    logger.info("No more posts available, stopping pagination")
                    break
                
                all_posts.extend(posts)
                
                # Get next page token
                after_token = response.get("meta", {}).get("nextPage")
                if not after_token:
                    logger.info("No more pages available, stopping pagination")
                    break
                
                logger.info(f"Collected {len(all_posts)}/{total_limit} posts so far")
                
            except RedditAPIError as e:
                logger.error(f"Pagination failed: {e}")
                break
        
        # Calculate metadata
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        metadata = {
            "total_posts_collected": len(all_posts),
            "api_requests_made": requests_made,
            "processing_time_seconds": processing_time,
            "collection_timestamp": end_time.isoformat(),
            "has_more_pages": after_token is not None
        }
        
        logger.info(f"Pagination complete: {len(all_posts)} posts in {processing_time:.2f}s")
        return all_posts, metadata
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check if Reddit API is accessible and authenticated
        """
        try:
            # Try a simple request to verify connectivity
            response = await self.fetch_subreddit_posts("test", limit=1)
            return {
                "status": "healthy",
                "api_accessible": True,
                "authentication": "valid",
                "timestamp": datetime.now().isoformat()
            }
        except RedditAPIError as e:
            return {
                "status": "unhealthy",
                "api_accessible": False,
                "authentication": "invalid" if "Authentication" in str(e) else "unknown",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }


class SubredditDataCollector(BaseRedditDataCollector):
    """
    Specialized collector for subreddit-based data collection.
    Handles complete workflow: fetch posts → extract from cells → fetch comments → clean data.
    """
    
    async def collect_subreddit_posts(self, request: SubredditAnalysisRequest) -> Tuple[List[PostWithComments], Dict[str, Any]]:
        """
        Complete subreddit data collection workflow
        
        Args:
            request: SubredditAnalysisRequest with collection parameters
            
        Returns:
            Tuple of (list of PostWithComments, collection metadata)
        """
        start_time = datetime.now()
        collection_errors = []
        total_api_calls = 0
        
        logger.info(f"Starting subreddit collection: r/{request.subreddit} (limit: {request.limit})")
        
        try:
            # Step 1: Fetch raw subreddit posts using pagination
            raw_posts, pagination_metadata = await self.paginate_posts(
                fetch_method=self.fetch_subreddit_posts,
                total_limit=request.limit,
                per_page=min(25, request.limit),
                subreddit=request.subreddit,
                sort=request.sort,
                time=request.time
            )
            
            total_api_calls += pagination_metadata["api_requests_made"]
            logger.info(f"Fetched {len(raw_posts)} raw posts from Reddit API")
            
            # Step 2: Extract posts from cell structure
            extracted_posts = extract_posts_from_reddit_response({"data": raw_posts})
            logger.info(f"Extracted {len(extracted_posts)} posts from cell structure")
            
            # Step 3: Collect comments for each post and build PostWithComments
            posts_with_comments = []
            relevant_posts = 0
            
            for i, post in enumerate(extracted_posts[:request.limit]):
                try:
                    post_id = post.get("id", "")
                    if not post_id:
                        collection_errors.append(f"Post {i+1}: Missing post ID")
                        continue
                    
                    logger.info(f"Collecting comments for post {i+1}/{len(extracted_posts)}: {post_id}")
                    
                    # Fetch comment tree for this post
                    comments_response = await self.fetch_comment_tree(post_id, sort="best")
                    total_api_calls += 1
                    
                    # Build PostWithComments object
                    post_with_comments = build_post_with_comments(
                        post_data=post,
                        comments_data=comments_response.get("data", [])
                    )
                    
                    if post_with_comments:
                        posts_with_comments.append(post_with_comments)
                        relevant_posts += 1
                        logger.info(f"Successfully processed post {post_id} with {len(post_with_comments.comments)} comments")
                    else:
                        collection_errors.append(f"Post {post_id}: Failed to build PostWithComments")
                        
                except Exception as e:
                    collection_errors.append(f"Post {i+1}: {str(e)}")
                    logger.error(f"Failed to process post {i+1}: {e}")
                    continue
            
            # Step 4: Calculate collection metadata
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            
            metadata = {
                "total_posts_analyzed": len(extracted_posts),
                "total_comments_found": sum(len(p.comments) for p in posts_with_comments),
                "relevant_comments_extracted": sum(len(p.comments) for p in posts_with_comments),
                "irrelevant_posts": len(extracted_posts) - relevant_posts,
                "analysis_timestamp": end_time,
                "processing_time_seconds": processing_time,
                "model_used": "reddit-api-collector",
                "api_calls_made": total_api_calls,
                "collection_method": "subreddit",
                "cell_parsing_errors": len(collection_errors)
            }
            
            logger.info(f"Subreddit collection complete: {len(posts_with_comments)} posts with comments in {processing_time:.2f}s")
            
            if collection_errors:
                logger.warning(f"Collection errors encountered: {collection_errors}")
            
            return posts_with_comments, metadata
            
        except Exception as e:
            logger.error(f"Subreddit collection failed: {e}")
            raise RedditAPIError(f"Subreddit collection failed: {e}")


class SearchDataCollector(BaseRedditDataCollector):
    """
    Specialized collector for search-based data collection.
    Handles complete workflow: search posts → extract from flat objects → fetch comments → clean data.
    """
    
    async def collect_search_posts(self, request: SearchAnalysisRequest) -> Tuple[List[PostWithComments], Dict[str, Any]]:
        """
        Complete search data collection workflow
        
        Args:
            request: SearchAnalysisRequest with search parameters
            
        Returns:
            Tuple of (list of PostWithComments, collection metadata)
        """
        start_time = datetime.now()
        collection_errors = []
        total_api_calls = 0
        
        logger.info(f"Starting search collection: '{request.query}' (limit: {request.limit})")
        
        try:
            # Step 1: Search Reddit posts using pagination
            raw_posts, pagination_metadata = await self.paginate_posts(
                fetch_method=self.fetch_search_posts,
                total_limit=request.limit,
                per_page=min(25, request.limit),
                query=request.query,
                sort=request.sort,
                time=request.time,
                nsfw=request.nsfw
            )
            
            total_api_calls += pagination_metadata["api_requests_made"]
            logger.info(f"Found {len(raw_posts)} raw posts from search API")
            
            # Step 2: Extract posts from flat object structure
            extracted_posts = extract_posts_from_search_response({"data": raw_posts})
            logger.info(f"Extracted {len(extracted_posts)} posts from search results")
            
            # Step 3: Collect comments for each post and build PostWithComments
            posts_with_comments = []
            relevant_posts = 0
            
            for i, post in enumerate(extracted_posts[:request.limit]):
                try:
                    post_id = post.get("id", "")
                    if not post_id:
                        collection_errors.append(f"Post {i+1}: Missing post ID")
                        continue
                    
                    logger.info(f"Collecting comments for post {i+1}/{len(extracted_posts)}: {post_id}")
                    
                    # Fetch comment tree for this post
                    comments_response = await self.fetch_comment_tree(post_id, sort="best")
                    total_api_calls += 1
                    
                    # Build PostWithComments object
                    post_with_comments = build_post_with_comments(
                        post_data=post,
                        comments_data=comments_response.get("data", [])
                    )
                    
                    if post_with_comments:
                        posts_with_comments.append(post_with_comments)
                        relevant_posts += 1
                        logger.info(f"Successfully processed post {post_id} with {len(post_with_comments.comments)} comments")
                    else:
                        collection_errors.append(f"Post {post_id}: Failed to build PostWithComments")
                        
                except Exception as e:
                    collection_errors.append(f"Post {i+1}: {str(e)}")
                    logger.error(f"Failed to process post {i+1}: {e}")
                    continue
            
            # Step 4: Calculate collection metadata
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            
            metadata = {
                "total_posts_analyzed": len(extracted_posts),
                "total_comments_found": sum(len(p.comments) for p in posts_with_comments),
                "relevant_comments_extracted": sum(len(p.comments) for p in posts_with_comments),
                "irrelevant_posts": len(extracted_posts) - relevant_posts,
                "analysis_timestamp": end_time,
                "processing_time_seconds": processing_time,
                "model_used": "reddit-api-collector",
                "api_calls_made": total_api_calls,
                "collection_method": "search",
                "cell_parsing_errors": len(collection_errors)
            }
            
            logger.info(f"Search collection complete: {len(posts_with_comments)} posts with comments in {processing_time:.2f}s")
            
            if collection_errors:
                logger.warning(f"Collection errors encountered: {collection_errors}")
            
            return posts_with_comments, metadata
            
        except Exception as e:
            logger.error(f"Search collection failed: {e}")
            raise RedditAPIError(f"Search collection failed: {e}")
