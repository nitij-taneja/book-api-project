"""
LLM Service for book information extraction and enhancement using Groq.
This service acts as the primary brain for understanding user queries and enriching book data.
"""

import json
import os
from typing import Dict, List, Optional, Tuple
from groq import Groq
from django.conf import settings


class LLMService:
    """Service class for LLM operations using Groq."""
    
    def __init__(self):
        self.client = Groq(api_key=settings.GROQ_API_KEY)
        self.model = "llama3-8b-8192"
    
    def extract_book_info(self, query: str, language: str = 'en') -> Dict:
        """
        Extract structured book information from a user query.
        This is the primary function that makes LLM the first step in book search.
        
        Args:
            query: User's book search query
            language: Target language ('en' or 'ar')
            
        Returns:
            Dict containing extracted book information
        """
        
        # Create language-specific prompt
        if language == 'ar':
            prompt = f"""
            استخرج معلومات الكتاب من الاستعلام التالي: '{query}'
            
            أجب بتنسيق JSON فقط، مثل هذا:
            {{
                "title": "عنوان الكتاب",
                "author": "اسم المؤلف",
                "categories": ["الفئة الأولى", "الفئة الثانية"],
                "language": "ar",
                "search_variations": ["تنويع البحث 1", "تنويع البحث 2"],
                "description": "وصف مختصر للكتاب",
                "is_arabic_query": true
            }}
            
            إذا لم تكن المعلومات متوفرة، استخدم null. 
            للفئات، استخدم أسماء عربية مثل: "الأدب", "التاريخ", "العلوم", "الفلسفة", "الدين", "الشعر", "الرواية"
            """
        else:
            prompt = f"""
            Extract book information from the following query: '{query}'
            
            Respond in JSON format only, like this:
            {{
                "title": "Book Title",
                "author": "Author Name", 
                "categories": ["Category1", "Category2"],
                "language": "en",
                "search_variations": ["search variation 1", "search variation 2"],
                "description": "Brief description of the book",
                "is_arabic_query": false
            }}
            
            If information is not available, use null.
            For categories, use common genres like: "Fiction", "History", "Science", "Philosophy", "Religion", "Poetry", "Novel", "Biography"
            Generate 2-3 search variations to improve API search results.
            """
        
        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                model=self.model,
                response_format={"type": "json_object"},
                temperature=0.3,
            )
            
            llm_response = chat_completion.choices[0].message.content
            extracted_data = json.loads(llm_response)
            
            # Ensure required fields exist
            extracted_data.setdefault('title', query)
            extracted_data.setdefault('author', None)
            extracted_data.setdefault('categories', [])
            extracted_data.setdefault('language', language)
            extracted_data.setdefault('search_variations', [query])
            extracted_data.setdefault('description', None)
            extracted_data.setdefault('is_arabic_query', language == 'ar')
            
            return extracted_data
            
        except json.JSONDecodeError as e:
            print(f"LLM JSON decode error: {e}")
            return self._fallback_extraction(query, language)
        except Exception as e:
            print(f"LLM extraction error: {e}")
            return self._fallback_extraction(query, language)
    
    def enhance_book_description(self, title: str, author: str, existing_description: str = None, language: str = 'en') -> str:
        """
        Generate or enhance book description using LLM.
        
        Args:
            title: Book title
            author: Book author
            existing_description: Existing description to enhance (optional)
            language: Target language
            
        Returns:
            Enhanced description
        """
        
        if language == 'ar':
            if existing_description:
                prompt = f"""
                حسّن الوصف التالي للكتاب "{title}" للمؤلف "{author}":
                
                الوصف الحالي: {existing_description}
                
                اكتب وصفاً محسناً باللغة العربية (200-300 كلمة) يتضمن:
                - ملخص للمحتوى
                - أهمية الكتاب
                - الجمهور المستهدف
                """
            else:
                prompt = f"""
                اكتب وصفاً شاملاً للكتاب "{title}" للمؤلف "{author}" باللغة العربية.
                
                يجب أن يتضمن الوصف (200-300 كلمة):
                - ملخص للمحتوى الرئيسي
                - أهمية الكتاب وقيمته
                - الجمهور المستهدف
                - السياق التاريخي أو الأدبي إن أمكن
                """
        else:
            if existing_description:
                prompt = f"""
                Enhance the following description for the book "{title}" by "{author}":
                
                Current description: {existing_description}
                
                Write an enhanced description in English (200-300 words) that includes:
                - Content summary
                - Book's significance
                - Target audience
                """
            else:
                prompt = f"""
                Write a comprehensive description for the book "{title}" by "{author}" in English.
                
                The description should include (200-300 words):
                - Main content summary
                - Book's importance and value
                - Target audience
                - Historical or literary context if applicable
                """
        
        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                model=self.model,
                temperature=0.7,
            )
            
            return chat_completion.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"LLM description enhancement error: {e}")
            return existing_description or f"A book titled '{title}' by {author}."
    
    def get_related_books(self, title: str, author: str, categories: List[str], language: str = 'en') -> List[Dict]:
        """
        Generate related book suggestions using LLM.
        
        Args:
            title: Book title
            author: Book author  
            categories: Book categories
            language: Target language
            
        Returns:
            List of related book suggestions
        """
        
        categories_str = ', '.join(categories) if categories else 'General'
        
        if language == 'ar':
            prompt = f"""
            اقترح 5 كتب مشابهة للكتاب "{title}" للمؤلف "{author}" في فئات: {categories_str}
            
            أجب بتنسيق JSON فقط:
            {{
                "related_books": [
                    {{
                        "title": "عنوان الكتاب",
                        "author": "اسم المؤلف",
                        "reason": "سبب التشابه"
                    }}
                ]
            }}
            
            ركز على الكتب العربية أو المترجمة للعربية إن أمكن.
            """
        else:
            prompt = f"""
            Suggest 5 books similar to "{title}" by "{author}" in categories: {categories_str}
            
            Respond in JSON format only:
            {{
                "related_books": [
                    {{
                        "title": "Book Title",
                        "author": "Author Name", 
                        "reason": "Reason for similarity"
                    }}
                ]
            }}
            
            Focus on well-known books in similar genres or themes.
            """
        
        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                model=self.model,
                response_format={"type": "json_object"},
                temperature=0.8,
            )
            
            response = json.loads(chat_completion.choices[0].message.content)
            return response.get('related_books', [])
            
        except Exception as e:
            print(f"LLM related books error: {e}")
            return []
    
    def translate_categories(self, categories: List[str], target_language: str) -> List[str]:
        """
        Translate book categories to target language.
        
        Args:
            categories: List of categories to translate
            target_language: Target language ('en' or 'ar')
            
        Returns:
            List of translated categories
        """
        
        if not categories:
            return []
        
        categories_str = ', '.join(categories)
        
        if target_language == 'ar':
            prompt = f"""
            ترجم الفئات التالية إلى العربية: {categories_str}
            
            أجب بتنسيق JSON فقط:
            {{
                "translated_categories": ["الفئة الأولى", "الفئة الثانية"]
            }}
            
            استخدم مصطلحات عربية مناسبة للمكتبات والكتب.
            """
        else:
            prompt = f"""
            Translate the following categories to English: {categories_str}
            
            Respond in JSON format only:
            {{
                "translated_categories": ["Category 1", "Category 2"]
            }}
            
            Use appropriate English terms for library and book categories.
            """
        
        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                model=self.model,
                response_format={"type": "json_object"},
                temperature=0.3,
            )
            
            response = json.loads(chat_completion.choices[0].message.content)
            return response.get('translated_categories', categories)
            
        except Exception as e:
            print(f"LLM translation error: {e}")
            return categories
    
    def _fallback_extraction(self, query: str, language: str) -> Dict:
        """Fallback extraction when LLM fails."""
        return {
            'title': query,
            'author': None,
            'categories': [],
            'language': language,
            'search_variations': [query],
            'description': None,
            'is_arabic_query': language == 'ar'
        }

    def find_pdf_link(self, title: str, author: str, language: str = 'en') -> Optional[str]:
        """
        Use LLM to find a PDF link for a book when APIs don't provide one.

        Args:
            title: Book title
            author: Book author
            language: Book language

        Returns:
            PDF URL if found, None otherwise
        """
        # Create prompt based on language
        if language == 'ar':
            prompt = f"""
            ابحث عن رابط تحميل مباشر لملف PDF للكتاب "{title}" للمؤلف "{author}".

            أجب بتنسيق JSON فقط:
            {{
                "pdf_url": "https://example.com/book.pdf",
                "source": "اسم المصدر",
                "confidence": 0.8
            }}

            متطلبات مهمة:
            - أعطني فقط روابط تنتهي بـ .pdf أو تحتوي على /download/ وتؤدي إلى ملفات PDF فعلية
            - لا تعطني صفحات HTML أو صفحات بحث أو صفحات معلومات الكتاب
            - ركز على المصادر الموثوقة مثل:
              * Internet Archive (archive.org/download/...)
              * Project Gutenberg نسخ PDF
              * المكتبات الرقمية العربية
            - إذا لم تتمكن من العثور على رابط تحميل PDF مباشر، استخدم null للـ pdf_url
            """
        else:
            prompt = f"""
            Find a direct PDF download link for the book "{title}" by "{author}".

            Respond in JSON format only:
            {{
                "pdf_url": "https://example.com/book.pdf",
                "source": "source name",
                "confidence": 0.8
            }}

            IMPORTANT REQUIREMENTS:
            - Only return URLs that end with .pdf or contain /download/ and lead to actual PDF files
            - Do NOT return HTML pages, search pages, or book information pages
            - Focus on reliable sources like:
              * Internet Archive (archive.org/download/...)
              * Project Gutenberg PDF versions (gutenberg.org/files/.../filename.pdf)
              * ManyBooks (manybooks.net/download/...)
              * Open Library PDF downloads
            - If you cannot find a DIRECT PDF download link, use null for pdf_url
            - Verify the URL structure suggests it's a direct PDF download
            """

        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                model=self.model,
                response_format={"type": "json_object"},
                temperature=0.3,
            )

            response = json.loads(chat_completion.choices[0].message.content)
            pdf_url = response.get('pdf_url')

            # Validate URL format and ensure it's likely a PDF
            if pdf_url and self._is_valid_pdf_url(pdf_url):
                return pdf_url
            return None

        except Exception as e:
            print(f"LLM PDF link search error: {e}")
            return None

    def _is_valid_pdf_url(self, url: str) -> bool:
        """Validate if a URL is likely to be a direct PDF download link."""
        if not url or not (url.startswith('http://') or url.startswith('https://')):
            return False

        url_lower = url.lower()

        # Check if URL ends with .pdf
        if url_lower.endswith('.pdf'):
            return True

        # Check for common PDF download patterns
        pdf_patterns = [
            '/download/',
            'download.php',
            'get.php',
            'files/',
            '.pdf?',
            'format=pdf',
            'type=pdf'
        ]

        for pattern in pdf_patterns:
            if pattern in url_lower:
                return True

        # Exclude obvious non-PDF URLs
        exclude_patterns = [
            '.html',
            '.htm',
            '/search',
            '/browse',
            '/catalog',
            'search.php',
            'index.php',
            '-h.htm',  # Gutenberg HTML versions
            '.txt'
        ]

        for pattern in exclude_patterns:
            if pattern in url_lower:
                return False

        # If none of the PDF patterns matched, it's probably not a PDF
        return False

    def find_multiple_pdf_links(self, title: str, author: str, language: str = 'en') -> List[str]:
        """
        Use LLM to find multiple PDF links for a book, prioritizing reliable sources.

        Args:
            title: Book title
            author: Book author
            language: Book language

        Returns:
            List of potential PDF URLs, ordered by reliability
        """
        # Create enhanced prompt for multiple sources
        if language == 'ar':
            prompt = f"""
            ابحث عن روابط تحميل PDF متعددة للكتاب "{title}" للمؤلف "{author}".

            أجب بتنسيق JSON فقط:
            {{
                "pdf_urls": [
                    {{
                        "url": "https://archive.org/download/identifier/book.pdf",
                        "source": "Internet Archive",
                        "reliability": 0.9
                    }},
                    {{
                        "url": "https://www.gutenberg.org/files/123/123.pdf",
                        "source": "Project Gutenberg",
                        "reliability": 0.95
                    }}
                ]
            }}

            متطلبات:
            - ابحث في المصادر الموثوقة: Internet Archive, Project Gutenberg, المكتبات الرقمية
            - أعطني فقط روابط PDF مباشرة تنتهي بـ .pdf
            - رتب النتائج حسب الموثوقية (reliability)
            - إذا لم تجد أي روابط، أرجع قائمة فارغة
            """
        else:
            prompt = f"""
            Find multiple direct PDF download links for the book "{title}" by "{author}".

            Respond in JSON format only:
            {{
                "pdf_urls": [
                    {{
                        "url": "https://archive.org/download/identifier/book.pdf",
                        "source": "Internet Archive",
                        "reliability": 0.9
                    }},
                    {{
                        "url": "https://www.gutenberg.org/files/123/123.pdf",
                        "source": "Project Gutenberg",
                        "reliability": 0.95
                    }}
                ]
            }}

            Requirements:
            - Search reliable sources: Internet Archive, Project Gutenberg, digital libraries
            - Only return direct PDF download URLs ending with .pdf
            - Order results by reliability score (0.0 to 1.0)
            - Focus on public domain and open access books
            - If no PDFs found, return empty array
            - Verify URL patterns match known working sources
            """

        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                model=self.model,
                response_format={"type": "json_object"},
                temperature=0.2,  # Lower temperature for more consistent results
            )

            response = json.loads(chat_completion.choices[0].message.content)
            pdf_urls_data = response.get('pdf_urls', [])

            # Extract and validate URLs
            valid_urls = []
            for pdf_data in pdf_urls_data:
                url = pdf_data.get('url', '')
                if url and self._is_valid_pdf_url(url):
                    valid_urls.append(url)

            return valid_urls

        except Exception as e:
            print(f"LLM multiple PDF search error: {e}")
            # Fallback to single PDF search
            single_url = self.find_pdf_link(title, author, language)
            return [single_url] if single_url else []

