// Mirrors backend src/schemas/books.py

export interface BookIdentifiers {
  isbn_10?: string | null;
  isbn_13?: string | null;
  source_id?: string | null;
}

export interface ExternalLink {
  kind: string;
  label: string;
  url: string;
}

export interface ReadingEstimate {
  word_count?: number | null;
  page_count?: number | null;
  minutes?: number | null;
}

export interface BookMetadata {
  book_id: string;
  provider: string;
  title: string;
  authors: string[];
  description?: string | null;
  categories: string[];
  cover_url?: string | null;
  published_date?: string | null;
  language?: string | null;
  identifiers: BookIdentifiers;
  links: ExternalLink[];
  reading_estimate: ReadingEstimate;
}

export interface BookSearchResults {
  items: BookMetadata[];
  next_cursor?: string | null;
  query: string;
}
