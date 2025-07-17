"""
Flat object data extraction functions for Reddit posts/search-posts responses.
Handles the simple SubredditPost structure from Reddit's search API.
"""

from datetime import datetime
from typing import Dict, Any, List, Optional


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
    content = extract_post_content(post_item.get("content"))
    
    # Extract author name
    author_info = post_item.get("authorInfo", {})
    author_name = normalize_author_name(author_info)
    
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
    
    # Generate permalink and URL if missing
    if post_data["id"] and post_data["subreddit"] and not post_data["permalink"]:
        post_data["permalink"] = f"/r/{post_data['subreddit']}/comments/{post_data['id']}/"
        post_data["url"] = f"https://www.reddit.com{post_data['permalink']}"
    
    # Return post only if we have essential data
    return post_data if post_data["title"] and post_data["id"] else None


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
                content = content.replace('&#39;', "'").replace('&quot;', '"')
            return content.strip()
    
    return ""


def normalize_author_name(author_info) -> str:
    """
    Extract author name from different author formats
    """
    if not author_info:
        return ""
    
    # Handle both direct name and nested authorInfo structures
    if isinstance(author_info, str):
        name = author_info
    else:
        name = author_info.get("name", "")
    
    # Remove u/ prefix if present
    if name.startswith("u/"):
        name = name[2:]
    
    return name if name and name not in ["[deleted]", "[removed]"] else ""


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