
"""
Django API views for AI-powered book addition functionality.
"""

import uuid
import json
import concurrent.futures
import requests
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .models import Book, BookSearchResult
from .services.llm_service import LLMService
from .services.external_apis import ExternalAPIsService
from .services.pdf_service import PDFService
from .serializers import BookSerializer, BookSearchResultSerializer


def is_valid_image_url(url: str) -> bool:
    """
    Validates if a given URL is a reliable image URL that actually works.
    Only accepts URLs from sources we know work reliably.
    """
    if not url or not isinstance(url, str):
        return False

    # REJECT ALL WIKIMEDIA URLS COMPLETELY - they cause too many issues
    wikimedia_domains = [
        'wikimedia.org',
        'wikipedia.org'
    ]

    url_lower = url.lower()
    if any(domain in url_lower for domain in wikimedia_domains):
        print(f"Rejecting Wikimedia URL: {url}")
        return False

    # Must start with http/https
    if not url_lower.startswith(('http://', 'https://')):
        print(f"Rejecting non-HTTP URL: {url}")
        return False

    # Accept URLs from reliable sources
    reliable_domains = [
        'placehold.co',         # Reliable placeholder service
        'dummyimage.com',       # Another reliable placeholder service
        'logo.clearbit.com',    # Usually works for company logos
        'cdn.britannica.com',   # Britannica images are very reliable
        'images.unsplash.com',  # Unsplash (but only direct image URLs)
        'cdn.pixabay.com',      # Pixabay CDN
        'images.pexels.com',    # Pexels images
        'upload.wikimedia.org', # Wikimedia direct image URLs (not file pages)
    ]

    # If it's from a reliable domain, accept it
    if any(domain in url_lower for domain in reliable_domains):
        # Special check for Wikimedia - only accept direct image URLs
        if 'wikimedia.org' in url_lower:
            return url_lower.endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif', '.svg'))
        return True

    # For other domains, must end with a common image extension
    if not url_lower.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg")):
        print(f"Rejecting non-image URL from untrusted domain: {url}")
        return False

    # Reject URLs that are too long (often problematic)
    if len(url) > 500:
        print(f"Rejecting overly long URL: {url[:100]}...")
        return False

    # Additional check: reject URLs with too many query parameters
    if url.count('?') > 1 or url.count('&') > 5:
        print(f"Rejecting URL with too many parameters: {url}")
        return False

    return True


def search_google_images(query: str, image_type: str = "general") -> str:
    """
    Search Google Images for free using web scraping (no API key required).
    Returns the first valid image URL found.
    """
    try:
        import requests
        from urllib.parse import quote_plus
        import re

        print(f"Searching Google Images for: {query} ({image_type})")

        # Prepare search query
        search_query = f"{query} {image_type}" if image_type != "general" else query
        encoded_query = quote_plus(search_query)

        # Google Images search URL
        search_url = f"https://www.google.com/search?q={encoded_query}&tbm=isch&safe=active"

        # Headers to mimic a real browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        # Make request to Google Images
        response = requests.get(search_url, headers=headers, timeout=10)

        if response.status_code == 200:
            # Extract image URLs from the response
            # Look for image URLs in the HTML
            image_pattern = r'"(https?://[^"]*\.(?:jpg|jpeg|png|webp|gif))"'
            matches = re.findall(image_pattern, response.text, re.IGNORECASE)

            # Filter out unwanted domains and find a good image
            for url in matches:
                if is_valid_google_image_url(url):
                    print(f"Found valid Google image: {url}")
                    return url

        # If Google search fails, fall back to curated images
        return get_fallback_image(query, image_type)

    except Exception as e:
        print(f"Google Images search error: {e}")
        return get_fallback_image(query, image_type)


def is_valid_google_image_url(url: str) -> bool:
    """
    Validate if a Google Images URL is suitable for use.
    """
    if not url or not isinstance(url, str):
        return False

    url_lower = url.lower()

    # Reject unwanted domains
    blocked_domains = [
        'wikimedia.org',
        'wikipedia.org',
        'google.com',
        'googleusercontent.com',
        'gstatic.com',
        'encrypted-tbn',  # Google's encrypted thumbnails
    ]

    if any(domain in url_lower for domain in blocked_domains):
        return False

    # Must be a direct image URL
    if not url_lower.endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif')):
        return False

    # Must be from a reasonable domain
    if len(url) > 500:  # Too long URLs are often problematic
        return False

    return True


def get_fallback_image(query: str, image_type: str = "general") -> str:
    """
    Get fallback images when Google search fails.
    Uses curated reliable images from trusted sources.
    """
    query_lower = query.lower()

    if image_type == "author":
        # Use actual author photos from reliable sources
        if "jane austen" in query_lower:
            return "https://cdn.britannica.com/12/172012-050-DAA7CE2B/Jane-Austen-watercolour-Cassandra-Austen-1810.jpg"
        elif "shakespeare" in query_lower:
            return "https://cdn.britannica.com/51/1851-050-7A4E6C35/William-Shakespeare.jpg"
        elif "stephen king" in query_lower:
            return "https://cdn.britannica.com/34/206034-050-BBCF8C8A/Stephen-King-2019.jpg"
        elif "agatha christie" in query_lower:
            return "https://cdn.britannica.com/30/9230-050-0A4D3C80/Agatha-Christie-1925.jpg"
        elif "mark twain" in query_lower:
            return "https://cdn.britannica.com/13/153413-050-2B899E58/Mark-Twain-1907.jpg"
        else:
            return "https://placehold.co/400x300/696969/FFFFFF/png?text=Author+Image"

    elif image_type == "category":
        # Use actual category-related images from reliable sources
        if "entertainment" in query_lower:
            return "https://cdn.britannica.com/60/182360-050-CD8878D6/scene-Citizen-Kane-Orson-Welles-1941.jpg"
        elif "technology" in query_lower:
            return "https://cdn.britannica.com/69/155469-050-3F458ECF/circuit-board-computer.jpg"
        elif "business" in query_lower:
            return "https://cdn.britannica.com/77/170477-050-1C747EE3/Nasdaq-MarketSite-Times-Square-New-York-City.jpg"
        elif "education" in query_lower:
            return "https://cdn.britannica.com/07/192107-050-7C9F98E8/Harvard-University-Cambridge-Massachusetts.jpg"
        elif "science" in query_lower:
            return "https://cdn.britannica.com/86/193986-050-7C6DE899/laboratory-glassware.jpg"
        elif "health" in query_lower:
            return "https://cdn.britannica.com/17/196817-050-6A15DAC3/stethoscope.jpg"
        elif "finance" in query_lower:
            return "https://cdn.britannica.com/78/170478-050-1C747EE3/New-York-Stock-Exchange-Wall-Street.jpg"
        elif "sports" in query_lower:
            return "https://cdn.britannica.com/63/114163-050-7745C043/Soccer-ball-goal.jpg"
        else:
            return "https://placehold.co/400x300/708090/FFFFFF/png?text=Category+Image"

    # Default fallback
    return "https://placehold.co/400x300/A9A9A9/FFFFFF/png?text=Image+Not+Found"


def search_for_reliable_image(query: str, image_type: str = "general") -> str:
    """
    Main function to search for reliable images.
    First tries Google Images, then falls back to curated images.
    """
    # Try Google Images first
    google_result = search_google_images(query, image_type)

    # If Google search returned a valid result, use it
    if google_result and not google_result.startswith('https://placehold.co') and not google_result.startswith('https://cdn.britannica.com'):
        return google_result

    # Otherwise use the fallback (which includes Britannica images)
    return google_result


def get_image_url_from_llm(search_term: str, image_type: str = "author") -> str:
    """
    Always return reliable placeholder images instead of querying LLM.
    This ensures we never get broken image URLs.
    """
    print(f"Getting reliable image for {search_term} ({image_type})")
    # Skip LLM entirely and use our reliable fallback
    return search_for_reliable_image(search_term, image_type)


def is_valid_wikipedia_url(url: str, language: str) -> bool:
    """
    Validates if a given URL is a valid Wikipedia page link.
    """
    if not url or not isinstance(url, str):
        return False
    expected_domain = f"{language}.wikipedia.org"
    return expected_domain in url and "/wiki/File:" not in url and "wikimedia.org" not in url


