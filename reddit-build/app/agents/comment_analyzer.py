"""
AI-powered comment analysis agent using Pydantic AI.
Provides sentiment analysis, theme extraction, and purchase intent detection for Reddit comments.
"""

import asyncio
import json
import logging
from typing import List, Dict, Any, Optional, Tuple, Union
from datetime import datetime
from dataclasses import dataclass

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.models import Model
from pydantic_ai.models.google import GoogleModel, GoogleProvider
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

from app.core.config import get_settings
from app.models.schemas import (
    CommentAnalysis, 
    PostWithComments, 
    AnalysisMetadata, 
    UnifiedAnalysisResponse,
    SubredditAnalysisRequest,
    SearchAnalysisRequest
)

logger = logging.getLogger(__name__)


class CommentInsight(BaseModel):
    """Structured output model for individual comment analysis."""
    
    sentiment: str = Field(description="Sentiment: 'positive', 'negative', or 'neutral'")
    theme: str = Field(description="Main theme or topic of the comment")
    purchase_intent: str = Field(description="Purchase intent: 'high', 'medium', 'low', or 'none'")
    confidence: float = Field(description="Analysis confidence (0.0-1.0)", ge=0.0, le=1.0)


class ContextualAnalysisResult(BaseModel):
    """Enhanced result with conversation context and thread insights."""
    
    relevant_comments: List[Dict[str, Any]] = Field(default=[], description="Comments with thread context and analysis")
    thread_insights: List[str] = Field(default=[], description="Key insights from conversation flow")
    filtering_summary: str = Field(default="", description="Detailed explanation of filtering decisions")
    conversation_quality: float = Field(default=0.5, description="Thread coherence score 0-1")
    total_comments_reviewed: int = Field(default=0, description="Total number of comments reviewed")


class PostAnalysisResult(BaseModel):
    """Analysis result for a single post and its comments."""
    
    post_id: str
    post_url: str
    analyzed_comments: List[CommentAnalysis]
    total_comments_processed: int
    relevant_comments_found: int
    processing_time_seconds: float
    error_messages: List[str] = []


@dataclass
class AnalysisContext:
    """Enhanced analysis context with JSON threading support."""
    system_prompt: str
    max_comments_per_post: int = 50
    preserve_threading: bool = True
    analyze_conversation_flow: bool = True
    include_thread_context: bool = True
    max_thread_depth: int = 10


class CommentAnalyzerAgent:
    """
    AI-powered agent for analyzing Reddit comments using full post context.
    Supports OpenAI, Gemini, and Claude models with intelligent filtering.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.primary_agent = self._create_primary_agent()
        self.fallback_agent = self._create_fallback_agent()
        
    def _create_primary_agent(self) -> Agent:
        """Create the primary AI agent for contextual analysis."""
        model = self._get_model(self.settings.primary_ai_model)
        
        # Generic system prompt - the specific filtering will come from user's system_prompt
        system_prompt = """
        You are an expert social media analyst specializing in Reddit comment analysis.
        You will receive a complete Reddit post with its comments and specific analysis criteria.
        
        Your task:
        1. Read the post title and content to understand the discussion context
        2. Apply the specific filtering criteria provided by the user
        3. Only analyze comments that match the user's criteria
        4. Provide structured analysis for relevant comments only
        5. If no comments match the criteria, return an empty list
        
        Always consider the full context of the post when determining comment relevance.
        """
        
        return Agent(
            model=model,
            result_type=ContextualAnalysisResult,
            system_prompt=system_prompt,
        )
    
    def _count_threaded_comments(self, comments: List[Dict]) -> int:
        """Recursively count all comments including replies."""
        total = len(comments)
        for comment in comments:
            if comment.get("children"):
                total += self._count_threaded_comments(comment["children"])
        return total

    def _calculate_max_depth(self, comments: List[Dict]) -> int:
        """Calculate maximum thread depth."""
        if not comments:
            return 0
        
        max_depth = 0
        for comment in comments:
            current_depth = comment.get("depth", 0)
            if comment.get("children"):
                child_depth = self._calculate_max_depth(comment["children"])
                current_depth = max(current_depth, child_depth)
            max_depth = max(max_depth, current_depth)
        
        return max_depth
    
    def _validate_post_structure(self, post: Dict[str, Any]) -> bool:
        """Validate post has required structure for analysis."""
        required_fields = ["id", "title", "comments"]
        return all(field in post for field in required_fields)
    
    def _create_fallback_agent(self) -> Agent:
        """Create fallback agent with different model."""
        fallback_model_name = (
            "gpt-4" if self.settings.primary_ai_model.startswith("gemini") 
            else "gemini-2.5-pro"
        )
        model = self._get_model(fallback_model_name)
        
        return Agent(
            model=model,
            result_type=ContextualAnalysisResult,
            system_prompt="You are a social media analyst. Analyze Reddit posts and comments based on specific criteria.",
        )
    
    def _get_model(self, model_name: str) -> Model:
        """Get the appropriate AI model instance."""
        if model_name.startswith("gpt"):
            if not self.settings.openai_api_key:
                raise ValueError("OpenAI API key not configured")
            provider = OpenAIProvider(api_key=self.settings.openai_api_key)
            return OpenAIModel(model_name, provider=provider)
        
        elif model_name.startswith("gemini"):
            if not self.settings.gemini_api_key:
                raise ValueError("Gemini API key not configured")
            provider = GoogleProvider(api_key=self.settings.gemini_api_key)
            return GoogleModel(model_name, provider=provider)
        
        else:
            raise ValueError(f"Unsupported model: {model_name}")
    
    def _format_comments_for_analysis(self, comments: List[Dict[str, Any]], max_comments: int = 50) -> str:
        """Format comments into a readable structure for AI analysis."""
        if not comments:
            return "No comments available."
        
        # Limit comments to prevent token overflow
        comments_to_include = comments[:max_comments]
        
        formatted_comments = []
        for i, comment in enumerate(comments_to_include, 1):
            comment_text = comment.get('body', '').strip()
            author = comment.get('author', 'unknown')
            score = comment.get('score', 0)
            
            # Skip deleted/removed comments
            if comment_text in ['[deleted]', '[removed]', '']:
                continue
                
            formatted_comments.append(f"""
