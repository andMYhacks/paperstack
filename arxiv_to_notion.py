#!/usr/bin/env python3
"""
ArXiv to Notion Utility

A standalone utility to:
1. Search and retrieve papers from arXiv
2. Analyze papers using Claude API (summaries, focus labels, attack types)
3. Write enriched paper data to Notion database

Usage:
    python arxiv_to_notion.py --query "adversarial attacks" --max-results 50
    python arxiv_to_notion.py --use-default-query --max-results 100
"""

import argparse
import asyncio
import os
from datetime import datetime
from typing import List

try:
    from arxiv_utils import search_arxiv_as_paper
    from claude_utils import (
        get_claude_client,
        summarize_abstract_with_claude,
        get_focus_label_from_abstract,
        get_attack_type_from_abstract,
    )
    from notion_utils import (
        get_notion_client,
        validate_notion_token,
        write_papers_to_notion,
    )
    DEPENDENCIES_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Some dependencies not available: {e}")
    DEPENDENCIES_AVAILABLE = False

try:
    from _types import Paper
except ImportError:
    print("Warning: _types module not available")
    Paper = None

# Default search query for AI security papers
DEFAULT_ARXIV_QUERY = """
"adversarial attacks" OR "language model attacks" OR "LLM vulnerabilities" OR 
"AI security" OR "machine learning security" OR "jailbreak" OR "bypassing AI" OR
"prompt injection" OR "model extraction" OR "model inversion" OR "model poisoning"
"""


async def process_papers_with_claude(papers: List[Paper], claude_client) -> List[Paper]:
    """Process papers with Claude API to generate summaries and labels."""
    print(f" |- Processing {len(papers)} papers with Claude API")
    
    processed_count = 0
    for paper in papers:
        if not paper.abstract:
            print(f"    |- Skipping {paper.title[:50]}... (no abstract)")
            continue
            
        print(f"    |- Processing {paper.title[:50]}...")
        
        try:
            # Generate summary
            if not paper.summary:
                paper.summary = summarize_abstract_with_claude(claude_client, paper.abstract)
                print(f"      |- Generated summary: {paper.summary[:100]}...")
            
            # Assign focus label
            if not paper.focus:
                paper.focus = get_focus_label_from_abstract(claude_client, paper.abstract)
                print(f"      |- Assigned focus: {paper.focus}")
            
            # Assign attack type
            if not paper.attack_type:
                paper.attack_type = get_attack_type_from_abstract(claude_client, paper.abstract)
                print(f"      |- Assigned attack type: {paper.attack_type}")
                
            processed_count += 1
            
        except Exception as e:
            print(f"      |- Error processing paper: {e}")
            continue
    
    print(f" |- Successfully processed {processed_count}/{len(papers)} papers")
    return papers


async def main():
    if not DEPENDENCIES_AVAILABLE:
        print("Error: Required dependencies not available. Please install:")
        print("  pip install arxiv notion-client anthropic")
        return 1
        
    parser = argparse.ArgumentParser(
        description="Retrieve arXiv papers and store them in Notion with Claude AI analysis"
    )
    
    # API tokens
    parser.add_argument(
        "--notion-token",
        type=str,
        default=os.environ.get("NOTION_TOKEN"),
        help="Notion API token (default: NOTION_TOKEN env var)"
    )
    parser.add_argument(
        "--database-id", 
        type=str,
        default=os.environ.get("DATABASE_ID"),
        help="Notion database ID (default: DATABASE_ID env var)"
    )
    parser.add_argument(
        "--claude-token",
        type=str, 
        default=os.environ.get("CLAUDE_API_KEY"),
        help="Claude API token (default: CLAUDE_API_KEY env var)"
    )
    
    # ArXiv search parameters
    parser.add_argument(
        "--query",
        type=str,
        help="Custom arXiv search query"
    )
    parser.add_argument(
        "--use-default-query",
        action="store_true",
        help="Use the default AI security query"
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=20,
        help="Maximum number of papers to retrieve (default: 20)"
    )
    
    # Processing options
    parser.add_argument(
        "--skip-analysis",
        action="store_true", 
        help="Skip Claude analysis and only retrieve basic paper data"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Process papers but don't write to Notion"
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.query and not args.use_default_query:
        parser.error("Must specify either --query or --use-default-query")
    
    if not args.notion_token:
        parser.error("Notion token required (set NOTION_TOKEN env var or use --notion-token)")
        
    if not args.database_id:
        parser.error("Database ID required (set DATABASE_ID env var or use --database-id)")
        
    if not args.skip_analysis and not args.claude_token:
        parser.error("Claude token required for analysis (set CLAUDE_API_KEY env var or use --claude-token)")
    
    print("[+] ArXiv to Notion Utility")
    print(f"    |- Max results: {args.max_results}")
    print(f"    |- Skip analysis: {args.skip_analysis}")
    print(f"    |- Dry run: {args.dry_run}")
    
    # Determine search query
    search_query = args.query if args.query else DEFAULT_ARXIV_QUERY.strip()
    print(f"    |- Search query: {search_query[:100]}...")
    
    # Initialize clients
    notion_client = get_notion_client(args.notion_token)
    if not args.skip_analysis:
        claude_client = get_claude_client(args.claude_token)
    
    # Validate Notion token
    print(" |- Validating Notion API token...")
    if not await validate_notion_token(notion_client):
        print("    |- Invalid Notion token, exiting...")
        return
    print("    |- Notion token valid")
    
    # Search arXiv for papers
    print(f" |- Searching arXiv for papers...")
    papers = search_arxiv_as_paper(search_query, max_results=args.max_results)
    print(f"    |- Found {len(papers)} papers")
    
    if not papers:
        print(" |- No papers found, exiting...")
        return
    
    # Process with Claude if not skipping analysis
    if not args.skip_analysis:
        papers = await process_papers_with_claude(papers, claude_client)
    
    # Write to Notion unless dry run
    if args.dry_run:
        print(" |- Dry run mode: skipping Notion write")
        print(" |- Sample processed papers:")
        for i, paper in enumerate(papers[:3]):
            print(f"    {i+1}. {paper.title}")
            print(f"       Authors: {', '.join(paper.authors[:3])}...")
            if paper.summary:
                print(f"       Summary: {paper.summary[:100]}...")
            if paper.focus:
                print(f"       Focus: {paper.focus}")
            if paper.attack_type:
                print(f"       Attack Type: {paper.attack_type}")
            print()
    else:
        print(f" |- Writing {len(papers)} papers to Notion...")
        await write_papers_to_notion(notion_client, args.database_id, papers)
        print("    |- Successfully written to Notion")
    
    print("[+] Done!")


if __name__ == "__main__":
    asyncio.run(main())