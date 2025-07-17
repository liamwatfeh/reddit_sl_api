"""
Cell-based data extraction functions for Reddit subreddit/search responses.
Handles the complex CellGroup structure from Reddit's subreddit/search API.
"""

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