"""
Django API views for AI-powered book addition functionality.
"""

import uuid
import json
import concurrent.futures
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
        book_name = request.data.get('book_name', '').strip()
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

        # Step 3: Enhance results with LLM-generated content (no database operations)
        enhanced_results = []

        for result in search_results:
            try:
                enhanced_result = enhance_single_result(result, llm_service, language)
                enhanced_results.append(enhanced_result)
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
        website_name = request.data.get('website_name', '').strip()
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
        except Exception as e:
            print(f"LLM info failed: {e}")
            website_info = get_fallback_website_info(website_name, language)

        # Add website icon
        if 'website_icon' not in website_info or not website_info['website_icon']:
            website_info['website_icon'] = get_website_icon_url(website_name)

        # Try to get additional info from free APIs if available
        try:
            additional_info = get_website_api_info(website_name)
            if additional_info:
                # Merge API data with LLM data
                website_info.update(additional_info)
        except Exception as e:
            print(f"API info fetch failed: {e}")
            # Continue with LLM data only

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


@api_view(['POST'])
def author_search(request):
    """
    Author search endpoint with comprehensive information.
    No database operations - returns results directly.

    Expected input:
    {
        "author_name": "Stephen King",
        "language": "en" (optional, defaults to "en")
    }

    Returns:
    {
        "name": "Stephen King",
        "author_image": "https://example.com/stephen-king.jpg",
        "bio": "100-300 word biography of the author",
        "professions": ["Writer", "Novelist", "Screenwriter"],
        "wikilink": "https://en.wikipedia.org/wiki/Stephen_King",
        "youtube_link": "https://youtube.com/@stephenking",
        "birth_year": "1947",
        "nationality": "American",
        "notable_works": ["The Shining", "It", "The Stand"]
    }
    """
    try:
        # Validate input
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

        # Get comprehensive author information using LLM
        try:
            author_info = get_author_comprehensive_info(author_name, language)
        except Exception as e:
            print(f"LLM author info failed: {e}")
            author_info = get_fallback_author_info(author_name, language)

        # Add author image if not provided
        if 'author_image' not in author_info or not author_info['author_image']:
            author_info['author_image'] = get_author_image_url(author_name)

        end_time = timezone.now()
        search_time = (end_time - start_time).total_seconds()

        # Add metadata
        author_info['search_time'] = search_time
        author_info['language'] = language
        author_info['note'] = 'Author information without database storage'

        return Response(author_info, status=status.HTTP_200_OK)

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Author search failed with error: {e}")
        print(f"Full traceback: {error_details}")

        return Response(
            {'error': f'Author search failed: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


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

        أرجع JSON بهذا التنسيق المحدد:
        {{
            "name": "{author_name}",
            "author_image": "رابط صورة المؤلف إذا متوفر، أو نص فارغ",
            "bio": "سيرة ذاتية من 200 كلمة عربية بالضبط تتضمن حياته وأعماله وإنجازاته",
            "professions": ["قائمة بالمهن بالعربية مثل: كاتب، روائي، شاعر، أستاذ"],
            "wikilink": "https://ar.wikipedia.org/wiki/...",
            "youtube_link": "رابط يوتيوب الرسمي إذا متوفر، أو نص فارغ",
            "birth_year": "سنة الميلاد",
            "nationality": "الجنسية بالعربية",
            "notable_works": ["قائمة بأشهر الأعمال بالعربية"]
        }}

        ملاحظات مهمة:
        - استخدم معلومات حقيقية ودقيقة عن المؤلف
        - السيرة الذاتية: 200 كلمة عربية بالضبط
        - المهن: قائمة بالعربية (كاتب، روائي، شاعر، أستاذ، صحفي، إلخ)
        - الأعمال المشهورة: بالأسماء العربية إذا ترجمت
        - استخدم روابط ويكيبيديا عربية حقيقية
        - رابط يوتيوب: إذا كان للمؤلف قناة رسمية
        """
    else:
        prompt = f"""
        You are a literature and author research assistant. Find comprehensive information about the author: "{author_name}"

        Return JSON with this exact structure:
        {{
            "name": "{author_name}",
            "author_image": "Author photo URL if available, empty string if not",
            "bio": "Exactly 200 English words biography including life, works, and achievements",
            "professions": ["List of professions like: Writer, Novelist, Poet, Professor"],
            "wikilink": "https://en.wikipedia.org/wiki/...",
            "youtube_link": "Official YouTube channel URL if available, empty string if not",
            "birth_year": "Birth year",
            "nationality": "Nationality",
            "notable_works": ["List of most famous works"]
        }}

        Important notes:
        - Use real and accurate information about the author
        - Biography: exactly 200 English words
        - Professions: list in English (Writer, Novelist, Poet, Professor, Journalist, etc.)
        - Notable works: use original titles
        - Use real English Wikipedia links
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

        return response

    except Exception as e:
        print(f"LLM author info error: {e}")
        # Fallback response
        return get_fallback_author_info(author_name, language)


def get_author_image_url(author_name: str) -> str:
    """
    Get author image URL using common patterns.

    Args:
        author_name: Name of the author

    Returns:
        URL to author's image or placeholder
    """
    # For now, return a placeholder or try to construct a likely URL
    # In a real implementation, you might use APIs like:
    # - Google Images API
    # - Wikipedia API for author photos
    # - Goodreads API

    # Simple placeholder approach
    author_slug = author_name.lower().replace(' ', '-').replace('.', '')

    # Common patterns for author images
    possible_urls = [
        f"https://images.gr-assets.com/authors/{author_slug}.jpg",  # Goodreads pattern
        f"https://upload.wikimedia.org/wikipedia/commons/thumb/author-{author_slug}.jpg",  # Wikipedia pattern
        "https://via.placeholder.com/300x400/cccccc/666666?text=Author+Photo"  # Placeholder
    ]

    # Return the first URL (in a real implementation, you'd check which ones exist)
    return possible_urls[0]


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
            "author_image": get_author_image_url(author_name),
            "bio": ensure_word_count(f"{author_name} هو مؤلف معروف له إسهامات مهمة في الأدب", 200, 'ar'),
            "professions": ["كاتب"],
            "wikilink": f"https://ar.wikipedia.org/wiki/{author_name.replace(' ', '_')}",
            "youtube_link": "",
            "birth_year": "غير محدد",
            "nationality": "غير محدد",
            "notable_works": ["أعمال متنوعة"]
        }
    else:
        return {
            "name": author_name,
            "author_image": get_author_image_url(author_name),
            "bio": ensure_word_count(f"{author_name} is a notable author with significant contributions to literature", 200, 'en'),
            "professions": ["Writer"],
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
    llm_service = LLMService()

    if language == 'ar':
        prompt = f"""
        أنت مساعد بحث. ابحث عن معلومات حقيقية ودقيقة عن: "{website_name}"

        أرجع JSON بهذا التنسيق المحدد:
        {{
            "name": "{website_name}",
            "website_icon": "رابط أيقونة الموقع (تنسيق: https://{website_name.lower()}.com/favicon.ico)",
            "country": "البلد الذي تأسست فيه (مثل: الولايات المتحدة، الصين، إلخ)",
            "category": {{
                "name": "فئة الصناعة العامة (مثل: الترفيه، التكنولوجيا، التجارة الإلكترونية، وسائل التواصل الاجتماعي، التعليم، المالية)",
                "icon": "رمز تعبيري واحد مناسب (🎬 للترفيه، � للتكنولوجيا، 🛒 للتجارة، 📱 لوسائل التواصل، 📚 للتعليم، 💰 للمالية)",
                "wikilink": "رابط ويكيبيديا عربي حقيقي للفئة",
                "description": "90 كلمة بالضبط تشرح معنى هذه الفئة وما تشمله"
            }},
            "brief_description": "40 كلمة تصف ما يفعله {website_name}",
            "comprehensive_description": "200 كلمة وصف مفصل لـ {website_name} وتاريخه وخدماته وتأثيره",
            "app_links": {{
                "playstore": "رابط Google Play Store الحقيقي إذا كان لدى {website_name} تطبيق، نص فارغ إذا لم يكن",
                "appstore": "رابط Apple App Store الحقيقي إذا كان لدى {website_name} تطبيق، نص فارغ إذا لم يكن"
            }},
            "social_media": {{
                "youtube": "رابط يوتيوب حقيقي (تنسيق: https://youtube.com/@{website_name.lower()})",
                "instagram": "رابط إنستغرام حقيقي (تنسيق: https://instagram.com/{website_name.lower()})",
                "facebook": "رابط فيسبوك حقيقي (تنسيق: https://facebook.com/{website_name.lower()})",
                "twitter": "رابط تويتر/X حقيقي (تنسيق: https://twitter.com/{website_name.lower()})"
            }},
            "website_url": "رابط الموقع الرسمي",
            "founded": "سنة التأسيس (مثل: 1997، 1998، إلخ)",
            "headquarters": "مدينة، ولاية/بلد المقر الرئيسي"
        }}

        مهم جداً: استخدم معلومات حقيقية عن {website_name}. إذا لم تعرف التفاصيل الدقيقة، استخدم تقديرات معقولة بناءً على ما تعرفه عن الشركة.
        """
    else:
        prompt = f"""
        You are a research assistant. Find real, accurate information about: "{website_name}"

        Return JSON with this exact structure:
        {{
            "name": "{website_name}",
            "website_icon": "Website favicon URL (format: https://{website_name.lower()}.com/favicon.ico)",
            "country": "Country where founded (e.g., United States, China, etc.)",
            "category": {{
                "name": "Broad industry category (e.g., Entertainment, Technology, E-commerce, Social Media, Education, Finance)",
                "icon": "Single appropriate emoji (🎬 for entertainment, � for technology, 🛒 for e-commerce, 📱 for social media, 📚 for education, 💰 for finance)",
                "wikilink": "Real Wikipedia URL for the category",
                "description": "Exactly 90 words explaining what this category means and includes"
            }},
            "brief_description": "40 words describing what {website_name} does",
            "comprehensive_description": "200 words detailed description of {website_name}, its history, services, and impact",
            "app_links": {{
                "playstore": "Real Google Play Store URL if {website_name} has an app, empty string if not",
                "appstore": "Real Apple App Store URL if {website_name} has an app, empty string if not"
            }},
            "social_media": {{
                "youtube": "Real YouTube channel URL (format: https://youtube.com/@{website_name.lower()})",
                "instagram": "Real Instagram URL (format: https://instagram.com/{website_name.lower()})",
                "facebook": "Real Facebook URL (format: https://facebook.com/{website_name.lower()})",
                "twitter": "Real Twitter/X URL (format: https://twitter.com/{website_name.lower()})"
            }},
            "website_url": "Official website URL",
            "founded": "Year founded (e.g., 1997, 1998, etc.)",
            "headquarters": "City, State/Country of headquarters"
        }}

        CRITICAL: Use REAL information about {website_name}. If you don't know exact details, use reasonable estimates based on what you know about the company.
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

        response = json.loads(chat_completion.choices[0].message.content)

        # Ensure word counts are correct
        if 'category' in response and 'description' in response['category']:
            response['category']['description'] = ensure_word_count(
                response['category']['description'], 90, language
            )

        if 'comprehensive_description' in response:
            response['comprehensive_description'] = ensure_word_count(
                response['comprehensive_description'], 200, language
            )

        return response

    except Exception as e:
        print(f"LLM website info error: {e}")
        # Fallback response
        return get_fallback_website_info(website_name, language)


def get_website_icon_url(website_name: str) -> str:
    """
    Get the website icon URL using common patterns.

    Args:
        website_name: Name of the website

    Returns:
        URL to the website's favicon
    """
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


def get_website_api_info(website_name: str) -> dict:
    """
    Try to get additional website information from free APIs.

    Args:
        website_name: Name of the website/company

    Returns:
        Dict with additional API information
    """
    additional_info = {}

    try:
        # Try to get domain information (example with a hypothetical free API)
        # You can replace this with actual free APIs like:
        # - Clearbit API (has free tier)
        # - Hunter.io API (has free tier)
        # - Company information APIs

        # For now, we'll use a simple approach to construct likely URLs
        website_lower = website_name.lower()

        # Common website patterns
        likely_website = f"https://{website_lower}.com"

        # Common social media patterns
        social_patterns = {
            "youtube": f"https://youtube.com/@{website_lower}",
            "instagram": f"https://instagram.com/{website_lower}",
            "facebook": f"https://facebook.com/{website_lower}",
            "twitter": f"https://twitter.com/{website_lower}"
        }

        # Common app store patterns (these would need to be verified)
        app_patterns = {
            "playstore": f"https://play.google.com/store/search?q={website_name}",
            "appstore": f"https://apps.apple.com/search?term={website_name}"
        }

        additional_info = {
            "api_website_url": likely_website,
            "api_social_media": social_patterns,
            "api_app_links": app_patterns
        }

    except Exception as e:
        print(f"API info fetch error: {e}")

    return additional_info


def get_fallback_website_info(website_name: str, language: str) -> dict:
    """
    Fallback website information when LLM fails.

    Args:
        website_name: Name of the website/company
        language: Language preference

    Returns:
        Basic website information structure
    """
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
            "headquarters": "غير محدد"
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
            "headquarters": "Unknown"
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
    """
    categories = result.get('categories', [])
    author = result.get('author', '')
    title = result.get('title', '')

    # Get both structured categories and author info in one LLM call
    combined_info = llm_service.get_combined_structured_info(
        categories, author, title, language
    )

    result['structured_categories'] = combined_info.get('categories', [])
    result['structured_author'] = combined_info.get('author', {})
    result['ai_book_summary'] = combined_info.get('book_summary', '')

    # Only enhance description if it's too short or missing (skip for performance)
    if not result.get('description') or len(result.get('description', '')) < 30:
        # Use a faster, shorter description enhancement
        try:
            enhanced_description = llm_service.enhance_book_description(
                title, author, result.get('description'), language
            )
            result['description'] = enhanced_description
        except:
            # Skip description enhancement if it fails to maintain speed
            pass

    # Translate categories if needed (keep existing functionality)
    if language == 'ar' and result.get('categories'):
        try:
            translated_categories = llm_service.translate_categories(
                result.get('categories', []),
                'ar'
            )
            result['categories_arabic'] = translated_categories
        except:
            # Skip translation if it fails to maintain speed
            pass

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
            
            if is_valid and 'pdf' not in content_type.lower():
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

