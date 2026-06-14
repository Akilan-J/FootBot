import requests
import xml.etree.ElementTree as ET
from typing import List, Dict, Any
from backend.utils import logger

# Public BBC Sport Football RSS feed
BBC_FEED_URL = "http://feeds.bbci.co.uk/sport/football/rss.xml"

def fetch_live_scores_from_html() -> List[Dict[str, Any]]:
    """
    Scrapes actual live football scores and fixtures from the BBC Sport website.
    Uses DOM traversal to safely extract home/away teams, scores, status, and links.
    Also extracts the league classification using preceding header isolation.
    """
    logger.info("Scraping live football match scores from BBC Sport website...")
    results = []
    
    url = "https://www.bbc.com/sport/football/scores-fixtures"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    }
    
    try:
        from bs4 import BeautifulSoup
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        response.encoding = 'utf-8'  # Force UTF-8 so special chars (ç, é, ñ) decode correctly
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all home team elements
        home_teams = soup.find_all(class_=lambda x: x and 'StyledTeam-HomeTeam' in x)
        logger.info(f"HTML Scraper: found {len(home_teams)} potential match elements.")
        
        for ht in home_teams:
            # Traversal to find the smallest common ancestor containing both teams
            ancestor = ht
            while ancestor:
                away_el = ancestor.find(class_=lambda x: x and 'StyledTeam-AwayTeam' in x)
                if away_el:
                    break
                ancestor = ancestor.parent
                
            if not ancestor:
                continue
                
            # Extract the nearest preceding h2 as the League name
            h2 = ht.find_previous('h2')
            league = h2.get_text().strip() if h2 else "Unknown League"
            
            # Extract clean Home Team name
            home_team_el = ht.find(class_=lambda x: x and 'DesktopValue' in x)
            if not home_team_el:
                home_team_el = ht.find('span')
            home_team = home_team_el.get_text().strip() if home_team_el else ht.get_text().strip()
            
            # Extract clean Away Team name
            away_team_container = ancestor.find(class_=lambda x: x and 'StyledTeam-AwayTeam' in x)
            away_team_el = away_team_container.find(class_=lambda x: x and 'DesktopValue' in x) if away_team_container else None
            if away_team_container and not away_team_el:
                away_team_el = away_team_container.find('span')
            away_team = away_team_el.get_text().strip() if away_team_el else "Unknown"

            # Filter to include only men's football matches
            league_lower = league.lower()
            home_lower = home_team.lower()
            away_lower = away_team.lower()
            if "women" in league_lower or "women" in home_lower or "women" in away_lower:
                continue
            
            # Extract scores if they exist
            home_score_el = ancestor.find(class_=lambda x: x and 'HomeScore' in x)
            away_score_el = ancestor.find(class_=lambda x: x and 'AwayScore' in x)
            
            home_score = home_score_el.get_text().strip() if home_score_el else None
            away_score = away_score_el.get_text().strip() if away_score_el else None
            
            # Extract match status/progress
            progress_el = ancestor.find(class_=lambda x: x and 'MatchProgress' in x)
            progress = progress_el.get_text().strip() if progress_el else "Fixture"
            
            # Build clean title and description
            if home_score is not None and away_score is not None:
                title = f"{home_team} {home_score} - {away_score} {away_team}"
                desc = f"Status: {progress}"
            else:
                title = f"{home_team} vs {away_team}"
                desc = f"Fixture/Kickoff. Status: {progress or 'Not started'}"
                
            # Extract match link
            link_el = ancestor.find('a', href=True)
            link = "https://www.bbc.com" + link_el['href'] if link_el and link_el['href'].startswith('/') else (link_el['href'] if link_el else "https://www.bbc.com/sport/football/scores-fixtures")
            
            results.append({
                "title": title,
                "description": desc,
                "link": link,
                "published": "Today",
                "is_match": True,
                "league": league,
                "home_team": home_team,
                "away_team": away_team
            })
            
    except Exception as e:
        logger.error(f"Failed to scrape HTML live scores: {str(e)}")
        
    return results

