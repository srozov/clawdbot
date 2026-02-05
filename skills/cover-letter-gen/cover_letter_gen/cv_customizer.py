"""
CV customization module.
"""

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import CVResult, JobPosting, MatchInfo

logger = logging.getLogger(__name__)


class CVCustomizer:
    """Customize CV for specific job applications."""

    def __init__(self, llm_client=None):
        self.llm = llm_client

    def _extract_resume_sections(self, resume_content: str) -> dict:
        """Extract sections from resume markdown."""
        sections = {}

        # Define section markers
        section_markers = [
            "## Summary",
            "## Experience",
            "## Skills",
            "## Education",
            "## Projects",
            "## Certifications",
        ]

        lines = resume_content.split("\n")
        current_section = None
        current_content = []

        for line in lines:
            # Check if this is a section header
            is_section = False
            for marker in section_markers:
                if line.strip().startswith(marker):
                    # Save previous section
                    if current_section:
                        sections[current_section] = "\n".join(current_content).strip()
                    current_section = marker.replace("## ", "").strip()
                    current_content = []
                    is_section = True
                    break

            if not is_section and current_section:
                current_content.append(line)

        # Save last section
        if current_section:
            sections[current_section] = "\n".join(current_content).strip()

        return sections

    def _highlight_matching_skills(
        self,
        skills_section: str,
        matched_keywords: list[str],
    ) -> str:
        """Highlight skills that match the job."""
        if not skills_section:
            return ""

        lines = skills_section.split("\n")
        highlighted = []

        for line in lines:
            # Check if line contains any matched keywords
            line_lower = line.lower()
            for keyword in matched_keywords:
                if keyword.lower() in line_lower:
                    # Format as emphasized
                    highlighted.append(f"**{line.strip()}**")
                    break
            else:
                highlighted.append(line.strip())

        return "\n".join(filter(None, highlighted))

    def _extract_relevant_experience(
        self,
        experience_section: str,
        matched_keywords: list[str],
        missing_keywords: list[str],
    ) -> str:
        """Extract and prioritize relevant experience."""
        if not experience_section:
            return ""

        lines = experience_section.split("\n")
        relevant = []
        current_entry = []

        for line in lines:
            # Check if line contains matched keywords
            line_lower = line.lower()
            is_relevant = any(kw.lower() in line_lower for kw in matched_keywords)

            if line.strip().startswith("**") or line.strip().startswith("##"):
                # New entry - save previous if relevant
                if current_entry and any(
                    kw.lower() in " ".join(current_entry).lower()
                    for kw in matched_keywords
                ):
                    relevant.extend(current_entry)
                current_entry = [line]
            else:
                current_entry.append(line)

        # Check last entry
        if current_entry and any(
            kw.lower() in " ".join(current_entry).lower() for kw in matched_keywords
        ):
            relevant.extend(current_entry)

        return "\n".join(relevant) if relevant else experience_section

    async def customize_cv(
        self,
        resume_content: str,
        job: JobPosting,
        match: MatchInfo,
    ) -> CVResult:
        """
        Customize CV for a specific job application.

        Args:
            resume_content: Base resume content
            job: Job posting information
            match: Match analysis results

        Returns:
            CVResult with customized content
        """
        try:
            # Extract resume sections
            sections = self._extract_resume_sections(resume_content)

            # Build customized CV
            cv_parts = []

            # Add summary (potentially customize it)
            if "Summary" in sections:
                cv_parts.append(f"## Summary\n{sections['Summary']}")

            # Add relevant experience
            if "Experience" in sections:
                relevant_exp = self._extract_relevant_experience(
                    sections["Experience"],
                    match.matched_keywords,
                    match.missing_keywords,
                )
                if relevant_exp:
                    cv_parts.append(f"## Experience\n{relevant_exp}")
                else:
                    cv_parts.append(f"## Experience\n{sections['Experience']}")

            # Add skills (highlight matching ones)
            if "Skills" in sections:
                highlighted_skills = self._highlight_matching_skills(
                    sections["Skills"], match.matched_keywords
                )
                if highlighted_skills:
                    cv_parts.append(f"## Skills\n{highlighted_skills}")
                else:
                    cv_parts.append(f"## Skills\n{sections['Skills']}")

            # Add other sections as-is
            for section_name, content in sections.items():
                if section_name not in ["Summary", "Experience", "Skills"] and content:
                    cv_parts.append(f"## {section_name}\n{content}")

            # Build CV content
            cv_content = "\n\n".join(cv_parts)

            # If LLM is available, use it for better customization
            if self.llm:
                cv_content = await self._llm_customize_cv(
                    cv_content, job, match
                )

            # Determine highlighted experience
            highlighted = match.matched_keywords[:5]

            return CVResult(
                content=cv_content,
                highlighted_experience=highlighted,
                generated_at=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Error customizing CV: {e}")
            # Return original resume as fallback
            return CVResult(
                content=resume_content,
                highlighted_experience=match.matched_keywords[:5],
                generated_at=datetime.now(),
            )

    async def _llm_customize_cv(
        self,
        cv_content: str,
        job: JobPosting,
        match: MatchInfo,
    ) -> str:
        """Use LLM to further customize CV content."""
        try:
            system_prompt = """You are an expert CV writer who specializes in tailoring 
            resumes to specific job postings. Your task is to slightly adjust the resume 
            content to better match the job requirements while maintaining authenticity 
            and accuracy. Focus on:
            
            1. Emphasizing relevant experience and skills
            2. Using terminology from the job posting
            3. Highlighting achievements that demonstrate fit
            4. Keeping all information factual and truthful
            
            Return only the CV content, no explanations."""

            user_prompt = f"""
Customize this CV for the following job:

Job Title: {job.title}
Company: {job.company}
Matched Keywords: {', '.join(match.matched_keywords)}
Missing Keywords: {', '.join(match.missing_keywords)}

CV Content:
{cv_content}

Provide the customized CV content only.
"""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            response = await self.llm.ainvoke(messages)
            return response.content if hasattr(response, "content") else str(response)

        except Exception as e:
            logger.warning(f"LLM CV customization failed: {e}")
            return cv_content
