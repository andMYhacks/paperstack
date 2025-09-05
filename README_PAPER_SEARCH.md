# Paper Search Utility

A simple command-line tool to search arXiv for academic papers and display titles and links. Built on top of the existing `arxiv_utils.py` functionality.

## Installation

Install the required dependency:
```bash
pip install arxiv
```

## Usage

### Basic Usage

Search with a custom query and display 10 papers:
```bash
python paper_search.py --query "machine learning security" --limit 10
```

Use the default AI security query:
```bash
python paper_search.py --use-default-query --limit 20
```

### Advanced Options

Search with custom sorting and additional metadata:
```bash
python paper_search.py --query "adversarial attacks" --limit 5 --sort relevance --show-authors --show-abstract
```

Use detailed output format:
```bash
python paper_search.py --use-default-query --limit 15 --output-format detailed
```

## Command Line Options

### Required (one of):
- `--query "search terms"`: Custom search query
- `--use-default-query`: Use default AI security research query

### Optional:
- `--limit N`: Number of papers to retrieve (default: 10)
- `--sort {date,relevance,lastUpdatedDate}`: Sort criterion (default: date)
- `--show-authors`: Include author information
- `--show-abstract`: Include abstract preview (first 200 chars)
- `--output-format {simple,detailed}`: Output format (default: simple)

## Default Query

The default query searches for papers related to AI security topics:
- Adversarial attacks
- Language model attacks  
- LLM vulnerabilities
- AI/ML security
- Jailbreak techniques
- Bypassing AI systems
- Prompt injection
- Model extraction/inversion/poisoning

## Output Format

### Simple Format (Default)
```
📚 Found 5 papers:

================================================================================
 1. Adversarial Examples for Evaluating Reading Comprehension Systems
    🔗 Link: http://arxiv.org/abs/1707.07328
--------------------------------------------------------------------------------
 2. Explaining and Harnessing Adversarial Examples
    🔗 Link: http://arxiv.org/abs/1412.6572
--------------------------------------------------------------------------------
```

### Detailed Format
Includes authors and abstract previews:
```
📚 Found 5 papers:

================================================================================
 1. Adversarial Examples for Evaluating Reading Comprehension Systems
    🔗 Link: http://arxiv.org/abs/1707.07328
    👥 Authors: Robin Jia, Percy Liang
    📝 Abstract: Standard accuracy metrics indicate that reading comprehension systems are making rapid progress...
--------------------------------------------------------------------------------
```

## Examples

**Search for specific topic with author info:**
```bash
python paper_search.py --query "neural network robustness" --limit 8 --show-authors
```

**Get latest papers in AI security:**
```bash
python paper_search.py --use-default-query --limit 25 --sort date
```

**Search for most relevant papers with previews:**
```bash
python paper_search.py --query "prompt injection attacks" --limit 12 --sort relevance --show-abstract
```

**Quick overview of recent AI security research:**
```bash
python paper_search.py --use-default-query --limit 30 --output-format detailed
```

## Features

- ✅ **Flexible Search**: Custom queries or curated default AI security query
- ✅ **Configurable Results**: User-specified limit (1-1000+ papers)
- ✅ **Multiple Sort Options**: Date, relevance, or last updated
- ✅ **Rich Output**: Titles, links, authors, and abstract previews
- ✅ **Error Handling**: Graceful handling of API issues and missing dependencies
- ✅ **Clean Interface**: Formatted output with emojis and clear structure

## Integration

This utility builds upon `arxiv_utils.py` and can be used alongside:
- `paperstack.py` (main research workflow)
- `arxiv_to_notion.py` (arXiv-to-Notion automation)

It provides a lightweight way to explore arXiv papers before committing to full processing workflows.