Comment {i}:
Author: {author}
Score: {score}
Text: {comment_text}
""")
        
        return "\n".join(formatted_comments) if formatted_comments else "No valid comments to analyze."
    
    def _parse_contextual_analysis(
        self, 
        analysis_result: ContextualAnalysisResult, 
        post_with_comments: Dict[str, Any]
    ) -> List[CommentAnalysis]:
        """Convert enhanced AI analysis result with conversation context to CommentAnalysis objects."""
        comment_analyses = []
        
        # Log thread insights if available
        if hasattr(analysis_result, 'thread_insights') and analysis_result.thread_insights:
            logger.info(f"Thread insights detected: {', '.join(analysis_result.thread_insights[:3])}...")
        
        # Log conversation quality if available  
        if hasattr(analysis_result, 'conversation_quality'):
            logger.info(f"Conversation quality score: {analysis_result.conversation_quality:.2f}")
        
        for relevant_comment in analysis_result.relevant_comments:
            try:
                # Extract analysis data with enhanced context
                comment_text = relevant_comment.get("text", "") or relevant_comment.get("quote", "")
                
                # Build enhanced comment analysis with thread context
                comment_analysis = CommentAnalysis(
                    # Core fields
                    post_id=post_with_comments.get("id", "unknown"),
                    post_url=post_with_comments.get("url", "") or f"https://www.reddit.com{post_with_comments.get('permalink', '')}",
                    quote=comment_text[:500],  # Respect max quote length
                    sentiment=relevant_comment.get("sentiment", "neutral"),
                    theme=relevant_comment.get("theme", "general discussion"),
                    purchase_intent=relevant_comment.get("purchase_intent", "none"),
                    date=datetime.now(),
                    source="reddit",
                    
                    # Enhanced context fields (populated from AI analysis)
                    parent_comment_id=relevant_comment.get("parent_comment_id"),
                    thread_depth=relevant_comment.get("thread_depth"),
                    thread_position=relevant_comment.get("thread_position"),
                    children_count=relevant_comment.get("children_count"),
                    conversation_context=relevant_comment.get("conversation_context", "")[:200] if relevant_comment.get("conversation_context") else None,
                    thread_context=relevant_comment.get("thread_context", "")[:300] if relevant_comment.get("thread_context") else None,
                    confidence_score=relevant_comment.get("confidence_score"),
                    conversation_quality=getattr(analysis_result, 'conversation_quality', None)
                )
                comment_analyses.append(comment_analysis)
                
                # Log context information if available
                if relevant_comment.get("thread_context"):
                    logger.debug(f"Comment with context: {comment_text[:50]}... (responds to: {relevant_comment.get('thread_context', 'unknown')[:30]}...)")
                
            except Exception as e:
                logger.error(f"Error parsing comment analysis: {e}")
                logger.error(f"Problematic comment data: {relevant_comment}")
                continue
        
        logger.info(f"Parsed {len(comment_analyses)} relevant comments from enhanced AI analysis")
        return comment_analyses
    
    async def analyze_full_post_context(
        self,
        post_with_comments: Dict[str, Any],
        context: AnalysisContext
    ) -> List[CommentAnalysis]:
        """
        Analyze complete post with JSON threaded structure preserving conversation flow.
        
        Args:
            post_with_comments: Complete post with threaded comments structure
            context: Enhanced analysis context with JSON threading support
            
        Returns:
            List of CommentAnalysis objects for relevant comments with context
        """
        # Validate post structure
        if not self._validate_post_structure(post_with_comments):
            logger.warning("Post missing required fields for analysis")
            return []
            
        if not post_with_comments.get("comments"):
            logger.info("No comments to analyze for this post")
            return []
        
        try:
            # Log post analysis details
            post_id = post_with_comments.get("id", "unknown")
            post_title = post_with_comments.get("title", "No title")
            total_comments = self._count_threaded_comments(post_with_comments["comments"])
            max_depth = self._calculate_max_depth(post_with_comments["comments"])
            
            logger.info(f"Starting JSON context analysis for post {post_id}")
            logger.info(f"Post title: {post_title[:50]}...")
            logger.info(f"Comment structure: {total_comments} total comments, max depth: {max_depth}")
            
            # Build enhanced prompt with complete JSON structure
            analysis_prompt = f"""
{context.system_prompt}

