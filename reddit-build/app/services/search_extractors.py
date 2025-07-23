"""
Flat object data extraction functions for Reddit posts/search-posts responses.
Handles the simple SubredditPost structure from Reddit's search API.
"""

import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from html import unescape
from typing import Dict, Any, List, Optional, Tuple

from app.core.logging import get_logger

logger = get_logger(__name__)

# API Structure Constants (Improvement #5)
SUBREDDIT_POST_TYPE = "SubredditPost"
CONTENT_FORMATS = ["markdown", "preview", "html"]
DELETED_AUTHORS = {"[deleted]", "[removed]"}
TYPENAME_FIELD = "__typename"
POST_ID_PREFIX = "t3_"
AUTHOR_PREFIX = "u/"
REDDIT_BASE_URL = "https://www.reddit.com"
REQUIRED_SEARCH_FIELDS = ["id", "postTitle", "authorInfo", "subreddit"]


@dataclass
class SearchExtractionMetrics:
    """Extraction metrics for monitoring search extraction health (Improvement #6)."""
    total_items_processed: int = 0
    valid_posts_extracted: int = 0
    posts_dropped: int = 0
    validation_errors: List[str] = field(default_factory=list)
    validation_warnings: List[str] = field(default_factory=list)
    date_parsing_errors: int = 0
    html_cleaning_warnings: int = 0
    url_generation_count: int = 0
    extraction_time_seconds: float = 0.0


def parse_reddit_timestamp(timestamp_value: Any) -> int:
    """
    Centralized date parsing with fallback (Improvement #1).
    
    Args:
        timestamp_value: Timestamp in various formats
        
    Returns:
        Unix timestamp as integer
    """
    try:
        if isinstance(timestamp_value, str):
            try:
                dt = datetime.fromisoformat(timestamp_value.replace("+0000", "+00:00"))
                return int(dt.timestamp())
            except ValueError:
                logger.warning(f"Failed to parse timestamp: {timestamp_value}")
                return int(datetime.now().timestamp())  # Fallback to current time
        elif isinstance(timestamp_value, (int, float)):
            return int(timestamp_value)
        else:
            logger.warning(f"Unknown timestamp type: {type(timestamp_value)}")
            return int(datetime.now().timestamp())
    except Exception as e:
        logger.error(f"Error parsing timestamp {timestamp_value}: {e}")
        return int(datetime.now().timestamp())


def clean_html_content(content: str) -> Tuple[str, int]:
    """
    Enhanced HTML cleaning with proper entity decoding (Improvement #3).
    
    Args:
        content: Raw HTML content string
        
    Returns:
        Tuple of (cleaned_content, warning_count)
    """
    if not content:
        return "", 0
    
    warning_count = 0
    original_content = content
    
    try:
        # Use proper HTML entity decoding
        content = unescape(content)
        
        # More comprehensive tag removal
        content = re.sub(r'<[^>]+>', '', content)
        
        # Handle additional HTML entities that might remain
        content = re.sub(r'&\w+;', '', content)
        
        # Clean up whitespace
        content = re.sub(r'\s+', ' ', content).strip()
        
        # Check if significant cleaning occurred
        if len(content) < len(original_content) * 0.8:
            warning_count += 1
            logger.debug(f"Significant HTML content removed: {len(original_content)} -> {len(content)} chars")
            
    except Exception as e:
        logger.warning(f"Error in HTML cleaning: {e}")
        warning_count += 1
        # Return original content if cleaning fails
        content = original_content.strip()
    
    return content, warning_count


def generate_reddit_url(post_id: str, subreddit: str) -> Tuple[str, str]:
    """
    Generate and validate Reddit URLs (Improvement #8).
    
    Args:
        post_id: Reddit post ID
        subreddit: Subreddit name
        
    Returns:
        Tuple of (permalink, full_url)
    """
    if not post_id or not subreddit:
        logger.warning(f"Cannot generate URL: missing post_id={not post_id}, subreddit={not subreddit}")
        return "", ""
    
    # Generate permalink
    permalink = f"/r/{subreddit}/comments/{post_id}/"
    url = f"{REDDIT_BASE_URL}{permalink}"
    
    # Basic validation of permalink format
    if not re.match(r'^/r/[^/]+/comments/[^/]+/$', permalink):
        logger.warning(f"Generated malformed permalink: {permalink}")
    
    logger.debug(f"Generated URL for post {post_id}: {url}")
    return permalink, url


