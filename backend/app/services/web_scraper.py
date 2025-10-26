"""
Advanced AI-powered web scraping service for sports data
Uses Crawl4AI and other AI scraping tools
"""
import re
from typing import Dict, Any, List, Optional
from loguru import logger

try:
    from crawl4ai import AsyncWebCrawler
    from crawl4ai.extraction_strategy import LLMExtractionStrategy, CosineStrategy
    CRAWL4AI_AVAILABLE = True
except ImportError:
    CRAWL4AI_AVAILABLE = False
    logger.warning("Crawl4AI not installed, using basic scraping")


class WebScrapingService:
    """
    AI-powered web scraping service for sports data
    Uses Crawl4AI for intelligent content extraction
    """
    
    def __init__(self):
        self._crawler = None
        self._init_crawler()
    
    def _init_crawler(self):
        """Initialize AI crawler"""
        if CRAWL4AI_AVAILABLE:
            try:
                self._crawler = AsyncWebCrawler()
                logger.info("Crawl4AI initialized")
            except Exception as e:
                logger.error(f"Failed to initialize crawler: {e}")
        else:
            logger.warning("Using basic scraping without AI enhancement")
    
    async def scrape_sports_page(
        self,
        url: str,
        extraction_schema: Optional[Dict[str, Any]] = None,
        use_ai: bool = True
    ) -> Dict[str, Any]:
        """
        Scrape a sports page with AI-enhanced extraction
        
        Args:
            url: URL to scrape
            extraction_schema: Schema for extracting structured data
            use_ai: Whether to use AI for intelligent extraction
            
        Returns:
            Scraped data with markdown and extracted information
        """
        logger.info(f"Scraping {url} with AI={'enabled' if use_ai else 'disabled'}")
        
        try:
            if CRAWL4AI_AVAILABLE and use_ai and extraction_schema:
                # Use AI-enhanced extraction
                result = await self._scrape_with_ai(url, extraction_schema)
            else:
                # Basic scraping
                result = await self._scrape_basic(url)
            
            # Clean and structure the data
            structured_data = self._structure_sports_data(result)
            
            return structured_data
            
        except Exception as e:
            logger.error(f"Scraping error for {url}: {e}")
            raise
    
    async def _scrape_with_ai(
        self,
        url: str,
        extraction_schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Scrape with AI-enhanced extraction using Crawl4AI"""
        
        # Create extraction strategy
        strategy = LLMExtractionStrategy(
            schema=extraction_schema,
            extraction_type="schema",  # Extract based on schema
            llm_model="gpt-4"  # Use GPT-4 for better extraction
        )
        
        result = await self._crawler.arun(
            url=url,
            extraction_strategy=strategy,
            bypass_cache=True
        )
        
        return {
            'html': result.html,
            'markdown': result.markdown,
            'extracted_data': result.extracted_content,
            'links': result.links,
            'images': result.media.get('images', [])
        }
    
    async def _scrape_basic(self, url: str) -> Dict[str, Any]:
        """Basic scraping without AI"""
        import httpx
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=30.0)
            response.raise_for_status()
            
            html = response.text
            
            # Try to extract basic info
            data = self._extract_basic_info(html)
            
            return {
                'html': html,
                'markdown': self._html_to_markdown(html),
                'extracted_data': data,
                'links': []
            }
    
    def _extract_basic_info(self, html: str) -> Dict[str, Any]:
        """Extract basic information from HTML"""
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup(html, 'lxml')
        
        # Extract title
        title = soup.find('title')
        title_text = title.get_text() if title else ""
        
        # Extract headings
        headings = [h.get_text().strip() for h in soup.find_all(['h1', 'h2', 'h3'])]
        
        # Extract links
        links = [a.get('href') for a in soup.find_all('a', href=True)]
        
        return {
            'title': title_text,
            'headings': headings[:10],  # First 10 headings
            'links_count': len(links)
        }
    
    def _html_to_markdown(self, html: str) -> str:
        """Convert HTML to markdown"""
        try:
            import html2text
            h = html2text.HTML2Text()
            h.ignore_links = False
            h.ignore_images = False
            return h.handle(html)
        except:
            return html
    
    def _structure_sports_data(self, scraped_data: Dict[str, Any]) -> Dict[str, Any]:
        """Structure scraped data for sports analysis"""
        
        markdown = scraped_data.get('markdown', '')
        extracted = scraped_data.get('extracted_data', {})
        
        # Look for common sports data patterns
        structured = {
            'raw_markdown': markdown,
            'extracted_data': extracted,
            'sports_info': self._extract_sports_info(markdown),
            'links': scraped_data.get('links', []),
            'images': scraped_data.get('images', [])
        }
        
        return structured
    
    def _extract_sports_info(self, text: str) -> Dict[str, Any]:
        """Extract sports-specific information from text"""
        
        info = {
            'teams': self._extract_teams(text),
            'scores': self._extract_scores(text),
            'dates': self._extract_dates(text),
            'odds': self._extract_odds(text),
            'injuries': self._extract_injuries(text)
        }
        
        return info
    
    def _extract_teams(self, text: str) -> List[str]:
        """Extract team names from text"""
        # Common team name patterns
        team_patterns = [
            r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:vs|at)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            r'Team:\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
        ]
        
        teams = []
        for pattern in team_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if isinstance(match, tuple):
                    teams.extend(match)
                else:
                    teams.append(match)
        
        return list(set(teams))  # Remove duplicates
    
    def _extract_scores(self, text: str) -> List[Dict[str, Any]]:
        """Extract score information"""
        # Look for score patterns like "28-24", "Lakers 102-98 Warriors"
        score_pattern = r'(\d+)\s*[-–]\s*(\d+)'
        scores = []
        
        matches = re.findall(score_pattern, text)
        for home_score, away_score in matches:
            scores.append({
                'home': int(home_score),
                'away': int(away_score)
            })
        
        return scores
    
    def _extract_dates(self, text: str) -> List[str]:
        """Extract dates from text"""
        # Look for date patterns
        date_pattern = r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}'
        
        dates = re.findall(date_pattern, text, re.IGNORECASE)
        return dates
    
    def _extract_odds(self, text: str) -> List[str]:
        """Extract betting odds from text"""
        # Look for odds patterns like "+150", "-110", "2.5"
        odds_pattern = r'[-+]?\d+\.?\d*'
        
        potential_odds = re.findall(odds_pattern, text)
        # Filter for likely odds (between -1000 and +1000)
        odds = [o for o in potential_odds if -1000 <= float(o) <= 1000]
        
        return odds
    
    def _extract_injuries(self, text: str) -> List[str]:
        """Extract injury information"""
        injury_keywords = ['injury', 'out', 'questionable', 'doubtful', 'probable']
        
        injury_lines = []
        for line in text.split('\n'):
            for keyword in injury_keywords:
                if keyword.lower() in line.lower():
                    injury_lines.append(line.strip())
                    break
        
        return injury_lines
    
    async def scrape_multiple_pages(
        self,
        urls: List[str],
        extraction_schema: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Scrape multiple pages concurrently"""
        
        results = []
        for url in urls:
            try:
                result = await self.scrape_sports_page(
                    url,
                    extraction_schema,
                    use_ai=True
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to scrape {url}: {e}")
                results.append({'url': url, 'error': str(e)})
        
        return results
    
    def create_extraction_schema(self, data_type: str) -> Dict[str, Any]:
        """Create extraction schema for different data types"""
        
        schemas = {
            'scoreboard': {
                'games': [
                    {
                        'home_team': 'string',
                        'away_team': 'string',
                        'home_score': 'number',
                        'away_score': 'number',
                        'status': 'string',
                        'date': 'string'
                    }
                ]
            },
            'odds': {
                'markets': [
                    {
                        'game': 'string',
                        'market_type': 'string',
                        'selection': 'string',
                        'odds': 'number'
                    }
                ]
            },
            'news': {
                'articles': [
                    {
                        'title': 'string',
                        'content': 'string',
                        'date': 'string',
                        'author': 'string'
                    }
                ]
            }
        }
        
        return schemas.get(data_type, {})