def fetch_live_football_feed() -> List[Dict[str, Any]]:
    """
    Fetches both real-time match scores (via HTML scraping) and 
    breaking football news headlines (via RSS feed parsing).
    
    Returns a unified feed list.
    """
    logger.info("Assembling real-time football feed (HTML scores + RSS headlines)...")
    
    # 1. Fetch scores from HTML page
    scores = fetch_live_scores_from_html()
    
    # 2. Fetch news headlines from RSS feed
    news = []
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(BBC_FEED_URL, headers=headers, timeout=8)
        response.raise_for_status()
        
        # Parse XML content
        root = ET.fromstring(response.content)
        channel = root.find("channel")
        if channel is None:
            logger.warning("Invalid RSS feed structure: <channel> element not found.")
            return scores
            
        items = channel.findall("item")
        for item in items:
            title = item.find("title")
            title_text = title.text.strip() if title is not None and title.text else ""
            
            description = item.find("description")
            desc_text = description.text.strip() if description is not None and description.text else ""
            
            link = item.find("link")
            link_text = link.text.strip() if link is not None and link.text else ""
            
            pub_date = item.find("pubDate")
            date_text = pub_date.text.strip() if pub_date is not None and pub_date.text else ""
            
            # RSS feed items are strictly categorized as news (is_match = False)
            news.append({
                "title": title_text,
                "description": desc_text,
                "link": link_text,
                "published": date_text,
                "is_match": False,
                "league": "Breaking News"
            })
    except Exception as e:
        logger.error(f"Failed to fetch RSS football headlines: {str(e)}")
        
    logger.info(f"Unified Feed Compiled: {len(scores)} live matches, {len(news)} news articles.")
    return scores + news

def get_live_scores_context() -> str:
    """
    Gathers matches and news, formatting it into a highly structured 
    text block for dynamic prompt context injection.
    """
    items = fetch_live_football_feed()
    if not items:
        return "REAL-TIME SERVICE UPDATE: Unable to fetch live match scores or football news at this moment."
        
    context_lines = [
        "=== REAL-TIME FOOTBALL LATEST SCORES & BREAKING NEWS ===",
        "Source: BBC Sport Live Scores & News (Aggregated real-time updates)",
        ""
    ]
    
    matches = [i for i in items if i["is_match"]]
    news = [i for i in items if not i["is_match"]]
    
    if matches:
        context_lines.append("--- TODAY'S LIVE MATCHES & RECENT RESULTS ---")
        for idx, m in enumerate(matches[:15]): # top 15 matches
            context_lines.append(f"[{idx+1}] Score/Fixture: {m['title']} (League: {m.get('league', 'Unknown League')})")
            context_lines.append(f"    Details: {m['description']}")
            context_lines.append(f"    Match Centre Link: {m['link']}")
            context_lines.append("")
            
    if news:
        context_lines.append("--- BREAKING FOOTBALL HEADLINES & TRANSFERS ---")
        for idx, n in enumerate(news[:15]): # top 15 news headlines
            context_lines.append(f"[{idx+1}] Headline: {n['title']}")
            context_lines.append(f"    Summary: {n['description']}")
            context_lines.append(f"    Full Article: {n['link']}")
            context_lines.append("")
            
    return "\n".join(context_lines)

