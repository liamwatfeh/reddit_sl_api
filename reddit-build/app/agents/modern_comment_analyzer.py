"""
Modern AI-powered comment analysis using OpenAI's native structured outputs.
Replaces the problematic Pydantic AI validation approach.
"""

import asyncio
import json
import logging
from typing import List, Dict, Any, Optional, Tuple, Union
from datetime import datetime
from dataclasses import dataclass

import openai
from pydantic import BaseModel, Field

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


class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle datetime objects."""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


class CommentAnalysisSchema(BaseModel):
    """Schema for individual comment analysis - for OpenAI structured outputs."""
    text: str = Field(description="The full comment text")
    sentiment: str = Field(description="Sentiment: positive, negative, or neutral")
    theme: str = Field(description="Main theme or topic discussed")
    purchase_intent: str = Field(description="Purchase intent: high, medium, low, or none")
    parent_comment_id: Optional[str] = Field(description="ID of parent comment if applicable")
    thread_depth: int = Field(description="Depth in conversation thread")
    thread_position: int = Field(description="Position among sibling comments")
    children_count: int = Field(description="Number of direct replies")
    conversation_context: str = Field(description="Brief summary of what this comment responds to")
    thread_context: str = Field(description="Summary of conversation flow leading to this comment")
    confidence_score: float = Field(description="Analysis confidence 0.0-1.0")


class ContextualAnalysisSchema(BaseModel):
    """Schema for complete analysis result - for OpenAI structured outputs."""
    relevant_comments: List[CommentAnalysisSchema] = Field(description="Comments with thread context and analysis")
    thread_insights: List[str] = Field(description="Key insights from conversation flow")
    filtering_summary: str = Field(description="Detailed explanation of filtering decisions")
    conversation_quality: float = Field(description="Thread coherence score 0-1")
    total_comments_reviewed: int = Field(description="Total number of comments reviewed")


@dataclass
class AnalysisContext:
    """Context for comment analysis with conversation threading support."""
    
    system_prompt: str
    max_comments: int = 50
    preserve_threading: bool = True
    analyze_conversation_flow: bool = True
    include_thread_context: bool = True
    max_thread_depth: int = 10


class PostAnalysisResult(BaseModel):
    """Individual post analysis result with enhanced context."""
    
    post_id: str
    comment_analyses: List[CommentAnalysis]
    thread_insights: List[str]
    total_comments_found: int
    relevant_comments_extracted: int
    conversation_quality: float
    processing_time_seconds: float
    analysis_metadata: AnalysisMetadata


class ModernCommentAnalyzer:
    """
    Modern comment analyzer using OpenAI's native structured outputs.
    Replaces problematic Pydantic AI approach.
    """
    
    def __init__(self):
        self.settings = get_settings()
        # Initialize OpenAI client directly
        self.openai_client = openai.AsyncOpenAI(api_key=self.settings.openai_api_key)
        
    async def analyze_full_post_context(
        self, 
        post_with_comments: Dict[str, Any], 
        context: AnalysisContext
    ) -> Tuple[List[CommentAnalysis], List[str], float]:
        """
        Analyze a complete post with its threaded comments using OpenAI structured outputs.
        
        Args:
            post_with_comments: Complete post data with nested comment structure
            context: Analysis context with user criteria
            
        Returns:
            Tuple of (comment_analyses, thread_insights, conversation_quality)
        """
        try:
            logger.info("Starting modern JSON context analysis")
            
            # Validate post structure
            if not self._validate_post_structure(post_with_comments):
                logger.warning("Invalid post structure, skipping analysis")
                return [], [], 0.0
            
            post_id = post_with_comments.get("id", "unknown")
            post_title = post_with_comments.get("title", "No title")
            comments_list = post_with_comments.get("comments", [])
            
            logger.info(f"Analyzing post: {post_id}")
            logger.info(f"Post title: {post_title}")
            logger.info(f"Total comments in structure: {len(comments_list)}")
            
            total_threaded_comments = self._count_threaded_comments(comments_list)
            max_depth = self._calculate_max_depth(comments_list)
            
            logger.info(f"Total threaded comments: {total_threaded_comments}")
            logger.info(f"Maximum thread depth: {max_depth}")
            
            # Prepare the analysis prompt for OpenAI
            analysis_prompt = f"""
Analyze this Reddit post and its comments based on the following criteria:

FILTERING CRITERIA: {context.system_prompt}

POST DATA:
{json.dumps(post_with_comments, indent=2, cls=DateTimeEncoder)}

