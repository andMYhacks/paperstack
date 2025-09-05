import argparse
import asyncio
import os
from datetime import datetime
from pathlib import Path

# Load .env file if it exists
env_path = Path('.') / '.env'
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                os.environ[key] = value

from arxiv_utils import fill_papers_with_arxiv, search_arxiv_as_paper
from notion_utils import (
    get_notion_client,
    get_papers_from_notion,
    write_papers_to_notion,
)
from openai_utils import (
    get_attack_type_from_abstract,
    get_focus_label_from_abstract,
    get_openai_client,
    summarize_abstract_with_openai,
)
from claude_utils import (
    get_claude_client,
    summarize_abstract_with_claude,
    get_focus_label_from_abstract as get_focus_label_from_abstract_claude,
    get_attack_type_from_abstract as get_attack_type_from_abstract_claude,
)
from scholar_utils import get_recommended_arxiv_ids_from_semantic_scholar

def prompt_user_for_query() -> str:
    """Prompt the user for a new arXiv search query."""
    print("\n💡 Please provide a new search query for arXiv.")
    print("Examples:")
    print("  - \"machine learning security\"")
    print("  - \"adversarial examples neural networks\"") 
    print("  - \"LLM vulnerabilities\"")
    print("  - Or type 'default' to use the default AI security query")
    print("  - Or type 'skip' to skip arXiv search and continue with existing papers")
    
    while True:
        query = input("\nEnter your search query (or 'skip'): ").strip()
        if query:
            if query.lower() == 'default':
                return ARXIV_SEARCH.strip()
            elif query.lower() == 'skip':
                return 'SKIP_SEARCH'
            return query
        print("Please enter a non-empty query or 'skip'.")

def search_arxiv_with_retry(initial_query: str, max_results: int = 500, debug: bool = False) -> list:
    """Search arXiv with error handling and user retry prompts."""
    current_query = initial_query
    
    while True:
        try:
            if debug:
                print(f"    |- Debug: Searching arXiv with query: {current_query[:100]}...")
            
            # Import here to handle the UnexpectedEmptyPageError
            try:
                import arxiv
                from arxiv_utils import search_arxiv_as_paper
            except ImportError as e:
                print(f"❌ Error: Required modules not available: {e}")
                return []
            
            # Attempt the search
            results = search_arxiv_as_paper(current_query, max_results=max_results)
            
            if not results:
                print(f"⚠️  No papers found for query: {current_query[:50]}...")
                print("This could be due to:")
                print("  - Query too specific or unusual terms")
                print("  - Network connectivity issues") 
                print("  - arXiv API temporary issues")
                
                current_query = prompt_user_for_query()
                if current_query == 'SKIP_SEARCH':
                    print("    |- Skipping arXiv search as requested")
                    return []
                continue
            
            return results
            
        except Exception as e:
            error_type = type(e).__name__
            if "UnexpectedEmptyPage" in error_type or "EmptyPage" in str(e):
                print(f"⚠️  arXiv search returned empty results for query: {current_query[:50]}...")
                print("This usually means the search terms didn't match any papers.")
            else:
                print(f"❌ arXiv search error ({error_type}): {str(e)}")
                if debug:
                    import traceback
                    traceback.print_exc()
            
            print("Let's try a different search query.")
            current_query = prompt_user_for_query()
            if current_query == 'SKIP_SEARCH':
                print("    |- Skipping arXiv search as requested")
                return []

def format_notion_id(id_string: str) -> str:
    """Format a Notion ID string into proper UUID format if needed."""
    if not id_string:
        return id_string
    
    # Remove any existing hyphens
    clean_id = id_string.replace('-', '')
    
    # If it's 32 characters (hex UUID without hyphens), format it
    if len(clean_id) == 32:
        return f"{clean_id[:8]}-{clean_id[8:12]}-{clean_id[12:16]}-{clean_id[16:20]}-{clean_id[20:]}"
    
    # Otherwise return as-is
    return id_string

ARXIV_SEARCH = """\
"adversarial attacks" OR "language model attacks" OR "LLM vulnerabilities" OR \
"AI security" OR "machine learning security" OR "jailbreak" OR "bypassing AI"\
"""


