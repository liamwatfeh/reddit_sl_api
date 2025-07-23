"""
Universal data cleaning functions for Reddit posts and comments.
Works with both cell-based and flat object extraction formats.
"""

import dataclasses
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
import re
import json
import traceback

from app.core.logging import get_logger

logger = get_logger(__name__)

# Constants for data cleaning (Improvement #5)
DEFAULT_AUTHOR = "unknown"
DELETED_CONTENT_MARKER = "[deleted]"
REMOVED_CONTENT_MARKER = "[removed]"
MAX_COMMENT_LENGTH = 10000
MAX_POST_CONTENT_LENGTH = 50000
DELETED_AUTHORS = {"[deleted]", "[removed]"}
SPAM_REPEAT_THRESHOLD = 10
REQUIRED_COMMENT_FIELDS = ["id", "content", "authorInfo", "score"]
CONTENT_FORMATS = ["markdown", "preview", "html"]


@dataclass
class CleaningMetrics:
    """Data processing metrics for monitoring system health (Improvement #4)."""
    comments_processed: int = 0
    comments_dropped: int = 0
    posts_processed: int = 0
    posts_dropped: int = 0
    processing_time_seconds: float = 0.0
    validation_errors: List[str] = field(default_factory=list)
    validation_warnings: List[str] = field(default_factory=list)
    date_parsing_errors: int = 0
    content_sanitization_warnings: int = 0
    trees_processed: int = 0
    root_comments_found: int = 0


def parse_reddit_timestamp(timestamp_value: Any) -> datetime:
    """
    Centralized date parsing with multiple format support (Improvement #1).
    
    Args:
        timestamp_value: Unix timestamp (int/float) or ISO string
        
    Returns:
        datetime object in UTC timezone
    """
    try:
        if isinstance(timestamp_value, (int, float)):
            return datetime.fromtimestamp(timestamp_value, tz=timezone.utc)
        elif isinstance(timestamp_value, str):
            try:
                # Handle Reddit's ISO format with timezone
                return datetime.fromisoformat(timestamp_value.replace("+0000", "+00:00"))
            except ValueError:
                logger.warning(f"Failed to parse timestamp: {timestamp_value}")
                return datetime.now(tz=timezone.utc)
        else:
            logger.warning(f"Unknown timestamp type: {type(timestamp_value)}")
            return datetime.now(tz=timezone.utc)
    except Exception as e:
        logger.error(f"Error parsing timestamp {timestamp_value}: {e}")
        return datetime.now(tz=timezone.utc)


def sanitize_reddit_content(content: str, max_length: int = MAX_COMMENT_LENGTH) -> Tuple[str, int]:
    """
    Enhanced content sanitization with comprehensive cleaning (Improvement #3).
    
    Args:
        content: Raw content string
        max_length: Maximum allowed content length
        
    Returns:
        Tuple of (sanitized_content, warning_count)
    """
    if not content:
        return "", 0
    
    warning_count = 0
    original_length = len(content)
    
    # Truncate extremely long content
    if len(content) > max_length:
        content = content[:max_length] + "..."
        warning_count += 1
        logger.warning(f"Truncated content from {original_length} to {max_length} characters")
    
    # Handle malformed Unicode
    try:
        content = content.encode('utf-8', errors='ignore').decode('utf-8')
    except UnicodeError:
        warning_count += 1
        logger.warning("Fixed Unicode encoding issues in content")
    
    # Remove excessive repeated characters (spam detection)
    before_spam_removal = len(content)
    content = re.sub(rf'(.)\1{{{SPAM_REPEAT_THRESHOLD},}}', r'\1\1\1', content)
    if len(content) < before_spam_removal:
        warning_count += 1
        logger.warning("Removed spam-like repeated characters")
    
    # Remove potential XSS content
    content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.IGNORECASE | re.DOTALL)
    content = re.sub(r'javascript:', '', content, flags=re.IGNORECASE)
    
    # Clean up common Reddit formatting artifacts
    content = re.sub(r'\*\*(.*?)\*\*', r'\1', content)  # Remove bold markdown
    content = re.sub(r'\*(.*?)\*', r'\1', content)  # Remove italic markdown
    content = re.sub(r'~~(.*?)~~', r'\1', content)  # Remove strikethrough
    
    # Normalize whitespace
    content = re.sub(r'\s+', ' ', content)
    content = content.strip()
    
    return content, warning_count


