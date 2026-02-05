"""
Company research module using web search.
"""

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

import httpx

from .models import CompanyResearch

logger = logging.getLogger(__name__)


class CompanyResearcher:
    """Research companies using web search and scraping."""

    def __init__(
        self,
        cache_dir: str = ".cache/cover-letter-gen/company-research",
        ttl_days: int = 7,
    ):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_days = ttl_days

    def _get_cache_path(self, company_name: str) -> Path:
        """Get cache file path for a company."""
        safe_name = company_name.replace(" ", "_").replace("/", "_")
        return self.cache_dir / f"{safe_name}.json"

    def _get_cache_key(self, company_name: str) -> str:
        """Get cache key for a company."""
        return hashlib.md5(company_name.lower().encode()).hexdigest()[:16]

    def _is_cache_valid(self, cache_path: Path) -> bool:
        """Check if cache file is still valid."""
        if not cache_path.exists():
            return False

        # Check TTL
        cache_mtime = cache_path.stat().st_mtime
        cache_age_days = (datetime.now().timestamp() - cache_mtime) / (24 * 3600)
        return cache_age_days < self.ttl_days

    def get_cache(self, company_name: str) -> Optional[CompanyResearch]:
        """Get cached research for a company."""
        cache_path = self._get_cache_path(company_name)

        if not self._is_cache_valid(cache_path):
            return None

        try:
            with open(cache_path, "r") as f:
                data = json.load(f)
            return CompanyResearch(**data)
        except Exception as e:
            logger.warning(f"Failed to read cache for {company_name}: {e}")
            return None

    def save_cache(self, company_name: str, research: CompanyResearch) -> None:
        """Save research to cache."""
        cache_path = self._get_cache_path(company_name)

        try:
            with open(cache_path, "w") as f:
                json.dump(research.model_dump(), f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save cache for {company_name}: {e}")

    async def research_company(
        self,
        company_name: str,
        enable_search: bool = True,
    ) -> Optional[CompanyResearch]:
        """
        Research a company using web search and scraping.

        Args:
            company_name: Name of the company to research
            enable_search: Whether to perform web search (disable for testing)

        Returns:
            CompanyResearch object or None if research fails
        """
        # Check cache first
        cached = self.get_cache(company_name)
        if cached:
            logger.info(f"📋 Using cached research for {company_name}")
            return cached

        if not enable_search:
            return None

        try:
            logger.info(f"🔍 Researching {company_name}...")

            # Perform web search for company info
            search_results = await self._search_company(company_name)

            if not search_results:
                logger.warning(f"No search results for {company_name}")
                return None

            # Parse research from search results
            research = await self._parse_company_research(company_name, search_results)

            if research:
                # Save to cache
                self.save_cache(company_name, research)
                logger.info(f"✅ Research complete for {company_name}")

            return research

        except Exception as e:
            logger.error(f"Error researching {company_name}: {e}")
            return None

    async def _search_company(self, company_name: str) -> Dict[str, Any]:
        """Search for company information using web search."""
        try:
            # Use web_search tool
            from .web_search import web_search

            # Search for company info
            company_info = await web_search(
                query=f"{company_name} company information about us mission values culture",
                count=5,
            )

            # Search for recent news
            news_results = await web_search(
                query=f"{company_name} recent news updates 2024 2025",
                count=5,
            )

            return {
                "company_info": company_info,
                "news_results": news_results,
            }

        except ImportError:
            logger.warning("Web search not available, skipping company research")
            return {}
        except Exception as e:
            logger.error(f"Web search failed: {e}")
            return {}

    async def _parse_company_research(
        self,
        company_name: str,
        search_results: Dict[str, Any],
    ) -> Optional[CompanyResearch]:
        """Parse company research from search results."""
        try:
            # Extract info from search snippets
            company_info = search_results.get("company_info", [])
            news_results = search_results.get("news_results", [])

            # Parse snippets for company details
            industry = None
            size = None
            mission = None
            values = []
            recent_news = []
            culture = None

            # Extract from search results
            for result in company_info[:10]:
                title = result.get("title", "")
                snippet = result.get("snippet", "")

                # Try to identify company type/size
                if not industry and any(
                    kw in snippet.lower()
                    for kw in ["technology", "tech", "software", "SaaS", "AI"]
                ):
                    industry = "Technology"

                # Look for values/mission
                if "mission" in snippet.lower() or "purpose" in snippet.lower():
                    if not mission:
                        mission = snippet[:200]

                # Look for values
                if any(v in snippet.lower() for v in ["innovation", "collaboration", "customer-first"]):
                    if len(values) < 3:
                        values.append(snippet[:100])

            # Extract recent news
            for result in news_results[:5]:
                title = result.get("title", "")
                recent_news.append(title)

            return CompanyResearch(
                name=company_name,
                industry=industry,
                size=size,
                mission=mission,
                values=values,
                recent_news=recent_news,
                culture=culture,
            )

        except Exception as e:
            logger.error(f"Failed to parse company research: {e}")
            return None

    async def research_companies(
        self,
        companies: list[str],
        enable_search: bool = True,
    ) -> dict[str, Optional[CompanyResearch]]:
        """
        Research multiple companies in parallel.

        Args:
            companies: List of company names to research
            enable_search: Whether to perform web search

        Returns:
            Dict mapping company names to research results
        """
        import asyncio

        tasks = [
            self.research_company(company, enable_search)
            for company in companies
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        return {
            company: result if not isinstance(result, Exception) else None
            for company, result in zip(companies, results)
        }
