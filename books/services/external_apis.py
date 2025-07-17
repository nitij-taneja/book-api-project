"""
External APIs service for retrieving book information from multiple sources.
Integrates Google Books, Gutendx, Internet Archive, and Arabic Collections Online.
"""

import requests
import urllib.parse
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
import json
import re
import concurrent.futures
from .llm_service import LLMService


class ExternalAPIsService:
    """Service for integrating multiple external book APIs and sources."""

    def __init__(self):
        self.google_books_api = "https://www.googleapis.com/books/v1/volumes"
        self.gutendx_api = "https://gutendx.com/books"
        self.internet_archive_api = "https://archive.org/advancedsearch.php"
        self.aco_search_url = "https://dlib.nyu.edu/aco/search/"
        self.libgen_search_url = "https://libgen.is/search.php"
        self.pdfdrive_search_url = "https://www.pdfdrive.com/search"

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        # Additional PDF sources
        self.additional_pdf_sources = [
            "https://archive.org/details/",
            "https://www.gutenberg.org/ebooks/",
            "https://manybooks.net/search-book?search="
        ]
    
    def search_all_sources(self, extracted_info: Dict, max_results: int = 5) -> List[Dict]:
        """
        Search all available sources for book information.
        
        Args:
            extracted_info: Information extracted by LLM
            max_results: Maximum number of results to return
            
        Returns:
            List of book results from all sources
        """
        
        all_results = []
        title = extracted_info.get('title', '')
        author = extracted_info.get('author', '')
        search_variations = extracted_info.get('search_variations', [title])
        is_arabic_query = extracted_info.get('is_arabic_query', False)
        
        # If it's an Arabic query, prioritize fastest Arabic sources
        if is_arabic_query:
            # Use only the fastest sources for Arabic queries
            search_functions = [
                (self.search_google_books, search_variations[0] if search_variations else title, True),  # prefer_arabic=True
                (self.search_gutendx, search_variations[0] if search_variations else title, None),
            ]

            # Sequential processing for Arabic queries to avoid issues
            for func, query, args in search_functions:
                try:
                    if args is None:
                        results = func(query)
                    else:
                        results = func(query, args)
                    all_results.extend(results)
                    if len(all_results) >= max_results:
                        break
                except Exception as e:
                    print(f"Arabic search function failed: {e}")
                    continue
        else:
            # For English queries, search sequentially to avoid network issues
            try:
                # Try Google Books first (most reliable)
                google_results = self.search_google_books(search_variations[0] if search_variations else title)
                all_results.extend(google_results)
            except Exception as e:
                print(f"Google Books search failed: {e}")

            # Only try Gutendx if we need more results and Google worked
            if len(all_results) < max_results:
                try:
                    gutendx_results = self.search_gutendx(search_variations[0] if search_variations else title)
                    all_results.extend(gutendx_results)
                except Exception as e:
                    print(f"Gutendx search failed: {e}")
                    # Continue without Gutendx results
        
        # Remove duplicates and rank results
        unique_results = self._remove_duplicates(all_results)
        ranked_results = self._rank_results(unique_results, extracted_info)

        # Skip PDF enhancement for speed - return results directly
        return ranked_results[:max_results]
    
    def search_google_books(self, query: str, prefer_arabic: bool = False) -> List[Dict]:
        """Search Google Books API."""
        try:
            # Add language preference to query
            if prefer_arabic:
                search_query = f"{query} language:ar"
            else:
                search_query = query
            
            params = {
                'q': search_query,
                'maxResults': 10,
                'printType': 'books'
            }
            
            response = requests.get(self.google_books_api, params=params, timeout=3)
            response.raise_for_status()
            data = response.json()
            
            results = []
            for item in data.get('items', []):
                volume_info = item.get('volumeInfo', {})
                access_info = item.get('accessInfo', {})
                
                # Extract PDF URL - try multiple sources
                pdf_url = None

                # Check if PDF is directly available
                if access_info.get('pdf', {}).get('isAvailable'):
                    pdf_url = access_info.get('pdf', {}).get('downloadLink')

                # If no PDF, check for EPUB (can be converted)
                if not pdf_url and access_info.get('epub', {}).get('isAvailable'):
                    pdf_url = access_info.get('epub', {}).get('downloadLink')

                # Check for viewability and public domain status
                viewability = access_info.get('viewability', '')
                if not pdf_url and viewability in ['ALL_PAGES', 'PARTIAL'] and access_info.get('publicDomain', False):
                    # For public domain books, construct a potential PDF URL
                    book_id = item.get('id')
                    if book_id:
                        pdf_url = f"https://books.google.com/books/download/id{book_id}.pdf"
                
                # Extract cover image
                cover_url = None
                image_links = volume_info.get('imageLinks', {})
                if image_links:
                    cover_url = (image_links.get('large') or 
                               image_links.get('medium') or 
                               image_links.get('small') or 
                               image_links.get('thumbnail'))
                
                result = {
                    'title': volume_info.get('title', ''),
                    'author': ', '.join(volume_info.get('authors', [])),
                    'description': volume_info.get('description', ''),
                    'categories': volume_info.get('categories', []),
                    'cover_image_url': cover_url,
                    'pdf_url': pdf_url,
                    'pdf_source': 'google_books',
                    'isbn': self._extract_isbn(volume_info.get('industryIdentifiers', [])),
                    'publication_date': volume_info.get('publishedDate', ''),
                    'publisher': volume_info.get('publisher', ''),
                    'language': volume_info.get('language', 'en'),
                    'source_api': 'google_books',
                    'external_id': item.get('id'),
                    'relevance_score': 0.8
                }
                
                if result['title']:  # Only add if we have a title
                    results.append(result)
            
            return results
            
        except Exception as e:
            print(f"Google Books API error: {e}")
            return []
    
    def search_gutendx(self, query: str) -> List[Dict]:
        """Search Project Gutenberg via Gutendx API."""
        try:
            # First try with PDF mime type
            params = {
                'search': query,
                'mime_type': 'application/pdf'
            }

            response = requests.get(self.gutendx_api, params=params, timeout=3)
            response.raise_for_status()
            data = response.json()

            results = []
            for book in data.get('results', []):
                # Extract PDF URL - try multiple format types
                pdf_url = None
                formats = book.get('formats', {})

                # Look for PDF formats in order of preference
                for format_url, format_type in formats.items():
                    if any(pdf_type in format_type.lower() for pdf_type in ['pdf', 'application/pdf']):
                        pdf_url = format_url
                        break

                # If no PDF found, try EPUB (can be converted)
                if not pdf_url:
                    for format_url, format_type in formats.items():
                        if 'epub' in format_type.lower():
                            pdf_url = format_url
                            break
                
                # Extract author
                authors = []
                for person in book.get('authors', []):
                    authors.append(person.get('name', ''))
                
                # Extract subjects as categories
                categories = book.get('subjects', [])
                
                result = {
                    'title': book.get('title', ''),
                    'author': ', '.join(authors),
                    'description': f"Public domain book from Project Gutenberg. Download count: {book.get('download_count', 0)}",
                    'categories': categories,
                    'cover_image_url': None,  # Gutenberg doesn't provide covers
                    'pdf_url': pdf_url,
                    'pdf_source': 'gutendx',
                    'isbn': None,
                    'publication_date': '',
                    'publisher': 'Project Gutenberg',
                    'language': ', '.join(book.get('languages', ['en'])),
                    'source_api': 'gutendx',
                    'external_id': str(book.get('id')),
                    'relevance_score': 0.9 if pdf_url else 0.5
                }
                
                if result['title']:
                    results.append(result)
            
            return results
            
        except Exception as e:
            print(f"Gutendx API error: {e}")
            return []
    
    def search_internet_archive(self, query: str, prefer_arabic: bool = False) -> List[Dict]:
        """Search Internet Archive."""
        try:
            # Build search query
            if prefer_arabic:
                search_query = f"({query}) AND mediatype:texts AND language:Arabic"
            else:
                search_query = f"({query}) AND mediatype:texts"
            
            params = {
                'q': search_query,
                'fl': 'identifier,title,creator,description,subject,date,language,format',
                'rows': 10,
                'page': 1,
                'output': 'json'
            }
            
            response = requests.get(self.internet_archive_api, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            results = []
            for doc in data.get('response', {}).get('docs', []):
                identifier = doc.get('identifier')
                if not identifier:
                    continue
                
                # Check if PDF is available and get the correct PDF URL
                pdf_url = None
                formats = doc.get('format', [])
                if isinstance(formats, str):
                    formats = [formats]

                if 'PDF' in formats or 'Abbyy GZ' in formats:
                    # Try to get the actual PDF filename from Internet Archive
                    pdf_url = self._get_internet_archive_pdf_url(identifier)
                
                # Extract subjects as categories
                subjects = doc.get('subject', [])
                if isinstance(subjects, str):
                    subjects = [subjects]
                
                result = {
                    'title': doc.get('title', ''),
                    'author': doc.get('creator', ''),
                    'description': doc.get('description', ''),
                    'categories': subjects,
                    'cover_image_url': f"https://archive.org/services/img/{identifier}",
                    'pdf_url': pdf_url,
                    'pdf_source': 'internet_archive',
                    'isbn': None,
                    'publication_date': doc.get('date', ''),
                    'publisher': 'Internet Archive',
                    'language': doc.get('language', 'en'),
                    'source_api': 'internet_archive',
                    'external_id': identifier,
                    'relevance_score': 0.7 if pdf_url else 0.3
                }
                
                if result['title']:
                    results.append(result)
            
            return results
            
        except Exception as e:
            print(f"Internet Archive API error: {e}")
            return []
    
    def search_arabic_collections_online(self, query: str) -> List[Dict]:
        """Search Arabic Collections Online (ACO)."""
        try:
            search_url = f"{self.aco_search_url}?q={urllib.parse.quote(query)}&scope=containsAny"
            
            response = requests.get(search_url, headers=self.headers, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            results = []
            
            # Look for search result items
            # ACO has a specific structure - we need to find the right selectors
            result_items = soup.find_all('div', class_='search-result-item') or soup.find_all('div', class_='item')
            
            for item in result_items:
                title = ''
                author = ''
                pdf_url = None
                
                # Extract title
                title_elem = (item.find('h3') or 
                             item.find('h2') or 
                             item.find('a', class_='title') or
                             item.find('strong'))
                if title_elem:
                    title = title_elem.get_text(strip=True)
                
                # Extract author
                author_elem = (item.find('p', class_='author') or
                              item.find('span', class_='author') or
                              item.find('div', class_='author'))
                if author_elem:
                    author = author_elem.get_text(strip=True)
                
                # Look for PDF download links
                pdf_links = item.find_all('a', href=True)
                for link in pdf_links:
                    href = link.get('href', '')
                    link_text = link.get_text(strip=True).lower()
                    
                    if ('pdf' in link_text or 'تحميل' in link_text or 'download' in link_text):
                        if href.startswith('http'):
                            pdf_url = href
                        elif href.startswith('/'):
                            pdf_url = f"https://dlib.nyu.edu{href}"
                        break
                
                if title:
                    result = {
                        'title': title,
                        'author': author,
                        'description': f"Arabic book from Arabic Collections Online",
                        'categories': ['Arabic Literature'],
                        'cover_image_url': None,
                        'pdf_url': pdf_url,
                        'pdf_source': 'aco',
                        'isbn': None,
                        'publication_date': '',
                        'publisher': 'Arabic Collections Online',
                        'language': 'ar',
                        'source_api': 'aco',
                        'external_id': None,
                        'relevance_score': 0.9 if pdf_url else 0.6
                    }
                    results.append(result)
            
            return results
            
        except Exception as e:
            print(f"Arabic Collections Online error: {e}")
            return []
    
    def _extract_isbn(self, identifiers: List[Dict]) -> Optional[str]:
        """Extract ISBN from Google Books identifiers."""
        for identifier in identifiers:
            if identifier.get('type') in ['ISBN_13', 'ISBN_10']:
                return identifier.get('identifier')
        return None
    
    def _remove_duplicates(self, results: List[Dict]) -> List[Dict]:
        """Remove duplicate results based on title and author similarity."""
        unique_results = []
        seen_combinations = set()
        
        for result in results:
            # Create a normalized key for comparison
            title_key = result.get('title', '').lower().strip()
            author_key = result.get('author', '').lower().strip()
            combination_key = f"{title_key}|{author_key}"
            
            if combination_key not in seen_combinations:
                seen_combinations.add(combination_key)
                unique_results.append(result)
        
        return unique_results
    
    def _rank_results(self, results: List[Dict], extracted_info: Dict) -> List[Dict]:
        """Rank results based on relevance to the original query."""
        target_title = extracted_info.get('title', '').lower()
        target_author = extracted_info.get('author', '').lower() if extracted_info.get('author') else ''
        is_arabic_query = extracted_info.get('is_arabic_query', False)
        
        for result in results:
            score = result.get('relevance_score', 0.5)
            
            # Boost score for title match
            result_title = result.get('title', '').lower()
            if target_title in result_title or result_title in target_title:
                score += 0.3
            
            # Boost score for author match
            result_author = result.get('author', '').lower()
            if target_author and (target_author in result_author or result_author in target_author):
                score += 0.2
            
            # Boost score for Arabic books if Arabic query
            if is_arabic_query and result.get('language') == 'ar':
                score += 0.2
            
            # Boost score for books with PDF
            if result.get('pdf_url'):
                score += 0.1
            
            result['relevance_score'] = min(score, 1.0)  # Cap at 1.0
        
        # Sort by relevance score
        return sorted(results, key=lambda x: x.get('relevance_score', 0), reverse=True)

    def _enhance_pdf_urls(self, results: List[Dict]) -> List[Dict]:
        """Enhance results by finding and verifying PDF URLs, returning only top 5 verified results."""
        from .llm_service import LLMService
        from .pdf_service import PDFService

        try:
            llm_service = LLMService()
            pdf_service = PDFService()
            verified_results = []

            print(f"Enhancing {len(results)} results with PDF verification...")

            for result in results:
                title = result.get('title', '')
                author = result.get('author', '')
                language = result.get('language', 'en')

                print(f"Processing: {title} by {author}")

                # Try multiple methods to find a working PDF
                working_pdf_url = None
                pdf_source = None

                # Method 1: Check existing PDF URL if any
                existing_pdf = result.get('pdf_url')
                if existing_pdf and self._verify_pdf_url(existing_pdf, pdf_service):
                    working_pdf_url = existing_pdf
                    pdf_source = result.get('pdf_source', 'original')
                    print(f"  ✓ Existing PDF verified: {existing_pdf}")

                # Method 2: Use LLM to find verified PDF links
                if not working_pdf_url:
                    llm_pdf_urls = llm_service.find_multiple_pdf_links(title, author, language)
                    for pdf_url in llm_pdf_urls:
                        if self._verify_pdf_url(pdf_url, pdf_service):
                            working_pdf_url = pdf_url
                            pdf_source = 'llm_verified'
                            print(f"  ✓ LLM PDF verified: {pdf_url}")
                            break
                        else:
                            print(f"  ✗ LLM PDF failed verification: {pdf_url}")

                # Method 3: Try known working sources
                if not working_pdf_url:
                    known_pdf = self._find_from_known_sources(title, author, pdf_service)
                    if known_pdf:
                        working_pdf_url = known_pdf
                        pdf_source = 'known_source'
                        print(f"  ✓ Known source PDF verified: {known_pdf}")

                # Update result with verified PDF or mark as no PDF
                if working_pdf_url:
                    result['pdf_url'] = working_pdf_url
                    result['pdf_source'] = pdf_source
                    result['pdf_verified'] = True
                    result['relevance_score'] += 0.3  # Significant boost for verified PDF
                    verified_results.append(result)
                    print(f"  ✓ Added to verified results")
                else:
                    result['pdf_url'] = None
                    result['pdf_source'] = None
                    result['pdf_verified'] = False
                    print(f"  ✗ No working PDF found")

                    # Only add to results if we have less than 5 verified results
                    if len(verified_results) < 5:
                        verified_results.append(result)

                # Stop if we have 5 verified PDFs
                if len([r for r in verified_results if r.get('pdf_verified')]) >= 5:
                    break

            # Sort by relevance score and return top 5
            verified_results.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
            final_results = verified_results[:5]

            print(f"Final results: {len(final_results)} books, {len([r for r in final_results if r.get('pdf_verified')])} with verified PDFs")
            return final_results

        except Exception as e:
            print(f"Error enhancing PDF URLs: {e}")
            return results[:5]  # Return top 5 original results if enhancement fails

    def _get_internet_archive_pdf_url(self, identifier: str) -> Optional[str]:
        """Get the actual PDF URL from Internet Archive item details."""
        try:
            # Get item metadata
            metadata_url = f"https://archive.org/metadata/{identifier}"
            response = requests.get(metadata_url, timeout=10)
            response.raise_for_status()
            metadata = response.json()

            # Look for PDF files in the files list
            files = metadata.get('files', [])

            # First, look for files with PDF format
            for file_info in files:
                filename = file_info.get('name', '')
                format_type = file_info.get('format', '')

                if format_type == 'PDF' and filename.lower().endswith('.pdf'):
                    return f"https://archive.org/download/{identifier}/{filename}"

            # Second, look for any file ending with .pdf
            for file_info in files:
                filename = file_info.get('name', '')
                if filename.lower().endswith('.pdf'):
                    return f"https://archive.org/download/{identifier}/{filename}"

            # Third, look for PDF derivatives
            for file_info in files:
                filename = file_info.get('name', '')
                if 'pdf' in filename.lower() and not filename.lower().endswith('.xml'):
                    return f"https://archive.org/download/{identifier}/{filename}"

            # Fallback to standard naming
            standard_pdf = f"https://archive.org/download/{identifier}/{identifier}.pdf"

            # Verify if the standard PDF exists
            try:
                head_response = requests.head(standard_pdf, timeout=5)
                if head_response.status_code == 200:
                    return standard_pdf
            except:
                pass

            return None

        except Exception as e:
            print(f"Error getting Internet Archive PDF URL: {e}")
            return None

    def _search_additional_pdf_sources(self, title: str, author: str) -> Optional[str]:
        """Search additional sources for PDF links."""
        try:
            # Try searching ManyBooks
            search_query = f"{title} {author}".strip()
            manybooks_url = f"https://manybooks.net/search-book?search={urllib.parse.quote(search_query)}"

            response = requests.get(manybooks_url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                # Look for PDF download links
                pdf_links = soup.find_all('a', href=True)
                for link in pdf_links:
                    href = link.get('href', '')
                    if 'pdf' in href.lower() and ('download' in href.lower() or 'get' in href.lower()):
                        if href.startswith('http'):
                            return href
                        elif href.startswith('/'):
                            return f"https://manybooks.net{href}"

            return None

        except Exception as e:
            print(f"Error searching additional PDF sources: {e}")
            return None

    def _verify_pdf_url(self, pdf_url: str, pdf_service) -> bool:
        """Verify if a PDF URL actually works and points to a valid PDF."""
        if not pdf_url:
            return False

        try:
            # Use the PDF service to verify the URL
            is_valid, _, error = pdf_service.verify_and_download_pdf(pdf_url, "test", "test")
            return is_valid
        except Exception as e:
            print(f"PDF verification error for {pdf_url}: {e}")
            return False

    def _find_from_known_sources(self, title: str, author: str, pdf_service) -> Optional[str]:
        """Try to find PDFs from known reliable sources."""
        # Clean title and author for searching
        clean_title = re.sub(r'[^\w\s]', '', title).strip()
        clean_author = re.sub(r'[^\w\s]', '', author).strip() if author else ""

        # Known working PDF sources with URL patterns
        known_sources = [
            # Project Gutenberg patterns
            f"https://www.gutenberg.org/files/{{id}}/{{id}}-pdf.pdf",
            f"https://www.gutenberg.org/cache/epub/{{id}}/pg{{id}}.pdf",

            # Internet Archive patterns
            f"https://archive.org/download/{{identifier}}/{{identifier}}.pdf",

            # ManyBooks patterns
            f"https://manybooks.net/download/{{id}}/pdf",
        ]

        # Try to find the book on Project Gutenberg first (most reliable)
        gutenberg_pdf = self._search_gutenberg_by_title(clean_title, clean_author)
        if gutenberg_pdf and self._verify_pdf_url(gutenberg_pdf, pdf_service):
            return gutenberg_pdf

        # Try Internet Archive with better search
        ia_pdf = self._search_internet_archive_verified(clean_title, clean_author, pdf_service)
        if ia_pdf:
            return ia_pdf

        return None

    def _search_gutenberg_by_title(self, title: str, author: str) -> Optional[str]:
        """Search Project Gutenberg for a specific title and return PDF URL."""
        try:
            # Search Gutendx API more specifically
            search_terms = [title]
            if author:
                search_terms.append(f"{title} {author}")

            for search_term in search_terms:
                params = {
                    'search': search_term,
                    'mime_type': 'application/pdf'
                }

                response = requests.get(self.gutendx_api, params=params, timeout=10)
                if response.status_code == 200:
                    data = response.json()

                    for book in data.get('results', []):
                        book_title = book.get('title', '').lower()
                        if title.lower() in book_title or book_title in title.lower():
                            # Found a match, get PDF URL
                            formats = book.get('formats', {})
                            for format_url, format_type in formats.items():
                                if 'pdf' in format_type.lower() and format_url.endswith('.pdf'):
                                    return format_url

            return None

        except Exception as e:
            print(f"Gutenberg search error: {e}")
            return None

    def _search_internet_archive_verified(self, title: str, author: str, pdf_service) -> Optional[str]:
        """Search Internet Archive and verify PDF availability."""
        try:
            search_query = f"title:({title})"
            if author:
                search_query += f" AND creator:({author})"
            search_query += " AND mediatype:texts AND format:PDF"

            params = {
                'q': search_query,
                'fl': 'identifier,title,creator',
                'rows': 5,
                'output': 'json'
            }

            response = requests.get(self.internet_archive_api, params=params, timeout=15)
            if response.status_code == 200:
                data = response.json()

                for doc in data.get('response', {}).get('docs', []):
                    identifier = doc.get('identifier')
                    if identifier:
                        # Try to get the actual PDF URL
                        pdf_url = self._get_internet_archive_pdf_url(identifier)
                        if pdf_url and self._verify_pdf_url(pdf_url, pdf_service):
                            return pdf_url

            return None

        except Exception as e:
            print(f"Internet Archive verified search error: {e}")
            return None

