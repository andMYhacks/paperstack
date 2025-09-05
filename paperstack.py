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
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--notion-token",
        type=str,
        default=os.environ.get("NOTION_TOKEN"),
        help="Notion token",
    )
    parser.add_argument(
        "--database-id",
        type=str,
        default=os.environ.get("NOTION_DATABASE_ID"),
        help="Notion database id",
    )
    parser.add_argument(
        "--openai-token",
        type=str,
        default=os.environ.get("OPENAI_API_TOKEN"),
        help="OpenAI token",
    )
    parser.add_argument(
        "--claude-token",
        type=str,
        default=os.environ.get("CLAUDE_API_KEY"),
        help="Claude API token",
    )
    parser.add_argument(
        "--use-claude",
        action="store_true",
        default=False,
        help="Use Claude API instead of OpenAI",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="Enable debug output",
    )
    parser.add_argument(
        "--max-papers",
        type=int,
        default=None,
        help="Maximum number of NEW papers to retrieve from arXiv and process with Claude (does not limit existing Notion papers)",
    )
    parser.add_argument("--arxiv-search-query", type=str, default=ARXIV_SEARCH)
    parser.add_argument("--search-arxiv", action="store_true", default=False)
    parser.add_argument("--search-semantic-scholar", action="store_true", default=False)

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
        return
    
    if not args.notion_token:
        print("❌ Error: No Notion token provided!")
        print("   Set NOTION_TOKEN environment variable or use --notion-token")
        return
    
    # Validate max-papers argument
    if args.max_papers is not None and args.max_papers <= 0:
        print("❌ Error: --max-papers must be a positive integer")
        return
    
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
    papers = await get_papers_from_notion(notion_client, formatted_db_id, debug=args.debug)
    print(f"    |- {len(papers)} existing papers")
    
    # Track existing vs new papers for limit calculations
    existing_paper_count = len(papers)

    for p in papers:
        if p.published < datetime.fromisoformat("2024-07-01 00:00:00+00:00"):
            p.explored = True

        if len(p.authors) > 5:
            p.authors = p.authors[:5]

    if not all([p.has_arxiv_props() for p in papers]):
        print(" |- Filling in missing data from arXiv")
        papers = fill_papers_with_arxiv(papers)

    if args.search_arxiv:
        print(" |- Searching arXiv for new papers")
        existing_titles = [paper.title for paper in papers]
        
        # Calculate how many new papers we can add (excluding existing Notion papers)
        if args.max_papers:
            arxiv_limit = min(500, args.max_papers * 2)  # Search more to account for duplicates
            print(f"    |- Can add up to {args.max_papers} new papers from arXiv")
        else:
            arxiv_limit = 500
        
        # Use the new error-handling search function
        searched_papers = search_arxiv_with_retry(
            args.arxiv_search_query, 
            max_results=arxiv_limit, 
            debug=args.debug
        )
        
        new_papers_count = 0
        for searched_paper in searched_papers:
            if searched_paper.title not in existing_titles:
                # Stop if we've reached the limit for NEW papers (before adding this one)
                if args.max_papers and new_papers_count > args.max_papers:
                    break
                    
                print(f"    |- {searched_paper.title[:50]}...")
                papers.append(searched_paper)
                new_papers_count += 1
        
        limit_msg = f" (limited to {args.max_papers} new papers)" if args.max_papers and new_papers_count >= args.max_papers else ""
        print(f"    |- Added {new_papers_count} new papers from arXiv{limit_msg}")

    if args.search_semantic_scholar:
        to_explore = [p for p in papers if not p.explored]
        if to_explore:
            print(" |- Getting related papers from Semantic Scholar")
            recommended_papers = get_recommended_arxiv_ids_from_semantic_scholar(to_explore)
            papers.extend(fill_papers_with_arxiv(recommended_papers))
            print(f"    |- {len(recommended_papers)} new papers")
        else:
            print(" |- All papers have been explored")

    if not all([paper.summary for paper in papers]):
        papers_to_summarize = [p for p in papers if not p.summary and p.abstract]
        
        # Separate existing Notion papers from new arXiv papers
        existing_papers_to_summarize = papers_to_summarize[:existing_paper_count]
        new_papers_to_summarize = papers_to_summarize[existing_paper_count:]
        
        # Apply limit only to new papers, process all existing papers
        if args.max_papers and len(new_papers_to_summarize) > args.max_papers:
            new_papers_to_summarize = new_papers_to_summarize[:args.max_papers]
            print(f" |- Building summaries with {ai_name} ({len(existing_papers_to_summarize)} existing + {len(new_papers_to_summarize)} new papers, limited)")
        else:
            print(f" |- Building summaries with {ai_name} ({len(existing_papers_to_summarize)} existing + {len(new_papers_to_summarize)} new papers)")
        
        # Process all papers (existing + limited new)
        final_papers_to_summarize = existing_papers_to_summarize + new_papers_to_summarize
        for paper in final_papers_to_summarize:
            print(f"    |- {paper.title[:50]}...")
            if args.use_claude:
                paper.summary = summarize_abstract_with_claude(
                    ai_client, paper.abstract
                )
            else:
                paper.summary = summarize_abstract_with_openai(
                    ai_client, paper.abstract
                )

    if not all([paper.focus for paper in papers]):
        papers_to_label = [p for p in papers if not p.focus and (p.abstract or p.summary)]
        
        # Separate existing Notion papers from new arXiv papers
        existing_papers_to_label = papers_to_label[:existing_paper_count]
        new_papers_to_label = papers_to_label[existing_paper_count:]
        
        # Apply limit only to new papers, process all existing papers
        if args.max_papers and len(new_papers_to_label) > args.max_papers:
            new_papers_to_label = new_papers_to_label[:args.max_papers]
            print(f" |- Assigning focus labels with {ai_name} ({len(existing_papers_to_label)} existing + {len(new_papers_to_label)} new papers, limited)")
        else:
            print(f" |- Assigning focus labels with {ai_name} ({len(existing_papers_to_label)} existing + {len(new_papers_to_label)} new papers)")
        
        # Process all papers (existing + limited new)
        final_papers_to_label = existing_papers_to_label + new_papers_to_label
        for paper in final_papers_to_label:
            reference = paper.abstract or paper.summary
            if args.use_claude:
                paper.focus = get_focus_label_from_abstract_claude(ai_client, reference)
            else:
                paper.focus = get_focus_label_from_abstract(ai_client, reference)
            print(f"    |- {paper.focus}")

    if not all([paper.attack_type for paper in papers]):
        papers_to_classify = [p for p in papers if not p.attack_type and (p.abstract or p.summary)]
        
        # Separate existing Notion papers from new arXiv papers
        existing_papers_to_classify = papers_to_classify[:existing_paper_count]
        new_papers_to_classify = papers_to_classify[existing_paper_count:]
        
        # Apply limit only to new papers, process all existing papers
        if args.max_papers and len(new_papers_to_classify) > args.max_papers:
            new_papers_to_classify = new_papers_to_classify[:args.max_papers]
            print(f" |- Assigning attack types with {ai_name} ({len(existing_papers_to_classify)} existing + {len(new_papers_to_classify)} new papers, limited)")
        else:
            print(f" |- Assigning attack types with {ai_name} ({len(existing_papers_to_classify)} existing + {len(new_papers_to_classify)} new papers)")
        
        # Process all papers (existing + limited new)
        final_papers_to_classify = existing_papers_to_classify + new_papers_to_classify
        for paper in final_papers_to_classify:
            reference = paper.abstract or paper.summary
            if args.use_claude:
                paper.attack_type = get_attack_type_from_abstract_claude(ai_client, reference)
            else:
                paper.attack_type = get_attack_type_from_abstract(ai_client, reference)
            print(f"    |- {paper.attack_type}")
            
    to_write = [p for p in papers if p.has_changed()]
    if to_write:
        print(f" |- Writing {len(to_write)} updates back to Notion")
        await write_papers_to_notion(notion_client, formatted_db_id, to_write)

    print("[+] Done!")


if __name__ == "__main__":
    asyncio.run(main())
