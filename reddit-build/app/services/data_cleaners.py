"""
Universal data cleaning functions for Reddit posts and comments.
Works with both cell-based and flat object extraction formats.
"""

from datetime import datetime
from typing import Dict, Any, List, Optional
import re
import json
import traceback


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


def clean_posts_comments_response(api_response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Takes a posts/comments API response and returns a cleaned, nested comment tree.
    Handles the commentForest.trees structure from the posts/comments endpoint.
    Enhanced with comprehensive null safety checks.
    """
    try:
        # Handle None or empty api_response
        if not api_response or not isinstance(api_response, dict):
            print("API response is None or not a dict")
            return []
    
        # Extract data object with null safety
        data = api_response.get("data")
        if not data or not isinstance(data, dict):
            print("API response data is None or not a dict")
            return []
            
        # Extract comment forest with null safety
        comment_forest = data.get("commentForest")
        if not comment_forest or not isinstance(comment_forest, dict):
            print("Comment forest is None or not a dict")
            return []
        
        # Extract trees array with null safety
        trees = comment_forest.get("trees")
        if not trees or not isinstance(trees, list):
            print("Trees is None or not a list")
            return []
        
        print(f"Processing {len(trees)} trees from comment forest")
        
        # Build a dict of all comments keyed by id
        comments = {}
        processed_count = 0
        
        for i, tree in enumerate(trees):
            try:
                # Validate tree object
                if not tree or not isinstance(tree, dict):
                    print(f"Tree {i} is None or not a dict, skipping")
                    continue
                
                # Skip "more comments" placeholders (they have node: null)
                node = tree.get("node")
                if not node or not isinstance(node, dict):
                    print(f"Tree {i} has None or invalid node, skipping")
                    continue
                
                # Extract comment ID with null safety
                comment_id = node.get("id")
                if not comment_id or not isinstance(comment_id, str):
                    print(f"Tree {i} node missing valid ID, skipping")
                    continue
        
                # Extract comment content with null safety
                content_obj = node.get("content")
                if content_obj and isinstance(content_obj, dict):
                    content = extract_comment_content(content_obj)
                else:
                    content = ""
        
                # Extract author name with null safety
                author_info = node.get("authorInfo")
                author_name = ""
                if author_info and isinstance(author_info, dict):
                    author_name = author_info.get("name", "")
                    if not isinstance(author_name, str):
                        author_name = ""
        
                # Handle deleted/removed comments
                is_removed = node.get("isRemoved", False)
                if is_removed or not content.strip():
                    content = "[deleted]"
        
                # Convert creation date with null safety
                created_at = node.get("createdAt")
                comment_date = datetime.utcnow()
                if created_at and isinstance(created_at, str):
                    try:
                        comment_date = datetime.fromisoformat(created_at.replace("+0000", "+00:00"))
                    except Exception as date_error:
                        print(f"Date parsing error for comment {comment_id}: {date_error}")
                        pass
                
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
                    "author": author_name if author_name and author_name not in ["[deleted]", "[removed]"] else "unknown",
                    "body": content,
                    "score": int(score),
                    "date": comment_date,
                    "depth": int(depth),
                    "parentId": parent_id,
                    "children": []
                }
                processed_count += 1
                
            except Exception as tree_error:
                print(f"Error processing tree {i}: {tree_error}")
                continue
        
        print(f"Successfully processed {processed_count} comments out of {len(trees)} trees")
    
        # Build nested structure by attaching children to parents
        roots = []
        for comment in comments.values():
            parent_id = comment["parentId"]
            if parent_id and parent_id in comments:
                comments[parent_id]["children"].append(comment)
            else:
                roots.append(comment)
    
        print(f"Built comment tree with {len(roots)} root comments")
        return roots
        
    except Exception as e:
        # Log error and return empty list instead of None
        print(f"Error processing comments response: {e}")
        traceback.print_exc()
        return []


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
    # Handle case where clean_comments might be None
    if clean_comments is None:
        clean_comments = []
    
    post_with_comments = clean_post.copy()
    post_with_comments["comments"] = clean_comments
    return post_with_comments


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


def sanitize_reddit_content(content: str) -> str:
    """
    Sanitize Reddit content for safe processing
    """
    if not content:
        return ""
    
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
    
    return content 