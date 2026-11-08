export const search = {
  'search.title': 'Code search',
  'search.subtitle':
    'Semantic search across README, docs and source files of tracked repositories.',
  'search.placeholder': 'Search code (RAG)…',
  'search.submit': 'Search',
  'search.searching': 'Searching…',
  'search.results': 'Results',
  'search.empty': 'Nothing found. Change the query or the similarity threshold.',
  'search.noIndex': 'The index has not been built yet. Start indexing.',
  'search.index': 'Index repositories',
  'search.indexing': 'Indexing…',
  'search.indexStarted':
    'Indexing started. Refresh the status in a few seconds.',
  'search.refreshStatus': 'Refresh status',
  'search.status': 'Indexed: {chunks} chunks across {repos} repositories.',
  'search.unavailable':
    'RAG is unavailable: PostgreSQL + pgvector and an embedding model are required.',
  'search.embeddingUnavailable':
    'The embedding model is unavailable. Check the EMBEDDING_* settings.',
  'search.error': 'Could not run the search.',
  'search.stale': 'The index is stale — re-indexing is recommended.',
  'search.copyPath': 'Copy path',
  'search.copied': 'Path copied.',
  'search.openProject': 'Open project',
  'search.openGithub': 'Open on GitHub',
  'search.lines': 'lines {start}–{end}',
  'search.score': 'relevance {score}',
  'search.language': 'Language',
  'search.languageAll': 'All languages',
  'search.queryHint': 'For example: “where is Redis configured?”',
} as const