You are analyzing a Reddit discussion with complete conversation threading.
The data preserves parent-child relationships and conversation flow.

COMPLETE POST WITH THREADED COMMENTS:
```json
{json.dumps(post_with_comments, indent=2, default=str, ensure_ascii=False)}
```

ENHANCED ANALYSIS INSTRUCTIONS:
1. Read the post title and content to understand the discussion topic
2. Analyze the COMPLETE comment thread structure including:
   - Parent-child relationships (parentId and children arrays)
   - Conversational context and flow
   - Thread depth and positioning
   - What each comment is responding to

3. Pay special attention to conversation flow:
   - "I agree" refers to the parent comment
   - "That's wrong" responds to a specific statement
   - Follow reply chains to understand context

4. For filtering, consider:
   - Direct mentions of your criteria
   - Indirect references in conversation context
   - Comments that become relevant due to what they're responding to

5. For each relevant comment, analyze:
   - The comment text and its conversational context
   - What it's responding to (parent comment context)
   - Its position in the discussion thread
   - Sentiment considering conversation flow

6. Return insights about:
   - Thread quality and coherence
   - Key conversation flows
   - Why comments were included/excluded

CRITICAL - REQUIRED OUTPUT FORMAT:
You MUST return a ContextualAnalysisResult with these exact fields:

For each relevant comment in relevant_comments array, provide an object with these EXACT fields:
{{
  "text": "the full comment text",
  "sentiment": "positive|negative|neutral",
  "theme": "main theme or topic discussed",
  "purchase_intent": "high|medium|low|none",
  "parent_comment_id": "ID of parent comment if applicable",
  "thread_depth": depth_number_in_conversation,
  "thread_position": position_among_siblings,
  "children_count": number_of_direct_replies,
  "conversation_context": "brief summary of what this comment responds to",
  "thread_context": "summary of conversation flow leading to this comment",
  "confidence_score": confidence_score_0_to_1
}}

Required ContextualAnalysisResult structure:
{{
  "relevant_comments": [array of comment objects with fields above],
  "thread_insights": ["insight1", "insight2", "insight3"],
  "filtering_summary": "detailed explanation of why comments were included/excluded",
  "conversation_quality": quality_score_0_to_1,
  "total_comments_reviewed": total_number_of_comments_in_post
}}