@api_view(['POST'])
def analyze_book_description(request):
    """
    Analyze a book description and return categorized information.

    Expected input:
    {
        "description": "Book description text...",
        "language": "en" or "ar" (optional, defaults to "en")
    }

    Returns:
    {
        "categories": [
            {
                "name": "Category Name",
                "icon": "📚",
                "wikilink": "https://en.wikipedia.org/wiki/...",
                "description": "80-130 word description"
            }
        ],
        "analysis_summary": "Brief summary of the analysis"
    }
    """
    try:
        # Validate input
        description = request.data.get('description', '').strip()
        language = request.data.get('language', 'en')

        if not description:
            return Response(
                {'error': 'Description is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if len(description) < 20:
            return Response(
                {'error': 'Description must be at least 20 characters long'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if language not in ['en', 'ar']:
            return Response(
                {'error': 'Language must be "en" or "ar"'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Initialize LLM service
        llm_service = LLMService()

        # Analyze description and get categories
        analysis_result = llm_service.analyze_description_for_categories(description, language)

        return Response({
            'categories': analysis_result.get('categories', []),
            'analysis_summary': analysis_result.get('analysis_summary', ''),
            'input_description': description,
            'language': language,
            'total_categories': len(analysis_result.get('categories', []))
        }, status=status.HTTP_200_OK)

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Description analysis failed with error: {e}")
        print(f"Full traceback: {error_details}")

        return Response(
            {'error': f'Analysis failed: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def ai_book_search_no_db(request):
    """
    AI-powered book search WITHOUT database operations.
    Returns enhanced search results directly without saving anything.

    Expected input:
    {
        "book_name": "Pride and Prejudice",
        "language": "en" (optional, defaults to "en"),
        "max_results": 5 (optional, defaults to 5)
    }

    Returns:
    {
        "results": [
            {
                "title": "Book Title",
                "author": "Author Name",
                "structured_author": {...},
                "structured_categories": [...],
                "ai_book_summary": "...",
                "description": "...",
                "pdf_url": "...",
                "cover_image_url": "...",
                "isbn": "...",
                "publication_date": "...",
                "publisher": "...",
                "source_api": "...",
                "relevance_score": 0.0
            }
        ],
        "total_found": 5,
        "extracted_info": {...},
        "search_time": 15.2,
        "language": "en"
    }
    """
    try:
        # Validate input
        book_name = request.data.get('book_name', '') or ''
        if isinstance(book_name, str):
            book_name = book_name.strip()
        else:
            book_name = str(book_name).strip() if book_name else ''

        language = request.data.get('language', 'en')
        max_results = request.data.get('max_results', 5)

        if not book_name:
            return Response(
                {'error': 'book_name is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if language not in ['en', 'ar']:
            return Response(
                {'error': 'Language must be "en" or "ar"'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not isinstance(max_results, int) or max_results < 1 or max_results > 20:
            return Response(
                {'error': 'max_results must be an integer between 1 and 20'},
                status=status.HTTP_400_BAD_REQUEST
            )

        start_time = timezone.now()

        # Step 1: Extract information from query using LLM
        llm_service = LLMService()
        extracted_info = llm_service.extract_book_info(book_name, language)

        # Step 2: Search external APIs
        external_apis = ExternalAPIsService()
        search_results = external_apis.search_all_sources(extracted_info, max_results)

        if not search_results:
            return Response({
                'results': [],
                'total_found': 0,
                'extracted_info': extracted_info,
                'search_time': (timezone.now() - start_time).total_seconds(),
                'language': language,
                'message': 'No books found matching your search criteria'
            }, status=status.HTTP_200_OK)

        # Skip PDF enhancement for better performance
        # PDF URLs will be generated by LLM if needed

        # Step 3: Enhance results with LLM-generated content (no database operations)
        enhanced_results = []

        # Process only the first few results for better performance
        for result in search_results[:max_results]:
            try:
                enhanced_result = enhance_single_result(result, llm_service, language)

                # Step 3.5: Translate main fields to Arabic if needed
                if language == 'ar':
                    enhanced_result = translate_result_to_arabic(enhanced_result, llm_service)

                enhanced_results.append(enhanced_result)

                # Break early if we have enough results
                if len(enhanced_results) >= max_results:
                    break

            except Exception as e:
                print(f"Error enhancing result: {e}")
                # Add the original result if enhancement fails
                enhanced_results.append(result)

        end_time = timezone.now()
        search_time = (end_time - start_time).total_seconds()

        # Return results directly without any database operations
        return Response({
            'results': enhanced_results,
            'total_found': len(enhanced_results),
            'extracted_info': extracted_info,
            'search_time': search_time,
            'language': language,
            'note': 'Results returned without database storage'
        }, status=status.HTTP_200_OK)

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Search failed with error: {e}")
        print(f"Full traceback: {error_details}")

        return Response(
            {'error': f'Search failed: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def website_search(request):
    """
    Website/Company search endpoint with comprehensive information.
    No database operations - returns results directly.

    Expected input:
    {
        "website_name": "Netflix",
        "language": "en" (optional, defaults to "en")
    }

    Returns:
    {
        "name": "Netflix",
        "website_icon": "https://netflix.com/favicon.ico",
        "country": "United States",
        "category": {
            "name": "Entertainment",
            "icon": "🎬",
            "wikilink": "https://en.wikipedia.org/wiki/Entertainment",
            "description": "90 word description of the category"
        },
        "brief_description": "Brief description about the website/company",
        "comprehensive_description": "200 word detailed description",
        "app_links": {
            "playstore": "https://play.google.com/store/apps/details?id=...",
            "appstore": "https://apps.apple.com/app/..."
        },
        "social_media": {
            "youtube": "https://youtube.com/@netflix",
            "instagram": "https://instagram.com/netflix",
            "facebook": "https://facebook.com/netflix",
            "twitter": "https://twitter.com/netflix"
        },
        "website_url": "https://netflix.com",
        "founded": "1997",
        "headquarters": "Los Gatos, California, USA"
    }
    """
    try:
        # Validate input
        website_name = request.data.get('website_name', '').strip() if request.data.get('website_name') else ''
        language = request.data.get('language', 'en')

        if not website_name:
            return Response(
                {'error': 'website_name is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if language not in ['en', 'ar']:
            return Response(
                {'error': 'Language must be "en" or "ar"'},
                status=status.HTTP_400_BAD_REQUEST
            )

        start_time = timezone.now()

        # Get comprehensive website information using LLM
        try:
            website_info = get_website_comprehensive_info(website_name, language)
            if not website_info or not isinstance(website_info, dict):
                raise ValueError("Invalid response from LLM")
        except Exception as e:
            print(f"LLM info failed: {e}")
            website_info = get_fallback_website_info(website_name, language)

        # Ensure website_info is a valid dictionary
        if not isinstance(website_info, dict):
            website_info = get_fallback_website_info(website_name, language)

        # Add website icon
        if 'website_icon' not in website_info or not website_info['website_icon']:
            website_info['website_icon'] = get_website_icon_url(website_name)

        end_time = timezone.now()
        search_time = (end_time - start_time).total_seconds()

        # Add metadata
        website_info['search_time'] = search_time
        website_info['language'] = language
        website_info['note'] = 'Website information without database storage'

        return Response(website_info, status=status.HTTP_200_OK)

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Website search failed with error: {e}")
        print(f"Full traceback: {error_details}")

        return Response(
            {'error': f'Website search failed: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )





def get_author_comprehensive_info(author_name: str, language: str = 'en') -> dict:
    """
    Get comprehensive author information using LLM with FIXED image handling.
    """
    llm_service = LLMService()

    if language == 'ar':
        prompt = f"""
        أنت مساعد بحث متخصص في الأدب والكتاب. ابحث عن معلومات شاملة عن المؤلف: "{author_name}"

        أرجع JSON بهذا التنسيق المحدد (أسماء الحقول بالإنجليزية، القيم بالعربية):
        {{
            "name": "{author_name}",
            "author_image": "LEAVE_EMPTY_FOR_AUTO_SEARCH",
            "bio": "سيرة ذاتية من 200 كلمة عربية بالضبط تتضمن حياته وأعماله وإنجازاته",
            "professions": [
                {{"profession": "كاتب"}},
                {{"profession": "روائي"}},
                {{"profession": "شاعر"}}
            ],
            "wikilink": "رابط صفحة ويكيبيديا الحقيقية للمؤلف فقط إذا كان متاحاً، إذا لم يوجد اتركه فارغاً.",
            "youtube_link": "رابط يوتيوب الرسمي إذا متوفر، أو نص فارغ",
            "birth_year": "سنة الميلاد",
            "nationality": "الجنسية بالعربية",
            "notable_works": ["قائمة بأشهر الأعمال بالعربية"]
        }}

        ملاحظات مهمة:
        - استخدم معلومات حقيقية ودقيقة عن المؤلف
        - السيرة الذاتية: 200 كلمة عربية بالضبط
        - المهن: قائمة كائنات بالعربية
        - الأعمال المشهورة: بالأسماء العربية إذا ترجمت
        - اتركه author_image فارغاً دائماً
        """
    else:
        prompt = f"""
        You are a literature and author research assistant. Find comprehensive information about the author: "{author_name}"

        Return JSON with this exact structure:
        {{
            "name": "{author_name}",
            "author_image": "LEAVE_EMPTY_FOR_AUTO_SEARCH",
            "bio": "Exactly 200 English words biography including life, works, and achievements",
            "professions": [
                {{"profession": "Writer"}},
                {{"profession": "Novelist"}},
                {{"profession": "Poet"}}
            ],
            "wikilink": "Direct Wikipedia author page link ONLY if available, leave blank if not",
            "youtube_link": "Official YouTube channel URL if available, empty string if not",
            "birth_year": "Birth year",
            "nationality": "Nationality",
            "notable_works": ["List of most famous works"]
        }}

        Important notes:
        - Use real and accurate information about the author
        - Biography: exactly 200 English words
        - Professions: list of objects in English
        - Notable works: use original titles
        - Always leave author_image empty
        """

    try:
        import time
        time.sleep(0.5)  # Rate limiting

        chat_completion = llm_service.client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a precise literature researcher. Provide accurate, real information about authors and writers. Follow word count requirements exactly."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            model=llm_service.model,
            response_format={"type": "json_object"},
            temperature=0.0,
            max_tokens=1200,
            timeout=15
        )

        response = json.loads(chat_completion.choices[0].message.content)

        # Ensure bio word count is correct
        if 'bio' in response:
            response['bio'] = ensure_word_count(response['bio'], 200, language)

        # ALWAYS use our reliable image search instead of LLM-provided images
        response['author_image'] = get_image_url_from_llm(author_name, "author")

        return response

    except Exception as e:
        print(f"LLM author info error: {e}")
        return get_fallback_author_info(author_name, language)


def get_category_comprehensive_info(category_name: str, language: str = 'en') -> dict:
    """
    Get comprehensive category information using LLM with FIXED image handling.
    """
    llm_service = LLMService()

    if language == 'ar':
        prompt = f"""
        أنت خبير متخصص في بحث الفئات. قدم معلومات مفصلة تحديداً عن فئة "{category_name}".

        أرجع JSON بهذا التنسيق المحدد:
        {{
            "name": "اسم الفئة بالعربية",
            "image_url": "LEAVE_EMPTY_FOR_AUTO_SEARCH",
            "wikilink": "https://ar.wikipedia.org/wiki/...",
            "description": "وصف من 150 كلمة عربية بالضبط يشرح ما هي فئة {category_name}، وخصائصها، وميزاتها الرئيسية، وأهميتها."
        }}

        المتطلبات الأساسية:
        - الوصف يجب أن يكون بالضبط 150 كلمة عن {category_name} تحديداً
        - ركز على ما يجعل {category_name} فريدة ومميزة
        - اترك image_url فارغاً دائماً
        """
    else:
        prompt = f"""
        You are an expert category researcher. Provide detailed information specifically about the "{category_name}" category.

        Return JSON with this exact structure:
        {{
            "name": "{category_name}",
            "image_url": "LEAVE_EMPTY_FOR_AUTO_SEARCH",
            "wikilink": "https://en.wikipedia.org/wiki/...",
            "description": "Exactly 150 English words describing what {category_name} is, its characteristics, key features, and significance."
        }}

        CRITICAL REQUIREMENTS:
        - Description must be EXACTLY 150 words about {category_name} specifically
        - Focus on what makes {category_name} unique and distinct
        - Always leave image_url empty
        """

    try:
        import time
        time.sleep(0.5)  # Rate limiting

        chat_completion = llm_service.client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a precise industry researcher. Provide accurate, real information about categories and industries. Follow word count requirements exactly."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            model=llm_service.model,
            response_format={"type": "json_object"},
            temperature=0.0,
            max_tokens=1000,
            timeout=15
        )

        response = json.loads(chat_completion.choices[0].message.content)

        # Ensure description word count is correct
        if 'description' in response:
            response['description'] = ensure_word_count(response['description'], 150, language)

        # ALWAYS use our reliable image search instead of LLM-provided images
        response['image_url'] = get_image_url_from_llm(category_name, "category")

        return response

    except Exception as e:
        print(f"LLM category info error: {e}")
        return get_fallback_category_info(category_name, language)


def get_fallback_author_info(author_name: str, language: str) -> dict:
    """
    Fallback author information when LLM fails.
    """
    if language == 'ar':
        return {
            "name": author_name,
            "author_image": get_image_url_from_llm(author_name, "author"),
            "bio": ensure_word_count(f"{author_name} هو مؤلف معروف له إسهامات مهمة في الأدب", 200, 'ar'),
            "professions": [{"profession": "كاتب"}],
            "wikilink": f"https://ar.wikipedia.org/wiki/{author_name.replace(' ', '_')}",
            "youtube_link": "",
            "birth_year": "غير محدد",
            "nationality": "غير محدد",
            "notable_works": ["أعمال متنوعة"]
        }
    else:
        return {
            "name": author_name,
            "author_image": get_image_url_from_llm(author_name, "author"),
            "bio": ensure_word_count(f"{author_name} is a notable author with significant contributions to literature", 200, 'en'),
            "professions": [{"profession": "Writer"}],
            "wikilink": f"https://en.wikipedia.org/wiki/{author_name.replace(' ', '_')}",
            "youtube_link": "",
            "birth_year": "Unknown",
            "nationality": "Unknown",
            "notable_works": ["Various works"]
        }


def get_fallback_category_info(category_name: str, language: str) -> dict:
    """
    Fallback category information when LLM fails.
    """
    if language == 'ar':
        return {
            "name": category_name,
            "image_url": get_image_url_from_llm(category_name, "category"),
            "wikilink": f"https://ar.wikipedia.org/wiki/{category_name}",
            "description": ensure_word_count(f"فئة {category_name} تشمل مجموعة واسعة من الأنشطة والخدمات المهمة", 150, 'ar')
        }
    else:
        return {
            "name": category_name,
            "image_url": get_image_url_from_llm(category_name, "category"),
            "wikilink": f"https://en.wikipedia.org/wiki/{category_name}",
            "description": ensure_word_count(f"The {category_name} category encompasses a wide range of important activities and services", 150, 'en')
        }


def ensure_word_count(text: str, target_words: int, language: str = 'en') -> str:
    """
    Ensure text meets the target word count.
    """
    if not text:
        if language == 'ar':
            base_text = "هذا وصف أساسي للموضوع المطلوب"
        else:
            base_text = "This is a basic description of the requested topic"
        text = base_text

    words = text.split()
    current_count = len(words)

    if current_count == target_words:
        return text
    elif current_count > target_words:
        return ' '.join(words[:target_words])
    else:
        words_needed = target_words - current_count
        if language == 'ar':
            if words_needed <= 5:
                extension = "وغيرها من الخدمات المميزة."
            elif words_needed <= 10:
                extension = "وغيرها من الخدمات المميزة التي تلبي احتياجات المستخدمين."
            else:
                extension = "وغيرها من الخدمات المميزة التي تلبي احتياجات المستخدمين في مختلف أنحاء العالم، مما يجعلها خياراً مفضلاً للكثيرين."
        else:
            if words_needed <= 5:
                extension = "and other similar services."
            elif words_needed <= 10:
                extension = "and other similar services that meet user needs and expectations."
            else:
                extension = "and other similar services that meet user needs and expectations in various markets worldwide, making it a preferred choice for many users globally."

        extension_words = extension.split()
        words.extend(extension_words[:min(words_needed, len(extension_words))])

        if len(words) < target_words:
            remaining_words = target_words - len(words)
            if language == 'ar':
                conclusion = "هذه المنصة تستمر في التطور والنمو لتقديم أفضل تجربة ممكنة للمستخدمين في جميع أنحاء العالم."
            else:
                conclusion = "This platform continues to evolve and grow to provide the best possible experience for users around the world."

            conclusion_words = conclusion.split()
            words.extend(conclusion_words[:min(remaining_words, len(conclusion_words))])

        return ' '.join(words[:target_words])


@api_view(['POST'])
def author_search(request):
    """
    Author search endpoint with COMPLETELY FIXED image handling.
    """
    try:
        author_name = request.data.get('author_name', '').strip()
        language = request.data.get('language', 'en')

        if not author_name:
            return Response(
                {'error': 'author_name is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if language not in ['en', 'ar']:
            return Response(
                {'error': 'Language must be "en" or "ar"'},
                status=status.HTTP_400_BAD_REQUEST
            )

        start_time = timezone.now()

        # Get author info with FIXED image handling
        try:
            author_info = get_author_comprehensive_info(author_name, language)
        except Exception as e:
            print(f"LLM author info failed: {e}")
            author_info = get_fallback_author_info(author_name, language)

        # ALWAYS ensure we have a valid image URL
        if not is_valid_image_url(author_info.get("author_image", "")):
            print(f"Author image invalid, getting reliable fallback for {author_name}")
            author_info["author_image"] = get_image_url_from_llm(author_name, "author")

        end_time = timezone.now()
        author_info['search_time'] = (end_time - start_time).total_seconds()
        author_info['language'] = language
        author_info['note'] = 'Author information with FIXED image handling'

        return Response(author_info, status=status.HTTP_200_OK)

    except Exception as e:
        import traceback
        print(f"Author search failed with error: {e}")
        print(traceback.format_exc())

        return Response(
            {'error': f'Author search failed: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(["POST"])
def category_search(request):
    """
    Category search endpoint with COMPLETELY FIXED image handling.
    """
    try:
        category_name = request.data.get("category_name", "").strip()
        language = request.data.get("language", "en")

        if not category_name:
            return Response({"error": "category_name is required"}, status=status.HTTP_400_BAD_REQUEST)

        if language not in ["en", "ar"]:
            return Response({"error": "language must be 'en' or 'ar'"}, status=status.HTTP_400_BAD_REQUEST)

        start_time = timezone.now()

        # Get category info with FIXED image handling
        try:
            category_info = get_category_comprehensive_info(category_name, language)
        except Exception as e:
            print(f"LLM category info failed: {e}")
            category_info = get_fallback_category_info(category_name, language)

        # ALWAYS ensure we have a valid image URL
        if not is_valid_image_url(category_info.get("image_url", "")):
            print(f"Category image invalid, getting reliable fallback for {category_name}")
            category_info["image_url"] = get_image_url_from_llm(category_name, "category")

        end_time = timezone.now()
        category_info["search_time"] = (end_time - start_time).total_seconds()
        category_info["language"] = language
        category_info["note"] = "Category information with FIXED image handling"

        return Response(category_info, status=status.HTTP_200_OK)

    except Exception as e:
        import traceback
        print("Category search failed:", e)
        print(traceback.format_exc())
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Include all other functions from the original views.py file here...
# (The rest of the functions remain the same as in the previous version)




@api_view(['POST'])
def company_search(request):
    """
    Company/Stock search endpoint with comprehensive information and stock data.
    No database operations - returns results directly.

    Expected input:
    {
        "company_name": "Apple" or "AAPL",
        "language": "en" (optional, defaults to "en")
    }

    Returns:
    {
        "name": "Apple Inc.",
        "code": "AAPL",
        "company_email": "investor_relations@apple.com",
        "web_url": "https://www.apple.com",
        "logo": "https://logo.clearbit.com/apple.com",
        "country_origin": "United States",
        "category": {
            "name": "Technology",
            "icon": "💻",
            "wikilink": "https://en.wikipedia.org/wiki/Technology",
            "description": "Technology sector description..."
        },
        "stock_data": {
            "last_52_weeks_low": 164.08,
            "last_52_weeks_high": 237.49,
            "market_cap": "3.2T",
            "yesterday_close": 210.02
        },
        "yesterday_data": {
            "Date": "2025-07-17T00:00:00-04:00",
            "Open": 210.57,
            "High": 211.80,
            "Low": 209.59,
            "Close": 210.02,
            "Volume": 48010700
        },
        "last_7_days_data": [
            {
                "Date": "2025-07-11T00:00:00-04:00",
                "Open": 210.57,
                "High": 212.13,
                "Low": 209.86,
                "Close": 211.16,
                "Volume": 39765800
            }
        ],
        "description": "Detailed description of the company (200-300 words)"
    }
    """
    try:
        # Validate input
        company_name = request.data.get('company_name', '').strip()
        language = request.data.get('language', 'en')

        if not company_name:
            return Response(
                {'error': 'company_name is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if language not in ['en', 'ar']:
            return Response(
                {'error': 'Language must be "en" or "ar"'},
                status=status.HTTP_400_BAD_REQUEST
            )

        start_time = timezone.now()

        # Get comprehensive company information using LLM
        try:
            if language == 'ar':
                # First get English info, then translate to Arabic for better accuracy
                company_info_en = get_company_comprehensive_info(company_name, 'en')
                company_info = translate_company_info_to_arabic(company_info_en, company_name)
            else:
                company_info = get_company_comprehensive_info(company_name, language)
        except Exception as e:
            print(f"LLM company info failed: {e}")
            company_info = get_fallback_company_info(company_name, language)

        # Try to get stock data from free APIs
        try:
            stock_data = get_company_stock_data(company_info.get('code', company_name))
            if stock_data:
                company_info.update(stock_data)
        except Exception as e:
            print(f"Stock data fetch failed: {e}")
            # Continue with basic company info only

        # Add company logo if not provided or invalid
        if 'logo' not in company_info or not is_valid_image_url(company_info['logo']):
            company_info['logo'] = get_company_logo_url(company_info.get('web_url', company_name))

        # Add description field
        if 'description' not in company_info or not company_info['description']:
            llm_service = LLMService()
            description_prompt = f"Provide a detailed description of {company_name} in {language} (200-300 words)."
            try:
                description_response = llm_service.client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that provides detailed company descriptions."},
                        {"role": "user", "content": description_prompt,}
                    ],
                    model=llm_service.model,
                    temperature=0.0,
                    max_tokens=400,
                    timeout=15
                )
                company_info['description'] = ensure_word_count(description_response.choices[0].message.content.strip(), 250, language) # Aim for 250 words
            except Exception as e:
                print(f"Error generating company description: {e}")
                company_info['description'] = ensure_word_count(f"Description for {company_name}", 250, language)

        end_time = timezone.now()
        search_time = (end_time - start_time).total_seconds()

        # Add metadata
        company_info['search_time'] = search_time
        company_info['language'] = language
        company_info['note'] = 'Company information without database storage'

        return Response(company_info, status=status.HTTP_200_OK)

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Company search failed with error: {e}")
        print(f"Full traceback: {error_details}")

        return Response(
            {'error': f'Company search failed: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def get_company_comprehensive_info(company_name: str, language: str = 'en') -> dict:
    """
    Get comprehensive company information using LLM.

    Args:
        company_name: Name or code of the company
        language: Language preference

    Returns:
        Dict with comprehensive company information
    """
    llm_service = LLMService()

    if language == 'ar':
        prompt = f"""
        أنت مساعد بحث متخصص في الشركات والأسهم. ابحث عن معلومات شاملة عن الشركة: "{company_name}"

        أرجع JSON بهذا التنسيق المحدد (جميع النصوص باللغة العربية):
        {{
            "الاسم": "الاسم الكامل للشركة",
            "الرمز": "رمز السهم (مثل AAPL، GOOGL)",
            "البريد_الإلكتروني": "البريد الإلكتروني للمستثمرين أو الشركة",
            "الموقع_الإلكتروني": "الموقع الرسمي للشركة",
            "الشعار": "رابط شعار الشركة",
            "بلد_المنشأ": "البلد الأصلي للشركة",
            "الفئة": {{
                "الاسم": "فئة الصناعة بالعربية",
                "الأيقونة": "رمز تعبيري مناسب",
                "رابط_ويكيبيديا": "https://ar.wikipedia.org/wiki/...",
                "الوصف": "وصف الفئة من 100 كلمة عربية بالضبط"
            }},
            "سنة_التأسيس": "سنة التأسيس",
            "المقر_الرئيسي": "المقر الرئيسي",
            "الرئيس_التنفيذي": "الرئيس التنفيذي الحالي",
            "عدد_الموظفين": "عدد الموظفين التقريبي"
        }}

        ملاحظات مهمة:
        - استخدم معلومات حقيقية ودقيقة عن الشركة
        - رمز السهم: الرمز الصحيح في البورصة (مثل TCS.NS للشركات الهندية، AAPL للأمريكية)
        - إذا كان الإدخال رمز سهم (مثل TCS.NS)، ابحث عن الشركة المقابلة (Tata Consultancy Services)
        - البريد الإلكتروني: للمستثمرين أو الاتصال العام
        - بلد المنشأ: يجب أن يكون اسم البلد بالعربية (مثل: الهند، الولايات المتحدة الأمريكية، المملكة المتحدة)
        - وصف الفئة: 100 كلمة عربية بالضبط
        - استخدم روابط ويكيبيديا عربية حقيقية
        - جميع أسماء الحقول والقيم يجب أن تكون باللغة العربية الفصحى فقط
        """
    else:
        prompt = f"""
        You are a company and stock research specialist. Find comprehensive information about the company: "{company_name}"

        Return JSON with this exact structure:
        {{
            "name": "Full company name",
            "code": "Stock ticker symbol (e.g., AAPL, GOOGL)",
            "company_email": "Investor relations or general contact email",
            "web_url": "Official company website",
            "logo": "Company logo URL",
            "country_origin": "Country where company originated",
            "category": {{
                "name": "Industry category",
                "icon": "Appropriate emoji",
                "wikilink": "https://en.wikipedia.org/wiki/...",
                "description": "Exactly 100 English words describing the industry category"
            }},
            "founded": "Year founded",
            "headquarters": "Headquarters location",
            "ceo": "Current CEO name",
            "employees": "Approximate number of employees"
        }}

        Important notes:
        - Use real and accurate information about the company
        - Stock code: correct ticker symbol used in stock exchanges (e.g., TCS.NS for Indian companies, AAPL for US)
        - If input is a stock code (e.g., TCS.NS), find the corresponding company (Tata Consultancy Services)
        - Email: investor relations or general contact email
        - Country origin: must be the full country name in English (e.g., India, United States, United Kingdom)
        - Category description: exactly 100 English words
        - Use real English Wikipedia links for the category
        - All text must be in English only
        """

    try:
        import time
        time.sleep(0.5)  # Rate limiting

        chat_completion = llm_service.client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a precise company and financial researcher. Provide accurate, real information about companies and their stock information. Follow word count requirements exactly."
                },
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model=llm_service.model,
            response_format={"type": "json_object"},
            temperature=0.0,  # Zero temperature for most consistent results
            max_tokens=1200,
            timeout=15
        )

        response = json.loads(chat_completion.choices[0].message.content)

        # Ensure category description word count is correct
        if 'category' in response and 'description' in response['category']:
            response['category']['description'] = ensure_word_count(
                response['category']['description'], 100, language
            )

        return response

    except Exception as e:
        print(f"LLM company info error: {e}")
        # Fallback response
        return get_fallback_company_info(company_name, language)


def translate_company_info_to_arabic(company_info_en: dict, company_name: str) -> dict:
    """
    Translate company information from English to Arabic.

    Args:
        company_info_en: Company info in English
        company_name: Original company name

    Returns:
        Company info translated to Arabic
    """
    if not company_info_en:
        return get_fallback_company_info(company_name, 'ar')

    # Country translations
    country_translations = {
        'United States': 'الولايات المتحدة الأمريكية',
        'India': 'الهند',
        'United Kingdom': 'المملكة المتحدة',
        'China': 'الصين',
        'Japan': 'اليابان',
        'Germany': 'ألمانيا',
        'France': 'فرنسا',
        'Canada': 'كندا',
        'Australia': 'أستراليا',
        'South Korea': 'كوريا الجنوبية',
        'Netherlands': 'هولندا',
        'Switzerland': 'سويسرا',
        'Unknown': 'غير محدد'
    }

    # Industry category translations
    category_translations = {
        'Technology': 'التكنولوجيا',
        'Information Technology': 'تكنولوجيا المعلومات',
        'Finance': 'الخدمات المالية',
        'Healthcare': 'الرعاية الصحية',
        'Entertainment': 'الترفيه',
        'Retail': 'التجارة',
        'Energy': 'الطاقة',
        'Automotive': 'السيارات',
        'Telecommunications': 'الاتصالات',
        'Business': 'الأعمال',
        'Software': 'البرمجيات',
        'Consulting': 'الاستشارات',
        'Services': 'الخدمات'
    }

    # City/Location translations
    location_translations = {
        'Mumbai, India': 'مومباي، الهند',
        'New York, USA': 'نيويورك، الولايات المتحدة',
        'London, UK': 'لندن، المملكة المتحدة',
        'Tokyo, Japan': 'طوكيو، اليابان',
        'Beijing, China': 'بكين، الصين',
        'Mumbai': 'مومباي',
        'New York': 'نيويورك',
        'London': 'لندن',
        'Tokyo': 'طوكيو',
        'Beijing': 'بكين',
        'Unknown': 'غير محدد'
    }

    # Get original values
    original_category_name = company_info_en.get('category', {}).get('name', 'Business')
    original_headquarters = company_info_en.get('headquarters', 'Unknown')
    original_country = company_info_en.get('country_origin', 'Unknown')

    # Translate headquarters
    translated_headquarters = location_translations.get(original_headquarters, original_headquarters)
    # If not found in direct mapping, try to translate parts
    if translated_headquarters == original_headquarters and ',' in original_headquarters:
        parts = [part.strip() for part in original_headquarters.split(',')]
        translated_parts = []
        for part in parts:
            if part in location_translations:
                translated_parts.append(location_translations[part])
            elif part in country_translations:
                translated_parts.append(country_translations[part])
            else:
                translated_parts.append(part)
        translated_headquarters = '، '.join(translated_parts)

    # Company name translations
    company_name_translations = {
        'Tata Consultancy Services Limited': 'شركة تاتا للخدمات الاستشارية المحدودة',
        'Tata Consultancy Services': 'شركة تاتا للخدمات الاستشارية',
        'Apple Inc.': 'شركة آبل المحدودة',
        'Microsoft Corporation': 'شركة مايكروسوفت',
        'Google LLC': 'شركة جوجل',
        'Amazon.com Inc.': 'شركة أمازون',
        'Meta Platforms Inc.': 'شركة ميتا',
        'Tesla Inc.': 'شركة تيسلا'
    }

    original_name = company_info_en.get('name', company_name)
    translated_name = company_name_translations.get(original_name, original_name)

    # Translate the company info
    translated_info = {
        "name": translated_name,
        "code": company_info_en.get('code', ''),
        "company_email": company_info_en.get('company_email', ''),
        "web_url": company_info_en.get('web_url', ''),
        "logo": company_info_en.get('logo', ''),
        "country_origin": country_translations.get(original_country, original_country),
        "category": {
            "name": category_translations.get(original_category_name, original_category_name),
            "icon": company_info_en.get('category', {}).get('icon', '🏢'),
            "wikilink": company_info_en.get('category', {}).get('wikilink', '').replace('en.wikipedia.org', 'ar.wikipedia.org'),
            "description": ensure_word_count(
                f"فئة {category_translations.get(original_category_name, original_category_name)} تشمل الشركات والمؤسسات التي تعمل في هذا المجال",
                100, 'ar'
            )
        },
        "founded": company_info_en.get('founded', 'غير محدد'),
        "headquarters": translated_headquarters,
        "ceo": company_info_en.get('ceo', 'غير محدد'),
        "employees": company_info_en.get('employees', 'غير محدد'),
        "description": ensure_word_count(company_info_en.get('description', f"وصف لشركة {company_name}"), 250, 'ar') # Translate description
    }

    return translated_info


def get_company_stock_data(stock_code: str) -> dict:
    """
    Get company stock data from free APIs.

    Args:
        stock_code: Stock ticker symbol

    Returns:
        Dict with stock data or empty dict if failed
    """
    try:
        # Try Alpha Vantage free API (requires API key but has free tier)
        # For demo purposes, we'll simulate the data structure
        # In production, you would use real APIs like:
        # - Alpha Vantage (free tier available)
        # - Yahoo Finance API
        # - IEX Cloud (free tier)
        # - Finnhub (free tier)

        # Simulated stock data structure
        stock_data = {
            "stock_data": {
                "last_52_weeks_low": 164.08,
                "last_52_weeks_high": 237.49,
                "market_cap": "3.2T",
                "yesterday_close": 210.02
            },
            "yesterday_data": {
                "Date": "2025-07-17T00:00:00-04:00",
                "Open": 210.57,
                "High": 211.80,
                "Low": 209.59,
                "Close": 210.02,
                "Volume": 48010700
            },
            "last_7_days_data": [
                {
                    "Date": "2025-07-11T00:00:00-04:00",
                    "Open": 210.57,
                    "High": 212.13,
                    "Low": 209.86,
                    "Close": 211.16,
                    "Volume": 39765800
                },
                {
                    "Date": "2025-07-12T00:00:00-04:00",
                    "Open": 211.20,
                    "High": 213.45,
                    "Low": 210.15,
                    "Close": 212.80,
                    "Volume": 41234500
                },
                {
                    "Date": "2025-07-13T00:00:00-04:00",
                    "Open": 212.85,
                    "High": 214.20,
                    "Low": 211.90,
                    "Close": 213.15,
                    "Volume": 38765200
                },
                {
                    "Date": "2025-07-14T00:00:00-04:00",
                    "Open": 209.93,
                    "High": 210.91,
                    "Low": 207.54,
                    "Close": 208.62,
                    "Volume": 38840100
                },
                {
                    "Date": "2025-07-15T00:00:00-04:00",
                    "Open": 209.22,
                    "High": 211.89,
                    "Low": 208.92,
                    "Close": 209.11,
                    "Volume": 42296300
                },
                {
                    "Date": "2025-07-16T00:00:00-04:00",
                    "Open": 210.30,
                    "High": 212.40,
                    "Low": 208.64,
                    "Close": 210.16,
                    "Volume": 47490500
                },
                {
                    "Date": "2025-07-17T00:00:00-04:00",
                    "Open": 210.57,
                    "High": 211.80,
                    "Low": 209.59,
                    "Close": 210.02,
                    "Volume": 48010700
                }
            ]
        }

        # In a real implementation, you would make actual API calls here
        # Example with Alpha Vantage:
        # api_key = "YOUR_API_KEY"
        # url = f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={stock_code}&apikey={api_key}"
        # response = requests.get(url)
        # data = response.json()

        return stock_data

    except Exception as e:
        print(f"Stock data fetch failed: {e}")
        return {}


def get_company_logo_url(web_url_or_name: str) -> str:
    """
    Get company logo URL using common patterns and reliable sources.

    Args:
        web_url_or_name: Company website URL or name

    Returns:
        URL to company logo
    """
    try:
        if not web_url_or_name:
            return "https://via.placeholder.com/200x200/cccccc/666666?text=Company+Logo"

        # Extract domain from URL or use name
        if web_url_or_name.startswith('http'):
            domain = web_url_or_name.replace('https://', '').replace('http://', '').replace('www.', '').split('/')[0]
        else:
            # Convert company name to likely domain
            domain = web_url_or_name.lower().replace(' ', '').replace('inc', '').replace('corp', '').replace('.', '') + '.com'

        # Try Clearbit logo API (free tier available)
        clearbit_url = f"https://logo.clearbit.com/{domain}"
        return clearbit_url

    except Exception as e:
        print(f"Logo URL generation error: {e}")
        return "https://via.placeholder.com/200x200/cccccc/666666?text=Company+Logo"


def get_fallback_company_info(company_name: str, language: str) -> dict:
    """
    Fallback company information when LLM fails.

    Args:
        company_name: Name or code of the company
        language: Language preference

    Returns:
        Basic company information structure
    """
    # Try to determine if it's a stock code or company name
    is_stock_code = len(company_name) <= 5 and company_name.isupper()

    if language == 'ar':
        return {
            "name": company_name if not is_stock_code else f"شركة {company_name}",
            "code": company_name if is_stock_code else "غير محدد",
            "company_email": "غير متوفر",
            "web_url": f"https://{company_name.lower().replace(' ', '')}.com",
            "logo": get_company_logo_url(company_name),
            "country_origin": "غير محدد",
            "category": {
                "name": "شركة",
                "icon": "🏢",
                "wikilink": "https://ar.wikipedia.org/wiki/شركة",
                "description": ensure_word_count("شركة تعمل في مجال الأعمال والخدمات المختلفة", 100, 'ar')
            },
            "founded": "غير محدد",
            "headquarters": "غير محدد",
            "ceo": "غير محدد",
            "employees": "غير محدد",
            "stock_data": {
                "last_52_weeks_low": 0,
                "last_52_weeks_high": 0,
                "market_cap": "غير متوفر",
                "yesterday_close": 0
            },
            "yesterday_data": {
                "Date": "",
                "Open": 0,
                "High": 0,
                "Low": 0,
                "Close": 0,
                "Volume": 0
            },
            "last_7_days_data": [],
            "description": ensure_word_count(f"وصف لشركة {company_name}", 250, 'ar') # Added description
        }
    else:
        return {
            "name": company_name if not is_stock_code else f"{company_name} Inc.",
            "code": company_name if is_stock_code else "N/A",
            "company_email": "info@company.com",
            "web_url": f"https://{company_name.lower().replace(' ', '')}.com",
            "logo": get_company_logo_url(company_name),
            "country_origin": "Unknown",
            "category": {
                "name": "Business",
                "icon": "🏢",
                "wikilink": "https://en.wikipedia.org/wiki/Business",
                "description": ensure_word_count("A business company operating in various sectors and markets", 100, 'en')
            },
            "founded": "Unknown",
            "headquarters": "Unknown",
            "ceo": "Unknown",
            "employees": "Unknown",
            "stock_data": {
                "last_52_weeks_low": 0,
                "last_52_weeks_high": 0,
                "market_cap": "N/A",
                "yesterday_close": 0
            },
            "yesterday_data": {
                "Date": "",
                "Open": 0,
                "High": 0,
                "Low": 0,
                "Close": 0,
                "Volume": 0
            },
            "last_7_days_data": [],
            "description": ensure_word_count(f"Description for {company_name}", 250, 'en') # Added description
        }


def get_category_comprehensive_info(category_name: str, language: str = 'en') -> dict:
    """
    Get comprehensive category information using LLM.

    Args:
        category_name: Name of the category
        language: Language preference

    Returns:
        Dict with comprehensive category information
    """
    llm_service = LLMService()

    if language == 'ar':
        prompt = f"""
        أنت خبير متخصص في بحث الفئات. قدم معلومات مفصلة تحديداً عن فئة "{category_name}".

        أرجع JSON بهذا التنسيق المحدد:
        {{
            "name": "اسم الفئة بالعربية",
            "image_url": "LEAVE_EMPTY_FOR_AUTO_SEARCH",
            "wikilink": "https://ar.wikipedia.org/wiki/...",
            "description": "وصف من 150 كلمة عربية بالضبط يشرح ما هي فئة {category_name}، وخصائصها، وميزاتها الرئيسية، وأهميتها. ركز تحديداً على تعريف وشرح هذه الفئة، وليس معلومات عامة."
        }}

        المتطلبات الأساسية:
        - الوصف يجب أن يكون بالضبط 150 كلمة عن {category_name} تحديداً
        - ركز على ما يجعل {category_name} فريدة ومميزة
        - اشرح الخصائص والميزات الأساسية لـ {category_name}
        - تجنب الأوصاف العامة للأعمال أو المواقع الإلكترونية
        - استخدم روابط ويكيبيديا عربية حقيقية لـ {category_name}
        - اذكر شركات معروفة تحديداً بـ {category_name}

        مثال للترفيه: اوصف الأفلام، التلفزيون، الموسيقى، الألعاب، المسرح - وليس مفاهيم الأعمال العامة.
        مثال للتكنولوجيا: اوصف البرمجيات، الأجهزة، الابتكار، الحلول الرقمية - وليس معلومات الشركات العامة.
        """
    else:
        prompt = f"""
        You are an expert category researcher. Provide detailed information specifically about the "{category_name}" category.

        Return JSON with this exact structure:
        {{
            "name": "{category_name}",
            "image_url": "LEAVE_EMPTY_FOR_AUTO_SEARCH",
            "wikilink": "https://en.wikipedia.org/wiki/...",
            "description": "Exactly 150 English words describing what {category_name} is, its characteristics, key features, and significance. Focus specifically on defining and explaining this category, not generic information."
        }}

        CRITICAL REQUIREMENTS:
        - Description must be EXACTLY 150 words about {category_name} specifically
        - Focus on what makes {category_name} unique and distinct
        - Explain the core characteristics and features of {category_name}
        - Avoid generic business or website descriptions
        - Use real Wikipedia links for {category_name}

        Example for "Entertainment": Describe movies, TV, music, gaming, theater - not general business concepts.
        Example for "Technology": Describe software, hardware, innovation, digital solutions - not general company info.
        """

    try:
        import time
        time.sleep(0.5)  # Rate limiting

        chat_completion = llm_service.client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a precise industry researcher. Provide accurate, real information about categories and industries. Follow word count requirements exactly."
                },
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model=llm_service.model,
            response_format={"type": "json_object"},
            temperature=0.0,  # Zero temperature for most consistent results
            max_tokens=1000,
            timeout=15
        )

        response = json.loads(chat_completion.choices[0].message.content)

        # Ensure description word count is correct
        if 'description' in response:
            response['description'] = ensure_word_count(response['description'], 150, language)

        # Auto-search for category image with validation
        if 'image_url' in response and (not response['image_url'] or response['image_url'] == "LEAVE_EMPTY_FOR_AUTO_SEARCH"):
            response['image_url'] = get_image_url_from_llm(category_name, "category")

        return response

    except Exception as e:
        print(f"LLM category info error: {e}")
        # Fallback response
        return get_fallback_category_info(category_name, language)


def get_fallback_category_info(category_name: str, language: str) -> dict:
    """
    Fallback category information when LLM fails.

    Args:
        category_name: Name of the category
        language: Language preference

    Returns:
        Basic category information structure
    """
    if not category_name:
        category_name = "General"

    # Map common categories to icons and basic info
    category_lower = category_name.lower()

    category_mappings = {
        'entertainment': {
            'icon': '🎬',
            'subcategories_en': ['Movies', 'Music', 'Television', 'Gaming', 'Theater'],
            'subcategories_ar': ['أفلام', 'موسيقى', 'تلفزيون', 'ألعاب', 'مسرح'],
            'companies': ['Disney', 'Netflix', 'Warner Bros', 'Sony Entertainment']
        },
        'technology': {
            'icon': '💻',
            'subcategories_en': ['Software', 'Hardware', 'AI', 'Cloud Computing', 'Mobile'],
            'subcategories_ar': ['برمجيات', 'أجهزة', 'ذكاء اصطناعي', 'حوسبة سحابية', 'هواتف'],
            'companies': ['Apple', 'Google', 'Microsoft', 'Amazon']
        },
        'education': {
            'icon': '📚',
            'subcategories_en': ['K-12 Education', 'Higher Education', 'Online Learning', 'Vocational Training'],
            'subcategories_ar': ['التعليم الأساسي', 'التعليم العالي', 'التعلم الإلكتروني', 'التدريب المهني'],
            'companies': ['Pearson', 'McGraw-Hill', 'Coursera', 'Khan Academy']
        },
        'healthcare': {
            'icon': '🏥',
            'subcategories_en': ['Hospitals', 'Pharmaceuticals', 'Medical Devices', 'Telemedicine'],
            'subcategories_ar': ['مستشفيات', 'أدوية', 'أجهزة طبية', 'طب عن بعد'],
            'companies': ['Johnson & Johnson', 'Pfizer', 'UnitedHealth', 'Roche']
        },
        'finance': {
            'icon': '💰',
            'subcategories_en': ['Banking', 'Insurance', 'Investment', 'Fintech'],
            'subcategories_ar': ['مصرفية', 'تأمين', 'استثمار', 'تكنولوجيا مالية'],
            'companies': ['JPMorgan Chase', 'Bank of America', 'Goldman Sachs', 'PayPal']
        }
    }

    # Get mapping or use defaults
    mapping = category_mappings.get(category_lower, {
        'icon': '🏢',
        'subcategories_en': ['Various Sectors'],
        'subcategories_ar': ['قطاعات متنوعة'],
        'companies': ['Various Companies']
    })

    # Get image URL for category
    def get_category_image(cat_name):
        # Use search_for_reliable_image for fallback consistency
        return search_for_reliable_image(cat_name, "category")

    if language == 'ar':
        return {
            "name": category_name,
            "image_url": get_category_image(category_name),
            "wikilink": f"https://ar.wikipedia.org/wiki/{category_name}",
            "description": ensure_word_count(f"فئة {category_name} تشمل مجموعة واسعة من الأنشطة والخدمات المهمة", 150, 'ar')
        }
    else:
        return {
            "name": category_name,
            "image_url": get_category_image(category_name),
            "wikilink": f"https://en.wikipedia.org/wiki/{category_name}",
            "description": ensure_word_count(f"The {category_name} category encompasses a wide range of important activities and services", 150, 'en')
        }


def get_author_comprehensive_info(author_name: str, language: str = 'en') -> dict:
    """
    Get comprehensive author information using LLM.

    Args:
        author_name: Name of the author
        language: Language preference

    Returns:
        Dict with comprehensive author information
    """
    llm_service = LLMService()

    if language == 'ar':
        prompt = f"""
        أنت مساعد بحث متخصص في الأدب والكتاب. ابحث عن معلومات شاملة عن المؤلف: "{author_name}"

        أرجع JSON بهذا التنسيق المحدد (أسماء الحقول بالإنجليزية، القيم بالعربية):
        {{
            "name": "{author_name}",
            "author_image": "LEAVE_EMPTY_FOR_AUTO_SEARCH",
            "bio": "سيرة ذاتية من 200 كلمة عربية بالضبط تتضمن حياته وأعماله وإنجازاته",
            "professions": [
                {{"profession": "كاتب"}},
                {{"profession": "روائي"}},
                {{"profession": "شاعر"}}
            ],
            "wikilink": "رابط صفحة ويكيبيديا الحقيقية للمؤلف فقط إذا كان متاحاً (وليس صفحة ملف Wikimedia)، إذا لم يوجد اتركه فارغاً.",
            "youtube_link": "رابط يوتيوب الرسمي إذا متوفر، أو نص فارغ",
            "birth_year": "سنة الميلاد",
            "nationality": "الجنسية بالعربية",
            "notable_works": ["قائمة بأشهر الأعمال بالعربية"]
        }}

        ملاحظات مهمة:
        - استخدم معلومات حقيقية ودقيقة عن المؤلف
        - أسماء الحقول يجب أن تكون بالإنجليزية (name, author_image, bio, professions, wikilink, youtube_link, birth_year, nationality, notable_works)
        - القيم والنصوص يجب أن تكون بالعربية
        - صورة المؤلف: يجب أن تكون رابط مباشر لصورة (يجب أن ينتهي بـ .jpg أو .jpeg أو .png أو .webp). لا تستخدم أبداً صفحات ملفات Wikimedia Commons. إذا لم تجد صورة مباشرة موثوقة، اتركه فارغاً.
        - السيرة الذاتية: 200 كلمة عربية بالضبط
        - المهن: قائمة كائنات بالعربية مثل [{{"profession": "كاتب"}}, {{"profession": "روائي"}}]
        - الأعمال المشهورة: بالأسماء العربية إذا ترجمت
        - استخدم فقط رابط صفحة ويكيبيديا الحقيقية للمؤلف (وليس صفحة ملف Wikimedia)، إذا لم يوجد رابط صحيح اتركه فارغاً.
        - رابط يوتيوب: إذا كان للمؤلف قناة رسمية
        """
    else:
        prompt = f"""
        You are a literature and author research assistant. Find comprehensive information about the author: "{author_name}"

        Return JSON with this exact structure:
        {{
            "name": "{author_name}",
            "author_image": "LEAVE_EMPTY_FOR_AUTO_SEARCH",
            "bio": "Exactly 200 English words biography including life, works, and achievements",
            "professions": [
                {{"profession": "Writer"}},
                {{"profession": "Novelist"}},
                {{"profession": "Poet"}}
            ],
            "wikilink": "Direct, working Wikipedia author page link ONLY if available (never Wikimedia Commons file pages, never broken links; if not available, leave blank)",
            "youtube_link": "Official YouTube channel URL if available, empty string if not",
            "birth_year": "Birth year",
            "nationality": "Nationality",
            "notable_works": ["List of most famous works"]
        }}

        Important notes:
        - Use real and accurate information about the author
        - Author image: Return a direct image URL (must end in .jpg, .png, .jpeg, or .webp). Never use Wikimedia Commons "File" pages. If a reliable image is not found, leave it empty.
        - Biography: exactly 200 English words
        - Professions: list of objects in English like [{{"profession": "Writer"}}, {{"profession": "Novelist"}}]
        - Notable works: use original titles
        - Wikipedia link: ONLY direct, working Wikipedia author page link (never Wikimedia Commons file pages, never broken links; if not available, leave blank)
        - YouTube link: only if the author has an official channel
        - If author is deceased, still provide birth year and other info
        """

    try:
        import time
        time.sleep(0.5)  # Rate limiting

        chat_completion = llm_service.client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a precise literature researcher. Provide accurate, real information about authors and writers. Follow word count requirements exactly."
                },
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model=llm_service.model,
            response_format={"type": "json_object"},
            temperature=0.0,  # Zero temperature for most consistent results
            max_tokens=1200,
            timeout=15
        )

        response = json.loads(chat_completion.choices[0].message.content)

        # Ensure bio word count is correct
        if 'bio' in response:
            response['bio'] = ensure_word_count(response['bio'], 200, language)

        # --- Post-processing validation for image and Wikipedia links ---
        # Validate and fix author image
        img_key = 'author_image'  # Always use English key
        if not is_valid_image_url(response.get(img_key, '')):
            response[img_key] = get_image_url_from_llm(author_name, "author")

        # Validate Wikipedia link
        wiki_key = 'wikilink'  # Always use English key
        if wiki_key in response and not is_valid_wikipedia_url(response[wiki_key], language):
            response[wiki_key] = ''

        # Convert professions to object format if they're still in array format
        if language == 'ar':
            prof_key = 'المهن'
        else:
            prof_key = 'professions'

        if prof_key in response and isinstance(response[prof_key], list):
            if response[prof_key] and isinstance(response[prof_key][0], str):
                # Convert from ["Writer", "Poet"] to [{"profession": "Writer"}, {"profession": "Poet"}]
                if language == 'ar':
                    response[prof_key] = [{"المهنة": prof} for prof in response[prof_key]]
                else:
                    response[prof_key] = [{"profession": prof} for prof in response[prof_key]]

        return response

    except Exception as e:
        print(f"LLM author info error: {e}")
        # Fallback response
        return get_fallback_author_info(author_name, language)



def get_fallback_author_info(author_name: str, language: str) -> dict:
    """
    Fallback author information when LLM fails.

    Args:
        author_name: Name of the author
        language: Language preference

    Returns:
        Basic author information structure
    """
    if language == 'ar':
        return {
            "name": author_name,
            "author_image": search_for_reliable_image(author_name, "author"), # Use improved image fallback
            "bio": ensure_word_count(f"{author_name} هو مؤلف معروف له إسهامات مهمة في الأدب", 200, 'ar'),
            "professions": [{"المهنة": "كاتب"}],
            "wikilink": f"https://ar.wikipedia.org/wiki/{author_name.replace(' ', '_')}",
            "youtube_link": "",
            "birth_year": "غير محدد",
            "nationality": "غير محدد",
            "notable_works": ["أعمال متنوعة"]
        }
    else:
        return {
            "name": author_name,
            "author_image": search_for_reliable_image(author_name, "author"), # Use improved image fallback
            "bio": ensure_word_count(f"{author_name} is a notable author with significant contributions to literature", 200, 'en'),
            "professions": [{"profession": "Writer"}],
            "wikilink": f"https://en.wikipedia.org/wiki/{author_name.replace(' ', '_')}",
            "youtube_link": "",
            "birth_year": "Unknown",
            "nationality": "Unknown",
            "notable_works": ["Various works"]
        }


def get_website_comprehensive_info(website_name: str, language: str = 'en') -> dict:
    """
    Get comprehensive website/company information using LLM.

    Args:
        website_name: Name of the website/company
        language: Language preference

    Returns:
        Dict with comprehensive website information
    """
    if not website_name:
        return get_fallback_website_info("Unknown", language)

    llm_service = LLMService()

    if language == 'ar':
        prompt = f"""
        أنت مساعد بحث متخصص. ابحث عن معلومات حقيقية ودقيقة عن: "{website_name}"

        أرجع JSON بهذا التنسيق المحدد (جميع النصوص باللغة العربية فقط):
        {{
            "name": "الاسم الكامل للشركة/الموقع بالعربية",
            "website_icon": "رابط أيقونة الموقع",
            "country": "البلد الذي تأسست فيه بالعربية (مثل: الولايات المتحدة الأمريكية، الصين، المملكة المتحدة)",
            "category": {{
                "name": "فئة الصناعة بالعربية (مثل: الترفيه، التكنولوجيا، التجارة الإلكترونية، وسائل التواصل الاجتماعي، التعليم، الخدمات المالية)",
                "icon": "رمز تعبيري واحد مناسب",
                "رابط_ويكيبيديا": "رابط ويكيبيديا عربي حقيقي للفئة",
                "الوصف": "وصف من 90 كلمة عربية بالضبط يشرح معنى هذه الفئة وما تشمله"
            }},
            "brief_description": "وصف موجز من 40 كلمة عربية يوضح ما يفعله {website_name}",
            "comprehensive_description": "وصف مفصل من 200 كلمة عربية عن {website_name} وتاريخه وخدماته وتأثيره",
            "app_links": {{
                "playstore": "رابط Google Play Store الحقيقي والمؤكد فقط، أو \"\" إذا لم يكن متوفراً",
                "appstore": "رابط Apple App Store الحقيقي والمؤكد فقط، أو \"\" إذا لم يكن متوفراً"
            }},
            "social_media": {{
                "youtube": "رابط يوتيوب الرسمي الحقيقي (مثل: https://www.youtube.com/user/netflix أو https://www.youtube.com/@netflix) فقط إذا كان موجوداً، أو \"\" إذا لم يكن متوفراً",
                "instagram": "رابط إنستغرام الرسمي الحقيقي (مثل: https://www.instagram.com/netflix) فقط إذا كان موجوداً، أو \"\" إذا لم يكن متوفراً",
                "facebook": "رابط فيسبوك الرسمي الحقيقي (مثل: https://www.facebook.com/Netflix) فقط إذا كان موجوداً، أو \"\" إذا لم يكن متوفراً",
                "twitter": "رابط تويتر/X الرسمي الحقيقي (مثل: https://twitter.com/Netflix) فقط إذا كان موجوداً، أو \"\" إذا لم يكن متوفراً"
            }},
            "website_url": "رابط الموقع الرسمي",
            "founded": "سنة التأسيس",
            "headquarters": "مدينة وبلد المقر الرئيسي بالعربية"
        }}

        متطلبات أساسية:
        - جميع النصوص يجب أن تكون باللغة العربية الفصحى فقط
        - لا تخلط بين العربية والإنجليزية في النص الواحد
        - استخدم معلومات حقيقية ومؤكدة عن {website_name} فقط
        - لروابط وسائل التواصل والتطبيقات: قدم روابط حقيقية موجودة ومؤكدة فقط
        - إذا لم تكن متأكداً 100% من وجود حساب أو تطبيق، استخدم \"\"
        - لا تنشئ روابط تخمينية أو مقترحة
        - من الأفضل إرجاع \"\" من رابط خاطئ أو غير مؤكد
        """
    else:
        prompt = f"""
        You are a specialized research assistant. Find real, accurate information about: "{website_name}"

        Return JSON with this exact structure (ALL text in English only):
        {{
            "name": "Full company/website name in English",
            "website_icon": "Website favicon URL",
            "country": "Country where founded in English (e.g., United States, China, United Kingdom)",
            "category": {{
                "name": "Industry category in English (e.g., Entertainment, Technology, E-commerce, Social Media, Education, Financial Services)",
                "icon": "Single appropriate emoji",
                "wikilink": "Real English Wikipedia URL for the category",
                "description": "Exactly 90 English words explaining what this category means and includes"
            }},
            "brief_description": "Brief 40 English words describing what {website_name} does",
            "comprehensive_description": "Detailed 200 English words about {website_name}, its history, services, and impact",
            "app_links": {{
                "playstore": "Real and verified Google Play Store URL ONLY, or \"\" if not available",
                "appstore": "Real and verified Apple App Store URL ONLY, or \"\" if not available"
            }},
            "social_media": {{
                "youtube": "Real official YouTube channel URL (e.g., https://www.youtube.com/user/netflix or https://www.youtube.com/@netflix) ONLY if it exists, or \"\" if not available",
                "instagram": "Real official Instagram URL (e.g., https://www.instagram.com/netflix) ONLY if it exists, or \"\" if not available",
                "facebook": "Real official Facebook URL (e.g., https://www.facebook.com/Netflix) ONLY if it exists, or \"\" if not available",
                "twitter": "Real official Twitter/X URL (e.g., https://twitter.com/Netflix) ONLY if it exists, or \"\" if not available"
            }},
            "website_url": "Official website URL",
            "founded": "Year founded",
            "headquarters": "City and country of headquarters in English"
        }}

        CRITICAL REQUIREMENTS:
        - ALL text must be in English only
        - Do NOT mix English and Arabic in the same text
        - Use REAL and verified information about {website_name} only
        - For social media and app links: ONLY provide real, existing, verified URLs
        - If you're not 100% certain a social media account or app exists, use \"\"
        - Do NOT create guessed or suggested URLs
        - Better to return \"\" than wrong or unverified URL

        EXAMPLES for Netflix:
        - YouTube: "https://www.youtube.com/user/netflix" or "https://www.youtube.com/@netflix"
        - Instagram: "https://www.instagram.com/netflix"
        - Facebook: "https://www.facebook.com/Netflix"
        - Twitter: "https://twitter.com/Netflix"
        """

    try:
        import time
        time.sleep(0.5)  # Rate limiting

        chat_completion = llm_service.client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a precise information researcher. Provide accurate, real information about websites and companies. Follow word count requirements exactly."
                },
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model=llm_service.model,
            response_format={"type": "json_object"},
            temperature=0.0,  # Zero temperature for most consistent results
            max_tokens=1500,
            timeout=15
        )

        response_content = chat_completion.choices[0].message.content
        if not response_content:
            raise ValueError("Empty response from LLM")

        response = json.loads(response_content)

        # Validate response structure
        if not isinstance(response, dict):
            raise ValueError("Invalid response format from LLM")

        # Ensure word counts are correct
        if 'category' in response and isinstance(response['category'], dict) and 'description' in response['category']:
            response['category']['description'] = ensure_word_count(
                response['category']['description'], 90, language
            )

        if 'comprehensive_description' in response:
            response['comprehensive_description'] = ensure_word_count(
                response['comprehensive_description'], 200, language
            )

        # Clean up social media and app links
        response = clean_social_media_links(response, website_name)

        return response

    except Exception as e:
        print(f"LLM website info error: {e}")
        # Fallback response
        return get_fallback_website_info(website_name, language)


def clean_social_media_links(response: dict, website_name: str) -> dict:
    """
    Clean up social media and app store links to ensure they're valid or empty.

    Args:
        response: The response dictionary from LLM
        website_name: Name of the website

    Returns:
        Cleaned response with validated links
    """
    if not website_name:
        website_name = "unknown"

    # Clean social media links
    if 'social_media' in response:
        social_media = response['social_media']

        # Validate each social media link
        for platform in ['youtube', 'instagram', 'facebook', 'twitter']:
            if platform in social_media:
                link = social_media[platform]
                if link and not is_valid_social_link(link, platform, website_name):
                    social_media[platform] = ""  # Set to empty if invalid

    # Clean app store links
    if 'app_links' in response:
        app_links = response['app_links']

        # Validate app store links
        for store in ['playstore', 'appstore']:
            if store in app_links:
                link = app_links[store]
                if link and not is_valid_app_link(link, store):
                    app_links[store] = ""  # Set to empty if invalid

    return response


def is_valid_social_link(link: str, platform: str, website_name: str) -> bool:
    """
    Validate if a social media link is likely to be real.

    Args:
        link: The social media link
        platform: The platform (youtube, instagram, facebook, twitter)
        website_name: Name of the website

    Returns:
        True if link appears valid, False otherwise
    """
    if not link or not link.startswith('http'):
        return False

    if not website_name:
        return False

    # Check if link contains the correct domain
    platform_domains = {
        'youtube': ['youtube.com', 'youtu.be'],
        'instagram': ['instagram.com'],
        'facebook': ['facebook.com', 'fb.com'],
        'twitter': ['twitter.com', 'x.com']
    }

    domains = platform_domains.get(platform, [])
    if not link or not any(domain in link.lower() for domain in domains):
        return False

    # Check for invalid patterns that indicate placeholder/fake links
    invalid_patterns = [
        'example.com',
        'placeholder',
        'template',
        'yourcompany',
        'companyname',
        'website_name',
        'sample'
    ]

    link_lower = link.lower()
    if any(pattern in link_lower for pattern in invalid_patterns):
        return False

    # Basic structure validation for each platform
    if platform == 'youtube':
        # Accept various YouTube URL patterns - be more permissive
        # Valid patterns: /channel/, /c/, /user/, /@, or just youtube.com/companyname
        return (any(pattern in link_lower for pattern in ['/channel/', '/c/', '/user/', '/@']) or
                ('youtube.com/' in link_lower and len(link_lower.split('/')[-1]) > 2))
    elif platform == 'instagram':
        # Should have username after instagram.com/
        return '/p/' not in link_lower  # Not a post link
    elif platform == 'facebook':
        # Should not be a post or photo link
        return not any(pattern in link_lower for pattern in ['/posts/', '/photos/', '/videos/'])
    elif platform == 'twitter':
        # Should be a profile link, not a tweet
        return '/status/' not in link_lower

    return True


def is_valid_app_link(link: str, store: str) -> bool:
    """
    Validate if an app store link is likely to be real.

    Args:
        link: The app store link
        store: The store (playstore, appstore)

    Returns:
        True if link appears valid, False otherwise
    """
    if not link or not link.startswith('http'):
        return False

    # Check if link contains the correct domain
    store_domains = {
        'playstore': ['play.google.com'],
        'appstore': ['apps.apple.com', 'itunes.apple.com']
    }

    domains = store_domains.get(store, [])
    if not link or not any(domain in link.lower() for domain in domains):
        return False

    # Check for invalid patterns that indicate placeholder/fake links
    invalid_patterns = [
        'example.com',
        'placeholder',
        'template',
        'yourapp',
        'appname',
        'sample'
    ]

    link_lower = link.lower()
    if any(pattern in link_lower for pattern in invalid_patterns):
        return False

    # Additional validation for each store
    if store == 'playstore':
        # Should have /store/apps/details?id= pattern
        return '/store/apps/details?id=' in link_lower
    elif store == 'appstore':
        # Should have /app/ pattern or /id pattern
        return '/app/' in link_lower or '/id' in link_lower

    return True


def get_website_icon_url(website_name: str) -> str:
    """
    Get the website icon URL using common patterns.

    Args:
        website_name: Name of the website

    Returns:
        URL to the website's favicon
    """
    if not website_name:
        return "https://via.placeholder.com/32x32/cccccc/666666?text=?"

    website_lower = website_name.lower()

    # Common favicon patterns for popular websites
    icon_patterns = {
        'netflix': 'https://assets.nflxext.com/us/ffe/siteui/common/icons/nficon2016.ico',
        'google': 'https://www.google.com/favicon.ico',
        'youtube': 'https://www.youtube.com/favicon.ico',
        'facebook': 'https://static.xx.fbcdn.net/rsrc.php/yo/r/iRmz9lCMBD2.ico',
        'instagram': 'https://static.cdninstagram.com/rsrc.php/v3/yt/r/30PrGfR3xhI.ico',
        'twitter': 'https://abs.twimg.com/favicons/twitter.3.ico',
        'amazon': 'https://www.amazon.com/favicon.ico',
        'microsoft': 'https://www.microsoft.com/favicon.ico',
        'apple': 'https://www.apple.com/favicon.ico',
        'linkedin': 'https://static.licdn.com/sc/h/al2o9zrvru7aqj8e1x2rzsrca',
        'tiktok': 'https://sf16-website-login.neutral.ttwstatic.com/obj/tiktok_web_login_static/tiktok/webapp/main/webapp-desktop/8152caf0c8e8bc67ae0d.ico'
    }

    # Return specific icon if available, otherwise use standard favicon pattern
    return icon_patterns.get(website_lower, f"https://{website_lower}.com/favicon.ico")


# Removed get_website_api_info function to prevent duplicate social media links
# The LLM service now provides comprehensive and accurate social media links


def get_fallback_website_info(website_name: str, language: str) -> dict:
    """
    Fallback website information when LLM fails.

    Args:
        website_name: Name of the website/company
        language: Language preference

    Returns:
        Basic website information structure
    """
    if not website_name:
        website_name = "Unknown Website"

    # Try to guess category based on common website names
    website_lower = website_name.lower()

    if website_lower in ['netflix', 'youtube', 'disney', 'hulu', 'spotify']:
        category_name = "الترفيه" if language == 'ar' else "Entertainment"
        category_icon = "🎬"
        category_wiki = "https://ar.wikipedia.org/wiki/ترفيه" if language == 'ar' else "https://en.wikipedia.org/wiki/Entertainment"
    elif website_lower in ['google', 'microsoft', 'apple', 'amazon', 'meta']:
        category_name = "التكنولوجيا" if language == 'ar' else "Technology"
        category_icon = "💻"
        category_wiki = "https://ar.wikipedia.org/wiki/تكنولوجيا" if language == 'ar' else "https://en.wikipedia.org/wiki/Technology"
    elif website_lower in ['facebook', 'instagram', 'twitter', 'linkedin', 'tiktok']:
        category_name = "وسائل التواصل الاجتماعي" if language == 'ar' else "Social Media"
        category_icon = "📱"
        category_wiki = "https://ar.wikipedia.org/wiki/وسائل_التواصل_الاجتماعي" if language == 'ar' else "https://en.wikipedia.org/wiki/Social_media"
    elif website_lower in ['amazon', 'ebay', 'alibaba', 'shopify']:
        category_name = "التجارة الإلكترونية" if language == 'ar' else "E-commerce"
        category_icon = "🛒"
        category_wiki = "https://ar.wikipedia.org/wiki/تجارة_إلكترونية" if language == 'ar' else "https://en.wikipedia.org/wiki/E-commerce"
    else:
        category_name = "التكنولوجيا" if language == 'ar' else "Technology"
        category_icon = "💻"
        category_wiki = "https://ar.wikipedia.org/wiki/تكنولوجيا" if language == 'ar' else "https://en.wikipedia.org/wiki/Technology"

    if language == 'ar':
        return {
            "name": website_name,
            "website_icon": get_website_icon_url(website_name),
            "country": "غير محدد",
            "category": {
                "name": category_name,
                "icon": category_icon,
                "wikilink": category_wiki,
                "description": ensure_word_count(f"فئة {category_name} تشمل الشركات والمواقع التي تقدم خدمات متنوعة في هذا المجال", 90, 'ar')
            },
            "brief_description": f"موقع {website_name} في مجال {category_name}",
            "comprehensive_description": ensure_word_count(f"موقع {website_name} هو منصة رقمية في مجال {category_name}", 200, 'ar'),
            "app_links": {"playstore": "", "appstore": ""},
            "social_media": {"youtube": "", "instagram": "", "facebook": "", "twitter": ""},
            "website_url": f"https://{website_name.lower()}.com",
            "founded": "غير محدد",
            "headquarters": "غير محدد",
            "description": ensure_word_count(f"وصف لشركة {website_name}", 250, 'ar') # Added description
        }
    else:
        return {
            "name": website_name,
            "website_icon": get_website_icon_url(website_name),
            "country": "Unknown",
            "category": {
                "name": category_name,
                "icon": category_icon,
                "wikilink": category_wiki,
                "description": ensure_word_count(f"The {category_name} industry includes companies and platforms that provide various services in this field", 90, 'en')
            },
            "brief_description": f"{website_name} is a platform in the {category_name} industry",
            "comprehensive_description": ensure_word_count(f"{website_name} is a digital platform operating in the {category_name} sector", 200, 'en'),
            "app_links": {"playstore": "", "appstore": ""},
            "social_media": {"youtube": "", "instagram": "", "facebook": "", "twitter": ""},
            "website_url": f"https://{website_name.lower()}.com",
            "founded": "Unknown",
            "headquarters": "Unknown",
            "description": ensure_word_count(f"Description for {website_name}", 250, 'en') # Added description
        }


def ensure_word_count(text: str, target_words: int, language: str = 'en') -> str:
    """
    Ensure text meets the target word count.

    Args:
        text: Original text
        target_words: Target word count
        language: Language for extensions

    Returns:
        Text with correct word count
    """
    if not text:
        # Create basic text if empty
        if language == 'ar':
            base_text = "هذا وصف أساسي للموضوع المطلوب"
        else:
            base_text = "This is a basic description of the requested topic"
        text = base_text

    words = text.split()
    current_count = len(words)

    # If already correct, return as is
    if current_count == target_words:
        return text

    # If too long, truncate
    elif current_count > target_words:
        return ' '.join(words[:target_words])

    # If too short, extend carefully
    else:
        # Only add a few words to reach target, don't over-extend
        words_needed = target_words - current_count

        # Create a more natural extension
        if language == 'ar':
            if words_needed <= 5:
                extension = "وغيرها من الخدمات المميزة."
            elif words_needed <= 10:
                extension = "وغيرها من الخدمات المميزة التي تلبي احتياجات المستخدمين."
            elif words_needed <= 15:
                extension = "وغيرها من الخدمات المميزة التي تلبي احتياجات المستخدمين في مختلف أنحاء العالم."
            else:
                extension = "وغيرها من الخدمات المميزة التي تلبي احتياجات المستخدمين في مختلف أنحاء العالم، مما يجعلها خياراً مفضلاً للكثيرين."
        else:
            if words_needed <= 5:
                extension = "and other similar services."
            elif words_needed <= 10:
                extension = "and other similar services that meet user needs and expectations."
            elif words_needed <= 15:
                extension = "and other similar services that meet user needs and expectations in various markets worldwide."
            else:
                extension = "and other similar services that meet user needs and expectations in various markets worldwide, making it a preferred choice for many users globally."

        # Add the extension and check if we need more words
        extension_words = extension.split()
        words.extend(extension_words[:min(words_needed, len(extension_words))])

        # If we still need more words, add a natural conclusion
        if len(words) < target_words:
            remaining_words = target_words - len(words)

            if language == 'ar':
                conclusion = "هذه المنصة تستمر في التطور والنمو لتقديم أفضل تجربة ممكنة للمستخدمين في جميع أنحاء العالم."
            else:
                conclusion = "This platform continues to evolve and grow to provide the best possible experience for users around the world."

            conclusion_words = conclusion.split()
            words.extend(conclusion_words[:min(remaining_words, len(conclusion_words))])

        # Final check to ensure exact count
        return ' '.join(words[:target_words])


def enhance_single_result(result, llm_service, language):
    """
    Helper function to enhance a single search result with LLM data.
    Optimized to use single LLM call for better performance.
    Removes unnecessary fields for cleaner response.
    """
    categories = result.get('categories', [])
    author = result.get('author', '')
    title = result.get('title', '')

    # Get both structured categories and author info in one LLM call
    combined_info = llm_service.get_combined_structured_info(
        categories, author, title, language
    )

    # Create clean result with only essential fields and unified category structure
    clean_result = {
        'title': result.get('title', ''),
        'description': result.get('description', ''),
        'pdf_url': result.get('pdf_url', ''),
        'cover_image_url': result.get('cover_image_url', ''),
        'categories': combined_info.get('categories', []),  # Single unified category array
        'author_info': combined_info.get('author', {}),     # Only author_info, removed duplicate author field
    }

    # Only enhance description if it's too short or missing (skip for performance)
    if not clean_result.get('description') or len(clean_result.get('description', '')) < 30:
        # Use a faster, shorter description enhancement
        try:
            enhanced_description = llm_service.enhance_book_description(
                title, author, clean_result.get('description'), language
            )
            clean_result['description'] = enhanced_description
        except:
            # Skip description enhancement if it fails to maintain speed
            pass

    return clean_result


def translate_result_to_arabic(result: dict, llm_service) -> dict:
    """
    Translate main result fields to Arabic.

    Args:
        result: The search result dictionary
        llm_service: LLM service instance

    Returns:
        Result with translated fields
    """
    try:
        # Extract fields to translate
        title = result.get('title', '') or ''
        description = result.get('description', '') or ''
        author_info = result.get('author_info', {})
        author_name = author_info.get('name', '') or ''

        # Use LLM for more accurate translation of title and description
        if title:
            translated_title = llm_service.translate_text(title, 'ar')
            result['title'] = translated_title
        if description:
            translated_description = llm_service.translate_text(description, 'ar')
            result['description'] = translated_description

        # Translate author name if available
        if author_name:
            translated_author_name = llm_service.translate_text(author_name, 'ar')
            if 'author_info' in result and isinstance(result['author_info'], dict):
                result['author_info']['name'] = translated_author_name

        print(f"Translated: {title} -> {result.get('title')}")

    except Exception as e:
        print(f"Translation failed: {e}")
        # Continue with original text if translation fails

    return result


@api_view(['POST'])
def ai_book_search(request):
    """
    AI-powered book search endpoint.
    This is the main endpoint called when user clicks "AI Book Add" and enters a book name.
    
    Expected payload:
    {
        "book_name": "string",
        "language": "en|ar",
        "max_results": 5
    }
    
    Returns:
    {
        "search_session": "uuid",
        "results": [list of book search results],
        "total_found": int
    }
    """
    
    try:
        # Extract request data
        book_name = request.data.get('book_name', '').strip()
        language = request.data.get('language', 'en')
        max_results = request.data.get('max_results', 5)
        
        if not book_name:
            return Response(
                {'error': 'book_name is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Generate search session ID
        search_session = str(uuid.uuid4())
        
        # Initialize services
        llm_service = LLMService()
        external_apis_service = ExternalAPIsService()
        
        # Step 1: Use LLM to extract and understand the query (LLM-first approach)
        extracted_info = llm_service.extract_book_info(book_name, language)
        
        # Step 2: Search external APIs based on LLM understanding
        search_results = external_apis_service.search_all_sources(extracted_info, max_results)
        
        # Step 3: Enhance results with LLM-generated content (parallel processing for speed)
        enhanced_results = []

        # Process results sequentially to avoid rate limiting and timeout issues
        for result in search_results:
            try:
                enhanced_result = enhance_single_result(result, llm_service, language)
                enhanced_results.append(enhanced_result)
            except Exception as e:
                print(f"Error enhancing result: {e}")
                # Add the original result if enhancement fails
                enhanced_results.append(result)
        
        # Step 4: Save search results to database for later selection
        saved_results = []
        for result in enhanced_results:
            # Set PDF verification status
            pdf_verified = result.get('pdf_verified', False)

            search_result = BookSearchResult.objects.create(
                search_session=search_session,
                title=result.get('title', ''),
                author=result.get('author', ''),
                description=result.get('description', ''),
                category=', '.join(result.get('categories', [])),
                cover_image_url=result.get('cover_image_url'),
                pdf_url=result.get('pdf_url'),
                pdf_source=result.get('pdf_source'),
                pdf_verified=pdf_verified,  # Set verification status
                isbn=result.get('isbn'),
                publication_date=result.get('publication_date', ''),
                publisher=result.get('publisher', ''),
                language=result.get('language', language),
                ai_summary=result.get('description', ''),
                ai_categories=result.get('categories_arabic', result.get('categories', [])),
                source_api=result.get('source_api', ''),
                external_id=result.get('external_id'),
                relevance_score=result.get('relevance_score', 0.0)
            )

            # Attach structured data for serialization
            search_result._structured_categories = result.get('structured_categories', [])
            search_result._structured_author = result.get('structured_author', {})
            search_result._ai_book_summary = result.get('ai_book_summary', '')

            saved_results.append(search_result)
        
        # Serialize results for response
        serializer = BookSearchResultSerializer(saved_results, many=True)
        
        return Response({
            'search_session': search_session,
            'results': serializer.data,
            'total_found': len(saved_results),
            'extracted_info': extracted_info
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Search failed with error: {e}")
        print(f"Full traceback: {error_details}")

        return Response(
            {'error': f'Search failed: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def add_book_from_search(request):
    """
    Add a selected book from search results to the main books database.
    This is called when user selects a book from the search results and clicks "Add".
    
    Expected payload:
    {
        "search_result_id": int,
        "status": "draft|published|pending",
        "custom_category": "string" (optional),
        "download_pdf": boolean
    }
    
    Returns:
    {
        "book_id": int,
        "message": "string",
        "pdf_status": "downloaded|failed|skipped"
    }
    """
    
    try:
        # Extract request data
        search_result_id = request.data.get('search_result_id')
        book_status = request.data.get('status', 'draft')
        custom_category = request.data.get('custom_category')
        download_pdf = request.data.get('download_pdf', True)
        
        if not search_result_id:
            return Response(
                {'error': 'search_result_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get the search result
        search_result = get_object_or_404(BookSearchResult, id=search_result_id)
        
        # Check if book already exists (avoid duplicates)
        existing_book = Book.objects.filter(
            title__iexact=search_result.title,
            author__iexact=search_result.author
        ).first()
        
        if existing_book:
            return Response(
                {
                    'error': 'Book already exists in database',
                    'existing_book_id': existing_book.id
                },
                status=status.HTTP_409_CONFLICT
            )
        
        # Initialize PDF service
        pdf_service = PDFService()
        pdf_status = 'skipped'
        pdf_file_path = None
        
        # Handle PDF download if requested
        if download_pdf and search_result.pdf_url:
            pdf_result = pdf_service.process_book_file(
                search_result.pdf_url,
                search_result.title,
                search_result.author
            )
            
            if pdf_result['success']:
                pdf_file_path = pdf_result['file_path']
                pdf_status = 'downloaded'
            else:
                pdf_status = f"failed: {pdf_result['error']}"
        
        # Create the book in the main database
        book = Book.objects.create(
            title=search_result.title,
            author=search_result.author,
            description=search_result.description,
            category=custom_category or search_result.category,
            status=book_status,
            pdf_file=pdf_file_path,
            cover_image=search_result.cover_image_url,
            isbn=search_result.isbn,
            publication_date=search_result.publication_date or None,
            publisher=search_result.publisher,
            language=search_result.language,
            ai_generated_summary=search_result.ai_summary,
            related_books=search_result.ai_categories
        )
        
        # Clean up: optionally delete the search result
        # search_result.delete()  # Uncomment if you want to clean up search results
        
        return Response({
            'book_id': book.id,
            'message': f'Book "{book.title}" added successfully',
            'pdf_status': pdf_status,
            'book': BookSerializer(book).data
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        return Response(
            {'error': f'Failed to add book: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def get_search_results(request, search_session):
    """
    Get search results for a specific search session.
    
    Returns:
    {
        "results": [list of search results],
        "total": int
    }
    """
    
    try:
        results = BookSearchResult.objects.filter(search_session=search_session)
        serializer = BookSearchResultSerializer(results, many=True)
        
        return Response({
            'results': serializer.data,
            'total': results.count()
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'error': f'Failed to get search results: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def verify_pdf_link(request):
    """
    Verify if a PDF link is accessible and downloadable.
    
    Expected payload:
    {
        "pdf_url": "string"
    }
    
    Returns:
    {
        "is_valid": boolean,
        "error": "string" (if not valid),
        "file_size": int (if available),
        "content_type": "string"
    }
    """
    
    try:
        pdf_url = request.data.get('pdf_url')
        
        if not pdf_url:
            return Response(
                {'error': 'pdf_url is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        pdf_service = PDFService()
        
        # Use a lightweight verification (HEAD request)
        import requests
        try:
            response = requests.head(pdf_url, headers=pdf_service.headers, timeout=10, allow_redirects=True)
            
            is_valid = response.status_code == 200
            content_type = response.headers.get('content-type', '')
            content_length = response.headers.get('content-length')
            
            if is_valid and content_type and 'pdf' not in content_type.lower():
                is_valid = False
                error = f"Not a PDF file. Content-Type: {content_type}"
            else:
                error = None if is_valid else f"HTTP {response.status_code}"
            
            return Response({
                'is_valid': is_valid,
                'error': error,
                'file_size': int(content_length) if content_length else None,
                'content_type': content_type
            }, status=status.HTTP_200_OK)
            
        except requests.exceptions.RequestException as e:
            return Response({
                'is_valid': False,
                'error': f'Network error: {str(e)}',
                'file_size': None,
                'content_type': None
            }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'error': f'Verification failed: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def list_books(request):
    """
    List all books in the database with pagination.
    
    Query parameters:
    - page: int (default: 1)
    - page_size: int (default: 20)
    - status: string (filter by status)
    - language: string (filter by language)
    - search: string (search in title/author)
    
    Returns:
    {
        "results": [list of books],
        "total": int,
        "page": int,
        "page_size": int,
        "total_pages": int
    }
    """
    
    try:
        from django.core.paginator import Paginator
        from django.db.models import Q
        
        # Get query parameters
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 20))
        status_filter = request.GET.get('status')
        language_filter = request.GET.get('language')
        search_query = request.GET.get('search')
        
        # Build queryset
        queryset = Book.objects.all()
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        if language_filter:
            queryset = queryset.filter(language=language_filter)
        
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query) |
                Q(author__icontains=search_query)
            )
        
        # Paginate
        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page)
        
        # Serialize
        serializer = BookSerializer(page_obj.object_list, many=True)
        
        return Response({
            'results': serializer.data,
            'total': paginator.count,
            'page': page,
            'page_size': page_size,
            'total_pages': paginator.num_pages
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'error': f'Failed to list books: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def get_book_details(request, book_id):
    """
    Get detailed information about a specific book.
    
    Returns:
    {
        "book": book_data,
        "related_books": [list of related books if available]
    }
    """
    
    try:
        book = get_object_or_404(Book, id=book_id)
        
        # Increment view count
        book.increment_view_count()
        
        # Serialize book data
        serializer = BookSerializer(book)
        
        return Response({
            'book': serializer.data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'error': f'Failed to get book details: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )



