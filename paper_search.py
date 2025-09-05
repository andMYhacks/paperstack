#!/usr/bin/env python3
"""
Paper Search Utility

A simple command-line tool to search arXiv for academic papers and display
titles and links. Built on top of arxiv_utils.py functionality.

Usage:
    python paper_search.py --query "machine learning security" --limit 10
    python paper_search.py --use-default-query --limit 20
    python paper_search.py --query "adversarial attacks" --limit 5 --sort relevance
"""

import argparse
import sys
from typing import List

try:
    import arxiv
    from arxiv_utils import search_arxiv, search_arxiv_as_paper
    ARXIV_AVAILABLE = True
except ImportError as e:
    print(f"Error: Required arxiv module not available: {e}")
    print("Please install with: pip install arxiv")
    ARXIV_AVAILABLE = False

# Default search query for AI security papers (same as used in other utilities)
DEFAULT_QUERY = """
"adversarial attacks" OR "language model attacks" OR "LLM vulnerabilities" OR 
"AI security" OR "machine learning security" OR "jailbreak" OR "bypassing AI" OR
"prompt injection" OR "model extraction" OR "model inversion" OR "model poisoning"
"""


def format_paper_output(papers: List, show_abstract: bool = False, show_authors: bool = False) -> None:
    """Format and display paper results."""
    if not papers:
        print("No papers found.")
        return
    
    print(f"\n📚 Found {len(papers)} papers:\n")
    print("=" * 80)
    
    for i, paper in enumerate(papers, 1):
        # Handle both Paper objects and arxiv.Result objects
        if hasattr(paper, 'title'):
            title = paper.title
            url = paper.url if hasattr(paper, 'url') else paper.entry_id
            authors = paper.authors if hasattr(paper, 'authors') else [a.name for a in paper.authors]
            abstract = paper.abstract if hasattr(paper, 'abstract') else paper.summary
        else:
            title = paper.title
            url = paper.entry_id  
            authors = [a.name for a in paper.authors]
            abstract = paper.summary
        
        print(f"{i:2d}. {title}")
        print(f"    🔗 Link: {url}")
        
        if show_authors and authors:
            author_list = ", ".join(authors[:3])  # Show first 3 authors
            if len(authors) > 3:
                author_list += f" (and {len(authors) - 3} others)"
            print(f"    👥 Authors: {author_list}")
        
        if show_abstract and abstract:
            # Truncate abstract to first 200 characters
            abstract_preview = abstract.replace('\n', ' ')[:200]
            if len(abstract) > 200:
                abstract_preview += "..."
            print(f"    📝 Abstract: {abstract_preview}")
        
        print("-" * 80)
    
    print(f"\n✅ Displayed {len(papers)} papers")


def main():
    if not ARXIV_AVAILABLE:
        return 1
    
    parser = argparse.ArgumentParser(
        description="Search arXiv for academic papers and display titles and links",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python paper_search.py --query "machine learning security" --limit 10
  python paper_search.py --use-default-query --limit 20
  python paper_search.py --query "adversarial attacks" --limit 5 --sort relevance --show-authors
        """
    )
    
    # Search options
    search_group = parser.add_mutually_exclusive_group(required=True)
    search_group.add_argument(
        "--query",
        type=str,
        help="Custom search query for arXiv papers"
    )
    search_group.add_argument(
        "--use-default-query",
        action="store_true",
        help="Use the default AI security research query"
    )
    
    # Result options
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Number of papers to retrieve (default: 10)"
    )
    parser.add_argument(
        "--sort",
        choices=["date", "relevance", "lastUpdatedDate"],
        default="date",
        help="Sort papers by date (default), relevance, or lastUpdatedDate"
    )
    
    # Display options
    parser.add_argument(
        "--show-authors",
        action="store_true",
        help="Include author information in output"
    )
    parser.add_argument(
        "--show-abstract",
        action="store_true",
        help="Include abstract preview in output"
    )
    parser.add_argument(
        "--output-format",
        choices=["simple", "detailed"],
        default="simple",
        help="Output format: simple (titles and links) or detailed (includes metadata)"
    )
    
    args = parser.parse_args()
    
    # Validate limit
    if args.limit <= 0:
        print("Error: --limit must be a positive integer")
        return 1
    if args.limit > 1000:
        print("Warning: Large limit may take a long time. Consider using a smaller value.")
    
    # Determine search query
    if args.use_default_query:
        query = DEFAULT_QUERY.strip()
        print("🔍 Using default AI security research query")
    else:
        query = args.query
        print(f"🔍 Searching for: {query}")
    
    # Set sort criterion
    sort_map = {
        "date": arxiv.SortCriterion.SubmittedDate,
        "relevance": arxiv.SortCriterion.Relevance,
        "lastUpdatedDate": arxiv.SortCriterion.LastUpdatedDate
    }
    sort_by = sort_map[args.sort]
    
    print(f"📊 Retrieving {args.limit} papers (sorted by {args.sort})")
    print("⏳ Searching arXiv...")
    
    try:
        # Search arXiv
        results = search_arxiv(query, max_results=args.limit, sort_by=sort_by)
        
        if not results:
            print("❌ No papers found for the given query.")
            print("💡 Try adjusting your search terms or using the default query.")
            return 1
        
        # Format output based on user preference
        show_authors = args.show_authors or args.output_format == "detailed"
        show_abstract = args.show_abstract or args.output_format == "detailed"
        
        format_paper_output(results, show_abstract=show_abstract, show_authors=show_authors)
        
        # Show query info for reference
        if args.use_default_query:
            print(f"\n📋 Query used: {query[:100]}...")
        
        return 0
        
    except Exception as e:
        print(f"❌ Error searching arXiv: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())