def extract_posts_from_search_response(api_response: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], SearchExtractionMetrics]:
    """
    Extract posts from search API flat object response with comprehensive metrics.
    Enhanced with input validation, logging, and metrics tracking.
    
    Args:
        api_response: Raw search API response
        
    Returns:
        Tuple of (extracted_posts, extraction_metrics)
    """
    start_time = time.time()
    posts = []
    metrics = SearchExtractionMetrics()
    
    try:
        # Input validation (Improvement #4)
        if not api_response or not isinstance(api_response, dict):
            logger.warning("Invalid API response format")
            metrics.validation_errors.append("Invalid API response format")
            metrics.extraction_time_seconds = time.time() - start_time
            return [], metrics
        
        data = api_response.get("data")
        if not isinstance(data, list):
            logger.warning("API response data is not a list")
            metrics.validation_errors.append("API response data is not a list")
            metrics.extraction_time_seconds = time.time() - start_time
            return [], metrics
        
        logger.info(f"Processing {len(data)} items from search response")
        
        for item in data:
            metrics.total_items_processed += 1
            
            try:
                # Only process SubredditPost items
                if item.get(TYPENAME_FIELD) != SUBREDDIT_POST_TYPE:
                    logger.debug(f"Skipping non-SubredditPost item: {item.get(TYPENAME_FIELD)}")
                    metrics.posts_dropped += 1
                    continue
                
                # Convert SubredditPost to our standard format
                post_data = extract_search_post_data(item, metrics)
                if post_data:
                    posts.append(post_data)
                    metrics.valid_posts_extracted += 1
                else:
                    metrics.posts_dropped += 1
                    
            except Exception as e:
                logger.error(f"Error processing search item: {e}")
                metrics.validation_errors.append(f"Item processing error: {str(e)}")
                metrics.posts_dropped += 1
                continue
        
        metrics.extraction_time_seconds = time.time() - start_time
        
        logger.info(f"Search extraction completed: {metrics.valid_posts_extracted} posts extracted, "
                   f"{metrics.posts_dropped} dropped, processing time: {metrics.extraction_time_seconds:.2f}s")
        
        return posts, metrics
        
    except Exception as e:
        metrics.extraction_time_seconds = time.time() - start_time
        logger.error(f"Critical error in search extraction: {e}")
        metrics.validation_errors.append(f"Critical extraction error: {str(e)}")
        return [], metrics


def extract_search_post_data(post_item: Dict[str, Any], metrics: Optional[SearchExtractionMetrics] = None) -> Optional[Dict[str, Any]]:
    """
    Extract post information from SubredditPost object.
    Enhanced with validation integration, logging, and error handling.
    
    Args:
        post_item: Raw SubredditPost data
        metrics: Optional metrics object to update
        
    Returns:
        Extracted post data or None if invalid
    """
    if metrics is None:
        metrics = SearchExtractionMetrics()
    
    try:
        # Integrate validation into extraction pipeline (Improvement #7)
        validation_result = validate_search_post_structure(post_item)
        if not validation_result["is_valid"]:
            logger.warning(f"Invalid post structure: {validation_result['errors']}")
            metrics.validation_errors.extend(validation_result["errors"])
            return None
        
        # Track validation warnings
        if validation_result["warnings"]:
            metrics.validation_warnings.extend(validation_result["warnings"])
        
        # Extract post ID (remove t3_ prefix if present)
        post_id = post_item.get("id", "")
        if post_id.startswith(POST_ID_PREFIX):
            post_id = post_id[len(POST_ID_PREFIX):]
        
        # Extract content with enhanced HTML cleaning
        content_obj = post_item.get("content")
        content, html_warnings = extract_post_content(content_obj)
        metrics.html_cleaning_warnings += html_warnings
        
        # Extract author name
        author_info = post_item.get("authorInfo", {})
        author_name = normalize_author_name(author_info)
        
        # Extract subreddit name
        subreddit_info = post_item.get("subreddit", {})
        subreddit_name = subreddit_info.get("name", "")
        
        # Convert creation date with improved error handling
        created_utc = None
        created_at = post_item.get("createdAt")
        if created_at:
            try:
                created_utc = parse_reddit_timestamp(created_at)
            except Exception as e:
                logger.error(f"Error parsing date {created_at}: {e}")
                metrics.date_parsing_errors += 1
                created_utc = int(datetime.now().timestamp())  # Fallback
        
        # Extract basic post data
        title = post_item.get("postTitle", "")
        permalink = post_item.get("permalink", "")
        url = post_item.get("url", "")
        
        post_data = {
            "id": post_id,
            "title": title,
            "selftext": content,
            "author": author_name,
            "score": post_item.get("score", 0),
            "num_comments": post_item.get("commentCount", 0),
            "created_utc": created_utc,
            "permalink": permalink,
            "url": url,
            "subreddit": subreddit_name
        }
        
        # Generate permalink and URL if missing with validation
        if post_data["id"] and post_data["subreddit"] and not post_data["permalink"]:
            generated_permalink, generated_url = generate_reddit_url(post_data["id"], post_data["subreddit"])
            post_data["permalink"] = generated_permalink
            post_data["url"] = generated_url
            metrics.url_generation_count += 1
        
        # Enhanced logging for silent data loss (Improvement #2)
        has_title = bool(post_data["title"])
        has_id = bool(post_data["id"])
        
        if not (has_title and has_id):
            logger.warning(f"Dropping search post: missing title={not has_title}, missing id={not has_id}")
            return None
        
        return post_data
        
    except Exception as e:
        logger.error(f"Error extracting search post data: {e}")
        metrics.validation_errors.append(f"Post data extraction error: {str(e)}")
        return None


