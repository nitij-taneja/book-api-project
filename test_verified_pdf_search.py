#!/usr/bin/env python
"""
Test script to verify the enhanced PDF URL search and verification functionality.
"""

import os
import sys
import django
import time

# Add the project directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'book_api_project.settings')
django.setup()

from books.services.external_apis import ExternalAPIsService
from books.services.llm_service import LLMService
from books.services.pdf_service import PDFService

def test_verified_pdf_search():
    """Test the enhanced PDF URL search and verification functionality."""
    print("Testing Verified PDF Search...")
    
    # Initialize services
    llm_service = LLMService()
    pdf_service = PDFService()
    external_apis = ExternalAPIsService()
    
    # Test books to search for
    test_books = [
        {
            'title': 'Pride and Prejudice',
            'author': 'Jane Austen',
            'language': 'en'
        },
        {
            'title': 'The Great Gatsby',
            'author': 'F. Scott Fitzgerald',
            'language': 'en'
        },
        {
            'title': 'ألف ليلة وليلة',
            'author': 'مجهول',
            'language': 'ar'
        }
    ]
    
    # Test LLM multiple PDF links
    print("\n1. Testing LLM Multiple PDF Links...")
    for book in test_books:
        title = book['title']
        author = book['author']
        language = book['language']
        
        print(f"\nSearching for: {title} by {author}")
        pdf_urls = llm_service.find_multiple_pdf_links(title, author, language)
        
        print(f"Found {len(pdf_urls)} potential PDF URLs:")
        for i, url in enumerate(pdf_urls, 1):
            print(f"  {i}. {url}")
            
            # Verify each URL
            is_valid, _, error = pdf_service._verify_pdf_only(url)
            status = "✓ VALID" if is_valid else f"✗ INVALID: {error}"
            print(f"     {status}")
    
    # Test full search with verification
    print("\n2. Testing Full Search with Verification...")
    for book in test_books:
        title = book['title']
        author = book['author']
        language = book['language']
        
        print(f"\nFull search for: {title} by {author}")
        
        # Create extracted info
        extracted_info = {
            'title': title,
            'author': author,
            'categories': ['Fiction'],
            'language': language,
            'search_variations': [f"{title} {author}"],
            'is_arabic_query': language == 'ar'
        }
        
        # Perform search
        start_time = time.time()
        results = external_apis.search_all_sources(extracted_info, max_results=5)
        end_time = time.time()
        
        print(f"Search completed in {end_time - start_time:.2f} seconds")
        print(f"Found {len(results)} results:")
        
        for i, result in enumerate(results, 1):
            print(f"\nResult {i}:")
            print(f"  Title: {result.get('title', 'N/A')}")
            print(f"  Author: {result.get('author', 'N/A')}")
            print(f"  PDF URL: {result.get('pdf_url', 'None')}")
            print(f"  PDF Source: {result.get('pdf_source', 'N/A')}")
            print(f"  PDF Verified: {result.get('pdf_verified', False)}")
            print(f"  Source API: {result.get('source_api', 'N/A')}")
            print(f"  Relevance Score: {result.get('relevance_score', 0)}")
    
    print("\nTest completed!")

if __name__ == "__main__":
    test_verified_pdf_search()
