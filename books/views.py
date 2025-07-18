"""
Django API views for AI-powered book addition functionality.
"""

import uuid
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