def extract_post_content(content_obj: Dict[str, Any]) -> Tuple[str, int]:
    """
    Extract text content from various Reddit content formats.
    Enhanced with improved HTML cleaning and warning tracking.
    
    Args:
        content_obj: Content object with various format options
        
    Returns:
        Tuple of (extracted_content, warning_count)
    """
    if not content_obj:
        return "", 0
    
    total_warnings = 0
    
    # Priority order: markdown > preview > html > empty
    for format_name in CONTENT_FORMATS:
        content = content_obj.get(format_name, "")
        if content and content.strip():
            # Enhanced HTML cleaning for html format
            if format_name == "html":
                cleaned_content, warnings = clean_html_content(content)
                total_warnings += warnings
                return cleaned_content, total_warnings
            else:
                # Basic cleaning for other formats
                content = content.strip()
                return content, total_warnings
    
    return "", total_warnings


def normalize_author_name(author_info) -> str:
    """
    Extract author name from different author formats.
    Enhanced with better error handling and logging.
    
    Args:
        author_info: Author information in various formats
        
    Returns:
        Normalized author name or empty string
    """
    if not author_info:
        return ""
    
    try:
        # Handle both direct name and nested authorInfo structures
        if isinstance(author_info, str):
            name = author_info
        else:
            name = author_info.get("name", "")
        
        # Remove u/ prefix if present
        if name.startswith(AUTHOR_PREFIX):
            name = name[len(AUTHOR_PREFIX):]
        
        # Check for deleted/removed authors
        if name in DELETED_AUTHORS:
            logger.debug(f"Found deleted/removed author: {name}")
            return ""
        
        return name if name else ""
        
    except Exception as e:
        logger.warning(f"Error normalizing author name: {e}")
        return ""


def validate_search_post_structure(post: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate that required fields are present in search post response.
    Enhanced with more comprehensive validation.
    
    Args:
        post: Raw search post data
        
    Returns:
        Dictionary with validation results
    """
    validation_result = {
        "is_valid": True,
        "errors": [],
        "warnings": []
    }
    
    try:
        # Check required fields using constants
        for field in REQUIRED_SEARCH_FIELDS:
            if not post.get(field):
                validation_result["errors"].append(f"Missing required field: {field}")
                validation_result["is_valid"] = False
        
        # Check nested required fields
        author_info = post.get("authorInfo")
        if author_info:
            if not author_info.get("name"):
                validation_result["warnings"].append("Author info missing name")
        
        subreddit_info = post.get("subreddit")
        if subreddit_info:
            if not subreddit_info.get("name"):
                validation_result["warnings"].append("Subreddit info missing name")
        
        # Validate data types and ranges
        score = post.get("score")
        if score is not None:
            try:
                int(score)
            except (ValueError, TypeError):
                validation_result["warnings"].append(f"Invalid score format: {score}")
        
        comment_count = post.get("commentCount")
        if comment_count is not None:
            try:
                count = int(comment_count)
                if count < 0:
                    validation_result["warnings"].append(f"Negative comment count: {count}")
            except (ValueError, TypeError):
                validation_result["warnings"].append(f"Invalid comment count format: {comment_count}")
        
        # Validate timestamp format
        created_at = post.get("createdAt")
        if created_at and not isinstance(created_at, str):
            validation_result["warnings"].append("CreatedAt should be a string")
        
    except Exception as e:
        validation_result["errors"].append(f"Validation error: {str(e)}")
        validation_result["is_valid"] = False
    
    return validation_result 