async def main():
    parser = argparse.ArgumentParser(
        description="Paperstack: Automated academic paper research workflow with Notion integration and AI analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic Claude workflow (retrieves existing papers + searches arXiv + processes with Claude)
  python paperstack.py --use-claude
  
  # Limit new papers and enable debugging
  python paperstack.py --use-claude --max-papers 5 --debug
  
  # Use OpenAI with specific search
  python paperstack.py --search-arxiv --arxiv-search-query "machine learning security"
  
  # Environment variables (can be set in .env file):
  NOTION_TOKEN, NOTION_DATABASE_ID, CLAUDE_API_KEY, OPENAI_API_TOKEN
        """
    )

    parser.add_argument(
        "--notion-token",
        type=str,
        default=os.environ.get("NOTION_TOKEN"),
        help="Notion API token (default: NOTION_TOKEN env var)",
    )
    parser.add_argument(
        "--database-id",
        type=str,
        default=os.environ.get("NOTION_DATABASE_ID"),
        help="Notion database ID (default: NOTION_DATABASE_ID env var)",
    )
    parser.add_argument(
        "--openai-token",
        type=str,
        default=os.environ.get("OPENAI_API_TOKEN"),
        help="OpenAI API token (default: OPENAI_API_TOKEN env var)",
    )
    parser.add_argument(
        "--claude-token",
        type=str,
        default=os.environ.get("CLAUDE_API_KEY"),
        help="Claude API token (default: CLAUDE_API_KEY env var)",
    )
    parser.add_argument(
        "--use-claude",
        action="store_true",
        default=False,
        help="Use Claude API for analysis instead of OpenAI (automatically enables --search-arxiv)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="Enable detailed debug output and logging",
    )
    parser.add_argument(
        "--max-papers",
        type=int,
        default=None,
        help="Maximum number of NEW papers to retrieve from arXiv and process (does not limit existing Notion papers)",
    )
    parser.add_argument(
        "--arxiv-search-query", 
        type=str, 
        default=ARXIV_SEARCH,
        help="Custom arXiv search query (default: AI security terms)"
    )
    parser.add_argument(
        "--search-arxiv", 
        action="store_true", 
        default=False,
        help="Search arXiv for new papers to add to database"
    )
    parser.add_argument(
        "--search-semantic-scholar", 
        action="store_true", 
        default=False,
        help="Search Semantic Scholar for related papers"
    )

    args = parser.parse_args()
    print("[+] Paperstack")
    
    # Debug environment variables (only if --debug flag is set)
    if args.debug:
        print(f" |- Debug: NOTION_DATABASE_ID from env: {os.environ.get('NOTION_DATABASE_ID')}")
        print(f" |- Debug: args.database_id: {args.database_id}")
        print(f" |- Debug: NOTION_TOKEN from env: {os.environ.get('NOTION_TOKEN')[:10] if os.environ.get('NOTION_TOKEN') else None}...")
    
    if not args.database_id:
        print("❌ Error: No database ID provided!")
        print("   Set NOTION_DATABASE_ID environment variable or use --database-id")
        return 1
    
    if not args.notion_token:
        print("❌ Error: No Notion token provided!")
        print("   Set NOTION_TOKEN environment variable or use --notion-token")
        return 1
    
    # Validate max-papers argument
    if args.max_papers is not None and args.max_papers <= 0:
        print("❌ Error: --max-papers must be a positive integer")
        return 1
    
    # Format database ID properly
    formatted_db_id = format_notion_id(args.database_id)
    if args.debug:
        print(f" |- Debug: Formatted database ID: {formatted_db_id}")
        print(f" |- Debug: Max papers limit: {args.max_papers if args.max_papers else 'No limit'}")

    notion_client = get_notion_client(args.notion_token)
    
    if args.use_claude:
        ai_client = get_claude_client(args.claude_token)
        ai_name = "Claude"
        # Enable arXiv search by default when using Claude for the full workflow
        if not args.search_arxiv and not args.search_semantic_scholar:
            args.search_arxiv = True
            print(" |- Enabling arXiv search for Claude workflow")
        
        # Show limit information for Claude workflow
        if args.max_papers:
            print(f" |- New paper limit: {args.max_papers} new papers maximum (existing Notion papers unlimited)")
    else:
        ai_client = get_openai_client(args.openai_token)
        ai_name = "OpenAI"

    print(f" |- Getting papers from Notion database [{formatted_db_id}]")
    try:
        papers = await get_papers_from_notion(notion_client, formatted_db_id, debug=args.debug)
        print(f"    |- {len(papers)} existing papers")
        
        # Track existing vs new papers for limit calculations
        existing_paper_count = len(papers)
    except Exception as e:
        print(f"    |- Error retrieving papers from Notion: {e}")
        print("    |- Continuing with empty paper list...")
        papers = []
        existing_paper_count = 0

    for p in papers:
        if p.published < datetime.fromisoformat("2024-07-01 00:00:00+00:00"):
            p.explored = True

        if len(p.authors) > 5:
            p.authors = p.authors[:5]

    if not all([p.has_arxiv_props() for p in papers]):
        print(" |- Filling in missing data from arXiv")
        papers = fill_papers_with_arxiv(papers)

    if args.debug:
        print(f" |- Debug: args.search_arxiv = {args.search_arxiv}")
        print(f" |- Debug: existing_paper_count = {existing_paper_count}")
        print(f" |- Debug: args.max_papers = {args.max_papers}")
    
    if args.search_arxiv:
        print(" |- Searching arXiv for new papers")
        existing_titles = [paper.title for paper in papers]
        
        # Set search limit based on max_papers (independent of existing Notion papers)
        if args.max_papers:
            # For small limits, search much more broadly to account for duplicates
            if args.max_papers <= 5:
                arxiv_limit = min(500, args.max_papers * 50)  # Much broader search for small limits
            else:
                arxiv_limit = min(500, args.max_papers * 5)   # Moderate search for larger limits
            print(f"    |- Will add up to {args.max_papers} new papers from arXiv (searching {arxiv_limit} papers to find unique ones)")
        else:
            arxiv_limit = 500
            print(f"    |- Searching for new papers (no limit)")
        
        # Use the new error-handling search function
        searched_papers = search_arxiv_with_retry(
            args.arxiv_search_query, 
            max_results=arxiv_limit, 
            debug=args.debug
        )
        
        new_papers_count = 0
        duplicate_count = 0
        
        for searched_paper in searched_papers:
            if searched_paper.title not in existing_titles:
                # Stop if we've reached the limit for NEW papers (before adding this one)
                if args.max_papers and new_papers_count >= args.max_papers:
                    break
                    
                print(f"    |- {searched_paper.title[:50]}...")
                papers.append(searched_paper)
                new_papers_count += 1
            else:
                duplicate_count += 1
        
        if args.debug:
            print(f"    |- Debug: Found {len(searched_papers)} total papers, {duplicate_count} duplicates, {new_papers_count} unique")
        
        limit_msg = f" (limited to {args.max_papers} new papers)" if args.max_papers and new_papers_count >= args.max_papers else ""
        print(f"    |- Added {new_papers_count} new papers from arXiv{limit_msg}")
    else:
        print(f" |- Skipping arXiv search (args.search_arxiv = {args.search_arxiv})")

    if args.search_semantic_scholar:
        to_explore = [p for p in papers if not p.explored]
        if to_explore:
            print(" |- Getting related papers from Semantic Scholar")
            recommended_papers = get_recommended_arxiv_ids_from_semantic_scholar(to_explore)
            papers.extend(fill_papers_with_arxiv(recommended_papers))
            print(f"    |- {len(recommended_papers)} new papers")
        else:
            print(" |- All papers have been explored")

    # Only process NEW arXiv papers (not existing Notion papers)
    new_papers_needing_summary = [p for p in papers[existing_paper_count:] if not p.summary and p.abstract]
    
    if new_papers_needing_summary:
        print(f" |- Building summaries with {ai_name} for {len(new_papers_needing_summary)} new arXiv papers")
        
        for paper in new_papers_needing_summary:
            print(f"    |- {paper.title[:50]}...")
            if args.use_claude:
                paper.summary = summarize_abstract_with_claude(
                    ai_client, paper.abstract
                )
            else:
                paper.summary = summarize_abstract_with_openai(
                    ai_client, paper.abstract
                )

    # Only process NEW arXiv papers (not existing Notion papers)
    new_papers_needing_focus = [p for p in papers[existing_paper_count:] if not p.focus and (p.abstract or p.summary)]
    
    if new_papers_needing_focus:
        print(f" |- Assigning focus labels with {ai_name} for {len(new_papers_needing_focus)} new arXiv papers")
        
        for paper in new_papers_needing_focus:
            reference = paper.abstract or paper.summary
            if args.use_claude:
                paper.focus = get_focus_label_from_abstract_claude(ai_client, reference)
            else:
                paper.focus = get_focus_label_from_abstract(ai_client, reference)
            print(f"    |- {paper.focus}")

    # Only process NEW arXiv papers (not existing Notion papers)
    new_papers_needing_attack_type = [p for p in papers[existing_paper_count:] if not p.attack_type and (p.abstract or p.summary)]
    
    if new_papers_needing_attack_type:
        print(f" |- Assigning attack types with {ai_name} for {len(new_papers_needing_attack_type)} new arXiv papers")
        
        for paper in new_papers_needing_attack_type:
            reference = paper.abstract or paper.summary
            if args.use_claude:
                paper.attack_type = get_attack_type_from_abstract_claude(ai_client, reference)
            else:
                paper.attack_type = get_attack_type_from_abstract(ai_client, reference)
            print(f"    |- {paper.attack_type}")
            
    to_write = [p for p in papers if p.has_changed()]
    if to_write:
        print(f" |- Writing {len(to_write)} updates back to Notion")
        try:
            await write_papers_to_notion(notion_client, formatted_db_id, to_write)
            print("    |- Successfully written to Notion")
        except Exception as e:
            print(f"    |- Error writing to Notion: {e}")
            return 1
    else:
        print(" |- No changes to write back to Notion")

    print("[+] Done!")
    return 0


if __name__ == "__main__":
    import sys
    
    # Handle --help explicitly for clean exit
    if "--help" in sys.argv or "-h" in sys.argv:
        try:
            # Create parser and show help
            parser = argparse.ArgumentParser(
                description="Paperstack: Automated academic paper research workflow with Notion integration and AI analysis",
                formatter_class=argparse.RawDescriptionHelpFormatter,
                epilog="""
Examples:
  # Basic Claude workflow (retrieves existing papers + searches arXiv + processes with Claude)
  python paperstack.py --use-claude
  
  # Limit new papers and enable debugging
  python paperstack.py --use-claude --max-papers 5 --debug
  
  # Use OpenAI with specific search
  python paperstack.py --search-arxiv --arxiv-search-query "machine learning security"
  
  # Environment variables (can be set in .env file):
  NOTION_TOKEN, NOTION_DATABASE_ID, CLAUDE_API_KEY, OPENAI_API_TOKEN
                """
            )
            
            parser.add_argument("--notion-token", type=str, help="Notion API token (default: NOTION_TOKEN env var)")
            parser.add_argument("--database-id", type=str, help="Notion database ID (default: NOTION_DATABASE_ID env var)")
            parser.add_argument("--openai-token", type=str, help="OpenAI API token (default: OPENAI_API_TOKEN env var)")
            parser.add_argument("--claude-token", type=str, help="Claude API token (default: CLAUDE_API_KEY env var)")
            parser.add_argument("--use-claude", action="store_true", help="Use Claude API for analysis instead of OpenAI (automatically enables --search-arxiv)")
            parser.add_argument("--debug", action="store_true", help="Enable detailed debug output and logging")
            parser.add_argument("--max-papers", type=int, help="Maximum number of NEW papers to retrieve from arXiv and process (does not limit existing Notion papers)")
            parser.add_argument("--arxiv-search-query", type=str, help="Custom arXiv search query (default: AI security terms)")
            parser.add_argument("--search-arxiv", action="store_true", help="Search arXiv for new papers to add to database")
            parser.add_argument("--search-semantic-scholar", action="store_true", help="Search Semantic Scholar for related papers")
            
            parser.print_help()
            sys.exit(0)
        except Exception:
            # Fallback to letting argparse handle it normally
            pass
    
    # Run the main application
    try:
        exit_code = asyncio.run(main())
        if exit_code and exit_code != 0:
            sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n[!] Interrupted by user")
        sys.exit(130)  # Standard exit code for SIGINT
    except Exception as e:
        print(f"[!] Unexpected error: {e}")
        if hasattr(e, '__traceback__'):
            import traceback
            print("\nFull traceback:")
            traceback.print_exc()
        sys.exit(1)
