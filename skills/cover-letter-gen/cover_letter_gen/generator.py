"""
Cover letter generation logic.
"""

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import (
    CoverLetterResult,
    JobPosting,
    MatchInfo,
    CompanyResearch,
)

logger = logging.getLogger(__name__)


class CoverLetterGenerator:
    """Generate personalized cover letters using LLM."""

    SYSTEM_PROMPT = """You are an expert cover letter writer with deep knowledge of professional 
communication and recruitment best practices. Your role is to create compelling, personalized 
cover letters that effectively match candidate qualifications to specific job requirements.

For each cover letter, you must:
1. Analyze the job posting and candidate match results thoroughly
2. Craft a compelling opening that demonstrates genuine interest and research
3. Highlight the most relevant qualifications and experiences
4. Address any skill gaps with confidence and learning enthusiasm
5. Include specific examples and achievements where possible
6. Maintain a professional yet personable tone
7. Close with a strong call to action

Key principles:
- Personalize for the specific company and role
- Be concise but comprehensive (typically 3-4 paragraphs)
- Demonstrate value proposition clearly
- Show enthusiasm and cultural fit
- Avoid generic phrases and templates

Always return the cover letter content directly without additional commentary."""

    def __init__(
        self,
        llm_client=None,
        style: str = "adaptive",
        max_length_words: int = 350,
    ):
        self.llm = llm_client
        self.style = style
        self.max_length_words = max_length_words

    def _build_prompt(
        self,
        job: JobPosting,
        match: MatchInfo,
        resume_content: str,
        company_research: Optional[CompanyResearch] = None,
    ) -> str:
        """Build the prompt for cover letter generation."""
        # Build company context section
        company_context = ""
        if company_research:
            context_parts = []
            if company_research.industry:
                context_parts.append(f"Industry: {company_research.industry}")
            if company_research.mission:
                context_parts.append(f"Mission: {company_research.mission}")
            if company_research.values:
                context_parts.append(f"Values: {', '.join(company_research.values)}")
            if company_research.culture:
                context_parts.append(f"Culture: {company_research.culture}")
            if company_research.recent_news:
                context_parts.append(f"Recent: {company_research.recent_news[0]}")
            company_context = "\n".join(context_parts)

        # Build the user prompt
        prompt = f"""
Generate a personalized cover letter for the following job application.

JOB POSTING:
- Title: {job.title}
- Company: {job.company}
- Location: {job.location}
- Description: {job.description[:1500]}

MATCH ANALYSIS:
- Score: {match.match_score:.2f}/1.0
- Reasoning: {match.match_reasoning}
- Matched Skills: {', '.join(match.matched_keywords)}
- Missing Skills: {', '.join(match.missing_keywords)}

CANDIDATE RESUME:
{resume_content[:2000]}

{company_context}

Generate a compelling cover letter that:
1. Opens with genuine interest and company-specific insights
2. Highlights the strongest matching qualifications from the analysis
3. Addresses skill gaps with learning enthusiasm and transferable skills
4. Demonstrates understanding of the role and company
5. Closes with a confident call to action

The cover letter should be professional, concise ({self.max_length_words} words max), 
and tailored to this specific opportunity.
"""

        return prompt

    async def generate(
        self,
        job: JobPosting,
        match: MatchInfo,
        resume_content: str,
        company_research: Optional[CompanyResearch] = None,
    ) -> CoverLetterResult:
        """
        Generate a cover letter for a job application.

        Args:
            job: Job posting information
            match: Match analysis results
            resume_content: Base resume content
            company_research: Optional company research results

        Returns:
            CoverLetterResult with generated content
        """
        try:
            # Build prompt
            prompt = self._build_prompt(job, match, resume_content, company_research)

            # Generate using LLM
            if self.llm:
                return await self._generate_with_llm(prompt, match, company_research)
            else:
                return self._generate_fallback(job, match, company_research)

        except Exception as e:
            logger.error(f"Error generating cover letter: {e}")
            return self._create_fallback_cover_letter(job, match, company_research)

    async def _generate_with_llm(
        self,
        prompt: str,
        match: MatchInfo,
        company_research: Optional[CompanyResearch] = None,
    ) -> CoverLetterResult:
        """Generate cover letter using LLM."""
        try:
            messages = [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]

            response = await self.llm.ainvoke(messages)

            # Extract content
            content = response.content if hasattr(response, "content") else str(response)

            # Build company context string
            company_context = None
            if company_research:
                parts = []
                if company_research.mission:
                    parts.append(company_research.mission)
                if company_research.values:
                    parts.append(f"Values: {', '.join(company_research.values)}")
                if company_research.recent_news:
                    parts.append(f"Recent news: {company_research.recent_news[0]}")
                company_context = " | ".join(parts)

            # Determine key selling points
            key_selling_points = match.matched_keywords[:5]

            return CoverLetterResult(
                content=content,
                company_context=company_context,
                key_selling_points=key_selling_points,
                generated_at=datetime.now(),
            )

        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            raise

    def _generate_fallback(
        self,
        job: JobPosting,
        match: MatchInfo,
        company_research: Optional[CompanyResearch] = None,
    ) -> CoverLetterResult:
        """Generate a basic cover letter without LLM."""
        # Build a template-based cover letter
        content = self._create_fallback_cover_letter(job, match, company_research)

        key_selling_points = match.matched_keywords[:5]
        company_context = None
        if company_research:
            parts = []
            if company_research.mission:
                parts.append(company_research.mission)
            if company_research.values:
                parts.append(f"Values: {', '.join(company_research.values)}")
            company_context = " | ".join(parts)

        return CoverLetterResult(
            content=content,
            company_context=company_context,
            key_selling_points=key_selling_points,
            generated_at=datetime.now(),
        )

    def _create_fallback_cover_letter(
        self,
        job: JobPosting,
        match: MatchInfo,
        company_research: Optional[CompanyResearch] = None,
    ) -> str:
        """Create a fallback cover letter when LLM is unavailable."""
        # Add company research context if available
        research_line = ""
        if company_research and company_research.mission:
            research_line = f"\n\nI am particularly drawn to {job.company}'s mission: {company_research.mission}"

        matched_skills = ", ".join(match.matched_keywords[:5])
        missing_skills = ", ".join(match.missing_keywords[:3]) if match.missing_keywords else "none"

        return f"""# Cover Letter

Dear Hiring Manager,

I am writing to express my strong interest in the {job.title} position at {job.company} in {job.location}. With a {match.match_score:.0%} match between my background and this role, I am confident I can contribute meaningfully to your team.

## Why I am a Strong Fit

My technical background aligns closely with the role requirements, particularly in {matched_skills}.{research_line}

## Relevant Experience

I bring hands-on experience in {matched_skills}, which directly translates to the responsibilities of this position. I am eager to leverage my expertise to drive results for {job.company}.

## Addressing Any Gaps

While I may have less experience with {missing_skills}, I am a quick learner and confident in my ability to develop these skills quickly with the right guidance and opportunities.

## Closing

I would welcome the opportunity to discuss how my skills and experience can contribute to {job.company}'s continued success. Thank you for considering my application.

Best regards,
[Your Name]"""
