"""
Cell-based data extraction functions for Reddit subreddit/search responses.
Handles the complex CellGroup structure from Reddit's subreddit/search API.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, Generator

from app.core.logging import get_logger

logger = get_logger(__name__)

# API Structure Constants (Improvement #4)
CELL_GROUP_TYPE = "CellGroup"
METADATA_CELL_TYPE = "MetadataCell"
TITLE_CELL_TYPE = "TitleCell"
ACTION_CELL_TYPE = "ActionCell"
LEGACY_VIDEO_CELL_TYPE = "LegacyVideoCell"
IMAGE_CELL_TYPE = "ImageCell"
DEFAULT_FALLBACK_SUBREDDIT = "unknown"
POST_ID_PREFIX = "t3_"
AUTHOR_PREFIX = "u/"
REDDIT_BASE_URL = "https://www.reddit.com"


@dataclass
class ExtractionMetrics:
    """Extraction metrics for monitoring system health (Improvement #6)."""
    total_items_processed: int = 0
    ads_filtered: int = 0
    posts_extracted: int = 0
    posts_dropped: int = 0
    extraction_errors: List[str] = field(default_factory=list)
    validation_warnings: List[str] = field(default_factory=list)
    date_parsing_errors: int = 0
    missing_essential_data_count: int = 0
    processing_time_seconds: float = 0.0


def validate_extracted_post(post_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate extracted post data for consistency and correctness (Improvement #5).
    
    Args:
        post_data: Extracted post data dictionary
        
    Returns:
        Dictionary with validation results
    """
    validation_result = {
        "is_valid": True,
        "errors": [],
        "warnings": []
    }
    
    # Check essential fields
    if not post_data.get("id"):
        validation_result["errors"].append("Missing post ID")
        validation_result["is_valid"] = False
    
    if not post_data.get("title"):
        validation_result["errors"].append("Missing post title")
        validation_result["is_valid"] = False
    
    # Check for unusual values
    score = post_data.get("score", 0)
    if score < -100:  # Unusually negative score
        validation_result["warnings"].append(f"Unusual negative score: {score}")
    
    # Validate URL format
    url = post_data.get("url", "")
    if url and not (url.startswith("https://") or url.startswith("http://")):
        validation_result["warnings"].append(f"Invalid URL format: {url}")
    
    # Check timestamp validity
    created_utc = post_data.get("created_utc")
    if created_utc:
        try:
            # Check if timestamp is reasonable (not too far in future or past)
            current_time = datetime.now().timestamp()
            if created_utc > current_time + 86400:  # More than 1 day in future
                validation_result["warnings"].append("Post timestamp appears to be in the future")
            elif created_utc < current_time - (365 * 24 * 3600 * 10):  # More than 10 years old
                validation_result["warnings"].append("Post timestamp is very old")
        except (ValueError, TypeError):
            validation_result["warnings"].append("Invalid timestamp format")
    
    # Check comment count
    num_comments = post_data.get("num_comments", 0)
    if num_comments < 0:
        validation_result["warnings"].append(f"Negative comment count: {num_comments}")
    
    return validation_result


def filter_content_types_generator(api_response: Dict[str, Any]) -> Generator[Dict[str, Any], None, None]:
    """
    Generator version to reduce memory usage for large responses (Improvement #7).
    
    Args:
        api_response: Raw API response
        
    Yields:
        Filtered content items (CellGroups without ads)
    """
    for item in api_response.get("data", []):
        if (item.get("__typename") == CELL_GROUP_TYPE and
            item.get("adPayload") is None):
            yield item


def extract_posts_from_reddit_response(api_response: Dict[str, Any], fallback_subreddit: str = DEFAULT_FALLBACK_SUBREDDIT) -> Tuple[List[Dict[str, Any]], ExtractionMetrics]:
    """
    Extract actual posts from Reddit API cell-based response with comprehensive metrics.
    Enhanced with logging, validation, and metrics tracking.
    
    Args:
        api_response: Raw Reddit API response
        fallback_subreddit: Default subreddit name if not extractable
        
    Returns:
        Tuple of (extracted_posts, extraction_metrics)
    """
    import time
    start_time = time.time()
    
    posts = []
    metrics = ExtractionMetrics()
    
    try:
        # Use generator for memory efficiency with large responses
        for item in filter_content_types_generator(api_response):
            metrics.total_items_processed += 1
            
            try:
                # Check for ads and skip them
                if item.get("adPayload") is not None:
                    metrics.ads_filtered += 1
                    logger.debug(f"Filtered out ad with groupId: {item.get('groupId', 'unknown')}")
                    continue
                
                # Extract post ID from groupId (format: "t3_postid")
                group_id = item.get("groupId", "")
                if not group_id.startswith(POST_ID_PREFIX):
                    logger.warning(f"Skipping item with invalid groupId format: {group_id}")
                    metrics.posts_dropped += 1
                    continue
                
                # Convert cell structure to flat post object
                post_data = extract_post_from_cells(group_id, item.get("cells", []), fallback_subreddit)
                if post_data:
                    # Validate extracted post data
                    validation_result = validate_extracted_post(post_data)
                    
                    if validation_result["is_valid"]:
                        posts.append(post_data)
                        metrics.posts_extracted += 1
                        
                        # Log validation warnings if any
                        if validation_result["warnings"]:
                            metrics.validation_warnings.extend(validation_result["warnings"])
                            logger.info(f"Post {post_data['id']} validation warnings: {validation_result['warnings']}")
                    else:
                        logger.warning(f"Dropping post {group_id} due to validation errors: {validation_result['errors']}")
                        metrics.posts_dropped += 1
                        metrics.extraction_errors.extend(validation_result["errors"])
                else:
                    # Post was dropped in extract_post_from_cells
                    metrics.posts_dropped += 1
                    
            except Exception as e:
                logger.error(f"Error processing item {item.get('groupId', 'unknown')}: {e}")
                metrics.extraction_errors.append(f"Item processing error: {str(e)}")
                metrics.posts_dropped += 1
                continue
        
        metrics.processing_time_seconds = time.time() - start_time
        
        logger.info(f"Extraction completed: {metrics.posts_extracted} posts extracted, "
                   f"{metrics.posts_dropped} dropped, {metrics.ads_filtered} ads filtered, "
                   f"processing time: {metrics.processing_time_seconds:.2f}s")
        
        return posts, metrics
        
    except Exception as e:
        metrics.processing_time_seconds = time.time() - start_time
        logger.error(f"Critical error in post extraction: {e}")
        metrics.extraction_errors.append(f"Critical extraction error: {str(e)}")
        return [], metrics


def extract_post_from_cells(group_id: str, cells: List[Dict[str, Any]], fallback_subreddit: str = DEFAULT_FALLBACK_SUBREDDIT) -> Optional[Dict[str, Any]]:
    """
    Extract post information from Reddit cell structure.
    Enhanced with better error handling, logging, and flexible subreddit handling.
    
    Args:
        group_id: Reddit post group ID (format: "t3_postid")
        cells: List of cell data structures
        fallback_subreddit: Default subreddit if not extractable from cells
        
    Returns:
        Extracted post data or None if essential data is missing
    """
    post_data = {
        "id": group_id.replace(POST_ID_PREFIX, ""),  # Remove t3_ prefix
        "title": "",
        "selftext": "",
        "author": "",
        "score": 0,
        "num_comments": 0,
        "created_utc": None,
        "permalink": "",
        "url": "",
        "subreddit": fallback_subreddit  # Use parameter instead of hardcoded value (Improvement #1)
    }
    
    extraction_issues = []
    
    for cell in cells:
        try:
            cell_type = cell.get("__typename", "")
            
            if cell_type == METADATA_CELL_TYPE:
                # Extract author and creation date
                author_name = cell.get("authorName", "")
                if author_name.startswith(AUTHOR_PREFIX):
                    post_data["author"] = author_name[len(AUTHOR_PREFIX):]  # Remove u/ prefix
                elif author_name:
                    post_data["author"] = author_name
                
                created_at = cell.get("createdAt")
                if created_at:
                    try:
                        # Convert ISO format to Unix timestamp with improved error handling (Improvement #3)
                        dt = datetime.fromisoformat(created_at.replace("+0000", "+00:00"))
                        post_data["created_utc"] = int(dt.timestamp())
                    except Exception as e:
                        logger.error(f"Error parsing date {created_at} for post {group_id}: {e}")
                        # Fallback to current time (Improvement #3)
                        post_data["created_utc"] = int(datetime.now().timestamp())
                        extraction_issues.append(f"Date parsing failed: {str(e)}")
                        
            elif cell_type == TITLE_CELL_TYPE:
                # Extract post title
                title = cell.get("title", "")
                if title:
                    post_data["title"] = title
                else:
                    extraction_issues.append("TitleCell missing title content")
                    
            elif cell_type == ACTION_CELL_TYPE:
                # Extract score and comment count
                score = cell.get("score", 0)
                comment_count = cell.get("commentCount", 0)
                
                try:
                    post_data["score"] = int(score) if score is not None else 0
                    post_data["num_comments"] = int(comment_count) if comment_count is not None else 0
                except (ValueError, TypeError) as e:
                    logger.warning(f"Error parsing numeric values for post {group_id}: score={score}, comments={comment_count}, error={e}")
                    extraction_issues.append(f"Numeric parsing error: {str(e)}")
                    
            elif cell_type in [LEGACY_VIDEO_CELL_TYPE, IMAGE_CELL_TYPE]:
                # For media posts, extract subreddit if available
                subreddit_visual = cell.get("subredditVisualName", "")
                if subreddit_visual:
                    post_data["subreddit"] = subreddit_visual
                    
        except Exception as e:
            logger.error(f"Error processing {cell_type} cell for post {group_id}: {e}")
            extraction_issues.append(f"{cell_type} processing error: {str(e)}")
            continue
    
    # Generate permalink and URL
    if post_data["id"] and post_data["subreddit"]:
        post_data["permalink"] = f"/r/{post_data['subreddit']}/comments/{post_data['id']}/"
        post_data["url"] = f"{REDDIT_BASE_URL}{post_data['permalink']}"
    
    # Enhanced logging for silent data loss (Improvement #2)
    has_title = bool(post_data["title"])
    has_id = bool(post_data["id"])
    
    if not (has_title and has_id):
        logger.warning(f"Dropping post {group_id}: missing title={not has_title}, "
                      f"missing id={not has_id}, extraction_issues={extraction_issues}")
        return None
    
    # Log extraction issues even for successful posts
    if extraction_issues:
        logger.info(f"Post {group_id} extracted with issues: {extraction_issues}")
    
    return post_data


def extract_pagination_token(api_response: Dict[str, Any]) -> Optional[str]:
    """
    Extract pagination token from Reddit API response.
    Enhanced with error handling and logging.
    
    Args:
        api_response: Raw API response
        
    Returns:
        Pagination token or None if not found
    """
    try:
        token = api_response.get("meta", {}).get("nextPage")
        if token:
            logger.debug(f"Found pagination token: {token[:50]}...")  # Log first 50 chars
        else:
            logger.debug("No pagination token found")
        return token
    except Exception as e:
        logger.error(f"Error extracting pagination token: {e}")
        return None


def filter_content_types(api_response: Dict[str, Any]) -> Tuple[Dict[str, Any], ExtractionMetrics]:
    """
    Filter out ads and recommendations from API response with metrics tracking.
    Enhanced with comprehensive filtering metrics.
    
    Args:
        api_response: Raw API response
        
    Returns:
        Tuple of (filtered_response, extraction_metrics)
    """
    import time
    start_time = time.time()
    
    filtered_data = []
    metrics = ExtractionMetrics()
    
    try:
        for item in api_response.get("data", []):
            metrics.total_items_processed += 1
            
            # Keep only CellGroup items without ads
            if item.get("__typename") == CELL_GROUP_TYPE:
                if item.get("adPayload") is None:
                    filtered_data.append(item)
                    metrics.posts_extracted += 1
                else:
                    metrics.ads_filtered += 1
                    logger.debug(f"Filtered ad with groupId: {item.get('groupId', 'unknown')}")
            else:
                # Non-CellGroup items (recommendations, etc.)
                metrics.posts_dropped += 1
                logger.debug(f"Filtered non-CellGroup item: {item.get('__typename', 'unknown')}")
        
        metrics.processing_time_seconds = time.time() - start_time
        
        filtered_response = {
            **api_response,
            "data": filtered_data
        }
        
        logger.info(f"Content filtering completed: {metrics.posts_extracted} posts kept, "
                   f"{metrics.ads_filtered} ads filtered, {metrics.posts_dropped} other items dropped")
        
        return filtered_response, metrics
        
    except Exception as e:
        metrics.processing_time_seconds = time.time() - start_time
        logger.error(f"Error in content filtering: {e}")
        metrics.extraction_errors.append(f"Filtering error: {str(e)}")
        return api_response, metrics  # Return original response on error


def validate_cell_structure(cells: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Validate that required cells are present and well-formed (for cell-based responses).
    Enhanced with more comprehensive validation using constants.
    
    Args:
        cells: List of cell data structures
        
    Returns:
        Dictionary with validation results
    """
    validation_result = {
        "is_valid": True,
        "errors": [],
        "warnings": [],
        "required_cells_found": {
            METADATA_CELL_TYPE: False,
            TITLE_CELL_TYPE: False,
            ACTION_CELL_TYPE: False
        }
    }
    
    for cell in cells:
        try:
            cell_type = cell.get("__typename", "")
            
            if cell_type in validation_result["required_cells_found"]:
                validation_result["required_cells_found"][cell_type] = True
            
            # Validate cell-specific requirements using constants
            if cell_type == METADATA_CELL_TYPE:
                if not cell.get("authorName"):
                    validation_result["warnings"].append("MetadataCell missing authorName")
                if not cell.get("createdAt"):
                    validation_result["warnings"].append("MetadataCell missing createdAt")
                    
            elif cell_type == TITLE_CELL_TYPE:
                if not cell.get("title"):
                    validation_result["errors"].append("TitleCell missing title")
                    validation_result["is_valid"] = False
                    
            elif cell_type == ACTION_CELL_TYPE:
                # Validate numeric fields
                score = cell.get("score")
                comment_count = cell.get("commentCount")
                
                if score is not None:
                    try:
                        int(score)
                    except (ValueError, TypeError):
                        validation_result["warnings"].append(f"ActionCell has invalid score: {score}")
                
                if comment_count is not None:
                    try:
                        int(comment_count)
                    except (ValueError, TypeError):
                        validation_result["warnings"].append(f"ActionCell has invalid commentCount: {comment_count}")
                        
        except Exception as e:
            validation_result["errors"].append(f"Error validating cell {cell_type}: {str(e)}")
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