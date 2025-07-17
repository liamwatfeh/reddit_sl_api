"""
AI-powered comment analysis agent using Pydantic AI.
Provides sentiment analysis, theme extraction, and purchase intent detection for Reddit comments.
"""

import asyncio
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
    """Context for comment analysis."""
    system_prompt: str
    max_comments_per_post: int = 50


class CommentAnalyzerAgent:
    """
    AI-powered agent for analyzing Reddit comments using multiple AI models.
    Supports OpenAI, Gemini, and Claude models with fallback mechanisms.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.primary_agent = self._create_primary_agent()
        self.fallback_agent = self._create_fallback_agent()
        
    def _create_primary_agent(self) -> Agent:
        """Create the primary AI agent for comment analysis."""
        model = self._get_model(self.settings.primary_ai_model)
        
        system_prompt = """
        You are an expert social media analyst specializing in Reddit comment analysis.
        Your task is to analyze comments for:
        1. SENTIMENT: Determine if the comment is positive, negative, or neutral
        2. THEME: Identify the main topic or theme being discussed  
        3. PURCHASE INTENT: Assess likelihood of purchase intent (high/medium/low/none)
        
        Guidelines:
        - Be objective and evidence-based in your analysis
        - Consider context and nuance in sentiment analysis
        - Purchase intent should reflect actual buying signals or interest
        - Analyze ALL comments regardless of topic
        - Provide confidence scores reflecting certainty of your analysis
        """
        
        return Agent(
            model=model,
            result_type=CommentInsight,
            system_prompt=system_prompt,
        )
    
    def _create_fallback_agent(self) -> Agent:
        """Create fallback agent with different model."""
        fallback_model_name = (
            "gpt-4" if self.settings.primary_ai_model.startswith("gemini") 
            else "gemini-2.5-pro"
        )
        model = self._get_model(fallback_model_name)
        
        return Agent(
            model=model,
            result_type=CommentInsight,
            system_prompt="You are a social media analyst. Analyze comments for sentiment, theme, and purchase intent.",
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
    
    async def analyze_comment(
        self, 
        comment_text: str, 
        context: AnalysisContext,
        post_id: str,
        post_url: str
    ) -> Optional[CommentAnalysis]:
        """
        Analyze a single comment using AI.
        
        Args:
            comment_text: The comment text to analyze
            context: Analysis context with keywords and settings
            post_id: ID of the parent post
            post_url: URL of the parent post
            
        Returns:
            CommentAnalysis object or None if analysis fails
        """
        if not comment_text or len(comment_text.strip()) < 10:
            return None
            
        try:
            # Prepare analysis prompt
            analysis_prompt = f"""
            Analyze this Reddit comment for sentiment, theme, and purchase intent:
            
            Comment: "{comment_text}"
            
            Provide structured analysis with confidence scores.
            """
            
            # Try primary agent first
            try:
                result = await self.primary_agent.run(
                    analysis_prompt,
                    message_history=[]
                )
                insight = result.data
                
            except Exception as e:
                logger.warning(f"Primary agent failed, trying fallback: {e}")
                result = await self.fallback_agent.run(
                    analysis_prompt,
                    message_history=[]
                )
                insight = result.data
            
            # Convert to CommentAnalysis
            return CommentAnalysis(
                post_id=post_id,
                post_url=post_url,
                quote=comment_text[:500],  # Truncate long quotes
                sentiment=insight.sentiment,
                theme=insight.theme,
                purchase_intent=insight.purchase_intent,
                date=datetime.now(),
                source="reddit"
            )
            
        except Exception as e:
            logger.error(f"Comment analysis failed: {e}")
            return None
    
    async def analyze_post_comments(
        self,
        post: Dict[str, Any],
        context: AnalysisContext
    ) -> PostAnalysisResult:
        """
        Analyze all comments in a post.
        
        Args:
            post: Post with comments to analyze
            context: Analysis context
            
        Returns:
            PostAnalysisResult with all analysis results
        """
        start_time = datetime.now()
        analyzed_comments = []
        error_messages = []
        
        # Limit comments processed per post
        max_comments = getattr(context, 'max_comments_per_post', 50)
        logger.info(f"DEBUG: max_comments = {max_comments}, type = {type(max_comments)}")
        logger.info(f"DEBUG: context = {context}")
        comments_list = post.get("comments", [])
        logger.info(f"DEBUG: comments_list type = {type(comments_list)}, length = {len(comments_list) if hasattr(comments_list, '__len__') else 'no length'}")
        logger.info(f"DEBUG: comments_list = {comments_list}")
        
        # Ensure max_comments is an integer
        if not isinstance(max_comments, int):
            logger.error(f"max_comments is not an integer: {max_comments}, type: {type(max_comments)}")
            max_comments = 50
            
        # Ensure comments_list is actually a list
        if not isinstance(comments_list, list):
            logger.error(f"comments_list is not a list: {type(comments_list)}, value: {comments_list}")
            comments_list = []
            
        comments_to_process = comments_list[:max_comments]
        
        post_id = post.get("post_id", "unknown")
        logger.info(f"DEBUG: Full post structure = {post}")
        logger.info(f"DEBUG: Post keys = {list(post.keys()) if isinstance(post, dict) else 'not a dict'}")
        logger.info(f"Analyzing {len(comments_to_process)} comments for post {post_id}")
        
        # Process comments concurrently (but with rate limiting)
        semaphore = asyncio.Semaphore(5)  # Limit concurrent analyses
        
        async def analyze_single_comment(comment_data: Dict[str, Any]) -> Optional[CommentAnalysis]:
            async with semaphore:
                try:
                    comment_text = comment_data.get('body', '')
                    if not comment_text or comment_text == '[deleted]' or comment_text == '[removed]':
                        return None
                    
                    return await self.analyze_comment(
                        comment_text=comment_text,
                        context=context,
                        post_id=post.get("post_id", "unknown"),
                        post_url=post.get("url", "")
                    )
                except Exception as e:
                    error_messages.append(f"Comment analysis error: {str(e)}")
                    return None
        
        # Run analyses concurrently
        tasks = [analyze_single_comment(comment) for comment in comments_to_process]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Collect successful analyses
        for result in results:
            if isinstance(result, CommentAnalysis):
                analyzed_comments.append(result)
            elif isinstance(result, Exception):
                error_messages.append(f"Analysis exception: {str(result)}")
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        return PostAnalysisResult(
            post_id=post.get("post_id", "unknown"),
            post_url=post.get("url", ""),
            analyzed_comments=analyzed_comments,
            total_comments_processed=len(comments_to_process),
            relevant_comments_found=len(analyzed_comments),
            processing_time_seconds=processing_time,
            error_messages=error_messages
        )
    
    async def analyze_multiple_posts(
        self,
        posts: List[Dict[str, Any]],
        context: AnalysisContext
    ) -> List[PostAnalysisResult]:
        """
        Analyze comments across multiple posts.
        
        Args:
            posts: List of posts to analyze
            context: Analysis context
            
        Returns:
            List of PostAnalysisResult objects
        """
        logger.info(f"Starting analysis of {len(posts)} posts")
        
        # Process posts concurrently with rate limiting
        semaphore = asyncio.Semaphore(3)  # Limit concurrent post processing
        
        async def analyze_single_post(post: Dict[str, Any]) -> PostAnalysisResult:
            async with semaphore:
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
        
        logger.info(f"Completed analysis of {len(final_results)} posts")
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
        
        logger.info(f"Starting full analysis pipeline for {len(posts)} posts")
        
        # Prepare analysis context
        context = AnalysisContext(
            system_prompt=analysis_request.system_prompt,
            max_comments_per_post=50
        )
        
        # Run AI analysis across all posts
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
        
        logger.info(f"Analysis pipeline completed. Found {len(unified_response.comment_analyses)} relevant comments")
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
            len(all_comment_analyses)  # AI API calls (approximately)
        )
        
        # Build metadata
        metadata = AnalysisMetadata(
            total_posts_analyzed=len(posts),
            total_comments_found=actual_total_comments,
            relevant_comments_extracted=len(all_comment_analyses),
            irrelevant_posts=irrelevant_posts,
            analysis_timestamp=datetime.now(),
            processing_time_seconds=processing_time,
            model_used=model_used,
            api_calls_made=api_calls_made,
            collection_method=collection_method,
            cell_parsing_errors=collection_metadata.get("cell_parsing_errors", 0)
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
