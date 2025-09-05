# ArXiv to Notion Utility

A standalone Python utility that retrieves papers from arXiv, analyzes them using Claude AI, and stores the enriched data in a Notion database.

## Features

- 🔍 **arXiv Search**: Search for papers using custom or default AI security queries
- 🤖 **Claude AI Analysis**: Generate summaries, focus labels, and attack type classifications
- 📝 **Notion Integration**: Automatically write enriched paper data to Notion database
- ⚡ **Flexible Options**: Support for dry runs, skipping analysis, and custom queries

## Installation

1. Install required Python packages:
```bash
pip install arxiv notion-client anthropic
```

2. Set up environment variables in `.env`:
```bash
NOTION_TOKEN=your_notion_token_here
DATABASE_ID=your_notion_database_id_here
CLAUDE_API_KEY=your_claude_api_key_here
```

## Usage

### Basic Usage

Search arXiv with the default AI security query and process 20 papers:
```bash
python arxiv_to_notion.py --use-default-query --max-results 20
```

### Custom Query

Use a custom search query:
```bash
python arxiv_to_notion.py --query "machine learning adversarial examples" --max-results 50
```

### Dry Run

Test the workflow without writing to Notion:
```bash
python arxiv_to_notion.py --use-default-query --max-results 10 --dry-run
```

### Skip AI Analysis

Only retrieve basic paper data without Claude analysis:
```bash
python arxiv_to_notion.py --use-default-query --max-results 30 --skip-analysis
```

## Command Line Options

### Required
- `--query "search terms"` OR `--use-default-query`: Specify search terms or use default AI security query
- Environment variables: `NOTION_TOKEN`, `DATABASE_ID`, `CLAUDE_API_KEY`

### Optional
- `--max-results N`: Maximum papers to retrieve (default: 20)
- `--skip-analysis`: Skip Claude AI analysis
- `--dry-run`: Process papers but don't write to Notion
- `--notion-token TOKEN`: Override Notion token
- `--database-id ID`: Override database ID
- `--claude-token TOKEN`: Override Claude token

## Default Search Query

The default query searches for papers related to:
- Adversarial attacks
- Language model attacks
- LLM vulnerabilities
- AI security
- Machine learning security
- Jailbreak techniques
- Bypassing AI
- Prompt injection
- Model extraction/inversion/poisoning

## Paper Processing

For each paper, the utility:

1. **Retrieves** basic metadata from arXiv (title, authors, abstract, publication date)
2. **Analyzes** with Claude AI:
   - Generates concise summary (1-2 sentences)
   - Assigns focus label (research category)
   - Classifies attack type (evasion, extraction, inversion, poisoning, prompt injection)
3. **Writes** enriched data to Notion database

## Output Example

```
[+] ArXiv to Notion Utility
    |- Max results: 20
    |- Skip analysis: False
    |- Dry run: False
    |- Search query: "adversarial attacks" OR "language model attacks"...
 |- Validating Notion API token...
    |- Notion token valid
 |- Searching arXiv for papers...
    |- Found 20 papers
 |- Processing 20 papers with Claude API
    |- Processing Adversarial Examples for Natural Language...
      |- Generated summary: Novel approach to generate adversarial examples...
      |- Assigned focus: Research
      |- Assigned attack type: ModelEvasion
 |- Writing 20 papers to Notion...
    |- Successfully written to Notion
[+] Done!
```

## Error Handling

- **Invalid API tokens**: Validates tokens before processing
- **Network issues**: Includes retry logic with exponential backoff
- **Processing errors**: Continues with other papers if individual papers fail
- **Missing dependencies**: Clear error messages with installation instructions

## Integration with Main Paperstack

This utility can be used alongside the main `paperstack.py` or as a standalone tool. It uses the same underlying modules (`arxiv_utils`, `claude_utils`, `notion_utils`) but provides a focused workflow specifically for arXiv-to-Notion operations.