def validate_comment_structure(comment_node: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate that required fields are present in comment node (Improvement #6).
    
    Args:
        comment_node: Raw comment data structure
        
    Returns:
        Dictionary with validation results
    """
    validation_result = {
        "is_valid": True,
        "errors": [],
        "warnings": []
    }
    
    # Check required fields
    for field in REQUIRED_COMMENT_FIELDS:
        if field not in comment_node:
            validation_result["errors"].append(f"Missing required field: {field}")
            validation_result["is_valid"] = False
    
    # Check nested required fields
    if comment_node.get("content"):
        content = comment_node["content"]
        if not any(content.get(fmt) for fmt in CONTENT_FORMATS):
            validation_result["warnings"].append("Comment content missing text in all formats")
    
    if comment_node.get("authorInfo") and not comment_node["authorInfo"].get("name"):
        validation_result["warnings"].append("Author info missing name")
    
    # Check for removed/deleted content
    if comment_node.get("isRemoved") or comment_node.get("isAdminTakedown"):
        validation_result["warnings"].append("Comment appears to be removed or taken down")
    
    return validation_result


def clean_reddit_post_updated(extracted_post: Dict[str, Any]) -> Tuple[Dict[str, Any], CleaningMetrics]:
    """
    Takes an extracted post object and returns a clean, minimal post schema with metrics.
    Enhanced with standardized date handling and metrics tracking.
    
    Args:
        extracted_post: Raw post data from Reddit API
        
    Returns:
        Tuple of (cleaned_post, cleaning_metrics)
    """
    start_time = time.time()
    metrics = CleaningMetrics()
    
    try:
        metrics.posts_processed = 1
        
        # Sanitize post content
        post_content = extracted_post.get("selftext", "")
        sanitized_content, content_warnings = sanitize_reddit_content(
            post_content, 
            max_length=MAX_POST_CONTENT_LENGTH
        )
        metrics.content_sanitization_warnings = content_warnings
        
        # Parse post date with standardized function
        post_date = datetime.now(tz=timezone.utc)
        created_utc = extracted_post.get("created_utc")
        if created_utc:
            try:
                post_date = parse_reddit_timestamp(created_utc)
            except Exception:
                metrics.date_parsing_errors += 1
        
        # Clean author name
        author = extracted_post.get("author", DEFAULT_AUTHOR)
        if author in DELETED_AUTHORS:
            author = DEFAULT_AUTHOR
        
        cleaned_post = {
            "post_id": extracted_post.get("id", ""),
            "post_title": extracted_post.get("title", ""),
            "post_content": sanitized_content,
            "post_author": author,
            "post_score": extracted_post.get("score", 0),
            "post_date": post_date,
            "subreddit": extracted_post.get("subreddit", ""),
            "permalink": extracted_post.get("permalink", ""),
            "url": extracted_post.get("url", ""),
        }
        
        metrics.processing_time_seconds = time.time() - start_time
        return cleaned_post, metrics
        
    except (KeyError, TypeError, ValueError) as data_error:
        logger.error(f"Data structure error in post cleaning: {data_error}")
        metrics.posts_dropped = 1
        metrics.validation_errors.append(f"Post data structure error: {str(data_error)}")
        metrics.processing_time_seconds = time.time() - start_time
        return {}, metrics
    except Exception as unexpected_error:
        logger.error(f"Unexpected error in post cleaning: {unexpected_error}")
        metrics.posts_dropped = 1
        metrics.validation_errors.append(f"Unexpected post cleaning error: {str(unexpected_error)}")
        metrics.processing_time_seconds = time.time() - start_time
        raise  # Re-raise unexpected errors for proper handling upstream


def clean_posts_comments_response(api_response: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], CleaningMetrics]:
    """
    Takes a posts/comments API response and returns a cleaned, nested comment tree with metrics.
    Enhanced with comprehensive error handling, validation, and metrics tracking.
    
    Args:
        api_response: Raw API response from Reddit posts/comments endpoint
        
    Returns:
        Tuple of (cleaned_comments_tree, cleaning_metrics)
    """
    start_time = time.time()
    metrics = CleaningMetrics()
    
    try:
        # Handle None or empty api_response with specific error handling
        if not api_response or not isinstance(api_response, dict):
            logger.warning("API response is None or not a dict")
            metrics.validation_errors.append("Invalid API response structure")
            metrics.processing_time_seconds = time.time() - start_time
            return [], metrics
    
        # Extract data object with null safety
        data = api_response.get("data")
        if not data or not isinstance(data, dict):
            logger.warning("API response data is None or not a dict")
            metrics.validation_errors.append("Invalid API response data structure")
            metrics.processing_time_seconds = time.time() - start_time
            return [], metrics
            
        # Extract comment forest with null safety
        comment_forest = data.get("commentForest")
        if not comment_forest or not isinstance(comment_forest, dict):
            logger.warning("Comment forest is None or not a dict")
            metrics.validation_errors.append("Invalid comment forest structure")
            metrics.processing_time_seconds = time.time() - start_time
            return [], metrics
        
        # Extract trees array with null safety
        trees = comment_forest.get("trees")
        if not trees or not isinstance(trees, list):
            logger.warning("Trees is None or not a list")
            metrics.validation_errors.append("Invalid trees structure")
            metrics.processing_time_seconds = time.time() - start_time
            return [], metrics
        
        logger.info(f"Processing {len(trees)} trees from comment forest")
        metrics.trees_processed = len(trees)
        
        # Build a dict of all comments keyed by id
        comments = {}
        
        for i, tree in enumerate(trees):
            try:
                # Validate tree object
                if not tree or not isinstance(tree, dict):
                    logger.warning(f"Tree {i} is None or not a dict, skipping")
                    metrics.comments_dropped += 1
                    continue
                
                # Skip "more comments" placeholders (they have node: null)
                node = tree.get("node")
                if not node or not isinstance(node, dict):
                    logger.warning(f"Tree {i} has None or invalid node, skipping")
                    metrics.comments_dropped += 1
                    continue
                
                # Integrate validation into cleaning pipeline (Improvement #6)
                validation_result = validate_comment_structure(node)
                if not validation_result["is_valid"]:
                    logger.warning(f"Invalid comment structure in tree {i}: {validation_result['errors']}")
                    metrics.validation_errors.extend(validation_result["errors"])
                    metrics.comments_dropped += 1
                    continue
                
                # Track validation warnings
                if validation_result["warnings"]:
                    metrics.validation_warnings.extend(validation_result["warnings"])
                
                # Extract comment ID with null safety
                comment_id = node.get("id")
                if not comment_id or not isinstance(comment_id, str):
                    logger.warning(f"Tree {i} node missing valid ID, skipping")
                    metrics.comments_dropped += 1
                    continue
        
                # Extract comment content with enhanced sanitization
                content_obj = node.get("content")
                content = ""
                content_warnings = 0
                if content_obj and isinstance(content_obj, dict):
                    raw_content = extract_comment_content(content_obj)
                    content, content_warnings = sanitize_reddit_content(raw_content)
                    metrics.content_sanitization_warnings += content_warnings
        
                # Extract author name with null safety
                author_info = node.get("authorInfo")
                author_name = DEFAULT_AUTHOR
                if author_info and isinstance(author_info, dict):
                    raw_author = author_info.get("name", "")
                    if isinstance(raw_author, str) and raw_author not in DELETED_AUTHORS:
                        author_name = raw_author
        
                # Handle deleted/removed comments
                is_removed = node.get("isRemoved", False)
                if is_removed or not content.strip():
                    content = DELETED_CONTENT_MARKER
        
                # Convert creation date with standardized parsing
                created_at = node.get("createdAt")
                comment_date = datetime.now(tz=timezone.utc)
                if created_at and isinstance(created_at, str):
                    try:
                        comment_date = parse_reddit_timestamp(created_at)
                    except Exception as date_error:
                        logger.warning(f"Date parsing error for comment {comment_id}: {date_error}")
                        metrics.date_parsing_errors += 1
                
                # Extract score with null safety
                score = node.get("score", 0)
                if not isinstance(score, (int, float)):
                    score = 0
                
                # Extract depth and parentId with null safety
                depth = tree.get("depth", 0)
                if not isinstance(depth, (int, float)):
                    depth = 0
                
                parent_id = tree.get("parentId")
                if parent_id and not isinstance(parent_id, str):
                    parent_id = None
                
                # Store cleaned comment
                comments[comment_id] = {
                    "id": comment_id,
                    "author": author_name,
                    "body": content,
                    "score": int(score),
                    "date": comment_date,
                    "depth": int(depth),
                    "parentId": parent_id,
                    "children": []
                }
                metrics.comments_processed += 1
                
            except (KeyError, TypeError, ValueError) as data_error:
                logger.error(f"Data structure error processing tree {i}: {data_error}")
                metrics.comments_dropped += 1
                metrics.validation_errors.append(f"Tree {i} data error: {str(data_error)}")
                continue
            except Exception as tree_error:
                logger.error(f"Unexpected error processing tree {i}: {tree_error}")
                metrics.comments_dropped += 1
                metrics.validation_errors.append(f"Tree {i} unexpected error: {str(tree_error)}")
                continue
        
        logger.info(f"Successfully processed {metrics.comments_processed} comments out of {metrics.trees_processed} trees")
    
        # Build nested structure by attaching children to parents
        roots = []
        for comment in comments.values():
            parent_id = comment["parentId"]
            if parent_id and parent_id in comments:
                comments[parent_id]["children"].append(comment)
            else:
                roots.append(comment)
    
        metrics.root_comments_found = len(roots)
        metrics.processing_time_seconds = time.time() - start_time
        
        logger.info(f"Built comment tree with {len(roots)} root comments")
        return roots, metrics
        
    except (KeyError, TypeError, ValueError) as data_error:
        logger.error(f"Data structure error in comments response: {data_error}")
        metrics.validation_errors.append(f"Comments response data error: {str(data_error)}")
        metrics.processing_time_seconds = time.time() - start_time
        return [], metrics
    except Exception as unexpected_error:
        logger.error(f"Unexpected error processing comments response: {unexpected_error}")
        traceback.print_exc()
        metrics.validation_errors.append(f"Unexpected comments processing error: {str(unexpected_error)}")
        metrics.processing_time_seconds = time.time() - start_time
        raise  # Re-raise unexpected errors for proper handling upstream


def extract_comment_content(content_obj: Dict[str, Any]) -> str:
    """
    Extract text content from Reddit comment content object.
    Enhanced with better format prioritization and error handling.
    
    Args:
        content_obj: Reddit comment content object
        
    Returns:
        Extracted text content
    """
    if not content_obj:
        return ""
    
    # Priority order: markdown > preview > html > empty
    for format_name in CONTENT_FORMATS:
        content = content_obj.get(format_name, "")
        if content and content.strip():
            # Clean HTML tags if present
            if format_name == "html":
                content = re.sub(r'<[^>]+>', '', content)
                content = content.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
                content = content.replace('&#39;', "'").replace('&quot;', '"')
            return content.strip()
    
    return ""


def clean_reddit_comment_tree_legacy(raw_comment_trees: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], CleaningMetrics]:
    """
    Legacy comment cleaner for backward compatibility with metrics support.
    Takes a Reddit comment 'forest' and returns a cleaned, nested comment tree.
    
    Args:
        raw_comment_trees: Raw comment tree data
        
    Returns:
        Tuple of (cleaned_comments, cleaning_metrics)
    """
    start_time = time.time()
    metrics = CleaningMetrics()
    
    if not raw_comment_trees:
        metrics.processing_time_seconds = time.time() - start_time
        return [], metrics
    
    try:
        # Build a dict of all comments keyed by id
        comments = {}
        for comment in raw_comment_trees:
            try:
                node = comment.get("node", comment)
                comment_id = node.get("id")
                
                if not comment_id:
                    metrics.comments_dropped += 1
                    continue
                
                # Enhanced content extraction and sanitization
                body_content = node.get("content", {}).get("markdown", "") or node.get("body", "")
                sanitized_body, content_warnings = sanitize_reddit_content(body_content)
                metrics.content_sanitization_warnings += content_warnings
                
                # Standardized date parsing
                comment_date = datetime.now(tz=timezone.utc)
                if "createdAt" in node and node["createdAt"]:
                    try:
                        comment_date = parse_reddit_timestamp(node["createdAt"])
                    except Exception:
                        metrics.date_parsing_errors += 1
                
                # Clean author
                author = node.get("authorInfo", {}).get("name", DEFAULT_AUTHOR)
                if author in DELETED_AUTHORS:
                    author = DEFAULT_AUTHOR
                    
                comments[comment_id] = {
                    "id": comment_id,
                    "author": author,
                    "body": sanitized_body,
                    "score": node.get("score", 0),
                    "date": comment_date,
                    "depth": comment.get("depth", 0),
                    "parentId": comment.get("parentId"),
                    "children": []
                }
                metrics.comments_processed += 1
                
            except (KeyError, TypeError, ValueError) as data_error:
                logger.error(f"Data structure error in legacy comment: {data_error}")
                metrics.comments_dropped += 1
                metrics.validation_errors.append(f"Legacy comment data error: {str(data_error)}")
                continue
            except Exception as comment_error:
                logger.error(f"Unexpected error in legacy comment: {comment_error}")
                metrics.comments_dropped += 1
                continue
        
        # Attach each comment to its parent's 'children'
        roots = []
        for comment in comments.values():
            parent_id = comment["parentId"]
            if parent_id and parent_id in comments:
                comments[parent_id]["children"].append(comment)
            else:
                roots.append(comment)
        
        metrics.root_comments_found = len(roots)
        metrics.processing_time_seconds = time.time() - start_time
        return roots, metrics
        
    except Exception as unexpected_error:
        logger.error(f"Unexpected error in legacy comment cleaning: {unexpected_error}")
        metrics.validation_errors.append(f"Legacy cleaning error: {str(unexpected_error)}")
        metrics.processing_time_seconds = time.time() - start_time
        raise


def build_post_with_comments(
    clean_post: Dict[str, Any], 
    clean_comments: List[Dict[str, Any]], 
    post_metrics: Optional[CleaningMetrics] = None,
    comment_metrics: Optional[CleaningMetrics] = None
) -> Tuple[Dict[str, Any], CleaningMetrics]:
    """
    Combine a cleaned post and its comments tree into a single structure with aggregated metrics.
    
    Args:
        clean_post: Cleaned post data
        clean_comments: Cleaned comments tree
        post_metrics: Optional metrics from post cleaning
        comment_metrics: Optional metrics from comment cleaning
        
    Returns:
        Tuple of (post_with_comments, aggregated_metrics)
    """
    # Handle case where clean_comments might be None
    if clean_comments is None:
        clean_comments = []
    
    post_with_comments = clean_post.copy()
    post_with_comments["comments"] = clean_comments
    
    # Aggregate metrics if provided
    combined_metrics = CleaningMetrics()
    if post_metrics:
        combined_metrics.posts_processed = post_metrics.posts_processed
        combined_metrics.posts_dropped = post_metrics.posts_dropped
        combined_metrics.processing_time_seconds += post_metrics.processing_time_seconds
        combined_metrics.validation_errors.extend(post_metrics.validation_errors)
        combined_metrics.validation_warnings.extend(post_metrics.validation_warnings)
        combined_metrics.date_parsing_errors += post_metrics.date_parsing_errors
        combined_metrics.content_sanitization_warnings += post_metrics.content_sanitization_warnings
    
    if comment_metrics:
        combined_metrics.comments_processed = comment_metrics.comments_processed
        combined_metrics.comments_dropped = comment_metrics.comments_dropped
        combined_metrics.processing_time_seconds += comment_metrics.processing_time_seconds
        combined_metrics.validation_errors.extend(comment_metrics.validation_errors)
        combined_metrics.validation_warnings.extend(comment_metrics.validation_warnings)
        combined_metrics.date_parsing_errors += comment_metrics.date_parsing_errors
        combined_metrics.content_sanitization_warnings += comment_metrics.content_sanitization_warnings
        combined_metrics.trees_processed = comment_metrics.trees_processed
        combined_metrics.root_comments_found = comment_metrics.root_comments_found
    
    return post_with_comments, combined_metrics 