#!/usr/bin/env python
"""
Test script to verify PDF URL enhancement functionality.
"""

import os
import sys
import django

# Add the project directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'book_api_project.settings')
django.setup()

from books.services.external_apis import ExternalAPIsService
from books.services.llm_service import LLMService

def test_pdf_enhancement():
    """Test the PDF URL enhancement functionality."""
    print("Testing PDF URL Enhancement...")
    
    # Test LLM service
    print("\n1. Testing LLM Service...")
    try:
        llm_service = LLMService()
        
        # Test with a well-known public domain book
        pdf_url = llm_service.find_pdf_link("Pride and Prejudice", "Jane Austen", "en")
        print(f"LLM found PDF URL: {pdf_url}")
        
        # Test with an Arabic book
        pdf_url_ar = llm_service.find_pdf_link("ألف ليلة وليلة", "مجهول", "ar")
        print(f"LLM found Arabic PDF URL: {pdf_url_ar}")
        
    except Exception as e:
        print(f"LLM Service Error: {e}")
    
    # Test External APIs Service
    print("\n2. Testing External APIs Service...")
    try:
        external_apis = ExternalAPIsService()
        
        # Test with a sample query
        extracted_info = {
            'title': 'Pride and Prejudice',
            'author': 'Jane Austen',
            'categories': ['Fiction', 'Romance'],
            'language': 'en',
            'search_variations': ['Pride and Prejudice Jane Austen'],
            'is_arabic_query': False
        }
        
        results = external_apis.search_all_sources(extracted_info, max_results=3)
        
        print(f"Found {len(results)} results:")
        for i, result in enumerate(results, 1):
            print(f"\nResult {i}:")
            print(f"  Title: {result.get('title', 'N/A')}")
            print(f"  Author: {result.get('author', 'N/A')}")
            print(f"  PDF URL: {result.get('pdf_url', 'None')}")
            print(f"  PDF Source: {result.get('pdf_source', 'N/A')}")
            print(f"  Source API: {result.get('source_api', 'N/A')}")
            print(f"  Relevance Score: {result.get('relevance_score', 0)}")
        
    except Exception as e:
        print(f"External APIs Service Error: {e}")
    
    print("\nTest completed!")

if __name__ == "__main__":
    test_pdf_enhancement()