ANALYSIS INSTRUCTIONS:
1. Read the post title and content to understand the discussion topic
2. Analyze the COMPLETE comment thread structure including parent-child relationships
3. Apply the filtering criteria to identify relevant comments
4. For each relevant comment, provide detailed analysis with conversation context
5. If no comments match criteria, return empty relevant_comments but provide other insights

CONVERSATION CONTEXT GUIDELINES:
- Consider what each comment is responding to
- Follow reply chains to understand context
- Analyze thread depth and positioning
- Note conversation quality and coherence

MANDATORY: You must return a structured response matching the required schema.
"""

            logger.info(f"Calling OpenAI with structured output schema")
            
            # Call OpenAI with structured outputs
            response = await self.openai_client.beta.chat.completions.parse(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert Reddit comment analyzer. Analyze posts and comments according to user criteria and return structured results."},
                    {"role": "user", "content": analysis_prompt}
                ],
                response_format=ContextualAnalysisSchema,
                temperature=0.1,
                max_tokens=4000
            )
            
            # Extract the structured result
            analysis_result = response.choices[0].message.parsed
            
            logger.info(f"OpenAI structured output received successfully")
            logger.info(f"Relevant comments found: {len(analysis_result.relevant_comments)}")
            logger.info(f"Thread insights: {len(analysis_result.thread_insights)}")
            logger.info(f"Total reviewed: {analysis_result.total_comments_reviewed}")
            
            # Log what OpenAI returned for debugging
            if analysis_result.relevant_comments:
                logger.info(f"First comment from OpenAI: {analysis_result.relevant_comments[0].dict()}")
            
            # Convert to our internal format
            comment_analyses = self._convert_to_comment_analysis(analysis_result, post_with_comments)
            
            logger.info(f"Converted {len(comment_analyses)} comments to CommentAnalysis format")
            
            return comment_analyses, analysis_result.thread_insights, analysis_result.conversation_quality
            
        except Exception as e:
            logger.error(f"Modern analysis failed: {type(e).__name__}: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return [], [], 0.0
    
    def _validate_post_structure(self, post_with_comments: Dict[str, Any]) -> bool:
        """Validate that the post has the required structure."""
        required_fields = ["id", "title", "comments"]
        return all(field in post_with_comments for field in required_fields)
    
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
    
    def _convert_to_comment_analysis(
        self, 
        analysis_result: ContextualAnalysisSchema, 
        post_with_comments: Dict[str, Any]
    ) -> List[CommentAnalysis]:
        """Convert OpenAI structured output to our CommentAnalysis format."""
        comment_analyses = []
        
        # Extract post info for required fields
        post_id = post_with_comments.get("id", "unknown")
        post_url = f"https://reddit.com/r/{post_with_comments.get('subreddit', 'unknown')}/comments/{post_id}/"
        
        for comment_schema in analysis_result.relevant_comments:
            try:
                comment_analysis = CommentAnalysis(
                    # Required fields
                    post_id=post_id,
                    post_url=post_url,
                    quote=comment_schema.text,  # Map 'text' to 'quote'
                    date=datetime.now(),  # Use current time since comment date not available
                    
                    # Core analysis fields
                    sentiment=comment_schema.sentiment,
                    theme=comment_schema.theme,
                    purchase_intent=comment_schema.purchase_intent,
                    
                    # Enhanced threading fields
                    parent_comment_id=comment_schema.parent_comment_id,
                    thread_depth=comment_schema.thread_depth,
                    thread_position=comment_schema.thread_position,
                    children_count=comment_schema.children_count,
                    conversation_context=comment_schema.conversation_context,
                    thread_context=comment_schema.thread_context,
                    confidence_score=comment_schema.confidence_score
                )
                comment_analyses.append(comment_analysis)
                
            except Exception as e:
                logger.error(f"Failed to convert comment analysis: {e}")
                logger.error(f"Comment schema data: {comment_schema.dict()}")
                import traceback
                logger.error(f"Conversion traceback: {traceback.format_exc()}")
                continue
        
        return comment_analyses

    async def analyze_post_comments(
        self, 
        post: Dict[str, Any], 
        context: AnalysisContext
    ) -> PostAnalysisResult:
        """
        Analyze comments for a single post using modern approach.
        
        Args:
            post: Single post with comments
            context: Analysis context
            
        Returns:
            PostAnalysisResult with analysis data
        """
        start_time = datetime.now()
        
        try:
            post_id = post.get("id", "unknown")
            logger.info(f"Starting modern analysis for post: {post_id}")
            logger.info(f"Post title: {post.get('title', 'No title')}")
            
            comments = post.get("comments", [])
            total_comments = self._count_threaded_comments(comments)
            logger.info(f"Total comments to analyze: {total_comments}")
            
            if not comments:
                logger.warning(f"No comments found for post {post_id}")
                processing_time = (datetime.now() - start_time).total_seconds()
                
                return PostAnalysisResult(
                    post_id=post_id,
                    comment_analyses=[],
                    thread_insights=[],
                    total_comments_found=0,
                    relevant_comments_extracted=0,
                    conversation_quality=0.0,
                    processing_time_seconds=processing_time,
                    analysis_metadata=AnalysisMetadata(
                        total_posts_analyzed=1,
                        total_comments_found=0,
                        relevant_comments_extracted=0,
                        irrelevant_posts=1,
                        analysis_timestamp=datetime.now(),
                        processing_time_seconds=processing_time,
                        model_used="gpt-4o-mini",
                        api_calls_made=0,
                        collection_method="modern",
                        max_thread_depth=0,
                        total_threaded_comments=0
                    )
                )
            
            # Perform modern analysis
            comment_analyses, thread_insights, conversation_quality = await self.analyze_full_post_context(
                post, context
            )
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            logger.info(f"Post analysis complete: {len(comment_analyses)} relevant comments from {total_comments} total")
            
            return PostAnalysisResult(
                post_id=post_id,
                comment_analyses=comment_analyses,
                thread_insights=thread_insights,
                total_comments_found=total_comments,
                relevant_comments_extracted=len(comment_analyses),
                conversation_quality=conversation_quality,
                processing_time_seconds=processing_time,
                analysis_metadata=AnalysisMetadata(
                    total_posts_analyzed=1,
                    total_comments_found=total_comments,
                    relevant_comments_extracted=len(comment_analyses),
                    irrelevant_posts=0,
                    analysis_timestamp=datetime.now(),
                    processing_time_seconds=processing_time,
                    model_used="gpt-4o-mini",
                    api_calls_made=1,  # One OpenAI call per post
                    collection_method="modern",
                    max_thread_depth=self._calculate_max_depth(comments),
                    total_threaded_comments=total_comments
                )
            )
            
        except Exception as e:
            logger.error(f"Error analyzing post {post.get('id', 'unknown')}: {e}")
            processing_time = (datetime.now() - start_time).total_seconds()
            
            return PostAnalysisResult(
                post_id=post.get("id", "unknown"),
                comment_analyses=[],
                thread_insights=[],
                total_comments_found=0,
                relevant_comments_extracted=0,
                conversation_quality=0.0,
                processing_time_seconds=processing_time,
                analysis_metadata=AnalysisMetadata(
                    total_posts_analyzed=1,
                    total_comments_found=0,
                    relevant_comments_extracted=0,
                    irrelevant_posts=1,
                    analysis_timestamp=datetime.now(),
                    processing_time_seconds=processing_time,
                    model_used="gpt-4o-mini",
                    api_calls_made=0,
                    collection_method="modern",
                    max_thread_depth=0,
                    total_threaded_comments=0
                )
            )

    async def analyze_multiple_posts(
        self, 
        posts: List[Dict[str, Any]], 
        context: AnalysisContext,
        max_concurrent: int = 3
    ) -> UnifiedAnalysisResponse:
        """
        Analyze multiple posts concurrently using modern approach.
        
        Args:
            posts: List of posts with comments
            context: Analysis context
            max_concurrent: Maximum concurrent analyses
            
        Returns:
            UnifiedAnalysisResponse with aggregated results
        """
        start_time = datetime.now()
        
        logger.info(f"Starting modern analysis of {len(posts)} posts with max_concurrent={max_concurrent}")
        
        # Create semaphore to limit concurrency
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def analyze_single_post_with_semaphore(post):
            async with semaphore:
                return await self.analyze_post_comments(post, context)
        
        # Execute analyses concurrently
        try:
            results = await asyncio.gather(
                *[analyze_single_post_with_semaphore(post) for post in posts],
                return_exceptions=True
            )
        except Exception as e:
            logger.error(f"Error in concurrent analysis: {e}")
            results = []
        
        # Process results and handle exceptions
        valid_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Analysis failed for post {i}: {result}")
                # Create error result
                error_result = PostAnalysisResult(
                    post_id=posts[i].get("id", "unknown"),
                    comment_analyses=[],
                    thread_insights=[],
                    total_comments_found=0,
                    relevant_comments_extracted=0,
                    conversation_quality=0.0,
                    processing_time_seconds=0.0,
                    analysis_metadata=AnalysisMetadata(
                        total_posts_analyzed=1,
                        total_comments_found=0,
                        relevant_comments_extracted=0,
                        irrelevant_posts=1,
                        analysis_timestamp=datetime.now(),
                        processing_time_seconds=0.0,
                        model_used="gpt-4o-mini",
                        api_calls_made=0,
                        collection_method="modern",
                        max_thread_depth=0,
                        total_threaded_comments=0
                    )
                )
                valid_results.append(error_result)
            else:
                valid_results.append(result)
        
        # Aggregate results
        all_comment_analyses = []
        all_thread_insights = []
        total_posts_analyzed = len([r for r in valid_results if r.total_comments_found > 0])
        total_comments_found = sum(r.total_comments_found for r in valid_results)
        relevant_comments_extracted = sum(r.relevant_comments_extracted for r in valid_results)
        api_calls_made = sum(r.analysis_metadata.api_calls_made for r in valid_results)
        max_thread_depth = max((r.analysis_metadata.max_thread_depth for r in valid_results), default=0)
        total_threaded_comments = sum(r.analysis_metadata.total_threaded_comments for r in valid_results)
        
        for result in valid_results:
            all_comment_analyses.extend(result.comment_analyses)
            all_thread_insights.extend(result.thread_insights)
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"Modern analysis pipeline completed. Found {relevant_comments_extracted} relevant comments")
        
        return UnifiedAnalysisResponse(
            comment_analyses=all_comment_analyses,
            metadata=AnalysisMetadata(
                total_posts_analyzed=len(posts),
                total_comments_found=total_comments_found,
                relevant_comments_extracted=relevant_comments_extracted,
                irrelevant_posts=len(posts) - total_posts_analyzed,
                analysis_timestamp=datetime.now(),
                processing_time_seconds=processing_time,
                model_used="gpt-4o-mini",
                api_calls_made=api_calls_made,
                collection_method="modern",
                max_thread_depth=max_thread_depth,
                total_threaded_comments=total_threaded_comments
            )
        )


class ModernConcurrentCommentAnalysisOrchestrator:
    """
    Orchestrator for managing concurrent comment analysis using modern approach.
    Replaces the problematic Pydantic AI orchestrator.
    """
    
    def __init__(self, max_concurrent_agents: int = 5):
        self.max_concurrent_agents = max_concurrent_agents
        self.analyzer = ModernCommentAnalyzer()
        
    async def analyze_posts(
        self, 
        posts: List[Dict[str, Any]], 
        analysis_request: Union[SubredditAnalysisRequest, SearchAnalysisRequest]
    ) -> UnifiedAnalysisResponse:
        """
        Orchestrate analysis of multiple posts using modern approach.
        
        Args:
            posts: List of posts with comments
            analysis_request: Analysis configuration
            
        Returns:
            UnifiedAnalysisResponse with results
        """
        logger.info(f"Modern orchestrator starting analysis of {len(posts)} posts")
        
        # Create analysis context
        context = AnalysisContext(
            system_prompt=analysis_request.system_prompt,
            max_comments=50,  # Reasonable default
            preserve_threading=True,
            analyze_conversation_flow=True,
            include_thread_context=True,
            max_thread_depth=10
        )
        
        # Use the modern analyzer
        return await self.analyzer.analyze_multiple_posts(
            posts=posts,
            context=context,
            max_concurrent=self.max_concurrent_agents
        )
    
    async def run_full_analysis(
        self,
        posts: List[Dict[str, Any]],
        analysis_request: Union[SubredditAnalysisRequest, SearchAnalysisRequest],
        collection_metadata: Dict[str, Any] = None
    ) -> UnifiedAnalysisResponse:
        """
        Execute the complete analysis pipeline from posts to final response.
        Maintains compatibility with existing route interface.
        
        Args:
            posts: List of posts with comments to analyze
            analysis_request: Original request parameters
            collection_metadata: Metadata from data collection phase
            
        Returns:
            UnifiedAnalysisResponse with all analyses and metadata
        """
        logger.info(f"Modern orchestrator running full analysis for {len(posts)} posts")
        logger.info(f"User system prompt: {analysis_request.system_prompt[:100]}...")
        
        # Use the modern analyze_posts method
        return await self.analyze_posts(posts, analysis_request) 