def fetch_historical_results_from_html() -> List[Dict[str, Any]]:
    """
    Crawls past football scorelines from multiple BBC scores-fixtures URLs
    (today, yesterday, and two days ago) using BeautifulSoup,
    parsing home/away teams, final scores, dates, and leagues.
    """
    import datetime
    
    today = datetime.date.today()
    urls_to_crawl = [
        ("https://www.bbc.com/sport/football/scores-fixtures", "Today"),
        (f"https://www.bbc.com/sport/football/scores-fixtures/{today - datetime.timedelta(days=1)}", (today - datetime.timedelta(days=1)).strftime("%d %b %Y")),
        (f"https://www.bbc.com/sport/football/scores-fixtures/{today - datetime.timedelta(days=2)}", (today - datetime.timedelta(days=2)).strftime("%d %b %Y")),
    ]
    
    logger.info(f"Scraping historical football results from BBC Sport website for {len(urls_to_crawl)} dates...")
    results = []
    seen_matches = set()
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    }
    
    for url, date_fallback in urls_to_crawl:
        try:
            from bs4 import BeautifulSoup
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            response.encoding = 'utf-8'  # Force UTF-8 so special chars (ç, é, ñ) decode correctly
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find all home team elements
            home_teams = soup.find_all(class_=lambda x: x and 'StyledTeam-HomeTeam' in x)
            logger.info(f"HTML Results Scraper: found {len(home_teams)} potential result elements on {url}.")
            
            for ht in home_teams:
                # Traversal to find the smallest common ancestor containing both teams
                ancestor = ht
                while ancestor:
                    away_el = ancestor.find(class_=lambda x: x and 'StyledTeam-AwayTeam' in x)
                    if away_el:
                        break
                    ancestor = ancestor.parent
                    
                if not ancestor:
                    continue
                    
                # Extract the nearest preceding h2 as the League name
                h2 = ht.find_previous('h2')
                league = h2.get_text().strip() if h2 else "Unknown League"
                
                # Find the nearest preceding h3 or date divider
                h3 = ht.find_previous('h3')
                date_str = h3.get_text().strip() if h3 else date_fallback
                
                # If date_str is a group or round instead of a calendar date, include date_fallback
                date_str_lower = date_str.lower()
                is_real_date = any(m in date_str_lower for m in ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec', 'today', 'yesterday'])
                if not is_real_date and date_fallback != "Today":
                    date_str = f"{date_fallback} - {date_str}"
                
                # Extract clean Home Team name
                home_team_el = ht.find(class_=lambda x: x and 'DesktopValue' in x)
                if not home_team_el:
                    home_team_el = ht.find('span')
                home_team = home_team_el.get_text().strip() if home_team_el else ht.get_text().strip()
                
                # Extract clean Away Team name
                away_team_container = ancestor.find(class_=lambda x: x and 'StyledTeam-AwayTeam' in x)
                away_team_el = away_team_container.find(class_=lambda x: x and 'DesktopValue' in x) if away_team_container else None
                if away_team_container and not away_team_el:
                    away_team_el = away_team_container.find('span')
                away_team = away_team_el.get_text().strip() if away_team_el else "Unknown"

                # Filter to include only men's football matches
                league_lower = league.lower()
                home_lower = home_team.lower()
                away_lower = away_team.lower()
                if "women" in league_lower or "women" in home_lower or "women" in away_lower:
                    continue
                
                # Extract scores
                home_score_el = ancestor.find(class_=lambda x: x and 'HomeScore' in x)
                away_score_el = ancestor.find(class_=lambda x: x and 'AwayScore' in x)
                
                home_score = None
                away_score = None
                try:
                    if home_score_el:
                        home_score = int(home_score_el.get_text().strip())
                    if away_score_el:
                        away_score = int(away_score_el.get_text().strip())
                except ValueError:
                    pass
                    
                match_key = (home_team.lower(), away_team.lower(), league.lower())
                if match_key not in seen_matches:
                    seen_matches.add(match_key)
                    results.append({
                        "home_team": home_team,
                        "away_team": away_team,
                        "home_score": home_score,
                        "away_score": away_score,
                        "match_date": date_str,
                        "league": league
                    })
                    
        except Exception as e:
            logger.error(f"Failed to scrape HTML historical results for {url}: {str(e)}")
        
    return results

