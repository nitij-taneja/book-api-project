#!/usr/bin/env python
"""
API Testing Script for AI-Powered Book Search API
Run this script to test all API endpoints
"""

import requests
import json
import time
import sys

# API Base URL
BASE_URL = "http://localhost:8000/api/books"

def test_ai_search():
    """Test the AI book search endpoint."""
    print("\n🔍 Testing AI Book Search...")
    
    test_cases = [
        {
            "book_name": "The Great Gatsby",
            "language": "en",
            "max_results": 3
        },
        {
            "book_name": "Pride and Prejudice",
            "language": "en",
            "max_results": 2
        },
        {
            "book_name": "ألف ليلة وليلة",
            "language": "ar",
            "max_results": 2
        }
    ]
    
    for i, test_data in enumerate(test_cases, 1):
        print(f"\n📖 Test Case {i}: {test_data['book_name']}")
        
        try:
            response = requests.post(
                f"{BASE_URL}/ai-search/",
                json=test_data,
                timeout=120
            )
            
            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])
                verified_count = sum(1 for r in results if r.get('pdf_verified'))
                
                print(f"✅ Status: {response.status_code}")
                print(f"📊 Results: {len(results)} books found")
                print(f"✅ Verified PDFs: {verified_count}")
                print(f"🔗 Session: {data.get('search_session', 'N/A')}")
                
                # Show first result details
                if results:
                    first_result = results[0]
                    print(f"📚 First Result:")
                    print(f"   Title: {first_result.get('title', 'N/A')}")
                    print(f"   Author: {first_result.get('author', 'N/A')}")
                    print(f"   PDF: {'✅ Available' if first_result.get('pdf_url') else '❌ Not found'}")
                    print(f"   Verified: {'✅ Yes' if first_result.get('pdf_verified') else '❌ No'}")
                
            else:
                print(f"❌ Status: {response.status_code}")
                print(f"Error: {response.text}")
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Request failed: {e}")
        
        # Wait between requests
        if i < len(test_cases):
            print("⏳ Waiting 2 seconds...")
            time.sleep(2)

def test_pdf_verification():
    """Test PDF verification endpoint."""
    print("\n🔍 Testing PDF Verification...")
    
    test_urls = [
        "https://archive.org/download/the-great-gatsby-1st-ed-1925/The_Great_Gatsby-1stEd-1925.pdf",
        "https://invalid-url.com/nonexistent.pdf"
    ]
    
    for i, pdf_url in enumerate(test_urls, 1):
        print(f"\n📄 Test {i}: {pdf_url}")
        
        try:
            response = requests.post(
                f"{BASE_URL}/verify-pdf/",
                json={"pdf_url": pdf_url},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Status: {response.status_code}")
                print(f"Valid: {'✅ Yes' if data.get('is_valid') else '❌ No'}")
                if not data.get('is_valid'):
                    print(f"Error: {data.get('error', 'Unknown')}")
            else:
                print(f"❌ Status: {response.status_code}")
                print(f"Error: {response.text}")
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Request failed: {e}")

def test_list_books():
    """Test list books endpoint."""
    print("\n📚 Testing List Books...")
    
    try:
        response = requests.get(f"{BASE_URL}/", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Status: {response.status_code}")
            print(f"📊 Total books in database: {len(data) if isinstance(data, list) else 'N/A'}")
        else:
            print(f"❌ Status: {response.status_code}")
            print(f"Error: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")

def check_server():
    """Check if the server is running."""
    print("🔍 Checking server status...")
    
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        print("✅ Server is running")
        return True
    except requests.exceptions.RequestException:
        print("❌ Server is not running")
        print("Please start the server with: python manage.py runserver")
        return False

def main():
    """Main testing function."""
    print("🧪 AI-Powered Book Search API - Test Suite")
    print("=" * 50)
    
    # Check if server is running
    if not check_server():
        sys.exit(1)
    
    # Run tests
    test_ai_search()
    test_pdf_verification()
    test_list_books()
    
    print("\n" + "=" * 50)
    print("🎉 Testing completed!")
    print("\nAPI Endpoints Summary:")
    print(f"• AI Search: POST {BASE_URL}/ai-search/")
    print(f"• Verify PDF: POST {BASE_URL}/verify-pdf/")
    print(f"• List Books: GET {BASE_URL}/")
    print(f"• Add Book: POST {BASE_URL}/add-from-search/")
    print(f"• Get Results: GET {BASE_URL}/search-results/<session>/")
    print(f"• Book Details: GET {BASE_URL}/<id>/")

if __name__ == "__main__":
    main()