MANDATORY: Return at least one comment if ANY comments exist, unless absolutely none match criteria.
If no comments match your criteria, return empty relevant_comments array but still provide other fields.
"""

            logger.info(f"JSON prompt prepared, length: {len(analysis_prompt)} characters")
            
            # Execute analysis with primary agent
            try:
                logger.info("Calling primary agent for analysis...")
                result = await self.primary_agent.run(analysis_prompt, message_history=[])
                logger.info(f"Raw AI response received: {result}")
                logger.info(f"Raw AI response type: {type(result)}")
                logger.info(f"Raw AI response data: {result.data}")
                logger.info(f"Raw AI response data type: {type(result.data)}")
                analysis_result = result.data
                logger.info("Primary agent analysis completed successfully")
                logger.info(f"AI Response Debug - Relevant comments count: {len(analysis_result.relevant_comments)}")
                logger.info(f"AI Response Debug - Thread insights: {len(analysis_result.thread_insights)}")
                logger.info(f"AI Response Debug - Total reviewed: {analysis_result.total_comments_reviewed}")
                logger.info(f"AI Response Debug - Filtering summary: {analysis_result.filtering_summary[:200]}...")
                if analysis_result.relevant_comments:
                    logger.info(f"AI Response Debug - First comment sample: {analysis_result.relevant_comments[0]}")
                else:
                    logger.warning("AI Response Debug - NO RELEVANT COMMENTS RETURNED by AI")
                
            except Exception as e:
                logger.error(f"Primary agent failed with error: {type(e).__name__}: {e}")
                logger.error(f"Full error details: {str(e)}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                logger.warning(f"Primary agent failed, trying fallback: {e}")
                result = await self.fallback_agent.run(analysis_prompt, message_history=[])
                analysis_result = result.data
                logger.info("Fallback agent analysis completed")
                logger.info(f"Fallback AI Response Debug - Relevant comments count: {len(analysis_result.relevant_comments)}")
                logger.info(f"Fallback AI Response Debug - Total reviewed: {analysis_result.total_comments_reviewed}")
                if analysis_result.relevant_comments:
                    logger.info(f"Fallback AI Response Debug - First comment sample: {analysis_result.relevant_comments[0]}")
                else:
                    logger.warning("Fallback AI Response Debug - NO RELEVANT COMMENTS RETURNED by fallback AI")
            
            # Parse results with enhanced context
            comment_analyses = self._parse_contextual_analysis(analysis_result, post_with_comments)
            
            # Log detailed results
            logger.info(f"JSON context analysis complete: {len(comment_analyses)} relevant comments found")
            logger.info(f"Thread insights: {len(analysis_result.thread_insights)} conversation flows identified")
            logger.info(f"Filtering summary: {analysis_result.filtering_summary}")
            
            return comment_analyses
            
        except Exception as e:
            logger.error(f"JSON context analysis failed: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    async def analyze_post_comments(
        self,
        post: Dict[str, Any],
        context: AnalysisContext
    ) -> PostAnalysisResult:
        """
        Analyze all comments in a post using full context approach.
        
        Args:
            post: Post with comments to analyze
            context: Analysis context
            
        Returns:
            PostAnalysisResult with all analysis results
        """
        start_time = datetime.now()
        
        # Get post info for logging
        post_id = post.get("id", "unknown")
        comments_list = post.get("comments", [])
        total_comments = len(comments_list) if isinstance(comments_list, list) else 0
        
        logger.info(f"Starting full context analysis for post {post_id}")
        logger.info(f"Post title: {post.get('title', 'No title')}")
        logger.info(f"Total comments available: {total_comments}")
        
        # Use full context analysis instead of individual comment processing
        analyzed_comments = await self.analyze_full_post_context(post, context)
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        result = PostAnalysisResult(
            post_id=post_id,
            post_url=post.get("url", ""),
            analyzed_comments=analyzed_comments,
            total_comments_processed=min(total_comments, context.max_comments_per_post),
            relevant_comments_found=len(analyzed_comments),
            processing_time_seconds=processing_time,
            error_messages=[]
        )
        
        logger.info(f"Post analysis complete: {len(analyzed_comments)} relevant comments from {total_comments} total")
        return result
    
    async def analyze_multiple_posts(
        self,
        posts: List[Dict[str, Any]], 
        context: AnalysisContext
    ) -> List[PostAnalysisResult]:
        """
        Analyze comments across multiple posts using enhanced JSON context.
        
        Args:
            posts: List of posts with threaded comments to analyze
            context: Enhanced analysis context with JSON threading support
            
        Returns:
            List of PostAnalysisResult objects with conversation insights
        """
        logger.info(f"Starting enhanced JSON context analysis of {len(posts)} posts")
        logger.info(f"Context settings: threading={context.preserve_threading}, flow_analysis={context.analyze_conversation_flow}")
        
        # Log post structure summary
        total_comments = sum(self._count_threaded_comments(post.get("comments", [])) for post in posts)
        max_depth = max((self._calculate_max_depth(post.get("comments", [])) for post in posts), default=0)
        logger.info(f"Dataset: {total_comments} total comments across {len(posts)} posts, max thread depth: {max_depth}")
        
        # Process posts concurrently with rate limiting
        semaphore = asyncio.Semaphore(3)  # Limit concurrent post processing
        
        async def analyze_single_post(post: Dict[str, Any]) -> PostAnalysisResult:
            async with semaphore:
                # Validate post structure before analysis
                if not self._validate_post_structure(post):
                    logger.warning(f"Post {post.get('id', 'unknown')} has invalid structure, skipping")
                    return PostAnalysisResult(
                        post_id=post.get("id", "unknown"),
                        post_url=post.get("url", ""),
                        analyzed_comments=[],
                        total_comments_processed=0,
                        relevant_comments_found=0,
                        processing_time_seconds=0.0,
                        error_messages=["Invalid post structure"]
                    )
                return await self.analyze_post_comments(post, context)
        
        tasks = [analyze_single_post(post) for post in posts]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle any exceptions
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, PostAnalysisResult):
                final_results.append(result)
            else:
                logger.error(f"Post analysis failed for post {i}: {result}")
                # Create error result
                error_result = PostAnalysisResult(
                    post_id=posts[i].get("id", "unknown") if i < len(posts) else "unknown",
                    post_url=posts[i].get("url", "") if i < len(posts) else "unknown",
                    analyzed_comments=[],
                    total_comments_processed=0,
                    relevant_comments_found=0,
                    processing_time_seconds=0.0,
                    error_messages=[f"Post analysis failed: {str(result)}"]
                )
                final_results.append(error_result)
        
        logger.info(f"Completed full context analysis of {len(final_results)} posts")
        return final_results


class ConcurrentCommentAnalysisOrchestrator:
    """
    High-level orchestrator for the complete Reddit comment analysis pipeline.
    Coordinates data collection, AI analysis, and result aggregation.
    """
    
    def __init__(self):
        self.analyzer = CommentAnalyzerAgent()
        self.settings = get_settings()
        
    async def run_full_analysis(
        self,
        posts: List[Dict[str, Any]],
        analysis_request: Union[SubredditAnalysisRequest, SearchAnalysisRequest],
        collection_metadata: Dict[str, Any] = None
    ) -> UnifiedAnalysisResponse:
        """
        Execute the complete analysis pipeline from posts to final response.
        
        Args:
            posts: List of posts with comments to analyze
            analysis_request: Original request parameters
            collection_metadata: Metadata from data collection phase
            
        Returns:
            UnifiedAnalysisResponse with all analyses and metadata
        """
        start_time = datetime.now()
        
        logger.info(f"Starting full context analysis pipeline for {len(posts)} posts")
        logger.info(f"User system prompt: {analysis_request.system_prompt[:100]}...")
        
        # Prepare analysis context with user's system prompt
        context = AnalysisContext(
            system_prompt=analysis_request.system_prompt,  # ✅ User's prompt used!
            max_comments_per_post=50
        )
        
        # Run AI analysis across all posts with full context
        analysis_results = await self.analyzer.analyze_multiple_posts(posts, context)
        
        # Calculate metadata
        collection_method = "subreddit" if isinstance(analysis_request, SubredditAnalysisRequest) else "search"
        processing_time = (datetime.now() - start_time).total_seconds()
        
        # Use ResultsStacker to build final response
        stacker = ResultsStacker()
        unified_response = stacker.stack_results(
            analysis_results=analysis_results,
            posts=posts,
            processing_time=processing_time,
            collection_metadata=collection_metadata or {},
            model_used=analysis_request.model,
            collection_method=collection_method
        )
        
        logger.info(f"Full context analysis pipeline completed. Found {len(unified_response.comment_analyses)} relevant comments")
        return unified_response


class ResultsStacker:
    """
    Combines individual analysis results into a unified response.
    Handles aggregation, metadata calculation, and response formatting.
    """
    
    def stack_results(
        self,
        analysis_results: List[PostAnalysisResult],
        posts: List[Dict[str, Any]],
        processing_time: float,
        collection_metadata: Dict[str, Any],
        model_used: str,
        collection_method: str
    ) -> UnifiedAnalysisResponse:
        """
        Stack all analysis results into a unified response.
        
        Args:
            analysis_results: Results from analyzing each post
            posts: Original posts that were analyzed
            processing_time: Total processing time in seconds
            collection_metadata: Metadata from data collection
            model_used: AI model used for analysis
            collection_method: "subreddit" or "search"
            
        Returns:
            UnifiedAnalysisResponse with aggregated results
        """
        # Aggregate all comment analyses
        all_comment_analyses = []
        total_comments_found = 0
        total_api_calls = 0
        total_errors = 0
        
        for result in analysis_results:
            all_comment_analyses.extend(result.analyzed_comments)
            total_comments_found += result.total_comments_processed
            total_errors += len(result.error_messages)
        
        # Calculate posts with no relevant comments (irrelevant posts)
        irrelevant_posts = sum(1 for result in analysis_results if len(result.analyzed_comments) == 0)
        
        # Count total comments across all posts
        actual_total_comments = sum(len(post["comments"]) for post in posts)
        
        # Extract API calls from collection metadata
        api_calls_made = (
            collection_metadata.get("api_calls_made", 0) +  # Reddit API calls
            len(analysis_results)  # AI API calls (one per post for full context analysis)
        )
        
        # Calculate enhanced thread analysis metrics
        analyzer = CommentAnalyzerAgent()  # Access helper methods
        
        # Calculate thread metrics across all posts
        max_thread_depth = 0
        total_threaded_comments = 0
        thread_depths = []
        conversation_threads = 0
        conversation_qualities = []
        thread_insights_count = 0
        
        for post in posts:
            if post.get("comments"):
                post_max_depth = analyzer._calculate_max_depth(post["comments"])
                post_total_comments = analyzer._count_threaded_comments(post["comments"])
                
                max_thread_depth = max(max_thread_depth, post_max_depth)
                total_threaded_comments += post_total_comments
                
                if post_total_comments > 0:
                    thread_depths.append(post_max_depth)
                    conversation_threads += 1
        
        # Extract conversation quality scores from comment analyses
        for comment in all_comment_analyses:
            if comment.conversation_quality is not None:
                conversation_qualities.append(comment.conversation_quality)
        
        # Count thread insights from analysis results
        thread_insights_count = sum(
            len(getattr(result, 'thread_insights', [])) 
            for result in analysis_results 
            if hasattr(result, 'analyzed_comments')
        )
        
        # Build enhanced metadata
        metadata = AnalysisMetadata(
            # Core metrics
            total_posts_analyzed=len(posts),
            total_comments_found=actual_total_comments,
            relevant_comments_extracted=len(all_comment_analyses),
            irrelevant_posts=irrelevant_posts,
            analysis_timestamp=datetime.now(),
            processing_time_seconds=processing_time,
            model_used=model_used,
            api_calls_made=api_calls_made,
            collection_method=collection_method,
            cell_parsing_errors=collection_metadata.get("cell_parsing_errors", 0),
            
            # Enhanced thread analysis metrics
            max_thread_depth=max_thread_depth if max_thread_depth > 0 else None,
            total_threaded_comments=total_threaded_comments if total_threaded_comments > 0 else None,
            average_thread_depth=sum(thread_depths) / len(thread_depths) if thread_depths else None,
            conversation_threads_analyzed=conversation_threads if conversation_threads > 0 else None,
            thread_insights_generated=thread_insights_count if thread_insights_count > 0 else None,
            average_conversation_quality=sum(conversation_qualities) / len(conversation_qualities) if conversation_qualities else None,
            json_context_analysis_used=True  # Since we're using enhanced JSON context analysis
        )
        
        # Create unified response
        response = UnifiedAnalysisResponse(
            comment_analyses=all_comment_analyses,
            metadata=metadata
        )
        
        logger.info(f"Results stacked: {len(all_comment_analyses)} comments from {len(posts)} posts")
        return response


# Singleton instances
_comment_analyzer_agent = None
_orchestrator = None

def get_comment_analyzer() -> CommentAnalyzerAgent:
    """Get singleton instance of comment analyzer agent."""
    global _comment_analyzer_agent
    if _comment_analyzer_agent is None:
        _comment_analyzer_agent = CommentAnalyzerAgent()
    return _comment_analyzer_agent

def get_orchestrator() -> ConcurrentCommentAnalysisOrchestrator:
    """Get singleton instance of analysis orchestrator."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = ConcurrentCommentAnalysisOrchestrator()
    return _orchestrator
