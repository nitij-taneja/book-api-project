#!/usr/bin/env python
"""
Test script to verify the API endpoint works with verified PDF URLs.
"""

import os
import sys
import django
import json

# Add the project directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'book_api_project.settings')
django.setup()

from django.test import Client
from django.urls import reverse

def test_api_endpoint():
    """Test the AI book search API endpoint."""
    print("Testing AI Book Search API Endpoint...")
    
    # Create a test client
    client = Client()
    
    # Test data
    test_data = {
        'book_name': 'The Great Gatsby',
        'language': 'en',
        'max_results': 3
    }
    
    print(f"Searching for: {test_data['book_name']}")
    
    # Make the API request
    response = client.post(
        '/api/books/ai-search/',
        data=json.dumps(test_data),
        content_type='application/json'
    )
    
    print(f"Response status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        
        print(f"Search session: {data.get('search_session')}")
        print(f"Total found: {data.get('total_found')}")
        
        results = data.get('results', [])
        print(f"\nFound {len(results)} results:")
        
        verified_count = 0
        for i, result in enumerate(results, 1):
            print(f"\nResult {i}:")
            print(f"  Title: {result.get('title')}")
            print(f"  Author: {result.get('author')}")
            print(f"  PDF URL: {result.get('pdf_url', 'None')}")
            print(f"  PDF Source: {result.get('pdf_source', 'N/A')}")
            print(f"  PDF Verified: {result.get('pdf_verified', False)}")
            print(f"  PDF Status: {result.get('pdf_verified_status', 'N/A')}")
            print(f"  Relevance Score: {result.get('relevance_score', 0)}")
            
            if result.get('pdf_verified'):
                verified_count += 1
        
        print(f"\nSummary: {verified_count} out of {len(results)} results have verified PDF links")
        
        if verified_count > 0:
            print("✓ SUCCESS: Found books with verified PDF links!")
        else:
            print("⚠ WARNING: No verified PDF links found")
    
    else:
        print(f"Error: {response.status_code}")
        print(response.content.decode())

if __name__ == "__main__":
    test_api_endpoint()
